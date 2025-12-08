"use client";

import { useEffect, useState } from "react";

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

export default function MusicBackground() {
  const [notes, setNotes] = useState<FloatingNote[]>([]);

  useEffect(() => {
    // Generate random notes on client-side only to avoid hydration mismatch
    const newNotes: FloatingNote[] = Array.from({ length: 20 }).map((_, i) => {
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
    setNotes(newNotes);
  }, []);

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
            opacity: note.opacity,
            animationDuration: `${note.duration}s`,
            animationDelay: `${note.delay}s`,
          }}
        >
          {note.char}
        </div>
      ))}

      {/* Gradient Overlay for depth */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-slate-950/50 to-slate-950/80" />
    </div>
  );
}
