import { useEffect, useRef, useState } from 'react';
import { Mic, Volume2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AudioWaveformProps {
  /** Whether currently recording */
  isRecording?: boolean;
  /** Whether currently playing TTS */
  isSpeaking?: boolean;
  /** Audio level (0-1) */
  audioLevel?: number;
  /** Class name overrides */
  className?: string;
}

/**
 * 增强版波形可视化组件
 * 
 * 设计规范：
 * | 状态   | 波形样式                          |
 * | ---- | ----------------------------- |
 * | 录音中 | 5-7根柱子，随音量高低动态变化          |
 * | 播放中 | 渐变色的柱子，节奏感动画             |
 * | 待机   | 简洁的单线条                      |
 */
export function AudioWaveform({
  isRecording = false,
  isSpeaking = false,
  audioLevel = 0,
  className,
}: AudioWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>();
  const [displayBars, setDisplayBars] = useState(5);

  // 根据音量动态调整柱子数量
  useEffect(() => {
    if (isRecording && audioLevel > 0.7) {
      setDisplayBars(7);
    } else if (isRecording && audioLevel > 0.4) {
      setDisplayBars(6);
    } else {
      setDisplayBars(5);
    }
  }, [isRecording, audioLevel]);

  // Canvas 动画
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 动画状态
    let phase = 0;
    
    const draw = () => {
      const { width, height } = canvas;
      ctx.clearRect(0, 0, width, height);
      
      const barWidth = width / displayBars;
      const gap = 3;
      
      for (let i = 0; i < displayBars; i++) {
        let barHeight: number;
        
        if (isRecording) {
          // 录音中：音量驱动 + 动画
          const time = Date.now() / 1000;
          const offset = Math.sin(time * 4 + i * 0.6) * 0.25;
          const randomOffset = Math.sin(time * 8 + i * 1.3) * 0.15;
          const level = Math.max(0.1, Math.min(1, audioLevel * 1.2 + offset + randomOffset));
          barHeight = level * height * 0.85;
        } else if (isSpeaking) {
          // 播放中：节奏感动画
          phase += 0.08;
          const wave = Math.sin(phase + i * 0.5) * 0.5 + 0.5;
          barHeight = wave * height * 0.7 + height * 0.15;
        } else {
          // 待机：简洁单线条
          barHeight = 4;
        }
        
        const x = i * barWidth;
        const y = (height - barHeight) / 2;
        
        // 渐变色
        let gradient: CanvasGradient;
        
        if (isRecording) {
          // 录音中：红色渐变
          gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
          gradient.addColorStop(0, '#ef4444'); // red-500
          gradient.addColorStop(0.5, '#f87171'); // red-400
          gradient.addColorStop(1, '#ef4444');
        } else if (isSpeaking) {
          // 播放中：蓝紫渐变
          gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
          gradient.addColorStop(0, '#3b82f6'); // blue-500
          gradient.addColorStop(0.5, '#8b5cf6'); // purple-500
          gradient.addColorStop(1, '#3b82f6');
        } else {
          // 待机：灰色
          gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
          gradient.addColorStop(0, '#6b7280'); // gray-500
          gradient.addColorStop(1, '#9ca3af'); // gray-400
        }
        
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
  }, [isRecording, isSpeaking, audioLevel, displayBars]);

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <canvas
        ref={canvasRef}
        width={displayBars * 18}
        height={32}
        className={cn(
          "transition-opacity duration-200",
          (isRecording || isSpeaking) ? "opacity-100" : "opacity-40"
        )}
      />
      {/* 状态图标 */}
      {isRecording ? (
        <Mic className="w-4 h-4 text-red-500 animate-pulse" />
      ) : isSpeaking ? (
        <Volume2 className="w-4 h-4 text-purple-500 animate-pulse" />
      ) : (
        <div className="w-4" />
      )}
    </div>
  );
}

/**
 * 简洁版音量指示器
 */
export function AudioLevelIndicator({
  isRecording = false,
  isSpeaking = false,
  audioLevel: _audioLevel = 0,
  className,
}: AudioWaveformProps) {
  const bars = 5;
  
  return (
    <div className={cn("flex items-center gap-0.5 h-6", className)}>
      {Array.from({ length: bars }).map((_, i) => {
        const heightValue = isRecording || isSpeaking ? (12 + i * 3) : 4;
        
        return (
          <div
            key={i}
            className={cn(
              "w-1 rounded-full transition-all duration-150",
              isRecording 
                ? "bg-gradient-to-t from-red-500 to-red-400" 
                : isSpeaking
                ? "bg-gradient-to-t from-blue-500 to-purple-500"
                : "bg-muted"
            )}
            style={{
              height: `${heightValue}px`
            }}
          />
        );
      })}
    </div>
  );
}
