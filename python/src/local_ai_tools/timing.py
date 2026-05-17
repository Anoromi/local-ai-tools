from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?")
WHITESPACE_RE = re.compile(r"\s+")


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def synthesis_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def actual_wpm(words: int, audio_seconds: float) -> float:
    return words / audio_seconds * 60.0 if audio_seconds else 0.0


def sidecar_document(
    *,
    output_path: Path,
    text: str,
    sample_rate: int,
    audio_seconds: float,
    voice: str,
    speed: float,
    target_wpm: float | None,
    precision: str,
    chunks: list[dict],
    words: list[dict],
    post_tempo: dict,
) -> dict:
    count = word_count(text)
    return {
        "engine": "kokoro-pytorch-direct",
        "backend": "rocm",
        "audio": str(output_path),
        "text": text,
        "sample_rate": sample_rate,
        "audio_seconds": audio_seconds,
        "word_count": count,
        "actual_wpm": actual_wpm(count, audio_seconds),
        "voice": voice,
        "speed": speed,
        "target_wpm": target_wpm,
        "precision": precision,
        "post_tempo": post_tempo,
        "timing_source": "kokoro_pred_dur",
        "chunks": chunks,
        "words": words,
        "notes": [
            "Timestamps come from Kokoro pred_dur joined onto pipeline tokens.",
            "These are model-predicted token timings, not external forced alignment.",
        ],
    }


PROFILE_TIMING_KEYS = [
    "engine_total",
    "prepare_paths",
    "voice_lookup",
    "synthesis_text_normalize",
    "model_pipeline",
    "chunk_cpu_transfer",
    "token_timing_extract",
    "native_audio_concat",
    "native_wav_write",
    "native_duration_probe",
    "postprocess",
    "final_wav_copy",
    "sidecar_build",
    "sidecar_write",
    "profile_write",
]


def profile_document(
    *,
    backend: str,
    precision: str,
    voice: str,
    speed: float,
    target_wpm: float | None,
    text: str,
    synthesis_text_value: str,
    sample_rate: int,
    audio_seconds: float,
    actual_wpm_value: float,
    rtf: float | None,
    environment: dict,
    timings: dict[str, float],
    chunks: list[dict],
) -> dict:
    normalized_timings = {key: float(timings.get(key, 0.0)) for key in PROFILE_TIMING_KEYS}
    return {
        "version": 1,
        "backend": backend,
        "precision": precision,
        "voice": voice,
        "speed": speed,
        "target_wpm": target_wpm,
        "text": {
            "characters": len(text),
            "words": word_count(text),
            "synthesis_characters": len(synthesis_text_value),
            "chunks": len(chunks),
        },
        "audio": {
            "sample_rate": sample_rate,
            "seconds": audio_seconds,
            "rtf": rtf,
            "actual_wpm": actual_wpm_value,
        },
        "environment": environment,
        "timings_seconds": normalized_timings,
        "chunks": chunks,
    }


def scale_timings(chunks: list[dict], words: list[dict], factor: float) -> tuple[list[dict], list[dict]]:
    scaled_chunks = deepcopy(chunks)
    scaled_words = deepcopy(words)
    for item in scaled_chunks + scaled_words:
        item["start"] = item["start"] / factor
        item["end"] = item["end"] / factor
        item["duration"] = max(0.0, item["end"] - item["start"])
    return scaled_chunks, scaled_words
