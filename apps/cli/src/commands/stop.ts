import { Effect } from "effect"
import { callOnce } from "../protocol/socket-client"
import { writeStdout } from "../runtime/output"
import { EXIT_DAEMON, EXIT_PROTOCOL } from "./exit-codes"

export function runStop(socket?: string | null): Effect.Effect<void> {
  return Effect.promise(async () => {
    try {
      const response = await callOnce({ socket }, "shutdown", {}, 2000)
      writeStdout(`${JSON.stringify(response.ok === true && "result" in response ? response.result : response, null, 2)}\n`)
      if (response.ok === false) {
        process.exitCode = EXIT_PROTOCOL
      }
    } catch (error) {
      writeStdout(`not running: ${error instanceof Error ? error.message : String(error)}\n`)
      process.exitCode = EXIT_DAEMON
    }
  })
}
