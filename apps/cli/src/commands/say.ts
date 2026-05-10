import { Effect } from "effect"
import { callOnce } from "../protocol/socket-client"
import { ensureDaemon } from "../runtime/daemon"
import { absolutePath, ensureParent, profilePath, sidecarPath } from "../runtime/paths"
import { readAllStdin } from "../runtime/stdin"
import { printError, writeStdout } from "../runtime/output"
import { EXIT_DAEMON, EXIT_PROTOCOL, EXIT_SYNTHESIS, EXIT_USAGE } from "./exit-codes"

export interface SayOptions {
  readonly output?: string | null
  readonly voice: string
  readonly speed: number
  readonly targetWpm?: number | null
  readonly precision: "fp32" | "fp16"
  readonly profile: boolean
  readonly profileOutput?: string | null
  readonly socket?: string | null
}

export function runSay(options: SayOptions): Effect.Effect<void> {
  return Effect.promise(async () => {
    if (!options.output) {
      printError("kokoro-rocm: -o/--output is required")
      process.exitCode = EXIT_USAGE
      return
    }
    const text = (await readAllStdin()).trim()
    if (!text) {
      printError("kokoro-rocm: stdin text is empty")
      process.exitCode = EXIT_USAGE
      return
    }
    const output = absolutePath(options.output)
    const timings = sidecarPath(output)
    const profile = options.profileOutput ? absolutePath(options.profileOutput) : options.profile ? profilePath(output) : null
    ensureParent(output)
    if (profile) ensureParent(profile)
    try {
      await ensureDaemon(options.socket)
    } catch (error) {
      printError(`kokoro-rocm: ${error instanceof Error ? error.message : String(error)}`)
      process.exitCode = EXIT_DAEMON
      return
    }
    const response = await callOnce(
      { socket: options.socket },
      "synthesize",
      {
        text,
        output_path: output,
        timings_path: timings,
        voice: options.voice,
        speed: options.speed,
        target_wpm: options.targetWpm ?? null,
        precision: options.precision,
        profile_path: profile,
        format: "wav"
      },
      3_600_000
    )
    if (response.ok === false) {
      printError(`kokoro-rocm: ${response.error.message}`)
      if (response.error.detail) printError(response.error.detail)
      process.exitCode = EXIT_SYNTHESIS
      return
    }
    if (!("result" in response)) {
      printError("kokoro-rocm: daemon returned a stream event for non-stream request")
      process.exitCode = EXIT_PROTOCOL
      return
    }
    const total = typeof response.result.total_seconds === "number" ? response.result.total_seconds.toFixed(2) : "?"
    writeStdout(`wrote ${response.result.output_path} and ${response.result.timings_path} in ${total}s\n`)
  })
}
