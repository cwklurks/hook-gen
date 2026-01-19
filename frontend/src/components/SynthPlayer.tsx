"use client";

import { useCallback, useEffect, useState, useRef } from "react";
import * as Tone from "tone";
import { Play, Square, Settings2, Download } from "lucide-react";

interface Note {
  pitch: number;
  start: number; // in beats
  duration: number; // in beats
  velocity: number;
}

export interface SynthPlayerControls {
  play: () => Promise<void>;
  stop: () => void;
  isPlaying: () => boolean;
}

// Stable audio level visualization bars to avoid render jitter
// Pre-computed deterministic heights to avoid Math.random() during render
const AUDIO_BAR_HEIGHTS = [76, 52, 88, 64, 70];

function AudioLevelBars() {
  return (
    <div className="flex h-6 items-end gap-1">
      {AUDIO_BAR_HEIGHTS.map((height, i) => (
        <div
          key={i}
          className="w-0.5 animate-pulse rounded-full bg-white"
          style={{
            height: `${height}%`,
            animationDelay: `${i * 0.1}s`,
          }}
        />
      ))}
    </div>
  );
}

interface SynthPlayerProps {
  notes: Note[];
  bpm: number;
  onPlayheadUpdate?: (beat: number | undefined) => void;
  onSeekRef?: React.MutableRefObject<((beat: number) => void) | null>; // Ref to expose seek function
  onPlayStateChange?: (isPlaying: boolean) => void;
  controlsRef?: React.MutableRefObject<SynthPlayerControls | null>;
  // Play Together props
  playTogetherEnabled?: boolean;
  isPlayingTogether?: boolean;
  onTogglePlayTogether?: () => void;
}

export default function SynthPlayer({
  notes,
  bpm,
  onPlayheadUpdate,
  onSeekRef,
  onPlayStateChange,
  controlsRef,
  playTogetherEnabled,
  isPlayingTogether,
  onTogglePlayTogether,
}: SynthPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [preset, setPreset] = useState("pluck");
  const synthRef = useRef<Tone.PolySynth | null>(null);
  const partRef = useRef<Tone.Part | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const onPlayStateChangeRef = useRef(onPlayStateChange);

  // Expose seek function via ref
  const seekToBeat = useCallback(
    (beat: number) => {
      // Clamp beat to 0-16 range
      const clampedBeat = Math.max(0, Math.min(16, beat));

      // Convert beat to Tone.js time format: "bars:quarters:sixteenths"
      const bar = Math.floor(clampedBeat / 4);
      const beatInBar = clampedBeat % 4;
      const quarter = Math.floor(beatInBar);
      const sixteenth = Math.round((beatInBar - quarter) * 4);

      const timeString = `${bar}:${quarter}:${sixteenth}`;
      Tone.Transport.position = timeString;

      // Update playhead immediately
      if (onPlayheadUpdate) {
        onPlayheadUpdate(clampedBeat);
      }
    },
    [onPlayheadUpdate]
  );

  useEffect(() => {
    if (onSeekRef) {
      onSeekRef.current = seekToBeat;
    }
    return () => {
      if (onSeekRef) {
        onSeekRef.current = null;
      }
    };
  }, [onSeekRef, seekToBeat]);

  // Keep onPlayStateChange ref updated
  useEffect(() => {
    onPlayStateChangeRef.current = onPlayStateChange;
  }, [onPlayStateChange]);

  // Expose controls via ref
  useEffect(() => {
    if (controlsRef) {
      controlsRef.current = {
        play: async () => {
          await Tone.start();
          if (Tone.Transport.state !== "started") {
            Tone.Transport.start();
            setIsPlaying(true);
            if (onPlayStateChangeRef.current) onPlayStateChangeRef.current(true);
          }
        },
        stop: () => {
          Tone.Transport.stop();
          setIsPlaying(false);
          if (onPlayheadUpdate) onPlayheadUpdate(undefined);
          if (onPlayStateChangeRef.current) onPlayStateChangeRef.current(false);
        },
        isPlaying: () => Tone.Transport.state === "started",
      };
    }
    return () => {
      if (controlsRef) {
        controlsRef.current = null;
      }
    };
  }, [controlsRef, onPlayheadUpdate]);

  useEffect(() => {
    // Initialize synth
    const synth = new Tone.PolySynth(Tone.Synth).toDestination();
    synthRef.current = synth;

    return () => {
      synth.dispose();
      partRef.current?.dispose();
    };
  }, []);

  useEffect(() => {
    if (!synthRef.current) return;

    // Apply presets
    const synth = synthRef.current;
    synth.releaseAll();

    if (preset === "pluck") {
      synth.set({
        oscillator: { type: "triangle" },
        envelope: { attack: 0.005, decay: 0.1, sustain: 0.3, release: 1 },
      });
    } else if (preset === "bass") {
      synth.set({
        oscillator: { type: "sawtooth" },
        envelope: { attack: 0.01, decay: 0.2, sustain: 0.8, release: 0.5 },
      });
    } else if (preset === "lead") {
      synth.set({
        oscillator: { type: "square" },
        envelope: { attack: 0.01, decay: 0.1, sustain: 0.5, release: 0.5 },
      });
    }
  }, [preset]);

  useEffect(() => {
    if (!notes.length || !synthRef.current) return;

    // Stop existing part
    if (partRef.current) {
      partRef.current.dispose();
    }

    // Notes have start in beats (0-16 for 4 bars, 4 beats per bar)
    // Convert to Tone.js time format: "bars:quarters:sixteenths"
    const events = notes.map((note) => {
      const bar = Math.floor(note.start / 4);
      const beatInBar = note.start % 4;
      const quarter = Math.floor(beatInBar);
      const sixteenth = Math.round((beatInBar - quarter) * 4);

      // Duration in beats → convert to notation (quarter notes)
      const durationInQuarters = note.duration;
      const durationNotation = `0:${durationInQuarters}:0`;

      return {
        time: `${bar}:${quarter}:${sixteenth}`,
        note: Tone.Frequency(note.pitch, "midi").toNote(),
        duration: durationNotation,
        velocity: note.velocity / 127,
      };
    });

    // Create new Part
    const part = new Tone.Part((time, value) => {
      synthRef.current?.triggerAttackRelease(value.note, value.duration, time, value.velocity);
    }, events).start(0);

    part.loop = true;
    part.loopEnd = "4m"; // 4 measures loop
    partRef.current = part;

    Tone.Transport.bpm.value = bpm;
  }, [notes, bpm]);

  // Track playhead position
  useEffect(() => {
    if (!isPlaying || !onPlayheadUpdate) {
      return;
    }

    const updatePlayhead = () => {
      // Check if transport is still playing
      if (Tone.Transport.state === "started") {
        // Get current transport position in beats
        // Transport position is in "bars:quarters:sixteenths" format
        const position = Tone.Transport.position as string;
        const parts = position.split(":").map(Number);
        const bars = parts[0] ?? 0;
        const quarters = parts[1] ?? 0;
        const sixteenths = parts[2] ?? 0;

        // Convert to total beats (4 beats per bar)
        const totalBeats = bars * 4 + quarters + sixteenths / 4;

        // Loop is 4 bars = 16 beats, so wrap around
        const beatPosition = totalBeats % 16;

        onPlayheadUpdate(beatPosition);

        animationFrameRef.current = requestAnimationFrame(updatePlayhead);
      }
    };

    animationFrameRef.current = requestAnimationFrame(updatePlayhead);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isPlaying, onPlayheadUpdate]);

  const togglePlay = async () => {
    await Tone.start();

    if (isPlaying) {
      Tone.Transport.stop();
      setIsPlaying(false);
      if (onPlayheadUpdate) {
        onPlayheadUpdate(undefined); // Hide playhead when stopped
      }
      if (onPlayStateChangeRef.current) {
        onPlayStateChangeRef.current(false);
      }
    } else {
      Tone.Transport.start();
      setIsPlaying(true);
      if (onPlayStateChangeRef.current) {
        onPlayStateChangeRef.current(true);
      }
    }
  };

  const downloadMidi = async () => {
    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
      const res = await fetch(`${API_BASE}/export/midi`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes, bpm }),
      });

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`Export failed: ${res.status} ${res.statusText} - ${errorText}`);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "hook.mid";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("MIDI download failed:", err);
    }
  };

  return (
    <div className="flex flex-col items-center justify-between gap-6 md:flex-row">
      <div className="flex items-center gap-4">
        <button
          onClick={togglePlay}
          aria-label={isPlaying ? "Stop playback" : "Play hook"}
          className={`flex items-center gap-3 rounded-sm border px-6 py-3 text-sm font-medium tracking-wide transition-all focus:outline-none focus:ring-2 focus:ring-white/50 ${
            isPlaying
              ? "border-white/20 bg-white/10 text-white"
              : "border-white bg-white text-black hover:bg-neutral-200"
          }`}
        >
          {isPlaying ? (
            <Square size={16} fill="currentColor" />
          ) : (
            <Play size={16} fill="currentColor" />
          )}
          {isPlaying ? "STOP" : "PLAY HOOK"}
        </button>

        {playTogetherEnabled && onTogglePlayTogether && (
          <button
            onClick={onTogglePlayTogether}
            className={`flex items-center gap-3 rounded-sm border px-6 py-3 text-sm font-medium tracking-wide transition-all ${
              isPlayingTogether
                ? "border-white/20 bg-white/10 text-white"
                : "border-white bg-white text-black hover:bg-neutral-200"
            }`}
          >
            {isPlayingTogether ? (
              <Square size={16} fill="currentColor" />
            ) : (
              <Play size={16} fill="currentColor" />
            )}
            {isPlayingTogether ? "STOP TOGETHER" : "PLAY TOGETHER"}
          </button>
        )}

        <button
          onClick={downloadMidi}
          aria-label="Download MIDI file"
          className="flex items-center gap-3 rounded-sm border border-white/20 bg-white/5 px-6 py-3 text-sm font-medium tracking-wide text-white transition-all hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-white/50"
        >
          <Download size={16} />
          MIDI
        </button>

        {isPlaying && <AudioLevelBars />}
      </div>

      <div className="flex items-center gap-4 border-l border-white/10 px-4 py-2">
        <Settings2 size={16} className="text-neutral-500" />
        <div className="flex flex-col">
          <label
            htmlFor="synth-preset"
            className="text-[10px] font-medium tracking-wider text-neutral-500 uppercase"
          >
            Patch
          </label>
          <select
            id="synth-preset"
            value={preset}
            onChange={(e) => setPreset(e.target.value)}
            className="cursor-pointer appearance-none bg-transparent text-sm text-white transition-colors outline-none hover:text-neutral-300 focus:ring-1 focus:ring-white/30"
          >
            <option value="pluck" className="bg-black text-white">
              Pluck
            </option>
            <option value="bass" className="bg-black text-white">
              80s Bass
            </option>
            <option value="lead" className="bg-black text-white">
              Square Lead
            </option>
          </select>
        </div>
      </div>
    </div>
  );
}
