import { Effect } from "effect"
import { delegateToPython } from "../runtime/python-helper"

export function runHealth(args: readonly string[]): Effect.Effect<void> {
  return Effect.promise(async () => {
    const code = await delegateToPython(["health", ...args])
    if (code !== 0) {
      process.exitCode = code || 1
    }
  })
}
