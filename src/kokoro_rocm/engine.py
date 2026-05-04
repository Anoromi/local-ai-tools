from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from kokoro import KModel, KPipeline

from . import audio as audio_utils
from . import env
from .timing import actual_wpm, scale_timings, sidecar_document, word_count

SAMPLE_RATE = 24000
WARMUP_TEXT = "Warmup sentence for local text to speech synthesis."


def sync() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def token_text(token) -> tuple[str, str]:
    return getattr(token, "text", "") or "", getattr(token, "whitespace", "") or ""


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
    ) -> dict:
        output_path = output_path.expanduser().resolve()
        timings_path = timings_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        timings_path.parent.mkdir(parents=True, exist_ok=True)
        voice_file = env.voice_path(voice)
        if not voice_file.exists():
            raise RuntimeError(f"voice not found: {voice}")

        with tempfile.TemporaryDirectory(prefix="kokoro-rocm-") as tmp:
            tmpdir = Path(tmp)
            native_path = tmpdir / "native.wav"
            final_path = tmpdir / "final.wav"
            generation = self._generate_native(text, voice_file, speed, native_path)
            native_seconds = audio_utils.duration_seconds(native_path)
            native_wpm = actual_wpm(word_count(text), native_seconds)
            post = {"used": False, "engine": None, "factor": None, "filter": None, "seconds": 0.0}
            final_audio_seconds = native_seconds
            chunks = generation["chunks"]
            words = generation["words"]

            if target_wpm is not None and not (target_wpm * 0.97 <= native_wpm <= target_wpm * 1.03):
                post = audio_utils.retime_to_wpm(native_path, final_path, native_wpm, target_wpm)
                chunks, words = scale_timings(chunks, words, post["factor"])
                final_audio_seconds = audio_utils.duration_seconds(final_path)
            else:
                shutil.copyfile(native_path, final_path)

            sidecar = sidecar_document(
                output_path=output_path,
                text=text,
                sample_rate=SAMPLE_RATE,
                audio_seconds=final_audio_seconds,
                voice=voice,
                speed=speed,
                target_wpm=target_wpm,
                chunks=chunks,
                words=words,
                post_tempo={k: post[k] for k in ["used", "engine", "factor", "filter"]},
            )
            tmp_wav = output_path.with_suffix(output_path.suffix + ".tmp")
            tmp_json = timings_path.with_suffix(timings_path.suffix + ".tmp")
            shutil.copyfile(final_path, tmp_wav)
            tmp_json.write_text(json.dumps(sidecar, indent=2))
            tmp_wav.replace(output_path)
            tmp_json.replace(timings_path)

        total_seconds = generation["generation_seconds"] + post["seconds"]
        return {
            "output_path": str(output_path),
            "timings_path": str(timings_path),
            "audio_seconds": final_audio_seconds,
            "word_count": word_count(text),
            "actual_wpm": actual_wpm(word_count(text), final_audio_seconds),
            "model_load_seconds": self.model_load_seconds,
            "generation_seconds": generation["generation_seconds"],
            "postprocess_seconds": post["seconds"],
            "total_seconds": total_seconds,
            "rtf": total_seconds / final_audio_seconds if final_audio_seconds else None,
            "backend": "rocm",
            "voice": voice,
            "speed": speed,
            "target_wpm": target_wpm,
        }

    def _generate_native(self, text: str, voice_file: Path, speed: float, wav_path: Path) -> dict:
        audio_chunks = []
        words = []
        chunks = []
        offset = 0.0
        sync()
        started = time.perf_counter()
        with torch.inference_mode():
            for chunk_index, result in enumerate(self.pipeline(text, voice=str(voice_file), speed=speed, model=self.model)):
                if result.audio is None:
                    continue
                audio = result.audio.detach().cpu().numpy().astype(np.float32)
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
                offset += chunk_duration
        sync()
        synthesis_seconds = time.perf_counter() - started
        if not audio_chunks:
            raise RuntimeError("Kokoro returned no audio chunks")
        audio = np.concatenate(audio_chunks)
        write_started = time.perf_counter()
        sf.write(str(wav_path), audio, SAMPLE_RATE)
        write_seconds = time.perf_counter() - write_started
        return {
            "chunks": chunks,
            "words": words,
            "synthesis_seconds": synthesis_seconds,
            "write_seconds": write_seconds,
            "generation_seconds": synthesis_seconds + write_seconds,
        }
