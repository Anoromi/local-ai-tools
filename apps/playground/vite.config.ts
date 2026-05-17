import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { spawn } from "node:child_process";
import { createReadStream } from "node:fs";
import { mkdir, readFile, stat } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "../..");
const outputDir = path.resolve(import.meta.dirname, ".kokoro-output");

type SynthesizeRequest = {
  text?: unknown;
  voice?: unknown;
  speed?: unknown;
  targetWpm?: unknown;
  precision?: unknown;
};

function readBody(request: import("node:http").IncomingMessage) {
  return new Promise<string>((resolve, reject) => {
    let body = "";

    request.setEncoding("utf8");
    request.on("data", (chunk) => {
      body += chunk;
    });
    request.on("end", () => resolve(body));
    request.on("error", reject);
  });
}

function sendJson(response: import("node:http").ServerResponse, status: number, value: unknown) {
  response.statusCode = status;
  response.setHeader("Content-Type", "application/json");
  response.end(JSON.stringify(value));
}

function runKokoro(args: string[], text: string) {
  return new Promise<void>((resolve, reject) => {
    const child = spawn("bun", ["run", "apps/cli/src/main.ts", ...args], {
      cwd: repoRoot,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += String(chunk);
    });
    child.stderr.on("data", (chunk) => {
      stderr += String(chunk);
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve();
        return;
      }

      reject(new Error((stderr || stdout || `local-ai-tools exited with code ${code}`).trim()));
    });
    child.stdin.end(text);
  });
}

export default defineConfig({
  plugins: [
    react(),
    {
      name: "kokoro-playground-api",
      configureServer(server) {
        server.middlewares.use(async (request, response, next) => {
          if (!request.url) {
            next();
            return;
          }

          const url = new URL(request.url, "http://localhost");

          if (request.method === "POST" && url.pathname === "/api/synthesize") {
            try {
              const rawBody = await readBody(request);
              const payload = JSON.parse(rawBody || "{}") as SynthesizeRequest;
              const text = typeof payload.text === "string" ? payload.text.trim() : "";

              if (!text) {
                sendJson(response, 400, { error: "Text is required." });
                return;
              }

              const id = randomUUID();
              await mkdir(outputDir, { recursive: true });
              const outputPath = path.join(outputDir, `${id}.wav`);
              const args = ["--output", outputPath];
              const voice = typeof payload.voice === "string" && payload.voice.trim() ? payload.voice.trim() : "af_sarah";
              const speed = typeof payload.speed === "number" && Number.isFinite(payload.speed) ? payload.speed : 1;
              const precision = payload.precision === "fp16" ? "fp16" : "fp32";

              args.push("--voice", voice, "--speed", String(speed), "--precision", precision);
              if (typeof payload.targetWpm === "number" && Number.isFinite(payload.targetWpm) && payload.targetWpm > 0) {
                args.push("--target-wpm", String(payload.targetWpm));
              }

              await runKokoro(args, text);
              const timingsPath = outputPath.replace(/\.wav$/, ".json");
              const timings = JSON.parse(await readFile(timingsPath, "utf8"));

              sendJson(response, 200, {
                id,
                audioUrl: `/api/audio/${id}.wav`,
                timings,
              });
            } catch (error) {
              sendJson(response, 500, {
                error: error instanceof Error ? error.message : String(error),
              });
            }
            return;
          }

          const audioMatch = url.pathname.match(/^\/api\/audio\/([A-Za-z0-9-]+)\.wav$/);
          if (request.method === "GET" && audioMatch) {
            const audioPath = path.join(outputDir, `${audioMatch[1]}.wav`);
            try {
              const info = await stat(audioPath);
              response.statusCode = 200;
              response.setHeader("Content-Type", "audio/wav");
              response.setHeader("Content-Length", String(info.size));
              createReadStream(audioPath).pipe(response);
            } catch {
              sendJson(response, 404, { error: "Audio not found." });
            }
            return;
          }

          next();
        });
      },
    },
  ],
});
