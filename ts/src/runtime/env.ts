export function rocmEnv(extra: NodeJS.ProcessEnv = {}): NodeJS.ProcessEnv {
  return {
    ...process.env,
    ...extra,
    HIP_VISIBLE_DEVICES: extra.HIP_VISIBLE_DEVICES ?? process.env.HIP_VISIBLE_DEVICES ?? "0",
    ROCR_VISIBLE_DEVICES: extra.ROCR_VISIBLE_DEVICES ?? process.env.ROCR_VISIBLE_DEVICES ?? "0",
    PYTORCH_ROCM_ARCH: extra.PYTORCH_ROCM_ARCH ?? process.env.PYTORCH_ROCM_ARCH ?? "gfx1151",
    HSA_OVERRIDE_GFX_VERSION: extra.HSA_OVERRIDE_GFX_VERSION ?? process.env.HSA_OVERRIDE_GFX_VERSION ?? "11.5.1",
    HF_HUB_DISABLE_TELEMETRY: extra.HF_HUB_DISABLE_TELEMETRY ?? process.env.HF_HUB_DISABLE_TELEMETRY ?? "1",
    TOKENIZERS_PARALLELISM: extra.TOKENIZERS_PARALLELISM ?? process.env.TOKENIZERS_PARALLELISM ?? "false"
  }
}

export function backendPython(): string {
  return process.env.KOKORO_ROCM_PYTHON || "/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/bin/python"
}

export function pythonPathEnv(existing?: string): string | undefined {
  const packaged = process.env.KOKORO_ROCM_PYTHONPATH || `${process.cwd()}/src`
  if (!packaged) {
    return existing
  }
  return existing ? `${packaged}:${existing}` : packaged
}
