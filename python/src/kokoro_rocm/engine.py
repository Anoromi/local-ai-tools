from __future__ import annotations

import json
import shutil
import tempfile
import time
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from kokoro import KModel, KPipeline

from . import audio as audio_utils
from . import env
from .timing import actual_wpm, profile_document, scale_timings, sidecar_document, synthesis_text, word_count

SAMPLE_RATE = 24000
WARMUP_TEXT = "Warmup sentence for local text to speech synthesis."


def sync() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def token_text(token) -> tuple[str, str]:
    return getattr(token, "text", "") or "", getattr(token, "whitespace", "") or ""


def inference_context(precision: str):
    if precision == "fp16":
        return torch.autocast(device_type="cuda", dtype=torch.float16)
    return nullcontext()


def elapsed_since(started: float) -> float:
    return time.perf_counter() - started


class KokoroEngine:
    def __init__(self) -> None:
        torch.backends.cudnn.enabled = False
        if not torch.cuda.is_available():
            raise RuntimeError("torch.cuda.is_available() is false; ROCm device is not available")

        self.model_path = env.model_path()
        self.config_path = env.config_path()
        self.voices_dir = env.voices_dir()
        for path in [self.model_path, self.config_path, self.voices_dir]:
            if not path.exists():
                raise RuntimeError(f"required Kokoro path is missing: {path}")

        started = time.perf_counter()
        self.model = KModel(config=str(self.config_path), model=str(self.model_path)).eval().cuda()
        sync()
        self.model_load_seconds = time.perf_counter() - started
        self.pipeline = KPipeline(lang_code="a", model=self.model, device="cuda")
        self.torch_info = {
            "version": torch.__version__,
            "hip": getattr(torch.version, "hip", None),
            "cuda_available": torch.cuda.is_available(),
            "device_count": torch.cuda.device_count(),
            "device": torch.cuda.get_device_name(0),
        }
        self._warmup()

    def _warmup(self) -> None:
        try:
            with tempfile.TemporaryDirectory(prefix="kokoro-rocm-warmup-") as tmp:
                self.synthesize(
                    text=WARMUP_TEXT,
                    output_path=Path(tmp) / "warmup.wav",
                    timings_path=Path(tmp) / "warmup.json",
                    voice=env.default_voice(),
                    speed=1.0,
                    target_wpm=None,
                )
        except Exception:
            raise RuntimeError("Kokoro warmup failed")

    def synthesize(
        self,
        *,
        text: str,
        output_path: Path,
        timings_path: Path,
        voice: str,
        speed: float,
        target_wpm: float | None,
        precision: str = "fp32",
        profile_path: Path | None = None,
        on_event: Callable[[dict], None] | None = None,
    ) -> dict:
        if precision not in ("fp32", "fp16"):
            raise RuntimeError(f"unsupported precision: {precision}")
        engine_started = time.perf_counter()
        timings: dict[str, float] = {}
        started = time.perf_counter()
        output_path = output_path.expanduser().resolve()
        timings_path = timings_path.expanduser().resolve()
        profile_path = profile_path.expanduser().resolve() if profile_path is not None else None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        timings_path.parent.mkdir(parents=True, exist_ok=True)
        if profile_path is not None:
            profile_path.parent.mkdir(parents=True, exist_ok=True)
        timings["prepare_paths"] = elapsed_since(started)
        started = time.perf_counter()
        voice_file = env.voice_path(voice)
        if not voice_file.exists():
            raise RuntimeError(f"voice not found: {voice}")
        timings["voice_lookup"] = elapsed_since(started)

        with tempfile.TemporaryDirectory(prefix="kokoro-rocm-") as tmp:
            tmpdir = Path(tmp)
            native_path = tmpdir / "native.wav"
            final_path = tmpdir / "final.wav"
            started = time.perf_counter()
            text_for_synthesis = synthesis_text(text)
            timings["synthesis_text_normalize"] = elapsed_since(started)
            generation = self._generate_native(
                text_for_synthesis, voice_file, speed, native_path, precision=precision, on_event=on_event
            )
            timings.update(generation["timings"])
            started = time.perf_counter()
            native_seconds = audio_utils.duration_seconds(native_path)
            timings["native_duration_probe"] = elapsed_since(started)
            native_wpm = actual_wpm(word_count(text), native_seconds)
            post = {"used": False, "engine": None, "factor": None, "filter": None, "seconds": 0.0}
            final_audio_seconds = native_seconds
            chunks = generation["chunks"]
            words = generation["words"]

            started = time.perf_counter()
            if target_wpm is not None and not (target_wpm * 0.97 <= native_wpm <= target_wpm * 1.03):
                post = audio_utils.retime_to_wpm(native_path, final_path, native_wpm, target_wpm)
                chunks, words = scale_timings(chunks, words, post["factor"])
                final_audio_seconds = audio_utils.duration_seconds(final_path)
            else:
                post_started = time.perf_counter()
                shutil.copyfile(native_path, final_path)
                timings["final_wav_copy"] = elapsed_since(post_started)
            timings["postprocess"] = elapsed_since(started)
            if post["used"]:
                timings["final_wav_copy"] = 0.0
            else:
                post["seconds"] = 0.0

            started = time.perf_counter()
            sidecar = sidecar_document(
                output_path=output_path,
                text=text,
                sample_rate=SAMPLE_RATE,
                audio_seconds=final_audio_seconds,
                voice=voice,
                speed=speed,
                target_wpm=target_wpm,
                precision=precision,
                chunks=chunks,
                words=words,
                post_tempo={k: post[k] for k in ["used", "engine", "factor", "filter"]},
            )
            timings["sidecar_build"] = elapsed_since(started)
            tmp_wav = output_path.with_suffix(output_path.suffix + ".tmp")
            tmp_json = timings_path.with_suffix(timings_path.suffix + ".tmp")
            started = time.perf_counter()
            shutil.copyfile(final_path, tmp_wav)
            tmp_wav.replace(output_path)
            timings["final_wav_copy"] += elapsed_since(started)
            started = time.perf_counter()
            tmp_json.write_text(json.dumps(sidecar, indent=2))
            tmp_json.replace(timings_path)
            timings["sidecar_write"] = elapsed_since(started)

        total_seconds = generation["generation_seconds"] + post["seconds"]
        timings["engine_total"] = elapsed_since(engine_started)
        actual_wpm_value = actual_wpm(word_count(text), final_audio_seconds)
        rtf = total_seconds / final_audio_seconds if final_audio_seconds else None
        profile = None
        if profile_path is not None:
            profile_chunks = generation["profile_chunks"]
            profile = profile_document(
                backend="rocm",
                precision=precision,
                voice=voice,
                speed=speed,
                target_wpm=target_wpm,
                text=text,
                synthesis_text_value=text_for_synthesis,
                sample_rate=SAMPLE_RATE,
                audio_seconds=final_audio_seconds,
                actual_wpm_value=actual_wpm_value,
                rtf=rtf,
                environment={
                    "torch": self.torch_info["version"],
                    "hip": self.torch_info["hip"],
                    "device": self.torch_info["device"],
                },
                timings=timings,
                chunks=profile_chunks,
            )
            started = time.perf_counter()
            tmp_profile = profile_path.with_suffix(profile_path.suffix + ".tmp")
            tmp_profile.write_text(json.dumps(profile, indent=2))
            tmp_profile.replace(profile_path)
            timings["profile_write"] = elapsed_since(started)
            timings["engine_total"] = elapsed_since(engine_started)
            profile = profile_document(
                backend="rocm",
                precision=precision,
                voice=voice,
                speed=speed,
                target_wpm=target_wpm,
                text=text,
                synthesis_text_value=text_for_synthesis,
                sample_rate=SAMPLE_RATE,
                audio_seconds=final_audio_seconds,
                actual_wpm_value=actual_wpm_value,
                rtf=rtf,
                environment={
                    "torch": self.torch_info["version"],
                    "hip": self.torch_info["hip"],
                    "device": self.torch_info["device"],
                },
                timings=timings,
                chunks=profile_chunks,
            )
            tmp_profile.write_text(json.dumps(profile, indent=2))
            tmp_profile.replace(profile_path)
        result = {
            "output_path": str(output_path),
            "timings_path": str(timings_path),
            "profile_path": str(profile_path) if profile_path is not None else None,
            "audio_seconds": final_audio_seconds,
            "word_count": word_count(text),
            "actual_wpm": actual_wpm_value,
            "model_load_seconds": self.model_load_seconds,
            "generation_seconds": generation["generation_seconds"],
            "postprocess_seconds": post["seconds"],
            "total_seconds": total_seconds,
            "rtf": rtf,
            "backend": "rocm",
            "voice": voice,
            "speed": speed,
            "target_wpm": target_wpm,
            "precision": precision,
            "profile": profile,
        }
        return result

    def _generate_native(
        self,
        text: str,
        voice_file: Path,
        speed: float,
        wav_path: Path,
        precision: str,
        on_event: Callable[[dict], None] | None = None,
    ) -> dict:
        audio_chunks = []
        words = []
        chunks = []
        profile_chunks = []
        offset = 0.0
        timings = {
            "model_pipeline": 0.0,
            "chunk_cpu_transfer": 0.0,
            "token_timing_extract": 0.0,
            "native_audio_concat": 0.0,
            "native_wav_write": 0.0,
        }
        sync()
        started = time.perf_counter()
        with torch.inference_mode(), inference_context(precision):
            for chunk_index, result in enumerate(self.pipeline(text, voice=str(voice_file), speed=speed, model=self.model)):
                sync()
                chunk_pipeline_seconds = elapsed_since(started)
                timings["model_pipeline"] += chunk_pipeline_seconds
                if result.audio is None:
                    started = time.perf_counter()
                    continue
                transfer_started = time.perf_counter()
                audio = result.audio.detach().cpu().numpy().astype(np.float32)
                sync()
                cpu_transfer_seconds = elapsed_since(transfer_started)
                timings["chunk_cpu_transfer"] += cpu_transfer_seconds
                audio_chunks.append(audio)
                chunk_duration = len(audio) / SAMPLE_RATE
                chunks.append(
                    {
                        "index": chunk_index,
                        "text": result.graphemes,
                        "phonemes": result.phonemes,
                        "start": offset,
                        "end": offset + chunk_duration,
                        "duration": chunk_duration,
                    }
                )
                if on_event is not None:
                    on_event(
                        {
                            "event": "chunk",
                            "chunk": {
                                "index": chunk_index,
                                "text": result.graphemes,
                                "start": offset,
                                "end": offset + chunk_duration,
                                "duration": chunk_duration,
                                "timing_basis": "native",
                            },
                        }
                    )
                token_started = time.perf_counter()
                for token_index, token in enumerate(result.tokens or []):
                    text_value, whitespace = token_text(token)
                    if not text_value.strip() or not hasattr(token, "start_ts") or not hasattr(token, "end_ts"):
                        continue
                    if token.start_ts is None or token.end_ts is None:
                        continue
                    start = float(token.start_ts) + offset
                    end = float(token.end_ts) + offset
                    words.append(
                        {
                            "index": len(words),
                            "chunk_index": chunk_index,
                            "token_index": token_index,
                            "text": text_value,
                            "whitespace": whitespace,
                            "start": start,
                            "end": end,
                            "duration": max(0.0, end - start),
                            "phonemes": getattr(token, "phonemes", ""),
                        }
                    )
                token_timing_extract_seconds = elapsed_since(token_started)
                timings["token_timing_extract"] += token_timing_extract_seconds
                profile_chunks.append(
                    {
                        "index": chunk_index,
                        "characters": len(result.graphemes or ""),
                        "audio_seconds": chunk_duration,
                        "model_pipeline_seconds": chunk_pipeline_seconds,
                        "cpu_transfer_seconds": cpu_transfer_seconds,
                        "token_timing_extract_seconds": token_timing_extract_seconds,
                    }
                )
                offset += chunk_duration
                started = time.perf_counter()
        sync()
        synthesis_seconds = time.perf_counter() - started
        if not audio_chunks:
            raise RuntimeError("Kokoro returned no audio chunks")
        started = time.perf_counter()
        audio = np.concatenate(audio_chunks)
        timings["native_audio_concat"] = elapsed_since(started)
        write_started = time.perf_counter()
        sf.write(str(wav_path), audio, SAMPLE_RATE)
        write_seconds = time.perf_counter() - write_started
        timings["native_wav_write"] = write_seconds
        model_seconds = timings["model_pipeline"] + timings["chunk_cpu_transfer"] + timings["token_timing_extract"]
        return {
            "chunks": chunks,
            "words": words,
            "profile_chunks": profile_chunks,
            "synthesis_seconds": model_seconds,
            "write_seconds": write_seconds,
            "generation_seconds": model_seconds + timings["native_audio_concat"] + write_seconds,
            "timings": timings,
        }
