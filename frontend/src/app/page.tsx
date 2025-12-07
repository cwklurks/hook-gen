"use client";

import { useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, Music, Sliders, Activity, Zap, ArrowRight } from "lucide-react";
import Waveform from "@/components/Waveform";
import PianoRoll from "@/components/PianoRoll";
import SynthPlayer from "@/components/SynthPlayer";
import SoundWaveBackground from "@/components/SoundWaveBackground";

// API base URL: use env var for local dev, empty string for production (same origin)
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface AnalysisResult {
  bpm: number;
  scale: string;
  scale_score: number;
  histogram: number[];
}

interface Note {
  pitch: number;
  start: number;
  duration: number;
  velocity: number;
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Generation Parameters
  const [density, setDensity] = useState(7);
  const [syncopation, setSyncopation] = useState(0.5);
  const [register, setRegister] = useState("mid");
  const [generatedHooks, setGeneratedHooks] = useState<Note[][]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedHookIndex, setSelectedHookIndex] = useState(0);
  const [currentBeat, setCurrentBeat] = useState<number | undefined>(undefined);
  const seekRef = useRef<((beat: number) => void) | null>(null);

  const ALLOWED_EXTENSIONS = [".wav", ".mp3", ".mp4", ".m4a"];

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const uploadedFile = e.target.files[0];

      // Clear previous error
      setUploadError(null);

      // Validate file extension
      const fileName = uploadedFile.name.toLowerCase();
      const fileExt = fileName.substring(fileName.lastIndexOf("."));
      if (!ALLOWED_EXTENSIONS.includes(fileExt)) {
        setUploadError("Unsupported file type. Please upload a WAV, MP3, or MP4 file.");
        return;
      }

      setFile(uploadedFile);
      setAudioUrl(URL.createObjectURL(uploadedFile));

      // Auto analyze
      setIsAnalyzing(true);
      const formData = new FormData();
      formData.append("file", uploadedFile);

      try {
        // Use API_BASE for local dev, empty for production (same origin)
        const res = await fetch(`${API_BASE}/analyze`, {
          method: "POST",
          body: formData,
        });
        const data = await res.json();

        if (!res.ok) {
          setUploadError(data.detail || "Failed to analyze audio file.");
          setFile(null);
          setAudioUrl(null);
          return;
        }

        setAnalysis(data);
      } catch (err) {
        console.error("Analysis failed", err);
        setUploadError("Failed to connect to the server. Please try again.");
      } finally {
        setIsAnalyzing(false);
      }
    }
  };

  const handleGenerate = async () => {
    if (!analysis) return;
    setIsGenerating(true);

    try {
      // Use API_BASE for local dev, empty for production (same origin)
      const res = await fetch(`${API_BASE}/generate`, {
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
      });
      const data = await res.json();
      setGeneratedHooks(data.hooks);
      setSelectedHookIndex(0);
    } catch (err) {
      console.error("Generation failed", err);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <main className="min-h-screen w-full relative overflow-hidden selection:bg-white/20 selection:text-white">
      <SoundWaveBackground />

      <div className="relative z-10 max-w-5xl mx-auto px-6 py-24 flex flex-col gap-24">

        {/* Hero Section */}
        <motion.header
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="text-center space-y-6 relative"
        >
          {/* Ambient Background Glow */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[300px] bg-indigo-500/20 rounded-full blur-[120px] -z-10 pointer-events-none" />

          <h1 className="text-6xl md:text-8xl font-light tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-white to-white/60">
            Hook<span className="font-bold text-transparent bg-clip-text bg-gradient-to-b from-white to-neutral-400">Gen</span>
          </h1>

          <p className="text-neutral-400 text-lg max-w-lg mx-auto font-light leading-relaxed tracking-wide">
            <strong className="text-neutral-200">Generate melodies that lock to your beat.</strong>
            <br />Upload a loop to begin.
          </p>
        </motion.header>

        {/* Main Workflow */}
        <div className="space-y-12">

          {/* Upload & Analysis */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.8 }}
            className="grid grid-cols-1 md:grid-cols-2 gap-8"
          >
            {/* Upload Area */}
            <div className={`group relative h-64 rounded-sm border bg-white/[0.02] hover:bg-white/[0.04] transition-all cursor-pointer overflow-hidden ${uploadError ? "border-red-500/50" : "border-white/10 hover:border-white/20"}`}>
              <input
                type="file"
                onChange={handleFileUpload}
                accept=".wav,.mp3,.mp4,.m4a,audio/wav,audio/mpeg,audio/mp4"
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-20"
              />
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 pointer-events-none">
                <div className={`p-4 rounded-full bg-white/5 group-hover:scale-110 transition-transform duration-500 ${uploadError ? "text-red-400" : "text-neutral-400"}`}>
                  <Upload size={24} strokeWidth={1.5} />
                </div>
                <div className="text-center">
                  <p className="text-neutral-200 font-medium">Drop Audio File</p>
                  <p className="text-neutral-500 text-sm mt-1">WAV, MP3, or MP4 • Max 100MB</p>
                </div>
                {uploadError && (
                  <p className="text-red-400 text-sm mt-2 px-4 text-center">{uploadError}</p>
                )}
              </div>
            </div>

            {/* Analysis Display */}
            <div className="h-64 rounded-sm border border-white/10 bg-white/[0.02] p-8 flex flex-col justify-center relative overflow-hidden">
              {isAnalyzing ? (
                <div className="flex flex-col items-center justify-center h-full gap-4 text-neutral-400">
                  <Activity className="animate-spin" strokeWidth={1.5} />
                  <span className="text-sm tracking-widest uppercase">Processing Audio...</span>
                </div>
              ) : analysis ? (
                <div className="space-y-8 relative z-10">
                  <div className="flex justify-between items-end border-b border-white/5 pb-4">
                    <span className="text-neutral-500 text-sm uppercase tracking-widest">Tempo</span>
                    <span className="text-4xl font-light text-white">{Math.round(analysis.bpm)} <span className="text-sm text-neutral-600">BPM</span></span>
                  </div>
                  <div className="flex justify-between items-end">
                    <span className="text-neutral-500 text-sm uppercase tracking-widest">Key</span>
                    <div className="text-right">
                      <span className="text-4xl font-light text-white block">{analysis.scale || "Unknown"}</span>
                      <span className="text-xs text-emerald-500/80">{(analysis.scale_score * 100).toFixed(0)}% Confidence</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full gap-4 text-neutral-600">
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
                <div className="p-8 rounded-sm border border-white/10 bg-white/[0.02]">
                  <Waveform audioUrl={audioUrl} />
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
                className="space-y-8 pt-12 border-t border-white/10"
              >
                <div className="flex items-center gap-4 mb-8">
                  <Sliders size={20} className="text-neutral-500" />
                  <h2 className="text-xl font-light text-white tracking-wide">Generator Settings</h2>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
                  <div className="space-y-4">
                    <div className="flex justify-between text-sm">
                      <label className="text-neutral-400">Density</label>
                      <span className="text-white font-mono">{density}</span>
                    </div>
                    <input
                      type="range" min="4" max="16" value={density}
                      onChange={(e) => setDensity(Number(e.target.value))}
                      className="w-full h-1 bg-neutral-800 rounded-none appearance-none cursor-pointer accent-white hover:accent-neutral-300"
                    />
                  </div>

                  <div className="space-y-4">
                    <div className="flex justify-between text-sm">
                      <label className="text-neutral-400">Syncopation</label>
                      <span className="text-white font-mono">{(syncopation * 100).toFixed(0)}%</span>
                    </div>
                    <input
                      type="range" min="0" max="1" step="0.1" value={syncopation}
                      onChange={(e) => setSyncopation(Number(e.target.value))}
                      className="w-full h-1 bg-neutral-800 rounded-none appearance-none cursor-pointer accent-white hover:accent-neutral-300"
                    />
                  </div>

                  <div className="space-y-4">
                    <label className="text-sm text-neutral-400 block">Register</label>
                    <div className="flex gap-2">
                      {["low", "mid", "high"].map((r) => (
                        <button
                          key={r}
                          onClick={() => setRegister(r)}
                          className={`flex-1 py-2 text-xs uppercase tracking-widest border transition-all ${register === r
                            ? "bg-white text-black border-white"
                            : "bg-transparent text-neutral-500 border-neutral-800 hover:border-neutral-600"
                            }`}
                        >
                          {r}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex justify-end pt-8">
                  <button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="group relative px-8 py-4 bg-white text-black font-medium text-sm uppercase tracking-widest hover:bg-neutral-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-3"
                  >
                    {isGenerating ? (
                      <>Processing <Activity size={16} className="animate-spin" /></>
                    ) : (
                      <>Generate Hooks <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" /></>
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
                className="pt-12 border-t border-white/10 pb-24"
              >
                <div className="flex items-center gap-4 mb-12">
                  <Zap size={20} className="text-neutral-500" />
                  <h2 className="text-xl font-light text-white tracking-wide">Output</h2>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 h-[500px]">
                  {/* List */}
                  <div className="lg:col-span-3 flex flex-col gap-2 overflow-y-auto pr-2 custom-scrollbar">
                    {generatedHooks.map((_, i) => (
                      <button
                        key={i}
                        onClick={() => {
                          setSelectedHookIndex(i);
                          setCurrentBeat(undefined); // Clear playhead when switching hooks
                        }}
                        className={`w-full text-left px-5 py-4 text-sm transition-all border-l-2 ${selectedHookIndex === i
                          ? "border-white bg-white/5 text-white"
                          : "border-transparent text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.02]"
                          }`}
                      >
                        <div className="flex justify-between items-center">
                          <span>Variation {i + 1}</span>
                          {selectedHookIndex === i && <div className="w-1.5 h-1.5 bg-white rounded-full" />}
                        </div>
                      </button>
                    ))}
                  </div>

                  {/* Visualization */}
                  <div className="lg:col-span-9 flex flex-col gap-6">
                    <div className="flex-1 bg-neutral-900/20 border border-white/5 rounded-sm relative overflow-hidden p-4 flex items-center justify-center">
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

                    <div className="bg-neutral-900/20 border border-white/5 rounded-sm p-4">
                      <SynthPlayer
                        notes={generatedHooks[selectedHookIndex]}
                        bpm={analysis?.bpm || 120}
                        onPlayheadUpdate={setCurrentBeat}
                        onSeekRef={seekRef}
                      />
                    </div>
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
