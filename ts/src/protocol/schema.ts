import * as Schema from "effect/Schema"

export const RequestId = Schema.NonEmptyString
export const SocketPath = Schema.NonEmptyString
export const OutputPath = Schema.NonEmptyString
export const VoiceName = Schema.NonEmptyString
export const PositiveNumber = Schema.Number.pipe(Schema.positive())
export const NullableTargetWpm = Schema.NullOr(PositiveNumber)

export const HealthParams = Schema.Struct({})
export const ShutdownParams = Schema.Struct({})

export const SynthesizeParams = Schema.Struct({
  text: Schema.NonEmptyString,
  output_path: OutputPath,
  timings_path: OutputPath,
  voice: Schema.optionalWith(VoiceName, { default: () => "af_sarah" }),
  speed: Schema.optionalWith(PositiveNumber, { default: () => 1 }),
  target_wpm: Schema.optionalWith(NullableTargetWpm, { default: () => null }),
  format: Schema.optionalWith(Schema.Literal("wav"), { default: () => "wav" as const })
})

export const DaemonMethod = Schema.Literal("health", "shutdown", "synthesize", "synthesize_stream")

export const DaemonRequest = Schema.Struct({
  id: RequestId,
  method: DaemonMethod,
  params: Schema.Record({ key: Schema.String, value: Schema.Unknown })
})

export const ErrorPayload = Schema.Struct({
  stage: Schema.String,
  message: Schema.String,
  detail: Schema.optionalWith(Schema.String, { default: () => "" })
})

export const DaemonSuccessResponse = Schema.Struct({
  id: RequestId,
  ok: Schema.Literal(true),
  result: Schema.Record({ key: Schema.String, value: Schema.Unknown })
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
  event: Schema.Literal("started", "chunk"),
  data: Schema.Record({ key: Schema.String, value: Schema.Unknown })
})

export const DaemonMessage = Schema.Union(DaemonSuccessResponse, DaemonFailureResponse, DaemonStreamEvent)

export const SessionMethod = Schema.Literal("health", "synthesize", "shutdownDaemon", "exit")

export const SessionRequest = Schema.Struct({
  id: RequestId,
  method: SessionMethod,
  params: Schema.Record({ key: Schema.String, value: Schema.Unknown })
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
  result: Schema.Record({ key: Schema.String, value: Schema.Unknown })
})

export const ErrorEvent = Schema.Struct({
  id: Schema.String,
  event: Schema.Literal("error"),
  error: ErrorPayload
})

export const HealthEvent = Schema.Struct({
  id: RequestId,
  event: Schema.Literal("health"),
  result: Schema.Record({ key: Schema.String, value: Schema.Unknown })
})

export const SessionEvent = Schema.Union(
  ReadyEvent,
  AcceptedEvent,
  DaemonStartingEvent,
  DaemonReadyEvent,
  StartedEvent,
  ChunkEvent,
  FinishedEvent,
  ErrorEvent,
  HealthEvent
)

export type SynthesizeParams = Schema.Schema.Type<typeof SynthesizeParams>
export type DaemonRequest = Schema.Schema.Type<typeof DaemonRequest>
export type DaemonSuccessResponse = Schema.Schema.Type<typeof DaemonSuccessResponse>
export type DaemonFailureResponse = Schema.Schema.Type<typeof DaemonFailureResponse>
export type DaemonStreamEvent = Schema.Schema.Type<typeof DaemonStreamEvent>
export type DaemonMessage = Schema.Schema.Type<typeof DaemonMessage>
export type SessionRequest = Schema.Schema.Type<typeof SessionRequest>
export type SessionEvent = Schema.Schema.Type<typeof SessionEvent>
export type ErrorPayload = Schema.Schema.Type<typeof ErrorPayload>
export type ChunkPayload = Schema.Schema.Type<typeof ChunkPayload>

export const decodeDaemonMessage = Schema.decodeUnknownSync(DaemonMessage)
export const decodeSessionRequest = Schema.decodeUnknownSync(SessionRequest)
export const decodeSynthesizeParams = Schema.decodeUnknownSync(SynthesizeParams)
export const encodeSessionEvent = Schema.encodeSync(SessionEvent)
