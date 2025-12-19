"use client";

import { useEffect, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import { Play, Pause } from "lucide-react";

export interface WaveformControls {
  play: () => void;
  pause: () => void;
  stop: () => void;
  isPlaying: () => boolean;
  getDuration: () => number;
  getCurrentTime: () => number;
  seekTo: (time: number) => void;
}

interface WaveformProps {
  audioUrl: string | null;
  onReady?: () => void;
  onPlayStateChange?: (isPlaying: boolean) => void;
  controlsRef?: React.MutableRefObject<WaveformControls | null>;
}

export default function Waveform({ audioUrl, onReady, onPlayStateChange, controlsRef }: WaveformProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurfer = useRef<WaveSurfer | null>(null);
  const onReadyRef = useRef(onReady);
  const onPlayStateChangeRef = useRef(onPlayStateChange);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [prevAudioUrl, setPrevAudioUrl] = useState(audioUrl);

  // Reset state when audioUrl changes (React-recommended pattern)
  if (audioUrl !== prevAudioUrl) {
    setPrevAudioUrl(audioUrl);
    setIsReady(false);
    setIsPlaying(false);
  }

  // Keep refs updated with latest callbacks
  useEffect(() => {
    onReadyRef.current = onReady;
  }, [onReady]);

  useEffect(() => {
    onPlayStateChangeRef.current = onPlayStateChange;
  }, [onPlayStateChange]);

  // Expose controls via ref
  useEffect(() => {
    if (controlsRef) {
      controlsRef.current = {
        play: () => {
          if (wavesurfer.current && isReady) {
            wavesurfer.current.play();
          }
        },
        pause: () => {
          if (wavesurfer.current) {
            wavesurfer.current.pause();
          }
        },
        stop: () => {
          if (wavesurfer.current) {
            wavesurfer.current.stop();
          }
        },
        isPlaying: () => isPlaying,
        getDuration: () => wavesurfer.current?.getDuration() || 0,
        getCurrentTime: () => wavesurfer.current?.getCurrentTime() || 0,
        seekTo: (time: number) => {
          if (wavesurfer.current) {
            wavesurfer.current.seekTo(time / wavesurfer.current.getDuration());
          }
        },
      };
    }
    return () => {
      if (controlsRef) {
        controlsRef.current = null;
      }
    };
  }, [controlsRef, isReady, isPlaying]);

  useEffect(() => {
    if (!containerRef.current || !audioUrl) return;

    const abortController = new AbortController();
    let ws: WaveSurfer | null = null;

    // Create WaveSurfer instance
    ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "#3f3f3f", // Unplayed: dark gray
      progressColor: "#ffffff", // Played: white
      cursorColor: "#ffffff",
      cursorWidth: 2,
      barWidth: 3,
      barGap: 2,
      barRadius: 2,
      height: 80,
      normalize: true,
    });

    wavesurfer.current = ws;

    // Load with abort signal support
    ws.load(audioUrl).catch((err) => {
      // Ignore abort errors - they're expected during cleanup
      if (err?.name === "AbortError" || abortController.signal.aborted) {
        return;
      }
      console.error("WaveSurfer load error:", err);
    });

    ws.on("ready", () => {
      if (!abortController.signal.aborted) {
        setIsReady(true);
        if (onReadyRef.current) onReadyRef.current();
      }
    });

    ws.on("finish", () => {
      if (!abortController.signal.aborted) {
        setIsPlaying(false);
        if (onPlayStateChangeRef.current) onPlayStateChangeRef.current(false);
      }
    });

    ws.on("play", () => {
      if (!abortController.signal.aborted) {
        setIsPlaying(true);
        if (onPlayStateChangeRef.current) onPlayStateChangeRef.current(true);
      }
    });
    ws.on("pause", () => {
      if (!abortController.signal.aborted) {
        setIsPlaying(false);
        if (onPlayStateChangeRef.current) onPlayStateChangeRef.current(false);
      }
    });

    return () => {
      abortController.abort();
      if (ws) {
        try {
          ws.destroy();
        } catch {
          // Ignore errors during cleanup
        }
      }
      wavesurfer.current = null;
    };
  }, [audioUrl]); // onReady is stored in a ref to avoid re-creating WaveSurfer

  const togglePlay = () => {
    if (wavesurfer.current && isReady) {
      wavesurfer.current.playPause();
    }
  };

  if (!audioUrl) return null;

  return (
    <div className="w-full">
      <div
        ref={containerRef}
        className="mb-6 min-h-[80px] w-full"
        style={{ opacity: isReady ? 1 : 0.5 }}
      />
      <div className="flex justify-center">
        <button
          onClick={togglePlay}
          disabled={!isReady}
          className="flex items-center gap-3 rounded-sm border border-white/10 bg-white/5 px-6 py-2 transition-all hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isPlaying ? (
            <Pause size={16} className="text-white" />
          ) : (
            <Play size={16} className="ml-1 text-white" />
          )}
          <span className="text-sm font-medium tracking-wide">
            {isPlaying ? "PAUSE LOOP" : "PLAY LOOP"}
          </span>
        </button>
      </div>
    </div>
  );
}
