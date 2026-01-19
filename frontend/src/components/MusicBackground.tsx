"use client";

import { useMemo, useSyncExternalStore } from "react";

const NOTES = ["♪", "♫", "♩", "♬", "♭", "♮", "♯"];

interface FloatingNote {
  id: number;
  char: string;
  x: number;
  y: number;
  size: number;
  duration: number;
  delay: number;
  opacity: number;
}

function generateNotes(): FloatingNote[] {
  return Array.from({ length: 20 }).map((_, i) => {
    const randomIndex = Math.floor(Math.random() * NOTES.length);
    const char = NOTES[randomIndex];
    return {
      id: i,
      char: char ?? NOTES[0] ?? "♪",
      x: Math.random() * 100, // vw
      y: Math.random() * 100, // vh
      size: Math.random() * 2 + 1, // rem
      duration: Math.random() * 20 + 10, // seconds
      delay: Math.random() * -20, // negative delay to start mid-animation
      opacity: Math.random() * 0.3 + 0.1,
    };
  });
}

// React 18+ pattern for detecting client-side mount without useEffect setState
const emptySubscribe = () => () => {};

export default function MusicBackground() {
  // useSyncExternalStore with different server/client values is the React 18+ way
  // to handle hydration-safe client-only rendering without setState in useEffect
  const isMounted = useSyncExternalStore(
    emptySubscribe,
    () => true, // Client value
    () => false // Server value
  );

  // Generate notes only on client-side to avoid hydration mismatch
  const notes = useMemo(() => {
    if (!isMounted) return [];
    return generateNotes();
  }, [isMounted]);

  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      {notes.map((note) => (
        <div
          key={note.id}
          className="animate-float-music absolute text-indigo-500/20"
          style={{
            left: `${note.x}vw`,
            top: `${note.y}vh`,
            fontSize: `${note.size}rem`,
            "--float-opacity": note.opacity,
            "--duration": `${note.duration}s`,
            "--delay": `${note.delay}s`,
          } as React.CSSProperties}
        >
          {note.char}
        </div>
      ))}

      {/* Gradient Overlay for depth */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-slate-950/50 to-slate-950/80" />
    </div>
  );
}
