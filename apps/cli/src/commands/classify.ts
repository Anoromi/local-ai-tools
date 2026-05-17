import { readFileSync, writeFileSync } from "node:fs"
import { Effect } from "effect"
import { callOnce } from "../protocol/socket-client"
import { ensureDaemon } from "../runtime/daemon"
import { absolutePath, ensureParent } from "../runtime/paths"
import { readAllStdin } from "../runtime/stdin"
import { printError, writeStdout } from "../runtime/output"
import { EXIT_DAEMON, EXIT_PROTOCOL, EXIT_SYNTHESIS, EXIT_USAGE } from "./exit-codes"

export interface ClassifyOptions {
  readonly input?: string | null
  readonly output?: string | null
  readonly includeAllScores: boolean
  readonly socket?: string | null
}

export function runClassify(options: ClassifyOptions): Effect.Effect<void> {
  return Effect.promise(async () => {
    const raw = options.input ? readFileSync(absolutePath(options.input), "utf8") : await readAllStdin()
    if (!raw.trim()) {
      printError(options.input ? "local-ai-tools: input JSON is empty" : "local-ai-tools: stdin JSON is empty")
      process.exitCode = EXIT_USAGE
      return
    }

    let params: Record<string, unknown>
    try {
      const parsed = JSON.parse(raw)
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("classify input must be a JSON object")
      params = parsed as Record<string, unknown>
    } catch (error) {
      printError(`local-ai-tools: ${error instanceof Error ? error.message : String(error)}`)
      process.exitCode = EXIT_USAGE
      return
    }
    if (options.includeAllScores) params.include_all_scores = true
    const validationError = validateShape(params)
    if (validationError) {
      printError(`local-ai-tools: ${validationError}`)
      process.exitCode = EXIT_USAGE
      return
    }

    try {
      await ensureDaemon(options.socket)
    } catch (error) {
      printError(`local-ai-tools: ${error instanceof Error ? error.message : String(error)}`)
      process.exitCode = EXIT_DAEMON
      return
    }

    const response = await callOnce({ socket: options.socket }, "classify", params, 3_600_000)
    if (response.ok === false) {
      printError(`local-ai-tools: ${response.error.message}`)
      if (response.error.detail) printError(response.error.detail)
      process.exitCode = EXIT_SYNTHESIS
      return
    }
    if (!("result" in response)) {
      printError("local-ai-tools: daemon returned a stream event for non-stream request")
      process.exitCode = EXIT_PROTOCOL
      return
    }

    const json = `${JSON.stringify(response.result, null, 2)}\n`
    if (options.output) {
      const output = absolutePath(options.output)
      ensureParent(output)
      writeFileSync(output, json)
    } else {
      writeStdout(json)
    }
  })
}

function validateShape(params: Record<string, unknown>): string | null {
  const sentences = params.sentences
  if (!Array.isArray(sentences) || sentences.length === 0) return "sentences must be a non-empty list"
  for (const [index, sentence] of sentences.entries()) {
    if (typeof sentence === "string") {
      if (!sentence.trim()) return `sentences[${index}] must be non-empty`
    } else if (!sentence || typeof sentence !== "object" || typeof (sentence as { text?: unknown }).text !== "string" || !(sentence as { text: string }).text.trim()) {
      return `sentences[${index}].text is required`
    }
  }
  const labels = params.labels
  if (!Array.isArray(labels) || labels.length === 0) return "labels must be a non-empty list"
  for (const [index, label] of labels.entries()) {
    if (typeof label === "string") {
      if (!label.trim()) return `labels[${index}] must be non-empty`
    } else if (!label || typeof label !== "object" || typeof (label as { label?: unknown }).label !== "string" || !(label as { label: string }).label.trim()) {
      return `labels[${index}].label is required`
    }
  }
  return null
}
