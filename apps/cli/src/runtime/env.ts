export function rocmEnv(extra: NodeJS.ProcessEnv = {}, base: NodeJS.ProcessEnv = process.env): NodeJS.ProcessEnv {
  return {
    ...base,
    ...extra,
    HIP_VISIBLE_DEVICES: extra.HIP_VISIBLE_DEVICES ?? base.HIP_VISIBLE_DEVICES ?? "0",
    ROCR_VISIBLE_DEVICES: extra.ROCR_VISIBLE_DEVICES ?? base.ROCR_VISIBLE_DEVICES ?? "0",
    PYTORCH_ROCM_ARCH: extra.PYTORCH_ROCM_ARCH ?? base.PYTORCH_ROCM_ARCH ?? "gfx1151",
    HSA_OVERRIDE_GFX_VERSION: extra.HSA_OVERRIDE_GFX_VERSION ?? base.HSA_OVERRIDE_GFX_VERSION ?? "11.5.1",
    TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL:
      extra.TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL ?? base.TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL ?? "1",
    TORCH_COMPILE_DISABLE: extra.TORCH_COMPILE_DISABLE ?? base.TORCH_COMPILE_DISABLE ?? "1",
    TORCHDYNAMO_DISABLE: extra.TORCHDYNAMO_DISABLE ?? base.TORCHDYNAMO_DISABLE ?? "1",
    PROJECT_TRANSFORMERS_PATH:
      extra.PROJECT_TRANSFORMERS_PATH ??
      base.PROJECT_TRANSFORMERS_PATH ??
      "/home/anoromi/code/my/testing-site/text-selection-tunings/.venv/lib/python3.12/site-packages",
    HF_HUB_DISABLE_TELEMETRY: extra.HF_HUB_DISABLE_TELEMETRY ?? base.HF_HUB_DISABLE_TELEMETRY ?? "1",
    TOKENIZERS_PARALLELISM: extra.TOKENIZERS_PARALLELISM ?? base.TOKENIZERS_PARALLELISM ?? "false"
  }
}

export function backendPython(): string {
  return process.env.LOCAL_AI_TOOLS_PYTHON || "/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/bin/python"
}

export function pythonPathEnv(existing?: string): string | undefined {
  const packaged = process.env.LOCAL_AI_TOOLS_PYTHONPATH || `${process.cwd()}/src`
  if (!packaged) {
    return existing
  }
  return existing ? `${packaged}:${existing}` : packaged
}
