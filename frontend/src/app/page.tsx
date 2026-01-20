"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, Music, Sliders, Activity, Zap, ArrowRight, Disc3, Github } from "lucide-react";
import Waveform, { WaveformControls } from "@/components/Waveform";
import PianoRoll from "@/components/PianoRoll";
import SynthPlayer, { SynthPlayerControls } from "@/components/SynthPlayer";
import SoundWaveBackground from "@/components/SoundWaveBackground";
import AnalysisProgress from "@/components/AnalysisProgress";
import ErrorDisplay, { RetryIndicator } from "@/components/ErrorDisplay";
import { ApiErrorResponse, parseErrorResponse } from "@/utils/errors";
import { fetchWithRetry, RetryState } from "@/utils/fetchWithRetry";

// API base URL: use env var for local dev, empty string for production (same origin)
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface GenreInfo {
  tags: string[];
  confidence: number;
  explanation: string[];
  preset: {
    density: number;
    syncopation: number;
    register: number;
  };
}

interface AnalysisResult {
  bpm: number;
  scale: string;
  scale_score: number;
  histogram: number[];
  genre?: GenreInfo;
}

interface Note {
  pitch: number;
  start: number;
  duration: number;
  velocity: number;
}

interface ExampleFile {
  name: string;
  filename: string;
  description: string;
}

interface AnalysisProgressState {
  stage: string;
  progress: number;
  message: string;
}

export default function Home() {
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [uploadError, setUploadError] = useState<ApiErrorResponse | string | null>(null);
  const [retryState, setRetryState] = useState<RetryState | null>(null);
  const [retryCountdown, setRetryCountdown] = useState<number | null>(null);

  // Progress tracking for analysis
  const [analysisProgress, setAnalysisProgress] = useState<AnalysisProgressState>({
    stage: "validating",
    progress: 0,
    message: "Starting...",
  });

  // Example files
  const [examples, setExamples] = useState<ExampleFile[]>([]);
  const [selectedExample, setSelectedExample] = useState<string | null>(null);

  // Generation Parameters
  const [density, setDensity] = useState(7);
  const [syncopation, setSyncopation] = useState(0.5);
  const [register, setRegister] = useState("mid");
  const [generatedHooks, setGeneratedHooks] = useState<Note[][]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedHookIndex, setSelectedHookIndex] = useState(0);
  const [currentBeat, setCurrentBeat] = useState<number | undefined>(undefined);
  const seekRef = useRef<((beat: number) => void) | null>(null);

  // Refs for synchronized playback
  const waveformControlsRef = useRef<WaveformControls | null>(null);
  const synthControlsRef = useRef<SynthPlayerControls | null>(null);
  const [isPlayingTogether, setIsPlayingTogether] = useState(false);
  const [waveformReady, setWaveformReady] = useState(false);

  // Abort controller for cancelling requests
  const abortControllerRef = useRef<AbortController | null>(null);

  const ALLOWED_EXTENSIONS = [".wav", ".mp3", ".mp4", ".m4a"];
  const MAX_FILE_SIZE_MB = 20;
  const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

  // Cleanup object URLs and abort controllers to prevent memory leaks
  useEffect(() => {
    return () => {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
      abortControllerRef.current?.abort();
    };
  }, [audioUrl]);

  // Toggle synchronized playback of both audio and MIDI
  const togglePlayTogether = async () => {
    if (isPlayingTogether) {
      // Stop both
      waveformControlsRef.current?.stop();
      synthControlsRef.current?.stop();
      setIsPlayingTogether(false);
    } else {
      // Start both - reset positions first
      waveformControlsRef.current?.seekTo(0);
      if (seekRef.current) {
        seekRef.current(0);
      }

      // Start both playbacks
      await synthControlsRef.current?.play();
      waveformControlsRef.current?.play();
      setIsPlayingTogether(true);
    }
  };

  // Handle when either audio stops (e.g., sample finishes)
  const handleWaveformPlayStateChange = (playing: boolean) => {
    if (!playing && isPlayingTogether) {
      // If waveform stops while playing together, restart it (loop behavior)
      waveformControlsRef.current?.seekTo(0);
      waveformControlsRef.current?.play();
    }
  };

  const handleSynthPlayStateChange = (playing: boolean) => {
    if (!playing && isPlayingTogether) {
      setIsPlayingTogether(false);
    }
  };

  // Fetch example files on mount
  useEffect(() => {
    console.log("Fetching examples from:", `${API_BASE}/examples`);
    fetch(`${API_BASE}/examples`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        console.log("Loaded examples:", data);
        setExamples(data);
      })
      .catch((err) => console.error("Failed to load examples:", err));
  }, []);

  const handleExampleSelect = async (example: ExampleFile) => {
    setUploadError(null);
    setSelectedExample(example.filename);
    setIsAnalyzing(true);
    setGeneratedHooks([]);
    setRetryState(null);
    setRetryCountdown(null);

    // Initialize progress
    setAnalysisProgress({ stage: "loading", progress: 10, message: "Fetching example audio..." });
    setWaveformReady(false);
    setIsPlayingTogether(false);

    try {
      // Fetch the audio file for waveform display
      const audioRes = await fetch(`${API_BASE}/examples/${example.filename}`);
      if (!audioRes.ok) throw new Error("Failed to fetch example file");

      setAnalysisProgress({ stage: "loading", progress: 25, message: "Decoding audio..." });
      const audioBlob = await audioRes.blob();
      setAudioUrl(URL.createObjectURL(audioBlob));

      // Analyze the example file on the server (simulate stages during wait)
      setAnalysisProgress({ stage: "tempo", progress: 40, message: "Analyzing tempo..." });

      // Simulate intermediate progress during the request
      const progressInterval = setInterval(() => {
        setAnalysisProgress((prev) => {
          if (prev.progress < 85) {
            const stages = [
              { stage: "tempo", progress: 50, message: "Detecting beats..." },
              { stage: "groove", progress: 60, message: "Analyzing groove pattern..." },
              { stage: "groove", progress: 70, message: "Building rhythm histogram..." },
              { stage: "scale", progress: 80, message: "Detecting musical key..." },
              { stage: "genre", progress: 90, message: "Classifying rhythm style..." },
            ];
            const nextStage = stages.find((s) => s.progress > prev.progress);
            return nextStage || prev;
          }
          return prev;
        });
      }, 800);

      const analysisRes = await fetch(`${API_BASE}/examples/${example.filename}/analyze`, {
        method: "POST",
      });

      clearInterval(progressInterval);

      const data = await analysisRes.json();

      if (!analysisRes.ok) {
        const parsedError = parseErrorResponse(data);
        setUploadError(parsedError || data.detail || "Failed to analyze example file.");
        if (parsedError?.retry_after) {
          setRetryCountdown(parsedError.retry_after);
        }
        setAudioUrl(null);
        return;
      }

      setAnalysisProgress({ stage: "complete", progress: 100, message: "Analysis complete!" });

      // Small delay to show completion before switching to results
      await new Promise((resolve) => setTimeout(resolve, 300));

      setAnalysis(data);
    } catch (err) {
      console.error("Example analysis failed", err);
      setUploadError({
        error_code: "INTERNAL_ERROR",
        message: "Failed to load example. Please try again.",
        retryable: true,
      });
      setAudioUrl(null);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const uploadedFile = e.target.files[0];

      // Abort any in-progress request
      abortControllerRef.current?.abort();
      abortControllerRef.current = new AbortController();

      // Clear previous error and example selection
      setUploadError(null);
      setSelectedExample(null);
      setGeneratedHooks([]);
      setWaveformReady(false);
      setIsPlayingTogether(false);
      setRetryState(null);
      setRetryCountdown(null);

      // Validate file extension
      const fileName = uploadedFile.name.toLowerCase();
      const fileExt = fileName.substring(fileName.lastIndexOf("."));
      if (!ALLOWED_EXTENSIONS.includes(fileExt)) {
        setUploadError({
          error_code: "UNSUPPORTED_FORMAT",
          message: "Unsupported file type.",
          retryable: false,
        });
        return;
      }

      // Validate file size
      if (uploadedFile.size > MAX_FILE_SIZE_BYTES) {
        setUploadError({
          error_code: "FILE_TOO_LARGE",
          message: "File exceeds 20MB limit.",
          retryable: false,
        });
        return;
      }

      setAudioUrl(URL.createObjectURL(uploadedFile));

      // Auto analyze (non-streaming for better compatibility with Render)
      setIsAnalyzing(true);
      setAnalysisProgress({
        stage: "analyzing",
        progress: 50,
        message: "Analyzing audio... this may take a moment",
      });

      const formData = new FormData();
      formData.append("file", uploadedFile);

      try {
        const response = await fetchWithRetry(`${API_BASE}/analyze`, {
          method: "POST",
          body: formData,
          abortSignal: abortControllerRef.current.signal,
          onRetryStateChange: setRetryState,
          retryConfig: {
            maxRetries: 2, // Fewer retries for large uploads
            retryableStatuses: [429, 502, 503, 504],
          },
        });

        setRetryState(null);

        if (!response.ok) {
          const errorData = await response
            .json()
            .catch(() => ({ detail: "Failed to analyze audio file." }));
          const parsedError = parseErrorResponse(errorData);

          setUploadError(parsedError || errorData.detail || "Failed to analyze audio file.");
          setAudioUrl(null);

          // Set retry countdown for rate limiting
          if (parsedError?.retry_after) {
            setRetryCountdown(parsedError.retry_after);
          }

          setIsAnalyzing(false);
          return;
        }

        const data = await response.json();
        setAnalysis(data);
        setIsAnalyzing(false);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          // Request was cancelled, don't show error
          setIsAnalyzing(false);
          return;
        }

        console.error("Analysis failed", err);
        setUploadError({
          error_code: "INTERNAL_ERROR",
          message: "Failed to connect to the server. Please try again.",
          retryable: true,
        });
        setIsAnalyzing(false);
      }
    }
  };

  const handleGenerate = async () => {
    if (!analysis) return;

    // Abort any in-progress request
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();

    setIsGenerating(true);
    setUploadError(null);
    setRetryState(null);
    setRetryCountdown(null);

    try {
      const res = await fetchWithRetry(`${API_BASE}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bpm: analysis.bpm,
          scale: analysis.scale || "C minor",
          density,
          syncopation,
          pitch_register: register,
          histogram: analysis.histogram,
          seed: Math.floor(Math.random() * 10000),
        }),
        abortSignal: abortControllerRef.current.signal,
        onRetryStateChange: setRetryState,
      });

      setRetryState(null);

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: "Generation failed" }));
        const parsedError = parseErrorResponse(errorData);

        console.error("Generation error:", errorData);
        setUploadError(parsedError || errorData.detail || "Failed to generate hooks. Please try again.");

        if (parsedError?.retry_after) {
          setRetryCountdown(parsedError.retry_after);
        }
        return;
      }

      const data = await res.json();
      if (!data.hooks || !Array.isArray(data.hooks)) {
        console.error("Invalid response format:", data);
        setUploadError({
          error_code: "INTERNAL_ERROR",
          message: "Received invalid data from server. Please try again.",
          retryable: true,
        });
        return;
      }

      setGeneratedHooks(data.hooks);
      setSelectedHookIndex(0);
      setUploadError(null);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }

      console.error("Generation failed", err);
      setUploadError({
        error_code: "INTERNAL_ERROR",
        message: "Failed to connect to the server. Please try again.",
        retryable: true,
      });
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <main className="relative min-h-screen w-full overflow-hidden selection:bg-white/20 selection:text-white">
      <SoundWaveBackground />

      {/* GitHub Link */}
      <a
        href="https://github.com/cwklurks/hook-gen"
        target="_blank"
        rel="noopener noreferrer"
        className="group fixed top-6 right-6 z-50 rounded-full border border-white/10 bg-white/[0.02] p-3 text-neutral-500 backdrop-blur-sm transition-all duration-300 hover:border-white/30 hover:bg-white/[0.05] hover:text-white"
        aria-label="View source on GitHub"
      >
        <Github
          size={18}
          strokeWidth={1.5}
          className="transition-transform duration-300 group-hover:scale-110"
        />
      </a>

      <div className="relative z-10 mx-auto flex max-w-7xl flex-col gap-12 px-6 py-12">
        {/* Hero Section */}
        <motion.header
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="relative space-y-4 text-center"
        >
          {/* Ambient Background Glow */}
          <div className="pointer-events-none absolute top-1/2 left-1/2 -z-10 h-[400px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-indigo-500/10 blur-[120px]" />

          <h1 className="bg-gradient-to-b from-white to-white/60 bg-clip-text text-5xl font-light tracking-tighter text-transparent md:text-7xl">
            Hook
            <span className="bg-gradient-to-b from-white to-neutral-400 bg-clip-text font-bold text-transparent">
              Gen
            </span>
          </h1>

          <p className="mx-auto max-w-lg text-base leading-relaxed font-light tracking-wide text-neutral-400 md:text-lg">
            <strong className="text-neutral-200">Generate melodies that lock to your beat.</strong>
            <br />
            Upload a loop to begin.
          </p>
        </motion.header>

        {/* Main Workflow */}
        <div className="space-y-8">
          {/* Upload & Analysis */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.8 }}
            className="grid grid-cols-1 items-stretch gap-6 md:grid-cols-2"
          >
            {/* Upload Area */}
            <div className="flex h-full flex-col gap-6 rounded-lg border border-white/10 bg-white/[0.02] p-6">
              <div
                className={`group relative min-h-[200px] flex-1 cursor-pointer overflow-hidden rounded-md border-2 border-dashed transition-all focus-within:ring-2 focus-within:ring-white/30 ${uploadError ? "border-red-500/50 bg-red-500/[0.02]" : "border-white/10 hover:border-white/20 hover:bg-white/[0.02]"}`}
              >
                <input
                  type="file"
                  onChange={handleFileUpload}
                  accept=".wav,.mp3,.mp4,.m4a,audio/wav,audio/mpeg,audio/mp4"
                  className="absolute inset-0 z-20 h-full w-full cursor-pointer opacity-0"
                  aria-label="Upload audio file"
                />
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-4">
                  <div
                    className={`rounded-full bg-white/5 p-4 transition-transform duration-500 group-hover:scale-110 ${uploadError ? "text-red-400" : "text-neutral-400"}`}
                  >
                    <Upload size={24} strokeWidth={1.5} />
                  </div>
                  <div className="text-center">
                    <p className="font-medium text-neutral-200">Drop Audio File</p>
                    <p className="mt-1 text-sm text-neutral-500">WAV, MP3, or MP4 • Max 20MB</p>
                  </div>
                  {/* Error display */}
                  {uploadError && (
                    <div className="mt-2 w-full max-w-md px-2">
                      <ErrorDisplay
                        error={uploadError}
                        onDismiss={() => {
                          setUploadError(null);
                          setRetryCountdown(null);
                        }}
                        onRetry={
                          typeof uploadError !== "string" && uploadError.retryable
                            ? () => {
                                const input = document.querySelector(
                                  'input[type="file"]'
                                ) as HTMLInputElement;
                                if (input?.files?.[0]) {
                                  handleFileUpload({
                                    target: input,
                                  } as React.ChangeEvent<HTMLInputElement>);
                                }
                              }
                            : undefined
                        }
                        retryCountdown={retryCountdown}
                      />
                    </div>
                  )}
                  {/* Retry indicator during retries */}
                  {retryState?.isRetrying && (
                    <div className="mt-2 px-2">
                      <RetryIndicator
                        attempt={retryState.attempt}
                        maxAttempts={3}
                        retryAfterMs={retryState.retryAfterMs}
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Example Files */}
              <div className="space-y-3">
                <div className="flex items-center gap-3 text-xs tracking-widest text-neutral-500 uppercase">
                  <div className="h-px flex-1 bg-white/10"></div>
                  <span className="flex items-center gap-2">
                    <Disc3 size={12} />
                    <span>Try an example</span>
                  </span>
                  <div className="h-px flex-1 bg-white/10"></div>
                </div>

                {examples.length > 0 ? (
                  <div className="custom-scrollbar grid max-h-[140px] grid-cols-2 gap-2 overflow-y-auto pr-1">
                    {examples.map((example) => (
                      <button
                        key={example.filename}
                        onClick={() => handleExampleSelect(example)}
                        disabled={isAnalyzing}
                        aria-pressed={selectedExample === example.filename}
                        aria-label={`Load example: ${example.name}`}
                        className={`group relative overflow-hidden rounded-md border p-2 text-left transition-all focus:outline-none focus:ring-2 focus:ring-white/30 disabled:cursor-not-allowed disabled:opacity-50 ${
                          selectedExample === example.filename
                            ? "border-white/30 bg-white/10 text-white"
                            : "border-white/5 bg-white/[0.02] text-neutral-400 hover:border-white/10 hover:bg-white/[0.05] hover:text-neutral-200"
                        }`}
                      >
                        <div className="mb-0.5 flex items-start justify-between">
                          <div className="truncate text-xs font-medium">{example.name}</div>
                          {selectedExample === example.filename && (
                            <Activity size={10} className="animate-pulse text-emerald-400" />
                          )}
                        </div>
                        <div className="line-clamp-1 text-[10px] leading-tight text-neutral-600 transition-colors group-hover:text-neutral-500">
                          {example.description}
                        </div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="flex items-center justify-center rounded-sm border border-dashed border-white/10 p-4 text-xs text-neutral-600 italic">
                    <div className="animate-pulse">Loading examples...</div>
                  </div>
                )}
              </div>
            </div>

            {/* Analysis Display */}
            <div className="relative flex h-full min-h-[300px] flex-col justify-center overflow-hidden rounded-lg border border-white/10 bg-white/[0.02] p-8">
              {isAnalyzing ? (
                <AnalysisProgress
                  progress={analysisProgress.progress}
                  stage={analysisProgress.stage}
                  message={analysisProgress.message}
                />
              ) : analysis ? (
                <div className="relative z-10 space-y-8">
                  <div className="flex items-end justify-between border-b border-white/5 pb-4">
                    <span className="text-sm tracking-widest text-neutral-500 uppercase">
                      Tempo
                    </span>
                    <span className="text-4xl font-light text-white">
                      {Math.round(analysis.bpm)}{" "}
                      <span className="text-sm text-neutral-600">BPM</span>
                    </span>
                  </div>
                  <div className="flex items-end justify-between">
                    <span className="text-sm tracking-widest text-neutral-500 uppercase">Key</span>
                    <div className="text-right">
                      <span className="block text-4xl font-light text-white">
                        {analysis.scale || "Unknown"}
                      </span>
                      <span className="text-xs text-emerald-500/80">
                        {(analysis.scale_score * 100).toFixed(0)}% Confidence
                      </span>
                    </div>
                  </div>

                  {/* Genre Display */}
                  {analysis.genre && (
                    <div className="space-y-3 border-t border-white/5 pt-4">
                      <span className="text-sm tracking-widest text-neutral-500 uppercase">
                        Style
                      </span>

                      {/* Tags */}
                      <div className="flex flex-wrap gap-2">
                        {analysis.genre.tags.map((tag) => (
                          <span
                            key={tag}
                            className="rounded-sm border border-white/20 bg-white/5 px-3 py-1 text-xs font-medium tracking-wide text-white"
                          >
                            {tag.replace(/_/g, " ").toUpperCase()}
                          </span>
                        ))}
                      </div>

                      {/* Confidence bar */}
                      <div className="flex items-center gap-3">
                        <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/10">
                          <div
                            className={`h-full transition-all ${
                              analysis.genre.confidence > 0.6
                                ? "bg-emerald-500"
                                : analysis.genre.confidence > 0.4
                                  ? "bg-yellow-500"
                                  : "bg-red-500"
                            }`}
                            style={{
                              width: `${analysis.genre.confidence * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs text-neutral-500">
                          {(analysis.genre.confidence * 100).toFixed(0)}%
                        </span>
                      </div>

                      {/* Collapsible explanation */}
                      <details className="group cursor-pointer">
                        <summary className="text-xs text-neutral-500 hover:text-neutral-400">
                          View Details
                        </summary>
                        <ul className="mt-2 space-y-1 pl-4 text-xs text-neutral-400">
                          {analysis.genre.explanation.map((bullet, i) => (
                            <li key={i} className="list-disc">
                              {bullet}
                            </li>
                          ))}
                        </ul>
                      </details>

                      {/* Apply Preset button */}
                      <button
                        onClick={() => {
                          const preset = analysis.genre!.preset;
                          // Convert normalized 0-1 to slider ranges
                          setDensity(Math.round(4 + (16 - 4) * preset.density));
                          setSyncopation(preset.syncopation);
                          // Map register: <0.34=low, 0.34-0.67=mid, >0.67=high
                          if (preset.register < 0.34) setRegister("low");
                          else if (preset.register < 0.67) setRegister("mid");
                          else setRegister("high");
                        }}
                        className="w-full border border-white/20 bg-white/5 px-4 py-2 text-xs font-medium tracking-wide text-white transition-all hover:bg-white/10"
                      >
                        Apply Preset →
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-4 text-neutral-600">
                  <Music size={32} strokeWidth={1} />
                  <span className="text-sm font-light">Waiting for input...</span>
                </div>
              )}
            </div>
          </motion.section>

          {/* Waveform */}
          <AnimatePresence>
            {audioUrl && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="rounded-sm border border-white/10 bg-white/[0.02] p-8">
                  <Waveform
                    audioUrl={audioUrl}
                    controlsRef={waveformControlsRef}
                    onReady={() => setWaveformReady(true)}
                    onPlayStateChange={handleWaveformPlayStateChange}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Controls */}
          <AnimatePresence>
            {analysis && (
              <motion.section
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="space-y-6 border-t border-white/10 pt-8"
              >
                <div className="mb-6 flex items-center gap-3">
                  <Sliders size={20} className="text-neutral-500" />
                  <h2 className="text-xl font-light tracking-wide text-white">
                    Generator Settings
                  </h2>
                </div>

                <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
                  <div className="space-y-4">
                    <div className="flex justify-between text-sm">
                      <label className="text-neutral-400">Density</label>
                      <span className="font-mono text-white">{density}</span>
                    </div>
                    <input
                      type="range"
                      min="4"
                      max="16"
                      value={density}
                      onChange={(e) => setDensity(Number(e.target.value))}
                      className="h-1 w-full cursor-pointer appearance-none rounded-none bg-neutral-800 accent-white hover:accent-neutral-300"
                    />
                  </div>

                  <div className="space-y-4">
                    <div className="flex justify-between text-sm">
                      <label className="text-neutral-400">Syncopation</label>
                      <span className="font-mono text-white">
                        {(syncopation * 100).toFixed(0)}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={syncopation}
                      onChange={(e) => setSyncopation(Number(e.target.value))}
                      className="h-1 w-full cursor-pointer appearance-none rounded-none bg-neutral-800 accent-white hover:accent-neutral-300"
                    />
                  </div>

                  <div className="space-y-4">
                    <label className="block text-sm text-neutral-400">Register</label>
                    <div className="flex gap-2">
                      {["low", "mid", "high"].map((r) => (
                        <button
                          key={r}
                          onClick={() => setRegister(r)}
                          className={`flex-1 border py-2 text-xs tracking-widest uppercase transition-all ${
                            register === r
                              ? "border-white bg-white text-black"
                              : "border-neutral-800 bg-transparent text-neutral-500 hover:border-neutral-600"
                          }`}
                        >
                          {r}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex justify-end pt-4">
                  <button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="group relative flex items-center gap-3 bg-white px-8 py-4 text-sm font-medium tracking-widest text-black uppercase transition-colors hover:bg-neutral-200 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isGenerating ? (
                      <>
                        Processing <Activity size={16} className="animate-spin" />
                      </>
                    ) : (
                      <>
                        Generate Hooks{" "}
                        <ArrowRight
                          size={16}
                          className="transition-transform group-hover:translate-x-1"
                        />
                      </>
                    )}
                  </button>
                </div>
              </motion.section>
            )}
          </AnimatePresence>

          {/* Results */}
          <AnimatePresence>
            {generatedHooks.length > 0 && (
              <motion.section
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="border-t border-white/10 pt-8 pb-12"
              >
                <div className="mb-8 flex items-center gap-4">
                  <Zap size={20} className="text-neutral-500" />
                  <h2 className="text-xl font-light tracking-wide text-white">Output</h2>
                </div>

                <div className="grid h-[500px] grid-cols-1 gap-6 lg:grid-cols-12">
                  {/* List */}
                  <div className="custom-scrollbar flex flex-col gap-2 overflow-y-auto pr-2 lg:col-span-3">
                    {generatedHooks.map((_, i) => (
                      <button
                        key={i}
                        onClick={() => {
                          setSelectedHookIndex(i);
                          setCurrentBeat(undefined); // Clear playhead when switching hooks
                          // Stop synchronized playback when switching hooks
                          if (isPlayingTogether) {
                            waveformControlsRef.current?.stop();
                            synthControlsRef.current?.stop();
                            setIsPlayingTogether(false);
                          }
                        }}
                        className={`w-full border-l-2 px-5 py-4 text-left text-sm transition-all ${
                          selectedHookIndex === i
                            ? "border-white bg-white/5 text-white"
                            : "border-transparent text-neutral-500 hover:bg-white/[0.02] hover:text-neutral-300"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span>Variation {i + 1}</span>
                          {selectedHookIndex === i && (
                            <div className="h-1.5 w-1.5 rounded-full bg-white" />
                          )}
                        </div>
                      </button>
                    ))}
                  </div>

                  {/* Visualization */}
                  <div className="flex flex-col gap-6 lg:col-span-9">
                    {generatedHooks[selectedHookIndex] && (
                      <>
                        <div className="relative flex flex-1 items-center justify-center overflow-hidden rounded-sm border border-white/5 bg-neutral-900/20 p-4">
                          <PianoRoll
                            notes={generatedHooks[selectedHookIndex]}
                            height={400}
                            currentBeat={currentBeat}
                            onSeek={(beat) => {
                              if (seekRef.current) {
                                seekRef.current(beat);
                              }
                            }}
                          />
                        </div>

                        <div className="rounded-sm border border-white/5 bg-neutral-900/20 p-4">
                          <SynthPlayer
                            notes={generatedHooks[selectedHookIndex]}
                            bpm={analysis?.bpm || 120}
                            onPlayheadUpdate={setCurrentBeat}
                            onSeekRef={seekRef}
                            controlsRef={synthControlsRef}
                            onPlayStateChange={handleSynthPlayStateChange}
                            playTogetherEnabled={!!(audioUrl && waveformReady)}
                            isPlayingTogether={isPlayingTogether}
                            onTogglePlayTogether={togglePlayTogether}
                          />
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </motion.section>
            )}
          </AnimatePresence>
        </div>
      </div>
    </main>
  );
}
