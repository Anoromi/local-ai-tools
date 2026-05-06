import { spawn } from "node:child_process"

export function pythonHelper(): string {
  return process.env.KOKORO_ROCM_PYTHON_HELPER || "kokoro-rocm-python"
}

export async function delegateToPython(args: readonly string[]): Promise<number> {
  const child = spawn(pythonHelper(), [...args], {
    stdio: "inherit",
    env: process.env
  })
  return await new Promise((resolve) => {
    child.on("close", (code) => resolve(code ?? 1))
    child.on("error", () => resolve(1))
  })
}
