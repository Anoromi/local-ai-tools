import { describe, expect, test } from "bun:test"
import { spawnSync } from "node:child_process"

const cli = ["bun", "run", "ts/src/main.ts"] as const

describe("cli contract", () => {
  test("root help lists session", () => {
    const result = spawnSync(cli[0], [...cli.slice(1), "--help"], { encoding: "utf8" })
    expect(result.status).toBe(0)
    expect(result.stdout).toContain("session")
  })

  test("say help works without output", () => {
    const result = spawnSync(cli[0], [...cli.slice(1), "say", "--help"], { encoding: "utf8" })
    expect(result.status).toBe(0)
    expect(result.stdout).toContain("kokoro-rocm say")
  })

  test("default say requires output", () => {
    const result = spawnSync(cli[0], cli.slice(1), { input: "Hello", encoding: "utf8" })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain("-o/--output is required")
  })
})
