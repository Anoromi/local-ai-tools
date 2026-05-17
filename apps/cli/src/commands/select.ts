import { readFileSync, writeFileSync } from "node:fs"
import { Effect } from "effect"
import { callOnce } from "../protocol/socket-client"
import { ensureDaemon } from "../runtime/daemon"
import { absolutePath, ensureParent } from "../runtime/paths"
import { readAllStdin } from "../runtime/stdin"
import { printError, writeStdout } from "../runtime/output"
import { EXIT_DAEMON, EXIT_PROTOCOL, EXIT_SYNTHESIS, EXIT_USAGE } from "./exit-codes"

export interface SelectQuestion {
  readonly id?: string
  readonly question: string
  readonly threshold?: number
}

export interface SelectOptions {
  readonly questions: readonly SelectQuestion[]
  readonly input?: string | null
  readonly output?: string | null
  readonly threshold: number
  readonly language: "auto" | "en" | "zh"
  readonly includeAllScores: boolean
  readonly socket?: string | null
}

export function runSelect(options: SelectOptions): Effect.Effect<void> {
  return Effect.promise(async () => {
    const text = (await readAllStdin()).trim()
    if (!text) {
      printError("local-ai-tools: stdin text is empty")
      process.exitCode = EXIT_USAGE
      return
    }
    const questions = loadQuestions(options)
    if (questions.length === 0) {
      printError("local-ai-tools: at least one --question or --input question is required")
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
    const response = await callOnce(
      { socket: options.socket },
      "select",
      {
        text,
        items: questions,
        language: options.language,
        include_all_scores: options.includeAllScores
      },
      3_600_000
    )
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

function loadQuestions(options: SelectOptions): SelectQuestion[] {
  const questions: SelectQuestion[] = options.questions.map((item) => ({
    ...item,
    question: item.question.trim(),
    threshold: item.threshold ?? options.threshold
  }))
  if (!options.input) return questions.filter((item) => item.question)
  const raw = JSON.parse(readFileSync(absolutePath(options.input), "utf8")) as { questions?: SelectQuestion[] }
  for (const item of raw.questions ?? []) {
    if (item.question?.trim()) {
      questions.push({
        id: item.id,
        question: item.question.trim(),
        threshold: item.threshold ?? options.threshold
      })
    }
  }
  return questions
}

export function parseSelectArgv(argv: readonly string[]): SelectOptions | null {
  const options: SelectQuestion[] = []
  let input: string | null = null
  let output: string | null = null
  let threshold = 0.5
  let language: "auto" | "en" | "zh" = "auto"
  let includeAllScores = false
  let socket: string | null = null
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    const next = () => {
      const value = argv[index + 1]
      if (!value) throw new Error(`${arg} requires a value`)
      index += 1
      return value
    }
    if (arg === "--question") options.push({ question: next() })
    else if (arg === "--input") input = next()
    else if (arg === "--output" || arg === "-o") output = next()
    else if (arg === "--threshold") threshold = Number(next())
    else if (arg === "--language") {
      const value = next()
      if (value !== "auto" && value !== "en" && value !== "zh") throw new Error("--language must be auto, en, or zh")
      language = value
    } else if (arg === "--include-all-scores") includeAllScores = true
    else if (arg === "--socket") socket = next()
    else return null
  }
  if (!Number.isFinite(threshold) || threshold < 0 || threshold > 1) throw new Error("--threshold must be between 0 and 1")
  return { questions: options, input, output, threshold, language, includeAllScores, socket }
}
