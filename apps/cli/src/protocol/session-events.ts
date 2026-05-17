import { eventLine } from "@anoromi/local-ai-tools-protocol"
import type { ChunkPayload, ErrorPayload, SessionEvent } from "@anoromi/local-ai-tools-protocol"

export function emitEvent(event: SessionEvent): void {
  process.stdout.write(eventLine(event))
}

export function ready(version: string): SessionEvent {
  return { event: "ready", version }
}

export function accepted(id: string): SessionEvent {
  return { id, event: "accepted" }
}

export function daemonStarting(id: string): SessionEvent {
  return { id, event: "daemon_starting" }
}

export function daemonReady(id: string, pid: number | null): SessionEvent {
  return { id, event: "daemon_ready", pid: pid ?? 0 }
}

export function started(id: string): SessionEvent {
  return { id, event: "started" }
}

export function chunk(id: string, value: ChunkPayload): SessionEvent {
  return { id, event: "chunk", chunk: value }
}

export function finished(id: string, result: Record<string, unknown>): SessionEvent {
  return { id, event: "finished", result }
}

export function health(id: string, result: Record<string, unknown>): SessionEvent {
  return { id, event: "health", result }
}

export function errorEvent(id: string, error: ErrorPayload): SessionEvent {
  return { id, event: "error", error }
}
