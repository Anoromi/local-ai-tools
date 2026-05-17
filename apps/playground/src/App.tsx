import { Activity, Clock3, Cpu, FileAudio, Pause, Play, RotateCcw, Square, Waves } from "lucide-react";
import { useMemo, useRef, useState } from "react";

type Chunk = {
  index: number;
  text: string;
  phonemes?: string;
  start: number;
  end: number;
  duration: number;
};

type TimedToken = {
  index: number;
  chunk_index: number;
  token_index: number;
  text: string;
  whitespace: string;
  start: number;
  end: number;
  duration: number;
  phonemes?: string;
};

type KokoroTimings = {
  text: string;
  audio_seconds: number;
  voice: string;
  speed: number;
  precision: string;
  timing_source: string;
  chunks: Chunk[];
  words: TimedToken[];
};

const sampleText =
  "Kokoro splits synthesis into model pipeline chunks. This playground generates real Kokoro ROCm audio and highlights the current Kokoro chunk while the WAV plays.";

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60)
    .toString()
    .padStart(2, "0");

  return `${minutes}:${remainder}`;
}

export function App() {
  const [draft, setDraft] = useState(sampleText);
  const [generatedText, setGeneratedText] = useState("");
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [activeChunk, setActiveChunk] = useState<number | null>(null);
  const [activeToken, setActiveToken] = useState<number | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [audioUrl, setAudioUrl] = useState("");
  const [timings, setTimings] = useState<KokoroTimings | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const totalSeconds = useMemo(
    () => timings?.audio_seconds ?? chunks.reduce((total, chunk) => total + chunk.duration, 0),
    [chunks, timings],
  );
  const tokenCount = timings?.words.length ?? 0;
  const progress = totalSeconds > 0 ? Math.min(100, (currentTime / totalSeconds) * 100) : 0;

  async function generate() {
    const text = draft.trim();
    if (!text) {
      setError("Enter text before generating Kokoro audio.");
      return;
    }

    setIsGenerating(true);
    setError("");
    setIsPlaying(false);
    setActiveChunk(null);
    setActiveToken(null);
    setCurrentTime(0);

    try {
      const response = await fetch("/api/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error ?? "Kokoro synthesis failed.");
      }

      const nextTimings = result.timings as KokoroTimings;
      setGeneratedText(nextTimings.text ?? text);
      setChunks(nextTimings.chunks ?? []);
      setTimings(nextTimings);
      setAudioUrl(`${result.audioUrl}?t=${Date.now()}`);
    } catch (error) {
      setError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsGenerating(false);
    }
  }

  function play() {
    if (!audioUrl) {
      generate();
      return;
    }

    void audioRef.current?.play();
  }

  function pause() {
    audioRef.current?.pause();
    setIsPlaying(false);
  }

  function stop() {
    if (!audioRef.current) return;
    audioRef.current.pause();
    audioRef.current.currentTime = 0;
    setIsPlaying(false);
    setActiveChunk(null);
    setActiveToken(null);
    setCurrentTime(0);
  }

  function updateActiveChunk(currentTime: number) {
    setCurrentTime(currentTime);
    const current = chunks.find((chunk) => currentTime >= chunk.start && currentTime < chunk.end);
    const currentToken = timings?.words.find((word) => currentTime >= word.start && currentTime < word.end);
    setActiveChunk(current?.index ?? null);
    setActiveToken(currentToken?.index ?? null);
  }

  function seekToChunk(chunk: Chunk) {
    if (!audioRef.current) return;
    audioRef.current.currentTime = chunk.start;
    updateActiveChunk(chunk.start);
    void audioRef.current.play();
  }

  return (
    <main className="app-shell">
      <section className="workspace" aria-labelledby="page-title">
        <div className="topbar">
          <div>
            <h1 id="page-title">Chunk playback alignment</h1>
            <p>Kokoro ROCm synthesis with sidecar timings, token playback, and chunk inspection in one pass.</p>
          </div>
          <div className="summary" aria-label="Chunk summary">
            <span>
              <FileAudio size={15} aria-hidden="true" />
              {chunks.length} chunks
            </span>
            <span>
              <Activity size={15} aria-hidden="true" />
              {tokenCount} tokens
            </span>
            <span>
              <Clock3 size={15} aria-hidden="true" />
              {formatTime(totalSeconds)}
            </span>
          </div>
        </div>

        <div className="playground-stack">
          <form
            className="input-panel"
            onSubmit={(event) => {
              event.preventDefault();
              generate();
            }}
          >
            <div className="panel-heading">
              <label htmlFor="text-input">Input text</label>
              <span>{draft.trim().length} chars</span>
            </div>
            <textarea
              id="text-input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              spellCheck="true"
            />
            <div className="actions">
              <button type="submit" disabled={isGenerating}>
                {isGenerating ? "Generating..." : "Generate"}
              </button>
              <button type="button" className="secondary" onClick={() => setDraft(sampleText)}>
                <RotateCcw size={16} aria-hidden="true" />
                Reset
              </button>
            </div>
          </form>

          <section className="output-panel" aria-label="Generated output">
            <div className="playback-bar">
              <div>
                <strong>Kokoro playback</strong>
                <span>
                  {generatedText
                    ? `${timings?.voice ?? "voice"} · ${timings?.timing_source ?? "kokoro timings"}`
                    : "No output yet"}
                </span>
              </div>
              <div className="player-buttons">
                {isPlaying ? (
                  <button type="button" className="icon-button" onClick={pause} aria-label="Pause playback" title="Pause">
                    <Pause size={18} aria-hidden="true" />
                  </button>
                ) : (
                  <button type="button" className="icon-button" onClick={play} aria-label="Play generated audio" title="Play">
                    <Play size={18} aria-hidden="true" />
                  </button>
                )}
                <button type="button" className="icon-button secondary" onClick={stop} aria-label="Stop playback" title="Stop">
                  <Square size={16} aria-hidden="true" />
                </button>
              </div>
            </div>

            {error ? <p className="error">{error}</p> : null}

            {audioUrl ? (
              <audio
                ref={audioRef}
                src={audioUrl}
                preload="metadata"
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                onEnded={() => {
                  setIsPlaying(false);
                  setActiveChunk(null);
                  setActiveToken(null);
                }}
                onTimeUpdate={(event) => updateActiveChunk(event.currentTarget.currentTime)}
              />
            ) : null}

            <div className="playhead">
              <span>{formatTime(currentTime)}</span>
              <div className="playhead-track" aria-hidden="true">
                <div style={{ width: `${progress}%` }} />
              </div>
              <span>{formatTime(totalSeconds)}</span>
            </div>

            <div className="generated-text">
              {timings?.words.length ? (
                timings.words.map((word) => (
                  <span
                    key={word.index}
                    className={word.index === activeToken ? "active text-token" : "text-token"}
                    title={`chunk ${word.chunk_index + 1}, ${formatTime(word.start)} - ${formatTime(word.end)}`}
                  >
                    {word.text}
                    {word.whitespace}
                  </span>
                ))
              ) : generatedText ? (
                chunks.map((chunk) => (
                  <span key={chunk.index} className="text-token">
                    {chunk.text}{" "}
                  </span>
                ))
              ) : (
                <span className="placeholder">Generated text appears here.</span>
              )}
            </div>

            <div className="inspector-grid">
              <section className="timeline-section" aria-label="Token timeline">
                <div className="chunk-section-header">
                  <strong>Token timing</strong>
                  <span>
                    <Waves size={14} aria-hidden="true" />
                    {tokenCount} tokens
                  </span>
                </div>
                <div className="timing-strip">
                  {timings?.words.length ? (
                    timings.words.map((word) => (
                      <button
                        key={word.index}
                        type="button"
                        className={word.index === activeToken ? "active token-tick" : "token-tick"}
                        style={{
                          width: `${Math.max(1.2, (word.duration / totalSeconds) * 100)}%`,
                        }}
                        title={`${word.text}: ${formatTime(word.start)} - ${formatTime(word.end)}`}
                        onClick={() => {
                          if (!audioRef.current) return;
                          audioRef.current.currentTime = word.start;
                          updateActiveChunk(word.start);
                          void audioRef.current.play();
                        }}
                      />
                    ))
                  ) : (
                    <div className="empty-timeline">
                      <Waves size={18} aria-hidden="true" />
                      Generate audio to inspect timing.
                    </div>
                  )}
                </div>
              </section>

              <section className="chunk-section" aria-label="Kokoro chunks">
                <div className="chunk-section-header">
                  <strong>Pipeline chunks</strong>
                  <span>
                    <Cpu size={14} aria-hidden="true" />
                    {timings?.precision ?? "fp32"}
                  </span>
                </div>
                <ol className="chunk-list">
                  {chunks.map((chunk) => (
                    <li key={chunk.index} className={chunk.index === activeChunk ? "active" : ""}>
                      <button type="button" onClick={() => seekToChunk(chunk)}>
                        <span className="chunk-index">{chunk.index + 1}</span>
                        <span className="chunk-copy">{chunk.text}</span>
                        <span className="chunk-time">
                          {formatTime(chunk.start)} - {formatTime(chunk.end)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ol>
              </section>
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
