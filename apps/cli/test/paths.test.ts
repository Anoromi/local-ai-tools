import { describe, expect, test } from "bun:test"
import { runtimeDir, sidecarPath, socketPath } from "../src/runtime/paths"

describe("paths", () => {
  test("explicit socket beats env", () => {
    expect(socketPath("/tmp/explicit.sock", { KOKORO_ROCM_SOCKET: "/tmp/env.sock" })).toBe("/tmp/explicit.sock")
  })

  test("socket uses env when present", () => {
    expect(socketPath(null, { KOKORO_ROCM_SOCKET: "/tmp/env.sock" })).toBe("/tmp/env.sock")
  })

  test("runtime dir uses xdg runtime dir", () => {
    expect(runtimeDir({ XDG_RUNTIME_DIR: "/tmp/x" })).toBe("/tmp/x/kokoro-rocm")
  })

  test("socket falls back to tmp runtime dir", () => {
    expect(socketPath(null, {})).toContain("/kokoro-rocm-")
  })

  test("sidecar replaces extension", () => {
    expect(sidecarPath("/tmp/foo.wav")).toBe("/tmp/foo.json")
  })
})
