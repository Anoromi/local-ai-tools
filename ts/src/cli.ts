import { Command, Options } from "@effect/cli"
import { NodeContext, NodeRuntime } from "@effect/platform-node"
import { Effect, Option, pipe } from "effect"
import { runSay } from "./commands/say"
import { runStatus } from "./commands/status"
import { runStop } from "./commands/stop"
import { runServe } from "./commands/serve"
import { runSetup } from "./commands/setup"
import { runHealth } from "./commands/health"
import { runSession } from "./commands/session"
import { CliExit, EXIT_USAGE } from "./commands/exit-codes"

const optString = (name: string) => Options.optional(Options.text(name))
const optNumber = (name: string) => Options.optional(Options.float(name))
const withDefault = <A, B>(option: Options.Options<A>, value: B) => Options.withDefault(option, value)
const optionValue = <A>(value: Option.Option<A>): A | undefined => Option.getOrUndefined(value)

const outputOption = Options.optional(Options.withAlias(Options.text("output"), "o"))
const voiceOption = withDefault(Options.text("voice"), "af_sarah")
const speedOption = withDefault(Options.float("speed"), 1)
const targetWpmOption = optNumber("target-wpm")
const socketOption = optString("socket")

const sayConfig = {
  output: outputOption,
  voice: voiceOption,
  speed: speedOption,
  targetWpm: targetWpmOption,
  socket: socketOption
}

const say = Command.make("say", sayConfig, (args) =>
  runSay({
    output: optionValue(args.output),
    voice: args.voice,
    speed: args.speed,
    targetWpm: optionValue(args.targetWpm) ?? null,
    socket: optionValue(args.socket)
  })
)

const status = Command.make("status", { socket: socketOption }, (args) => runStatus(optionValue(args.socket)))
const stop = Command.make("stop", { socket: socketOption }, (args) => runStop(optionValue(args.socket)))
const session = Command.make("session", { socket: socketOption }, (args) => runSession(optionValue(args.socket)))

const serve = Command.make(
  "serve",
  {
    foreground: Options.boolean("foreground"),
    socket: socketOption
  },
  (args) => runServe(renderOptions({ foreground: args.foreground, socket: optionValue(args.socket) }))
)

const setup = Command.make(
  "setup",
  {
    torch: withDefault(Options.choice("torch", ["rocm6.4", "rocm6.3", "cpu", "existing"] as const), "rocm6.4"),
    python: withDefault(Options.text("python"), "3.12"),
    pythonPath: optString("python-path"),
    dataDir: optString("data-dir"),
    voice: withDefault(Options.text("voice"), "af_sarah"),
    force: Options.boolean("force"),
    noDownload: Options.boolean("no-download"),
    modelUrl: optString("model-url"),
    configUrl: optString("config-url"),
    voiceUrl: optString("voice-url")
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
    json: Options.boolean("json"),
    output: optString("output"),
    probeSynthesis: Options.boolean("probe-synthesis"),
    keepProbeOutput: Options.boolean("keep-probe-output"),
    socket: socketOption
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

const root = pipe(Command.make("kokoro-rocm", {}, () => Effect.void), Command.withSubcommands([say, session, serve, status, stop, setup, health]))

const defaultSay = Command.make("kokoro-rocm", sayConfig, (args) =>
  runSay({
      output: optionValue(args.output),
    voice: args.voice,
    speed: args.speed,
    targetWpm: optionValue(args.targetWpm) ?? null,
    socket: optionValue(args.socket)
  })
)

export async function main(argv: readonly string[] = process.argv.slice(2)): Promise<void> {
  if (isSubcommandHelp(argv)) {
    printCommandHelp(argv[0]!)
    return
  }
  if (argv[0] === "setup") {
    await Effect.runPromise(runSetup(argv.slice(1)))
    return
  }
  if (argv[0] === "health") {
    await Effect.runPromise(runHealth(argv.slice(1)))
    return
  }
  if (argv[0] === "serve") {
    await Effect.runPromise(runServe(argv.slice(1)))
    return
  }
  if (argv[0] === "--help" || argv[0] === "-h") {
    printRootHelp()
    return
  }
  if (argv[0] === "--version" || argv[0] === "-v") {
    process.stdout.write("0.1.0\n")
    return
  }
  const { command, args } = selectCommand(argv)
  const run = Command.run(command as any, {
    name: "kokoro-rocm",
    version: "0.1.0"
  })
  try {
    await Effect.runPromise(pipe(run(["bun", "kokoro-rocm", ...args]), Effect.provide(NodeContext.layer)) as Effect.Effect<void, unknown, never>)
  } catch (error) {
    if (error instanceof CliExit) {
      process.exitCode = error.code
      return
    }
    process.stderr.write(`${String(error)}\n`)
    process.exitCode = EXIT_USAGE
  }
}

function isSubcommandHelp(argv: readonly string[]): boolean {
  return Boolean(argv[0] && ["say", "session", "serve", "status", "stop", "setup", "health"].includes(argv[0]) && (argv.includes("--help") || argv.includes("-h")))
}

function printCommandHelp(command: string): void {
  const usage: Record<string, string> = {
    say: "kokoro-rocm say -o output.wav [--voice af_sarah] [--speed 1.0] [--target-wpm 500] [--socket PATH]",
    session: "kokoro-rocm session [--socket PATH]",
    serve: "kokoro-rocm serve [--foreground] [--socket PATH]",
    status: "kokoro-rocm status [--socket PATH]",
    stop: "kokoro-rocm stop [--socket PATH]",
    setup: "kokoro-rocm setup [--torch rocm6.4|rocm6.3|cpu|existing] [--python 3.12] [--python-path PATH] [--data-dir PATH] [--voice NAME] [--force] [--no-download] [--model-url URL] [--config-url URL] [--voice-url URL]",
    health: "kokoro-rocm health [--json] [--output PATH] [--probe-synthesis] [--keep-probe-output] [--socket PATH]"
  }
  process.stdout.write(`${usage[command]}\n`)
}

function printRootHelp(): void {
  process.stdout.write(`kokoro-rocm 0.1.0

Usage:
  kokoro-rocm -o output.wav [options]
  kokoro-rocm say -o output.wav [options]
  kokoro-rocm session [--socket PATH]
  kokoro-rocm serve [--foreground] [--socket PATH]
  kokoro-rocm status [--socket PATH]
  kokoro-rocm stop [--socket PATH]
  kokoro-rocm setup [options]
  kokoro-rocm health [options]
`)
}

function selectCommand(argv: readonly string[]) {
  const first = argv[0]
  if (!first) return { command: defaultSay, args: argv }
  if (first === "--help" || first === "-h" || first === "--version" || first === "-v") return { command: root, args: argv }
  const subcommands = { say, session, serve, status, stop, setup, health } as const
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
