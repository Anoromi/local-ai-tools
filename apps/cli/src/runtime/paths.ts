import { existsSync, mkdirSync, chmodSync, unlinkSync } from "node:fs"
import { homedir, tmpdir } from "node:os"
import { dirname, resolve } from "node:path"

export function runtimeDir(env: NodeJS.ProcessEnv = process.env): string {
  const root = env.XDG_RUNTIME_DIR ? `${env.XDG_RUNTIME_DIR}/local-ai-tools` : `${tmpdir()}/local-ai-tools-${process.getuid?.() ?? "user"}`
  mkdirSync(root, { recursive: true })
  try {
    chmodSync(root, 0o700)
  } catch {
    // Best-effort for non-POSIX filesystems.
  }
  return root
}

export function socketPath(explicit?: string | null, env: NodeJS.ProcessEnv = process.env): string {
  return explicit || env.LOCAL_AI_TOOLS_SOCKET || `${runtimeDir(env)}/local-ai-tools.sock`
}

export function pidPath(env: NodeJS.ProcessEnv = process.env): string {
  return `${runtimeDir(env)}/local-ai-tools.pid`
}

export function logPath(env: NodeJS.ProcessEnv = process.env): string {
  return `${runtimeDir(env)}/daemon.log`
}

export function sidecarPath(outputPath: string): string {
  return outputPath.replace(/\.[^/.]+$/, "") + ".json"
}

export function profilePath(outputPath: string): string {
  return outputPath.replace(/\.[^/.]+$/, "") + ".profile.json"
}

export function absolutePath(path: string): string {
  if (path.startsWith("~")) {
    return resolve(homedir(), path.slice(1))
  }
  return resolve(path)
}

export function ensureParent(path: string): void {
  mkdirSync(dirname(path), { recursive: true })
}

export function removeIfExists(path: string): void {
  if (existsSync(path)) {
    unlinkSync(path)
  }
}
