const MANIFESTS = ["apps/cli/package.json", "packages/protocol/package.json"] as const

const dryRun = process.argv.includes("--dry-run")

function bumpMinor(version: string): string {
  const match = /^(\d+)\.(\d+)\.(\d+)(?:-.+)?$/.exec(version)
  if (!match) {
    throw new Error(`unsupported semver version: ${version}`)
  }
  const major = Number(match[1])
  const minor = Number(match[2])
  return `${major}.${minor + 1}.0`
}

for (const path of MANIFESTS) {
  const manifest = await Bun.file(path).json()
  if (typeof manifest.version !== "string") {
    throw new Error(`${path} does not have a string version`)
  }
  const next = bumpMinor(manifest.version)
  console.log(`${path}: ${manifest.version} -> ${next}${dryRun ? " (dry run)" : ""}`)
  if (!dryRun) {
    manifest.version = next
    await Bun.write(path, `${JSON.stringify(manifest, null, 2)}\n`)
  }
}
