"use client";

import { useEffect, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import { Play, Pause } from "lucide-react";

interface WaveformProps {
    audioUrl: string | null;
    onReady?: () => void;
}

export default function Waveform({ audioUrl, onReady }: WaveformProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const wavesurfer = useRef<WaveSurfer | null>(null);
    const onReadyRef = useRef(onReady);
    const [isPlaying, setIsPlaying] = useState(false);
    const [isReady, setIsReady] = useState(false);
    const [prevAudioUrl, setPrevAudioUrl] = useState(audioUrl);

    // Reset state when audioUrl changes (React-recommended pattern)
    if (audioUrl !== prevAudioUrl) {
        setPrevAudioUrl(audioUrl);
        setIsReady(false);
        setIsPlaying(false);
    }

    // Keep ref updated with latest onReady callback
    useEffect(() => {
        onReadyRef.current = onReady;
    }, [onReady]);

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
            if (err?.name === 'AbortError' || abortController.signal.aborted) {
                return;
            }
            console.error('WaveSurfer load error:', err);
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
            }
        });

        ws.on("play", () => {
            if (!abortController.signal.aborted) setIsPlaying(true);
        });
        ws.on("pause", () => {
            if (!abortController.signal.aborted) setIsPlaying(false);
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
                className="w-full mb-6 min-h-[80px]"
                style={{ opacity: isReady ? 1 : 0.5 }}
            />
            <div className="flex justify-center">
                <button
                    onClick={togglePlay}
                    disabled={!isReady}
                    className="flex items-center gap-3 px-6 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {isPlaying ? (
                        <Pause size={16} className="text-white" />
                    ) : (
                        <Play size={16} className="text-white ml-1" />
                    )}
                    <span className="font-medium text-sm tracking-wide">
                        {isPlaying ? "PAUSE LOOP" : "PLAY LOOP"}
                    </span>
                </button>
            </div>
        </div>
    );
}
