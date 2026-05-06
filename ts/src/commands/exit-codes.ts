export const EXIT_USAGE = 1
export const EXIT_DAEMON = 2
export const EXIT_SYNTHESIS = 3
export const EXIT_WRITE = 4
export const EXIT_PROTOCOL = 5
export const EXIT_SETUP = 6
export const EXIT_HEALTH = 7

export class CliExit extends Error {
  constructor(
    readonly code: number,
    message: string
  ) {
    super(message)
    this.name = "CliExit"
  }
}
