import { existsSync, openSync } from "node:fs"
import { spawn } from "node:child_process"
import { backendPython, pythonPathEnv, rocmEnv } from "./env"
import { logPath, pidPath, removeIfExists, socketPath } from "./paths"
import { callOnce, SocketClientError } from "../protocol/socket-client"

export interface EnsureDaemonEvents {
  readonly starting?: () => void
  readonly ready?: (pid: number | null) => void
}

export async function ensureDaemon(socket?: string | null, events: EnsureDaemonEvents = {}): Promise<void> {
  const health = await tryHealth(socket)
  if (health.ok) {
    events.ready?.(health.pid)
    return
  }
  removeIfExists(socketPath(socket))
  events.starting?.()
  startDaemon(socket)
  const deadline = Date.now() + 30_000
  let lastError = health.error
  while (Date.now() < deadline) {
    await Bun.sleep(250)
    const result = await tryHealth(socket)
    if (result.ok) {
      events.ready?.(result.pid)
      return
    }
    lastError = result.error
  }
  throw new SocketClientError(`daemon did not become ready within 30s: ${lastError}; log: ${logPath()}`)
}

export async function tryHealth(socket?: string | null): Promise<{ ok: true; pid: number | null } | { ok: false; error: string }> {
  try {
    const response = await callOnce({ socket }, "health", {}, 1000)
    if (response.ok === true && "result" in response) {
      const pid = typeof response.result.pid === "number" ? response.result.pid : null
      return { ok: true, pid }
    }
    return { ok: false, error: response.ok === false ? response.error.message : "daemon returned stream event for health request" }
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : String(error) }
  }
}

function startDaemon(socket?: string | null): void {
  const python = backendPython()
  if (!existsSync(python)) {
    throw new SocketClientError(`backend Python is missing: ${python}. Run: local-ai-tools setup`)
  }
  const args = ["-m", "local_ai_tools", "serve", "--socket", socketPath(socket)]
  const log = logPath()
  const fd = openSync(log, "a", 0o600)
  const env = rocmEnv({
    PYTHONPATH: pythonPathEnv(process.env.PYTHONPATH)
  })
  const child = spawn(python, args, {
    detached: true,
    stdio: ["ignore", fd, fd],
    env
  })
  child.unref()
  Bun.write(pidPath(), String(child.pid ?? ""))
}
