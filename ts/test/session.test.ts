import { describe, expect, test } from "bun:test"
import { decodeSessionLine, eventLine } from "../src/protocol/encode"

describe("session protocol", () => {
  test("health request decodes", () => {
    const request = decodeSessionLine('{"id":"1","method":"health","params":{}}')
    expect(request.id).toBe("1")
    expect(request.method).toBe("health")
  })

  test("unknown method fails", () => {
    expect(() => decodeSessionLine('{"id":"1","method":"nope","params":{}}')).toThrow()
  })

  test("finished event is valid ndjson", () => {
    const line = eventLine({ id: "1", event: "finished", result: { output_path: "/tmp/a.wav" } })
    expect(JSON.parse(line)).toEqual({ id: "1", event: "finished", result: { output_path: "/tmp/a.wav" } })
  })
})
