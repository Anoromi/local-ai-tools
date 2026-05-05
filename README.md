# kokoro-rocm

`kokoro-rocm` is a local Kokoro PyTorch ROCm CLI backed by a Unix-socket daemon.
The CLI reads text from stdin, auto-starts the daemon if needed, and writes a
WAV plus a timing JSON sidecar.

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

## Nix

Development:

```bash
nix develop
uv sync --dev
printf "Hello" | uv run kokoro-rocm -o /tmp/hello.wav
```

NixOS flake integration:

```nix
inputs.kokoro-rocm.url = "github:Anoromi/kokoro-rocm";
```

Home Manager package:

```nix
inputs.kokoro-rocm.packages.${pkgs.stdenv.hostPlatform.system}.default
```

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
