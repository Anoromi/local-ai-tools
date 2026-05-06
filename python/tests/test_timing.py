from pathlib import Path

from kokoro_rocm.timing import actual_wpm, scale_timings, sidecar_document, word_count


def test_word_count_handles_contractions():
    assert word_count("If you're here, here's a test.") == 6


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
        chunks=[],
        words=[],
        post_tempo={"used": False, "engine": None, "factor": None, "filter": None},
    )
    assert doc["audio"] == "/tmp/a.wav"
    assert doc["word_count"] == 2
    assert doc["actual_wpm"] == 120
