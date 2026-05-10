import { describe, expect, test } from "bun:test"
import { spawnSync } from "node:child_process"

const cli = ["bun", "run", "src/main.ts"] as const

describe("cli contract", () => {
  test("root help lists session", () => {
    const result = spawnSync(cli[0], [...cli.slice(1), "--help"], { encoding: "utf8" })
    expect(result.status).toBe(0)
    expect(result.stdout).toContain("session")
  })

  test("say help works without output", () => {
    const result = spawnSync(cli[0], [...cli.slice(1), "say", "--help"], { encoding: "utf8" })
    expect(result.status).toBe(0)
    expect(result.stdout).toContain("USAGE")
    expect(result.stdout).toContain("say [flags]")
    expect(result.stdout).toContain("--profile")
    expect(result.stdout).toContain("--profile-output")
  })

  test("default say accepts profile flags", () => {
    const result = spawnSync(cli[0], [...cli.slice(1), "--profile", "--profile-output", "/tmp/a.profile.json"], {
      input: "Hello",
      encoding: "utf8"
    })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain("-o/--output is required")
  })

  test("default say requires output", () => {
    const result = spawnSync(cli[0], cli.slice(1), { input: "Hello", encoding: "utf8" })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain("-o/--output is required")
  })
})
