export function writeStdout(text: string): void {
  process.stdout.write(text)
}

export function writeStderr(text: string): void {
  process.stderr.write(text)
}

export function printError(message: string): void {
  writeStderr(`${message}\n`)
}
