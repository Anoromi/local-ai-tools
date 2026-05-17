import { describe, expect, test } from "bun:test"
import { decodeDaemonLine, decodeSelectParams, decodeSessionLine, decodeSynthesizeParams, eventLine } from "@anoromi/local-ai-tools-protocol"

describe("protocol schemas", () => {
  test("valid synthesize request decodes", () => {
    const request = decodeSessionLine(
      '{"id":"1","method":"synthesize","params":{"text":"Hello","output_path":"/tmp/a.wav","timings_path":"/tmp/a.json","voice":"af_sarah","speed":1,"target_wpm":null,"precision":"fp16","format":"wav"}}'
    )
    expect(request.method).toBe("synthesize")
  })

  test("valid select request decodes", () => {
    const request = decodeSessionLine(
      '{"id":"1","method":"select","params":{"text":"Hello. Bye.","items":[{"question":"What happened?"}]}}'
    )
    expect(request.method).toBe("select")
  })

  test("select params default threshold and language", () => {
    const params = decodeSelectParams({ text: "Hello.", items: [{ question: "What happened?" }] })
    expect(params.language).toBe("auto")
    expect(params.include_all_scores).toBe(false)
    expect(params.items[0]?.threshold).toBe(0.5)
  })

  test("invalid select threshold fails", () => {
    expect(() => decodeSelectParams({ text: "Hello.", items: [{ question: "What happened?", threshold: 2 }] })).toThrow()
  })

  test("synthesize params default to fp32", () => {
    const params = decodeSynthesizeParams({ text: "Hello", output_path: "/tmp/a.wav", timings_path: "/tmp/a.json" })
    expect(params.precision).toBe("fp32")
    expect(params.profile_path).toBe(null)
  })

  test("synthesize params accept profile path", () => {
    const params = decodeSynthesizeParams({
      text: "Hello",
      output_path: "/tmp/a.wav",
      timings_path: "/tmp/a.json",
      profile_path: "/tmp/a.profile.json"
    })
    expect(params.profile_path).toBe("/tmp/a.profile.json")
  })

  test("missing text fails", () => {
    expect(() => decodeSynthesizeParams({ output_path: "/tmp/a.wav", timings_path: "/tmp/a.json" })).toThrow()
  })

  test("missing output path fails", () => {
    expect(() => decodeSynthesizeParams({ text: "Hello", timings_path: "/tmp/a.json" })).toThrow()
  })

  test("invalid target wpm fails", () => {
    expect(() =>
      decodeSynthesizeParams({ text: "Hello", output_path: "/tmp/a.wav", timings_path: "/tmp/a.json", target_wpm: -1 })
    ).toThrow()
  })

  test("invalid precision fails", () => {
    expect(() =>
      decodeSynthesizeParams({ text: "Hello", output_path: "/tmp/a.wav", timings_path: "/tmp/a.json", precision: "bf16" })
    ).toThrow()
  })

  test("invalid profile path fails", () => {
    expect(() =>
      decodeSynthesizeParams({ text: "Hello", output_path: "/tmp/a.wav", timings_path: "/tmp/a.json", profile_path: "" })
    ).toThrow()
  })

  test("daemon success, failure, and chunk events decode", () => {
    expect(decodeDaemonLine('{"id":"1","ok":true,"result":{"status":"ok"}}').ok).toBe(true)
    expect(decodeDaemonLine('{"id":"1","ok":false,"error":{"stage":"x","message":"bad","detail":""}}').ok).toBe(false)
    expect(decodeDaemonLine('{"id":"1","ok":true,"event":"chunk","data":{"chunk":{"index":0}}}')).toHaveProperty("event", "chunk")
  })

  test("session events encode to ndjson", () => {
    const line = eventLine({ id: "1", event: "accepted" })
    expect(line.endsWith("\n")).toBe(true)
    expect(JSON.parse(line).event).toBe("accepted")
  })
})
