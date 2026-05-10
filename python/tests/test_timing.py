from pathlib import Path

from kokoro_rocm.timing import PROFILE_TIMING_KEYS, actual_wpm, profile_document, scale_timings, sidecar_document, synthesis_text, word_count


def test_word_count_handles_contractions():
    assert word_count("If you're here, here's a test.") == 6


def test_synthesis_text_collapses_line_breaks():
    assert synthesis_text("A line,\nthen another.\n\nAnd one more.") == "A line, then another. And one more."


def test_actual_wpm():
    assert actual_wpm(100, 30) == 200


def test_scale_timings():
    chunks, words = scale_timings(
        [{"start": 2.0, "end": 6.0, "duration": 4.0}],
        [{"start": 1.0, "end": 3.0, "duration": 2.0}],
        2.0,
    )
    assert chunks[0]["start"] == 1.0
    assert chunks[0]["end"] == 3.0
    assert words[0]["start"] == 0.5
    assert words[0]["end"] == 1.5


def test_sidecar_document():
    doc = sidecar_document(
        output_path=Path("/tmp/a.wav"),
        text="hello world",
        sample_rate=24000,
        audio_seconds=1.0,
        voice="af_sarah",
        speed=1.0,
        target_wpm=None,
        precision="fp16",
        chunks=[],
        words=[],
        post_tempo={"used": False, "engine": None, "factor": None, "filter": None},
    )
    assert doc["audio"] == "/tmp/a.wav"
    assert doc["word_count"] == 2
    assert doc["actual_wpm"] == 120
    assert doc["precision"] == "fp16"


def test_profile_document_shape_includes_required_timings():
    doc = profile_document(
        backend="rocm",
        precision="fp16",
        voice="af_sarah",
        speed=1.0,
        target_wpm=None,
        text="hello world",
        synthesis_text_value="hello world",
        sample_rate=24000,
        audio_seconds=1.0,
        actual_wpm_value=120.0,
        rtf=0.5,
        environment={"torch": "x", "hip": "y", "device": "z"},
        timings={"engine_total": 0.5, "model_pipeline": 0.4},
        chunks=[{"index": 0, "characters": 11, "audio_seconds": 1.0}],
    )
    assert doc["version"] == 1
    assert doc["precision"] == "fp16"
    assert doc["audio"]["sample_rate"] == 24000
    assert doc["environment"]["device"] == "z"
    assert doc["text"]["words"] == 2
    for key in PROFILE_TIMING_KEYS:
        assert key in doc["timings_seconds"]
