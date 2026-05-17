import { describe, expect, test } from "bun:test"
import { runtimeDir, sidecarPath, socketPath } from "../src/runtime/paths"

describe("paths", () => {
  test("explicit socket beats env", () => {
    expect(socketPath("/tmp/explicit.sock", { LOCAL_AI_TOOLS_SOCKET: "/tmp/env.sock" })).toBe("/tmp/explicit.sock")
  })

  test("socket uses env when present", () => {
    expect(socketPath(null, { LOCAL_AI_TOOLS_SOCKET: "/tmp/env.sock" })).toBe("/tmp/env.sock")
  })

  test("runtime dir uses xdg runtime dir", () => {
    expect(runtimeDir({ XDG_RUNTIME_DIR: "/tmp/x" })).toBe("/tmp/x/local-ai-tools")
  })

  test("socket falls back to tmp runtime dir", () => {
    expect(socketPath(null, {})).toContain("/local-ai-tools-")
  })

  test("sidecar replaces extension", () => {
    expect(sidecarPath("/tmp/foo.wav")).toBe("/tmp/foo.json")
  })
})
