import { createInterface } from "node:readline/promises"

export async function readAllStdin(): Promise<string> {
  return await new Response(Bun.stdin.stream()).text()
}

export function stdinLines(): AsyncIterable<string> {
  return createInterface({ input: process.stdin, crlfDelay: Infinity })
}
