import * as BunServices from "@effect/platform-bun/BunServices"
import { Effect, Option } from "effect"
import { Command, Flag } from "effect/unstable/cli"
import { runSay } from "./commands/say"
import { runStatus } from "./commands/status"
import { runStop } from "./commands/stop"
import { runServe } from "./commands/serve"
import { runSetup } from "./commands/setup"
import { runHealth } from "./commands/health"
import { runSession } from "./commands/session"
import { parseSelectArgv, runSelect } from "./commands/select"
import { CliExit, EXIT_USAGE } from "./commands/exit-codes"

const VERSION = "0.1.0"

const optionValue = <A>(value: Option.Option<A>): A | undefined => Option.getOrUndefined(value)
const optionalString = (name: string) => Flag.string(name).pipe(Flag.optional)
const optionalFloat = (name: string) => Flag.float(name).pipe(Flag.optional)
const outputFlag = Flag.string("output").pipe(Flag.withAlias("o"), Flag.optional)
const voiceFlag = Flag.string("voice").pipe(Flag.withDefault("af_sarah"))
const speedFlag = Flag.float("speed").pipe(Flag.withDefault(1))
const targetWpmFlag = optionalFloat("target-wpm")
const precisionFlag = Flag.choice("precision", ["fp32", "fp16"] as const).pipe(Flag.withDefault("fp32"))
const profileFlag = Flag.boolean("profile")
const profileOutputFlag = optionalString("profile-output")
const socketFlag = optionalString("socket")
const thresholdFlag = Flag.float("threshold").pipe(Flag.withDefault(0.5))

const sayConfig = {
  output: outputFlag,
  voice: voiceFlag,
  speed: speedFlag,
  targetWpm: targetWpmFlag,
  precision: precisionFlag,
  profile: profileFlag,
  profileOutput: profileOutputFlag,
  socket: socketFlag
}

const say = Command.make("say", sayConfig, (args) =>
  runSay({
    output: optionValue(args.output),
    voice: args.voice,
    speed: args.speed,
    targetWpm: optionValue(args.targetWpm) ?? null,
    precision: args.precision,
    profile: args.profile,
    profileOutput: optionValue(args.profileOutput),
    socket: optionValue(args.socket)
  })
)

const status = Command.make("status", { socket: socketFlag }, (args) => runStatus(optionValue(args.socket)))
const stop = Command.make("stop", { socket: socketFlag }, (args) => runStop(optionValue(args.socket)))
const session = Command.make("session", { socket: socketFlag }, (args) => runSession(optionValue(args.socket)))
const select = Command.make(
  "select",
  {
    question: optionalString("question"),
    input: optionalString("input"),
    output: outputFlag,
    threshold: thresholdFlag,
    language: Flag.choice("language", ["auto", "en", "zh"] as const).pipe(Flag.withDefault("auto")),
    includeAllScores: Flag.boolean("include-all-scores"),
    socket: socketFlag
  },
  (args) =>
    runSelect({
      questions: optionValue(args.question) ? [{ question: optionValue(args.question)! }] : [],
      input: optionValue(args.input),
      output: optionValue(args.output),
      threshold: args.threshold,
      language: args.language,
      includeAllScores: args.includeAllScores,
      socket: optionValue(args.socket)
    })
)

const serve = Command.make(
  "serve",
  {
    foreground: Flag.boolean("foreground"),
    socket: socketFlag
  },
  (args) => runServe(renderOptions({ foreground: args.foreground, socket: optionValue(args.socket) }))
)

const setup = Command.make(
  "setup",
  {
    torch: Flag.choice("torch", ["rocm6.4", "rocm6.3", "cpu", "existing"] as const).pipe(Flag.withDefault("rocm6.4")),
    python: Flag.string("python").pipe(Flag.withDefault("3.12")),
    pythonPath: optionalString("python-path"),
    dataDir: optionalString("data-dir"),
    voice: Flag.string("voice").pipe(Flag.withDefault("af_sarah")),
    force: Flag.boolean("force"),
    noDownload: Flag.boolean("no-download"),
    modelUrl: optionalString("model-url"),
    configUrl: optionalString("config-url"),
    voiceUrl: optionalString("voice-url")
  },
  (args) =>
    runSetup(
      renderOptions({
        torch: args.torch,
        python: args.python,
        pythonPath: optionValue(args.pythonPath),
        dataDir: optionValue(args.dataDir),
        voice: args.voice,
        force: args.force,
        noDownload: args.noDownload,
        modelUrl: optionValue(args.modelUrl),
        configUrl: optionValue(args.configUrl),
        voiceUrl: optionValue(args.voiceUrl)
      })
    )
)

const health = Command.make(
  "health",
  {
    json: Flag.boolean("json"),
    output: optionalString("output"),
    probeSynthesis: Flag.boolean("probe-synthesis"),
    keepProbeOutput: Flag.boolean("keep-probe-output"),
    socket: socketFlag
  },
  (args) =>
    runHealth(
      renderOptions({
        json: args.json,
        output: optionValue(args.output),
        probeSynthesis: args.probeSynthesis,
        keepProbeOutput: args.keepProbeOutput,
        socket: optionValue(args.socket)
      })
    )
)

const root = Command.make("local-ai-tools").pipe(Command.withSubcommands([say, select, session, serve, status, stop, setup, health]))

const defaultSay = Command.make("local-ai-tools", sayConfig, (args) =>
  runSay({
    output: optionValue(args.output),
    voice: args.voice,
    speed: args.speed,
    targetWpm: optionValue(args.targetWpm) ?? null,
    precision: args.precision,
    profile: args.profile,
    profileOutput: optionValue(args.profileOutput),
    socket: optionValue(args.socket)
  })
)

export async function main(argv: readonly string[] = process.argv.slice(2)): Promise<void> {
  if (argv[0] === "select" && !argv.includes("--help") && !argv.includes("-h")) {
    try {
      const options = parseSelectArgv(argv.slice(1))
      if (options) {
        await Effect.runPromise(runSelect(options).pipe(Effect.provide(BunServices.layer)))
        return
      }
    } catch (error) {
      process.stderr.write(`local-ai-tools: ${error instanceof Error ? error.message : String(error)}\n`)
      process.exitCode = EXIT_USAGE
      return
    }
  }
  const { command, args } = selectCommand(argv)
  const run = Command.runWith(command, { version: VERSION })
  try {
    await Effect.runPromise(run(args).pipe(Effect.provide(BunServices.layer)))
  } catch (error) {
    if (error instanceof CliExit) {
      process.exitCode = error.code
      return
    }
    process.stderr.write(`${String(error)}\n`)
    process.exitCode = EXIT_USAGE
  }
}

function selectCommand(argv: readonly string[]) {
  const first = argv[0]
  if (!first) return { command: defaultSay, args: argv }
  if (first === "--help" || first === "-h" || first === "--version" || first === "-v") return { command: root, args: argv }
  const subcommands = { say, select, session, serve, status, stop, setup, health } as const
  if (first in subcommands) {
    return { command: subcommands[first as keyof typeof subcommands], args: argv.slice(1) }
  }
  return { command: defaultSay, args: argv }
}

function renderOptions(values: Record<string, string | number | boolean | null | undefined>): string[] {
  const args: string[] = []
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined || value === null || value === false) continue
    const name = key.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)
    if (value === true) {
      args.push(`--${name}`)
    } else {
      args.push(`--${name}`, String(value))
    }
  }
  return args
}
