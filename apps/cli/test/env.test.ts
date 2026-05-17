import { describe, expect, test } from "bun:test"
import { rocmEnv } from "../src/runtime/env"

describe("rocm env", () => {
  test("enables AOTriton attention by default", () => {
    const env = rocmEnv({}, {})
    expect(env.TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL).toBe("1")
  })

  test("allows AOTriton override", () => {
    const env = rocmEnv({ TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL: "0" }, {})
    expect(env.TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL).toBe("0")
  })
})
