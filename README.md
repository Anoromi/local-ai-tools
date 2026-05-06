# kokoro-rocm

`kokoro-rocm` is a local Kokoro PyTorch ROCm CLI backed by a Unix-socket daemon.
The user-facing CLI is TypeScript/Bun with Effect CLI and Effect Schema. Python
stays responsible for Kokoro, PyTorch, ROCm setup, health probes, and the daemon.
The CLI reads text from stdin, auto-starts the daemon if needed, and writes a WAV
plus a timing JSON sidecar.

This repository is a Turbo monorepo:

```text
apps/cli                 TypeScript/Bun CLI
packages/protocol        reusable Effect Schema protocol package
python                   Kokoro/PyTorch daemon, setup, and health implementation
```

The protocol package is named `@anoromi/kokoro-rocm-protocol`. It is structured
so editor extensions and other clients can reuse the daemon and session schemas
without importing CLI transport code. It is GitHub-consumable for now; it is not
published to npm yet.

```bash
printf "Hello from Kokoro." | kokoro-rocm -o /tmp/hello.wav
```

Outputs:

```text
/tmp/hello.wav
/tmp/hello.json
```

## Why a daemon?

Kokoro model loading is measurable. The daemon loads the model once and keeps it
resident so repeated CLI calls only pay synthesis and post-processing time.

## Commands

```bash
kokoro-rocm setup
kokoro-rocm health
kokoro-rocm session
kokoro-rocm serve
kokoro-rocm status
kokoro-rocm stop
printf "Text" | kokoro-rocm say -o out.wav
```

`say` is the default command, so this is equivalent:

```bash
printf "Text" | kokoro-rocm -o out.wav
```

Useful options:

```bash
printf "Text" | kokoro-rocm -o out.wav --voice af_sarah --speed 1.0 --target-wpm 500
```

If `--target-wpm` is set, FFmpeg `atempo` is used when native speech is outside
the target tolerance. Word and chunk timings in the JSON sidecar are rescaled by
the same factor.

## Session mode

For editor/app integrations, keep one client process alive:

```bash
kokoro-rocm session
```

`session` reads newline-delimited JSON from stdin and writes newline-delimited
JSON events to stdout. Human logs go to stderr.

Health example:

```bash
printf '{"id":"1","method":"health","params":{}}\n{"id":"2","method":"exit","params":{}}\n' \
  | kokoro-rocm session
```

Synthesis example:

```bash
printf '{"id":"1","method":"synthesize","params":{"text":"Hello","output_path":"/tmp/hello.wav","timings_path":"/tmp/hello.json","voice":"af_sarah","speed":1,"target_wpm":null,"format":"wav"}}\n{"id":"2","method":"exit","params":{}}\n' \
  | kokoro-rocm session
```

Typical events:

```json
{"event":"ready","version":"0.1.0"}
{"id":"1","event":"accepted"}
{"id":"1","event":"started"}
{"id":"1","event":"chunk","chunk":{"index":0,"text":"Hello","start":0,"end":1.2,"duration":1.2,"timing_basis":"native"}}
{"id":"1","event":"finished","result":{"output_path":"/tmp/hello.wav","timings_path":"/tmp/hello.json"}}
```

Session mode avoids repeated CLI process startup. One-shot commands are kept for
normal shell use.

## Nix

Development:

```bash
nix develop
bun install
bun run build
bun run typecheck
bun run test
cd python && uv sync --dev && uv run pytest
```

Run the CLI from source:

```bash
printf "Hello" | bun run apps/cli/src/main.ts -o /tmp/hello.wav
```

Nix builds the TypeScript bundle during the flake build. Generated `dist/`
directories are intentionally not committed.

Useful Nix commands:

```bash
nix flake check
nix run . -- health --json
```

NixOS flake integration:

```nix
inputs.kokoro-rocm.url = "github:Anoromi/kokoro-rocm";
```

Home Manager package:

```nix
inputs.kokoro-rocm.packages.${pkgs.stdenv.hostPlatform.system}.default
```

## Protocol package

`@anoromi/kokoro-rocm-protocol` exports Effect Schema definitions, inferred
TypeScript types, and JSON line helpers for both the daemon socket protocol and
the session NDJSON protocol.

Example:

```ts
import {
  SynthesizeParams,
  decodeSessionLine,
  eventLine,
} from "@anoromi/kokoro-rocm-protocol"

const params = SynthesizeParams
const request = decodeSessionLine(
  '{"id":"1","method":"health","params":{}}'
)
const line = eventLine({ event: "ready", version: "0.1.0" })
```

The package intentionally does not include Unix socket clients, daemon
auto-start logic, filesystem path resolution, or Bun-specific APIs.

## Setup

After installing through Home Manager or `nix run`, prepare the machine-local
runtime:

```bash
kokoro-rocm setup
kokoro-rocm health
printf "Hello" | kokoro-rocm -o /tmp/hello.wav
```

`setup` creates:

```text
~/.local/share/kokoro-rocm/
  .venv/
  env
  models/v1_0/kokoro-v1_0.pth
  models/v1_0/config.json
  voices/v1_0/af_sarah.pt
```

By default it installs PyTorch from the official ROCm 6.4 wheel index:

```bash
kokoro-rocm setup --torch rocm6.4
```

Other setup modes:

```bash
kokoro-rocm setup --torch rocm6.3
kokoro-rocm setup --torch existing --python-path /path/to/venv/bin/python
```

`setup` does not install AMD GPU drivers. Before setup, the machine should
already expose GPU devices such as:

```bash
ls -l /dev/kfd /dev/dri/renderD*
```

On Ubuntu, the user usually needs access to the `render` and `video` groups.

## Health

Run diagnostics without starting the daemon:

```bash
kokoro-rocm health
kokoro-rocm health --json
kokoro-rocm health --probe-synthesis
```

Health checks cover:

- wrapper tools: `uv`, `ffmpeg`, `soxi`, `gcc`
- setup env file
- model/config/voice assets
- `/dev/kfd` and `/dev/dri/renderD*`
- ROCm PyTorch import and GPU visibility
- Kokoro/SoundFile/NumPy imports
- daemon socket status
- optional direct synthesis probe

## Internal helper

The Nix package exposes:

```text
kokoro-rocm         TypeScript/Bun CLI
kokoro-rocm-python  Python helper used for serve/setup/health
```

`kokoro-rocm-python` is not intended as the primary user interface, but it is
available for debugging.

## Runtime assets

If `kokoro-rocm setup` has not been run, the MVP still falls back to local
benchmark assets on this development machine:

```text
KOKORO_ROCM_MODEL=/tmp/kokoro-bench/api-test/Kokoro-FastAPI/api/src/models/v1_0/kokoro-v1_0.pth
KOKORO_ROCM_CONFIG=/tmp/kokoro-bench/api-test/Kokoro-FastAPI/api/src/models/v1_0/config.json
KOKORO_ROCM_VOICES_DIR=/tmp/kokoro-bench/api-test/Kokoro-FastAPI/api/src/voices/v1_0
KOKORO_ROCM_DEFAULT_VOICE=af_sarah
KOKORO_ROCM_PYTHON=/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/bin/python
```

On another machine, prefer `kokoro-rocm setup`. You can also provide equivalent
paths through those environment variables. `KOKORO_ROCM_PYTHON` should point at
a Python environment with Kokoro, SoundFile, NumPy, and ROCm-enabled PyTorch.

## ROCm caveat

The direct PyTorch path sets:

```python
torch.backends.cudnn.enabled = False
```

This avoids a MIOpen HIPRTC InstanceNorm compilation failure observed on
`gfx1151`/Strix Halo.

## Timing sidecar

The JSON sidecar includes:

- final audio path
- audio duration
- WPM
- chunks
- word/token timings
- post-tempo metadata

Timestamps come from Kokoro `pred_dur` joined onto pipeline tokens. They are
model-predicted timings, not external forced alignment.

## Current benchmark context

On the tested Strix Halo machine, direct PyTorch ROCm was about 2x faster than
the ONNX CPU path for the 500 WPM retimed benchmark.
