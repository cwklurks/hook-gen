"use client";

import { useEffect, useRef, useState } from "react";

interface Note {
    pitch: number;
    start: number; // in beats (0-16 for 4 bars)
    duration: number; // in beats
    velocity: number;
}

interface PianoRollProps {
    notes: Note[];
    width?: number;
    height?: number;
    currentBeat?: number; // Current playback position in beats (0-16)
    onSeek?: (beat: number) => void; // Callback when user seeks to a beat
}

export default function PianoRoll({ notes, width = 800, height = 300, currentBeat, onSeek }: PianoRollProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [isDragging, setIsDragging] = useState(false);
    const [draggedBeat, setDraggedBeat] = useState<number | undefined>(undefined);

    useEffect(() => {
        const canvas = canvasRef.current;
        const container = containerRef.current;
        if (!canvas || !container) return;

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const draw = (w: number, h: number) => {
            // Clear canvas
            ctx.clearRect(0, 0, w, h);

            // 4 bars = 16 beats total
            const totalBeats = 16;
            const beatWidth = w / totalBeats;

            // Calculate pitch range from actual notes, with padding
            let minPitch = 60, maxPitch = 72; // Default C4 to C5
            if (notes.length > 0) {
                minPitch = Math.min(...notes.map(n => n.pitch)) - 2;
                maxPitch = Math.max(...notes.map(n => n.pitch)) + 2;
            }
            const numPitches = maxPitch - minPitch + 1;
            const noteHeight = h / numPitches;

            // Draw bar lines (every 4 beats)
            ctx.strokeStyle = "rgba(255, 255, 255, 0.1)";
            ctx.lineWidth = 1;
            for (let bar = 0; bar <= 4; bar++) {
                const x = bar * 4 * beatWidth;
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, h);
                ctx.stroke();
            }

            // Draw beat lines
            ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
            ctx.lineWidth = 0.5;
            for (let beat = 0; beat <= totalBeats; beat++) {
                const x = beat * beatWidth;
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, h);
                ctx.stroke();
            }

            // Draw horizontal pitch lines
            ctx.strokeStyle = "rgba(255, 255, 255, 0.02)";
            for (let i = 0; i <= numPitches; i++) {
                const y = i * noteHeight;
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(w, y);
                ctx.stroke();
            }

            // Draw notes
            notes.forEach((note) => {
                const x = note.start * beatWidth;
                const noteW = Math.max(note.duration * beatWidth - 1, 4);
                const pitchIndex = note.pitch - minPitch;
                const y = h - (pitchIndex + 1) * noteHeight;

                // Note rectangle
                ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
                ctx.fillRect(x, y, noteW, noteHeight - 1);
            });

            // Draw playhead/caret
            const displayBeat = currentBeat !== undefined ? currentBeat : (isDragging ? draggedBeat : undefined);
            if (displayBeat !== undefined) {
                const playheadX = displayBeat * beatWidth;

                // Draw vertical line with slight glow effect when dragging
                ctx.strokeStyle = isDragging ? "#ffffff" : "#ffffff";
                ctx.lineWidth = isDragging ? 3 : 2;
                ctx.shadowBlur = isDragging ? 10 : 0;
                ctx.shadowColor = "#ffffff";
                ctx.beginPath();
                ctx.moveTo(playheadX, 0);
                ctx.lineTo(playheadX, h);
                ctx.stroke();
                ctx.shadowBlur = 0;

                // Draw triangle caret at top
                const caretSize = isDragging ? 10 : 8;
                ctx.fillStyle = "#ffffff";
                ctx.beginPath();
                ctx.moveTo(playheadX, 0);
                ctx.lineTo(playheadX - caretSize / 2, caretSize);
                ctx.lineTo(playheadX + caretSize / 2, caretSize);
                ctx.closePath();
                ctx.fill();
            }
        };

        // Resize canvas to fit container width
        const resizeObserver = new ResizeObserver((entries) => {
            for (const entry of entries) {
                const { width: containerWidth } = entry.contentRect;
                canvas.width = containerWidth;
                canvas.height = height;
                draw(canvas.width, height);
            }
        });

        resizeObserver.observe(container);

        // Initial draw
        canvas.width = container.clientWidth;
        canvas.height = height;
        draw(container.clientWidth, height);

        return () => resizeObserver.disconnect();

    }, [notes, width, height, currentBeat, isDragging, draggedBeat]);

    // Handle mouse/touch events for seeking
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !onSeek) return;

        const getBeatFromEvent = (e: MouseEvent | TouchEvent): number | null => {
            const rect = canvas.getBoundingClientRect();
            let clientX: number;

            if (e instanceof MouseEvent) {
                clientX = e.clientX;
            } else {
                clientX = e.touches[0]?.clientX ?? 0;
            }

            const x = clientX - rect.left;
            const canvasWidth = canvas.width;
            const totalBeats = 16;
            const beatWidth = canvasWidth / totalBeats;

            // Clamp to valid range
            const beat = Math.max(0, Math.min(totalBeats, x / beatWidth));
            return beat;
        };

        const handleStart = (e: MouseEvent | TouchEvent) => {
            e.preventDefault();
            setIsDragging(true);
            const beat = getBeatFromEvent(e);
            if (beat !== null) {
                setDraggedBeat(beat);
                onSeek(beat);
            }
        };

        const handleMove = (e: MouseEvent | TouchEvent) => {
            if (!isDragging) return;
            e.preventDefault();
            const beat = getBeatFromEvent(e);
            if (beat !== null) {
                setDraggedBeat(beat);
                onSeek(beat);
            }
        };

        const handleEnd = () => {
            setIsDragging(false);
            // Keep draggedBeat visible briefly, then clear after a short delay
            setTimeout(() => {
                setDraggedBeat(undefined);
            }, 100);
        };

        // Mouse events
        canvas.addEventListener("mousedown", handleStart);
        canvas.addEventListener("mousemove", handleMove);
        canvas.addEventListener("mouseup", handleEnd);
        canvas.addEventListener("mouseleave", handleEnd);

        // Touch events
        canvas.addEventListener("touchstart", handleStart, { passive: false });
        canvas.addEventListener("touchmove", handleMove, { passive: false });
        canvas.addEventListener("touchend", handleEnd);
        canvas.addEventListener("touchcancel", handleEnd);

        // Change cursor to pointer when hovering
        canvas.style.cursor = "pointer";

        return () => {
            canvas.removeEventListener("mousedown", handleStart);
            canvas.removeEventListener("mousemove", handleMove);
            canvas.removeEventListener("mouseup", handleEnd);
            canvas.removeEventListener("mouseleave", handleEnd);
            canvas.removeEventListener("touchstart", handleStart);
            canvas.removeEventListener("touchmove", handleMove);
            canvas.removeEventListener("touchend", handleEnd);
            canvas.removeEventListener("touchcancel", handleEnd);
        };
    }, [isDragging, onSeek]);

    return (
        <div ref={containerRef} className="w-full overflow-hidden rounded-sm border border-white/5 bg-white/[0.02]">
            <canvas
                ref={canvasRef}
                height={height}
                className="w-full h-full block"
            />
        </div>
    );
}
