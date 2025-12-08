"use client";

import { motion } from "framer-motion";
import { CheckCircle2, FileAudio, Music2, Waves, Piano, Loader2 } from "lucide-react";

interface ProgressStage {
  id: string;
  label: string;
  icon: React.ReactNode;
}

const STAGES: ProgressStage[] = [
  { id: "validating", label: "Validating", icon: <FileAudio size={16} /> },
  { id: "loading", label: "Decoding", icon: <Music2 size={16} /> },
  { id: "tempo", label: "Tempo", icon: <Waves size={16} /> },
  { id: "groove", label: "Groove", icon: <Waves size={16} /> },
  { id: "scale", label: "Key", icon: <Piano size={16} /> },
];

interface AnalysisProgressProps {
  progress: number;
  stage: string;
  message: string;
}

export default function AnalysisProgress({ progress, stage, message }: AnalysisProgressProps) {
  const currentStageIndex = STAGES.findIndex((s) => s.id === stage);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 px-4">
      {/* Stage indicators */}
      <div className="flex w-full max-w-xs items-center gap-2">
        {STAGES.map((s, index) => {
          const isComplete = index < currentStageIndex || stage === "complete";
          const isCurrent = s.id === stage;

          return (
            <div key={s.id} className="flex flex-1 items-center">
              <motion.div
                initial={{ scale: 0.8, opacity: 0.5 }}
                animate={{
                  scale: isCurrent ? 1.1 : 1,
                  opacity: isComplete || isCurrent ? 1 : 0.3,
                }}
                className={`relative flex h-8 w-8 items-center justify-center rounded-full border transition-colors duration-300 ${
                  isComplete
                    ? "border-emerald-500/50 bg-emerald-500/20 text-emerald-400"
                    : isCurrent
                      ? "border-white/30 bg-white/10 text-white"
                      : "border-white/10 bg-white/5 text-neutral-600"
                } `}
              >
                {isComplete ? (
                  <CheckCircle2 size={14} />
                ) : isCurrent ? (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  >
                    <Loader2 size={14} />
                  </motion.div>
                ) : (
                  s.icon
                )}
              </motion.div>

              {/* Connector line */}
              {index < STAGES.length - 1 && (
                <div className="relative mx-1 h-px flex-1 overflow-hidden">
                  <div className="absolute inset-0 bg-white/10" />
                  <motion.div
                    className="absolute inset-0 bg-gradient-to-r from-emerald-500/50 to-emerald-500/30"
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: isComplete ? 1 : 0 }}
                    style={{ transformOrigin: "left" }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="w-full max-w-xs">
        <div className="h-1 overflow-hidden rounded-full bg-white/10">
          <motion.div
            className="h-full bg-gradient-to-r from-indigo-500 via-white to-indigo-500 bg-[length:200%_100%]"
            initial={{ width: 0 }}
            animate={{
              width: `${progress}%`,
              backgroundPosition: ["0% 0%", "100% 0%"],
            }}
            transition={{
              width: { duration: 0.3, ease: "easeOut" },
              backgroundPosition: { duration: 2, repeat: Infinity, ease: "linear" },
            }}
          />
        </div>

        <div className="mt-2 flex justify-between">
          <span className="text-xs tracking-widest text-neutral-500 uppercase">
            {progress < 100 ? "Processing" : "Complete"}
          </span>
          <span className="font-mono text-xs text-neutral-400">{Math.round(progress)}%</span>
        </div>
      </div>

      {/* Status message */}
      <div className="flex flex-col items-center">
        <motion.p
          key={message}
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          className="min-h-[20px] text-center text-sm text-neutral-300"
        >
          {message}
        </motion.p>

        {stage === "scale" && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 2 }}
            className="mt-1 text-xs text-neutral-500"
          >
            This may take 3-5 minutes
          </motion.p>
        )}
      </div>
    </div>
  );
}
