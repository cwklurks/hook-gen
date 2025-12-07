"use client";

import { useEffect, useRef } from "react";

export default function SoundWaveBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let time = 0;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    window.addEventListener("resize", resize);
    resize();

    const draw = () => {
      time += 0.005;
      ctx.fillStyle = "#050505";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.lineWidth = 1.5;
      
      // Draw multiple waves
      const lines = 6;
      for (let i = 0; i < lines; i++) {
        ctx.beginPath();
        
        // Calculate dynamic properties for each line
        const yOffset = canvas.height * 0.5 + (i - lines / 2) * 40;
        const amplitude = 50 + i * 10;
        const speed = 1 + i * 0.1;
        const alpha = 0.15 - (Math.abs(i - lines / 2) * 0.02);
        
        ctx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;

        for (let x = 0; x < canvas.width; x += 2) {
            // Complex wave function for organic look
            const y = yOffset + 
              Math.sin(x * 0.003 + time * speed) * amplitude * Math.sin(time * 0.2) +
              Math.cos(x * 0.001 + time * 0.5) * (amplitude * 0.5);
            
            if (x === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        ctx.stroke();
      }

      animationFrameId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full pointer-events-none z-0"
    />
  );
}


