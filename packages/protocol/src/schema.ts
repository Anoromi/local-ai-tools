import { Effect, Schema } from "effect"

export const RequestId = Schema.NonEmptyString
export const SocketPath = Schema.NonEmptyString
export const OutputPath = Schema.NonEmptyString
export const VoiceName = Schema.NonEmptyString
export const PositiveNumber = Schema.Number.check(Schema.isGreaterThan(0))
export const NullableTargetWpm = Schema.NullOr(PositiveNumber)
export const Precision = Schema.Literals(["fp32", "fp16"])

export const HealthParams = Schema.Struct({})
export const ShutdownParams = Schema.Struct({})

export const SynthesizeParams = Schema.Struct({
  text: Schema.NonEmptyString,
  output_path: OutputPath,
  timings_path: OutputPath,
  profile_path: Schema.NullOr(OutputPath).pipe(Schema.withDecodingDefaultKey(Effect.succeed(null))),
  voice: VoiceName.pipe(Schema.withDecodingDefaultKey(Effect.succeed("af_sarah"))),
  speed: PositiveNumber.pipe(Schema.withDecodingDefaultKey(Effect.succeed(1))),
  target_wpm: NullableTargetWpm.pipe(Schema.withDecodingDefaultKey(Effect.succeed(null))),
  precision: Precision.pipe(Schema.withDecodingDefaultKey(Effect.succeed("fp32" as const))),
  format: Schema.Literal("wav").pipe(Schema.withDecodingDefaultKey(Effect.succeed("wav" as const)))
})

export const DaemonMethod = Schema.Literals(["health", "shutdown", "synthesize", "synthesize_stream"])

export const DaemonRequest = Schema.Struct({
  id: RequestId,
  method: DaemonMethod,
  params: Schema.Record(Schema.String, Schema.Any)
})

export const ErrorPayload = Schema.Struct({
  stage: Schema.String,
  message: Schema.String,
  detail: Schema.String.pipe(Schema.withDecodingDefaultKey(Effect.succeed("")))
})

export const DaemonSuccessResponse = Schema.Struct({
  id: RequestId,
  ok: Schema.Literal(true),
  result: Schema.Record(Schema.String, Schema.Any)
})

export const DaemonFailureResponse = Schema.Struct({
  id: Schema.String,
  ok: Schema.Literal(false),
  error: ErrorPayload
})

export const ChunkPayload = Schema.Struct({
  index: Schema.Number,
  text: Schema.String,
  start: Schema.Number,
  end: Schema.Number,
  duration: Schema.Number,
  timing_basis: Schema.Literal("native")
})

export const DaemonStreamEvent = Schema.Struct({
  id: RequestId,
  ok: Schema.Literal(true),
  event: Schema.Literals(["started", "chunk"]),
  data: Schema.Record(Schema.String, Schema.Any)
})

export const DaemonMessage = Schema.Union([DaemonSuccessResponse, DaemonFailureResponse, DaemonStreamEvent])

export const SessionMethod = Schema.Literals(["health", "synthesize", "shutdownDaemon", "exit"])

export const SessionRequest = Schema.Struct({
  id: RequestId,
  method: SessionMethod,
  params: Schema.Record(Schema.String, Schema.Any)
})

export const ReadyEvent = Schema.Struct({
  event: Schema.Literal("ready"),
  version: Schema.String
})

export const AcceptedEvent = Schema.Struct({
  id: RequestId,
  event: Schema.Literal("accepted")
})

export const DaemonStartingEvent = Schema.Struct({
  id: RequestId,
  event: Schema.Literal("daemon_starting")
})

export const DaemonReadyEvent = Schema.Struct({
  id: RequestId,
  event: Schema.Literal("daemon_ready"),
  pid: Schema.Number
})

export const StartedEvent = Schema.Struct({
  id: RequestId,
  event: Schema.Literal("started")
})

export const ChunkEvent = Schema.Struct({
  id: RequestId,
  event: Schema.Literal("chunk"),
  chunk: ChunkPayload
})

export const FinishedEvent = Schema.Struct({
  id: RequestId,
  event: Schema.Literal("finished"),
  result: Schema.Record(Schema.String, Schema.Any)
})

export const ErrorEvent = Schema.Struct({
  id: Schema.String,
  event: Schema.Literal("error"),
  error: ErrorPayload
})

export const HealthEvent = Schema.Struct({
  id: RequestId,
  event: Schema.Literal("health"),
  result: Schema.Record(Schema.String, Schema.Any)
})

export const SessionEvent = Schema.Union([
  ReadyEvent,
  AcceptedEvent,
  DaemonStartingEvent,
  DaemonReadyEvent,
  StartedEvent,
  ChunkEvent,
  FinishedEvent,
  ErrorEvent,
  HealthEvent
])

export type SynthesizeParams = typeof SynthesizeParams.Type
export type DaemonRequest = typeof DaemonRequest.Type
export type DaemonSuccessResponse = typeof DaemonSuccessResponse.Type
export type DaemonFailureResponse = typeof DaemonFailureResponse.Type
export type DaemonStreamEvent = typeof DaemonStreamEvent.Type
export type DaemonMessage = typeof DaemonMessage.Type
export type SessionRequest = typeof SessionRequest.Type
export type SessionEvent = typeof SessionEvent.Type
export type ErrorPayload = typeof ErrorPayload.Type
export type ChunkPayload = typeof ChunkPayload.Type

export const decodeDaemonMessage = Schema.decodeUnknownSync(DaemonMessage)
export const decodeSessionRequest = Schema.decodeUnknownSync(SessionRequest)
export const decodeSynthesizeParams = Schema.decodeUnknownSync(SynthesizeParams)
export const encodeSessionEvent = Schema.encodeSync(SessionEvent)
