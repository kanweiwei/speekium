import { useEffect, useRef } from 'react';
import { Mic } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AudioWaveformProps {
  /** Whether currently recording */
  isRecording?: boolean;
  /** Audio level (0-1) */
  audioLevel?: number;
  /** Class name overrides */
  className?: string;
}

export function AudioWaveform({
  isRecording = false,
  audioLevel = 0,
  className,
}: AudioWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>();
  const bars = 20;
  
  // Simulated waveform animation when recording
  useEffect(() => {
    if (!isRecording) return;
    
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    const draw = () => {
      const { width, height } = canvas;
      ctx.clearRect(0, 0, width, height);
      
      const barWidth = width / bars;
      const gap = 2;
      
      for (let i = 0; i < bars; i++) {
        // Generate pseudo-random height based on time
        const time = Date.now() / 1000;
        const offset = Math.sin(time * 3 + i * 0.5) * 0.3;
        const randomOffset = Math.sin(time * 7 + i * 1.2) * 0.2;
        
        // Combine base level with animation
        const level = Math.max(0.1, Math.min(1, audioLevel + offset + randomOffset));
        const barHeight = level * height * 0.8;
        
        const x = i * barWidth;
        const y = (height - barHeight) / 2;
        
        // Gradient color
        const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
        gradient.addColorStop(0, 'rgb(59, 130, 246)'); // blue-500
        gradient.addColorStop(0.5, 'rgb(139, 92, 246)'); // purple-500
        gradient.addColorStop(1, 'rgb(59, 130, 246)'); // blue-500
        
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.roundRect(x + gap / 2, y, barWidth - gap, barHeight, 2);
        ctx.fill();
      }
      
      animationRef.current = requestAnimationFrame(draw);
    };
    
    draw();
    
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isRecording, audioLevel]);

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <canvas
        ref={canvasRef}
        width={120}
        height={24}
        className={cn(
          "transition-opacity duration-200",
          isRecording ? "opacity-100" : "opacity-0"
        )}
      />
      <Mic
        className={cn(
          "w-4 h-4 transition-all duration-200",
          isRecording 
            ? "text-red-500 animate-pulse" 
            : "text-muted-foreground"
        )}
      />
    </div>
  );
}

// Simple audio level indicator (alternative simpler version)
interface AudioLevelIndicatorProps {
  /** Whether currently recording */
  isRecording?: boolean;
  /** Audio level (0-1) */
  audioLevel?: number;
  /** Class name overrides */
  className?: string;
}

export function AudioLevelIndicator({
  isRecording = false,
  audioLevel = 0,
  className,
}: AudioLevelIndicatorProps) {
  const bars = 5;
  
  return (
    <div className={cn("flex items-center gap-0.5 h-6", className)}>
      {Array.from({ length: bars }).map((_, i) => {
        const threshold = (i + 1) / bars;
        const isActive = isRecording && audioLevel >= threshold - 0.2;
        
        return (
          <div
            key={i}
            className={cn(
              "w-1 rounded-full transition-all duration-150",
              isActive 
                ? "bg-gradient-to-t from-blue-500 to-purple-500" 
                : "bg-muted",
              isActive && `h-${3 + i}` // h-3, h-4, h-5, h-6, h-7
            )}
            style={{
              height: isActive ? `${12 + i * 3}px` : '4px'
            }}
          />
        );
      })}
    </div>
  );
}
