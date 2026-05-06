import { Effect } from "effect"
import { callOnce, callStream } from "../protocol/socket-client"
import { decodeSessionLine } from "../protocol/encode"
import { decodeSynthesizeParams } from "../protocol/schema"
import * as Events from "../protocol/session-events"
import { ensureDaemon } from "../runtime/daemon"
import { stdinLines } from "../runtime/stdin"

const VERSION = "0.1.0"

export function runSession(socket?: string | null): Effect.Effect<void> {
  return Effect.promise(async () => {
    Events.emitEvent(Events.ready(VERSION))
    let queue = Promise.resolve()
    for await (const line of stdinLines()) {
      if (!line.trim()) continue
      let request
      try {
        request = decodeSessionLine(line)
      } catch (error) {
        Events.emitEvent(
          Events.errorEvent(extractId(line), {
            stage: "protocol",
            message: "invalid session request",
            detail: String(error)
          })
        )
        continue
      }
      Events.emitEvent(Events.accepted(request.id))
      if (request.method === "exit") {
        await queue
        return
      }
      if (request.method === "synthesize") {
        queue = queue.then(() => handleSynthesize(request.id, request.params, socket))
        continue
      }
      void handleControl(request.id, request.method, socket)
    }
    await queue
  })
}

async function handleControl(id: string, method: "health" | "shutdownDaemon", socket?: string | null): Promise<void> {
  try {
    const response = await callOnce({ socket }, method === "health" ? "health" : "shutdown", {}, 2000)
    if (response.ok === false) {
      Events.emitEvent(Events.errorEvent(id, response.error))
      return
    }
    if ("result" in response) {
      Events.emitEvent(Events.health(id, response.result))
    } else {
      Events.emitEvent(
        Events.errorEvent(id, {
          stage: "protocol",
          message: "daemon returned stream event for control request",
          detail: ""
        })
      )
    }
  } catch (error) {
    Events.emitEvent(
      Events.errorEvent(id, {
        stage: "daemon",
        message: error instanceof Error ? error.message : String(error),
        detail: ""
      })
    )
  }
}

async function handleSynthesize(id: string, params: Record<string, unknown>, socket?: string | null): Promise<void> {
  try {
    const synth = decodeSynthesizeParams(params)
    await ensureDaemon(socket, {
      starting: () => Events.emitEvent(Events.daemonStarting(id)),
      ready: (pid) => Events.emitEvent(Events.daemonReady(id, pid))
    })
    const final = await callStream(
      { socket },
      "synthesize_stream",
      synth,
      (event) => {
        if (event.event === "started") {
          Events.emitEvent(Events.started(id))
        } else if (event.event === "chunk") {
          const data = event.data as { chunk?: unknown }
          const chunk = data.chunk as any
          if (chunk && typeof chunk === "object") {
            Events.emitEvent(Events.chunk(id, chunk))
          }
        }
      },
      3_600_000
    )
    if (final.ok === false) {
      Events.emitEvent(Events.errorEvent(id, final.error))
    } else {
      Events.emitEvent(Events.finished(id, final.result))
    }
  } catch (error) {
    Events.emitEvent(
      Events.errorEvent(id, {
        stage: "session",
        message: error instanceof Error ? error.message : String(error),
        detail: ""
      })
    )
  }
}

function extractId(line: string): string {
  try {
    const value = JSON.parse(line)
    if (value && typeof value === "object" && typeof value.id === "string") {
      return value.id
    }
  } catch {
    // ignored
  }
  return "unknown"
}
