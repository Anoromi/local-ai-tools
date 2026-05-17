import { describe, expect, test } from "bun:test"
import { spawnSync } from "node:child_process"
import { fileURLToPath } from "node:url"

const cli = ["bun", "run", "src/main.ts"] as const
const cwd = fileURLToPath(new URL("..", import.meta.url))

describe("cli contract", () => {
  test("root help lists session", () => {
    const result = spawnSync(cli[0], [...cli.slice(1), "--help"], { cwd, encoding: "utf8" })
    expect(result.status).toBe(0)
    expect(result.stdout).toContain("session")
  })

  test("say help works without output", () => {
    const result = spawnSync(cli[0], [...cli.slice(1), "say", "--help"], { cwd, encoding: "utf8" })
    expect(result.status).toBe(0)
    expect(result.stdout).toContain("USAGE")
    expect(result.stdout).toContain("say [flags]")
    expect(result.stdout).toContain("--profile")
    expect(result.stdout).toContain("--profile-output")
  })

  test("select help lists selection flags", () => {
    const result = spawnSync(cli[0], [...cli.slice(1), "select", "--help"], { cwd, encoding: "utf8" })
    expect(result.status).toBe(0)
    expect(result.stdout).toContain("--question")
    expect(result.stdout).toContain("--input")
    expect(result.stdout).toContain("--output")
    expect(result.stdout).toContain("--threshold")
    expect(result.stdout).toContain("--include-all-scores")
  })

  test("classify help lists classification flags", () => {
    const result = spawnSync(cli[0], [...cli.slice(1), "classify", "--help"], { cwd, encoding: "utf8" })
    expect(result.status).toBe(0)
    expect(result.stdout).toContain("--input")
    expect(result.stdout).toContain("--output")
    expect(result.stdout).toContain("--include-all-scores")
  })

  test("classify rejects empty stdin", () => {
    const result = spawnSync(cli[0], [...cli.slice(1), "classify"], { cwd, input: "", encoding: "utf8" })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain("stdin JSON is empty")
  })

  test("classify rejects invalid JSON before daemon startup", () => {
    const result = spawnSync(cli[0], [...cli.slice(1), "classify"], { cwd, input: "not-json", encoding: "utf8" })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain("Unexpected")
  })

  test("classify rejects empty sentences and labels", () => {
    const noSentences = spawnSync(cli[0], [...cli.slice(1), "classify"], {
      cwd,
      input: '{"sentences":[],"labels":["issue"]}',
      encoding: "utf8"
    })
    expect(noSentences.status).toBe(1)
    expect(noSentences.stderr).toContain("sentences must be a non-empty list")

    const noLabels = spawnSync(cli[0], [...cli.slice(1), "classify"], {
      cwd,
      input: '{"sentences":["Hello."],"labels":[]}',
      encoding: "utf8"
    })
    expect(noLabels.status).toBe(1)
    expect(noLabels.stderr).toContain("labels must be a non-empty list")
  })

  test("select rejects empty stdin", () => {
    const result = spawnSync(cli[0], [...cli.slice(1), "select", "--question", "What failed?"], { cwd, input: "", encoding: "utf8" })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain("stdin text is empty")
  })

  test("select rejects empty questions", () => {
    const result = spawnSync(cli[0], [...cli.slice(1), "select"], { cwd, input: "Hello.", encoding: "utf8" })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain("at least one --question")
  })

  test("default say accepts profile flags", () => {
    const result = spawnSync(cli[0], [...cli.slice(1), "--profile", "--profile-output", "/tmp/a.profile.json"], {
      cwd,
      input: "Hello",
      encoding: "utf8"
    })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain("-o/--output is required")
  })

  test("default say requires output", () => {
    const result = spawnSync(cli[0], cli.slice(1), { cwd, input: "Hello", encoding: "utf8" })
    expect(result.status).toBe(1)
    expect(result.stderr).toContain("-o/--output is required")
  })
})
