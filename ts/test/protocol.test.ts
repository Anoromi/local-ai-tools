import { describe, expect, test } from "bun:test"
import { decodeDaemonLine, decodeSessionLine, eventLine } from "../src/protocol/encode"
import { decodeSynthesizeParams } from "../src/protocol/schema"

describe("protocol schemas", () => {
  test("valid synthesize request decodes", () => {
    const request = decodeSessionLine(
      '{"id":"1","method":"synthesize","params":{"text":"Hello","output_path":"/tmp/a.wav","timings_path":"/tmp/a.json","voice":"af_sarah","speed":1,"target_wpm":null,"format":"wav"}}'
    )
    expect(request.method).toBe("synthesize")
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
