import { Socket } from "node:net"
import { requestLine, decodeDaemonLine } from "@anoromi/local-ai-tools-protocol"
import type { DaemonMessage, DaemonSuccessResponse, DaemonStreamEvent } from "@anoromi/local-ai-tools-protocol"
import { socketPath } from "../runtime/paths"

export class SocketClientError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "SocketClientError"
  }
}

export interface SocketClientOptions {
  readonly socket?: string | null
}

export async function callOnce(
  options: SocketClientOptions,
  method: string,
  params: Record<string, unknown>,
  timeoutMs: number
): Promise<DaemonMessage> {
  const id = crypto.randomUUID()
  const messages = await callRaw(options, requestLine(id, method, params), timeoutMs, false)
  const first = messages[0]
  if (!first) {
    throw new SocketClientError("empty daemon response")
  }
  if (first.id !== id) {
    throw new SocketClientError("daemon response id mismatch")
  }
  return first
}

export async function callStream(
  options: SocketClientOptions,
  method: string,
  params: Record<string, unknown>,
  onEvent: (event: DaemonStreamEvent) => void | Promise<void>,
  timeoutMs: number
): Promise<DaemonSuccessResponse | Extract<DaemonMessage, { ok: false }>> {
  const id = crypto.randomUUID()
  const messages = await callRaw(options, requestLine(id, method, params), timeoutMs, true, async (message) => {
    if (message.id !== id) {
      throw new SocketClientError("daemon response id mismatch")
    }
    if (message.ok === true && "event" in message) {
      await onEvent(message)
    }
  })
  const final = [...messages].reverse().find((message) => !("event" in message))
  if (!final) {
    throw new SocketClientError("stream ended without final response")
  }
  if (final.id !== id) {
    throw new SocketClientError("daemon response id mismatch")
  }
  return final as DaemonSuccessResponse | Extract<DaemonMessage, { ok: false }>
}

async function callRaw(
  options: SocketClientOptions,
  line: string,
  timeoutMs: number,
  stream: boolean,
  onMessage?: (message: DaemonMessage) => void | Promise<void>
): Promise<DaemonMessage[]> {
  const path = socketPath(options.socket)
  const client = new Socket()
  const messages: DaemonMessage[] = []
  let buffer = ""
  let settled = false

  return await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      client.destroy()
      reject(new SocketClientError(`daemon response timed out after ${timeoutMs}ms`))
    }, timeoutMs)

    function finish(fn: () => void): void {
      if (settled) return
      settled = true
      clearTimeout(timer)
      fn()
    }

    client.on("error", (error) => finish(() => reject(new SocketClientError(error.message))))
    client.on("data", (data) => {
      buffer += data.toString("utf8")
      const lines = buffer.split("\n")
      buffer = lines.pop() ?? ""
      for (const responseLine of lines) {
        if (!responseLine.trim()) continue
        let message: DaemonMessage
        try {
          message = decodeDaemonLine(responseLine)
        } catch (error) {
          finish(() => reject(new SocketClientError(`invalid daemon response: ${String(error)}`)))
          return
        }
        messages.push(message)
        Promise.resolve(onMessage?.(message)).catch((error) => finish(() => reject(error)))
        if (!stream && !("event" in message)) {
          client.end()
          finish(() => resolve(messages))
          return
        }
      }
    })
    client.on("end", () => finish(() => resolve(messages)))
    client.connect(path, () => {
      client.write(line)
    })
  })
}
