# PREFACE
Most of this project is ai generated, even the goddamn readme. Don't depend on this package in any reasonable way. It's public because I don't want to deal with private github issues and I'm using it.

## local-ai-tools

`local-ai-tools` is a local AI CLI backed by a Unix-socket daemon. It currently
supports Kokoro TTS, Zilliz semantic text selection, and ModernBERT sentence
classification on a ROCm PyTorch stack.
The user-facing CLI is TypeScript/Bun with Effect CLI and Effect Schema. Python
stays responsible for Kokoro, PyTorch, ROCm setup, health probes, and the daemon.
The CLI reads text from stdin, auto-starts the daemon if needed, and writes a WAV
plus a timing JSON sidecar.

This repository is a Turbo monorepo:

```text
apps/cli                 TypeScript/Bun CLI
packages/protocol        reusable Effect Schema protocol package
python                   PyTorch daemon, setup, health, TTS, selection, and classification implementation
```

The protocol package is named `@anoromi/local-ai-tools-protocol`. It is structured
so editor extensions and other clients can reuse the daemon and session schemas
without importing CLI transport code. It is published to npm as a public package.

```bash
printf "Hello from Kokoro." | local-ai-tools -o /tmp/hello.wav
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
local-ai-tools setup
local-ai-tools health
local-ai-tools session
local-ai-tools serve
local-ai-tools status
local-ai-tools stop
printf "Text" | local-ai-tools say -o out.wav
cat doc.txt | local-ai-tools select --question "What failed?"
cat classify.json | local-ai-tools classify
```

`say` is the default command, so this is equivalent:

```bash
printf "Text" | local-ai-tools -o out.wav
```

Useful options:

```bash
printf "Text" | local-ai-tools -o out.wav --voice af_sarah --speed 1.0 --target-wpm 500
```

If `--target-wpm` is set, FFmpeg `atempo` is used when native speech is outside
the target tolerance. Word and chunk timings in the JSON sidecar are rescaled by
the same factor.

## Selection

`select` reads one document from stdin and batches many questions through
`zilliz/semantic-highlight-bilingual-v1` in one daemon request:

```bash
cat doc.txt | local-ai-tools select \
  --question "What are the action items?" \
  --question "What risks were found?"
```

It returns JSON with selected sentence text, sentence index, character span, and
score. Use `--input questions.json` for larger batches:

```json
{
  "questions": [
    { "id": "actions", "question": "What are the action items?", "threshold": 0.5 },
    { "id": "risks", "question": "What risks were found?", "threshold": 0.55 }
  ]
}
```

Add `--include-all-scores` when tuning thresholds.

## Classification

`classify` reads JSON from stdin or `--input` and batches many sentences against
many labels through `tasksource/ModernBERT-base-nli`. ROCm/CUDA is required;
there is no CPU fallback.

```bash
printf '%s\n' '{
  "sentences": ["The deploy passed.", "The parser failed on invoices."],
  "labels": ["success", "issue"]
}' | local-ai-tools classify
```

Structured labels can set stable ids and per-label thresholds:

```json
{
  "sentences": [
    { "id": "s1", "text": "The deploy passed." },
    { "id": "s2", "text": "The parser failed on invoices." }
  ],
  "labels": [
    { "id": "success", "label": "success", "threshold": 0.5 },
    { "id": "issue", "label": "issue", "threshold": 0.5 }
  ],
  "hypothesis_template": "This sentence indicates {}.",
  "include_all_scores": false
}
```

## Session mode

For editor/app integrations, keep one client process alive:

```bash
local-ai-tools session
```

`session` reads newline-delimited JSON from stdin and writes newline-delimited
JSON events to stdout. Human logs go to stderr.

Health example:

```bash
printf '{"id":"1","method":"health","params":{}}\n{"id":"2","method":"exit","params":{}}\n' \
  | local-ai-tools session
```

Synthesis example:

```bash
printf '{"id":"1","method":"synthesize","params":{"text":"Hello","output_path":"/tmp/hello.wav","timings_path":"/tmp/hello.json","voice":"af_sarah","speed":1,"target_wpm":null,"format":"wav"}}\n{"id":"2","method":"exit","params":{}}\n' \
  | local-ai-tools session
```

Selection example:

```bash
printf '{"id":"1","method":"select","params":{"text":"The deploy passed. The parser failed.","items":[{"id":"failures","question":"What failed?"}]}}\n{"id":"2","method":"exit","params":{}}\n' \
  | local-ai-tools session
```

Classification example:

```bash
printf '{"id":"1","method":"classify","params":{"sentences":["The deploy passed.","The parser failed."],"labels":["success","issue"]}}\n{"id":"2","method":"exit","params":{}}\n' \
  | local-ai-tools session
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

Tooling can be installed with mise:

```bash
mise trust
mise install
```

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
inputs.local-ai-tools.url = "github:Anoromi/local-ai-tools";
```

Home Manager package:

```nix
inputs.local-ai-tools.packages.${pkgs.stdenv.hostPlatform.system}.default
```

## Protocol package

`@anoromi/local-ai-tools-protocol` exports Effect Schema definitions, inferred
TypeScript types, and JSON line helpers for both the daemon socket protocol and
the session NDJSON protocol.

Install:

```bash
npm install @anoromi/local-ai-tools-protocol effect@4.0.0-beta.45
```

Example:

```ts
import {
  decodeDaemonLine,
  decodeSessionLine,
  eventLine,
  requestLine,
} from "@anoromi/local-ai-tools-protocol"

const request = decodeSessionLine(
  '{"id":"1","method":"health","params":{}}'
)
const daemonRequest = requestLine("2", "health", {})
const line = eventLine({ event: "ready", version: "0.1.0" })
const response = decodeDaemonLine(
  '{"id":"2","ok":true,"result":{"status":"ok"}}'
)
```

The package intentionally does not include Unix socket clients, daemon
auto-start logic, filesystem path resolution, or Bun-specific APIs. It uses
Effect 4 schemas. Generated `dist/` output is produced during build/publish and
is not committed. The CLI package remains private.

## Setup

After installing through Home Manager or `nix run`, prepare the machine-local
runtime:

```bash
local-ai-tools setup
local-ai-tools health
printf "Hello" | local-ai-tools -o /tmp/hello.wav
```

`setup` creates:

```text
~/.local/share/local-ai-tools/
  .venv/
  env
  models/v1_0/kokoro-v1_0.pth
  models/v1_0/config.json
  voices/v1_0/af_sarah.pt
```

By default it installs PyTorch from the official ROCm 6.4 wheel index:

```bash
local-ai-tools setup --torch rocm6.4
```

Other setup modes:

```bash
local-ai-tools setup --torch rocm6.3
local-ai-tools setup --torch existing --python-path /path/to/venv/bin/python
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
local-ai-tools health
local-ai-tools health --json
local-ai-tools health --probe-synthesis
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
local-ai-tools         TypeScript/Bun CLI
local-ai-tools-python  Python helper used for serve/setup/health
```

`local-ai-tools-python` is not intended as the primary user interface, but it is
available for debugging.

## Runtime assets

If `local-ai-tools setup` has not been run, the MVP still falls back to local
benchmark assets on this development machine:

```text
LOCAL_AI_TOOLS_MODEL=/tmp/kokoro-bench/api-test/Kokoro-FastAPI/api/src/models/v1_0/kokoro-v1_0.pth
LOCAL_AI_TOOLS_CONFIG=/tmp/kokoro-bench/api-test/Kokoro-FastAPI/api/src/models/v1_0/config.json
LOCAL_AI_TOOLS_VOICES_DIR=/tmp/kokoro-bench/api-test/Kokoro-FastAPI/api/src/voices/v1_0
LOCAL_AI_TOOLS_DEFAULT_VOICE=af_sarah
LOCAL_AI_TOOLS_PYTHON=/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/bin/python
```

On another machine, prefer `local-ai-tools setup`. You can also provide equivalent
paths through those environment variables. `LOCAL_AI_TOOLS_PYTHON` should point at
a Python environment with Kokoro, SoundFile, NumPy, and ROCm-enabled PyTorch.

## ROCm caveat

Kokoro ROCm enables PyTorch's experimental ROCm AOTriton attention path by
default:

```bash
TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
```

This environment variable must be set before importing PyTorch. Override it to
`0` if a specific ROCm/PyTorch build regresses.

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

## Profiling

Write engine-side per-step performance timings with:

```bash
local-ai-tools say -o speech.wav --precision fp16 --profile
```

By default this writes `speech.profile.json` next to `speech.wav` and
`speech.json`. Use `--profile-output PATH` to choose a different path. The
profile measures synthesis work inside the daemon; it does not include CLI stdin
read time or daemon startup time.

## Current benchmark context

On the tested Strix Halo machine, direct PyTorch ROCm was about 2x faster than
the ONNX CPU path for the 500 WPM retimed benchmark.
