import { decodeDaemonMessage, decodeSessionRequest, encodeSessionEvent, type DaemonMessage, type SessionEvent, type SessionRequest } from "./schema"

export function parseJsonLine(line: string): unknown {
  return JSON.parse(line)
}

export function decodeSessionLine(line: string): SessionRequest {
  return decodeSessionRequest(parseJsonLine(line))
}

export function decodeDaemonLine(line: string): DaemonMessage {
  return decodeDaemonMessage(parseJsonLine(line))
}

export function requestLine(id: string, method: string, params: Record<string, unknown>): string {
  return JSON.stringify({ id, method, params }) + "\n"
}

export function eventLine(event: SessionEvent): string {
  return JSON.stringify(encodeSessionEvent(event)) + "\n"
}
