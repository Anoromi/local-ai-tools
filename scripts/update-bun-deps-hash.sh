#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
flake_file="$repo_root/flake.nix"
fake_hash="sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

current_hash="$(grep -E '^[[:space:]]*outputHash = "sha256-' "$flake_file" | sed -E 's/.*"([^"]+)".*/\1/' | head -n1)"
if [[ -z "$current_hash" ]]; then
  echo "update-bun-deps-hash: could not find outputHash in $flake_file" >&2
  exit 1
fi

perl -0pi -e 's/outputHash = "sha256-[^"]+";/outputHash = "'$fake_hash'";/' "$flake_file"

set +e
build_output="$(cd "$repo_root" && nix build .#default --no-link 2>&1)"
build_status=$?
set -e

new_hash="$(printf '%s\n' "$build_output" | sed -nE 's/^[[:space:]]*got:[[:space:]]*(sha256-[^[:space:]]+)$/\1/p' | tail -n1)"
if [[ -z "$new_hash" ]]; then
  perl -0pi -e 's/outputHash = "sha256-[^"]+";/outputHash = "'$current_hash'";/' "$flake_file"
  printf '%s\n' "$build_output" >&2
  if [[ $build_status -eq 0 ]]; then
    echo "update-bun-deps-hash: build unexpectedly succeeded with fake hash" >&2
  else
    echo "update-bun-deps-hash: could not parse got hash from nix output" >&2
  fi
  exit 1
fi

perl -0pi -e 's/outputHash = "sha256-[^"]+";/outputHash = "'$new_hash'";/' "$flake_file"
echo "$new_hash"
