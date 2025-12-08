"use client";

import { motion } from "framer-motion";
import { 
  CheckCircle2, 
  FileAudio, 
  Music2, 
  Waves, 
  Piano,
  Loader2
} from "lucide-react";

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
  const currentStageIndex = STAGES.findIndex(s => s.id === stage);
  
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 px-4">
      {/* Stage indicators */}
      <div className="flex items-center gap-2 w-full max-w-xs">
        {STAGES.map((s, index) => {
          const isComplete = index < currentStageIndex || stage === "complete";
          const isCurrent = s.id === stage;
          
          return (
            <div key={s.id} className="flex items-center flex-1">
              <motion.div
                initial={{ scale: 0.8, opacity: 0.5 }}
                animate={{ 
                  scale: isCurrent ? 1.1 : 1,
                  opacity: isComplete || isCurrent ? 1 : 0.3
                }}
                className={`
                  relative flex items-center justify-center w-8 h-8 rounded-full border transition-colors duration-300
                  ${isComplete 
                    ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-400" 
                    : isCurrent 
                      ? "bg-white/10 border-white/30 text-white"
                      : "bg-white/5 border-white/10 text-neutral-600"
                  }
                `}
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
                <div className="flex-1 h-px mx-1 relative overflow-hidden">
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
        <div className="h-1 bg-white/10 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-indigo-500 via-white to-indigo-500 bg-[length:200%_100%]"
            initial={{ width: 0 }}
            animate={{ 
              width: `${progress}%`,
              backgroundPosition: ["0% 0%", "100% 0%"]
            }}
            transition={{ 
              width: { duration: 0.3, ease: "easeOut" },
              backgroundPosition: { duration: 2, repeat: Infinity, ease: "linear" }
            }}
          />
        </div>
        
        <div className="flex justify-between mt-2">
          <span className="text-xs text-neutral-500 uppercase tracking-widest">
            {progress < 100 ? "Processing" : "Complete"}
          </span>
          <span className="text-xs font-mono text-neutral-400">
            {Math.round(progress)}%
          </span>
        </div>
      </div>
      
      {/* Status message */}
      <motion.p
        key={message}
        initial={{ opacity: 0, y: 5 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-sm text-neutral-300 text-center min-h-[20px]"
      >
        {message}
      </motion.p>
    </div>
  );
}


