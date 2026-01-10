import React, { useEffect, useRef } from 'react';
import { Card, CardContent } from '@/components/ui/card';

interface Props {
  isActive: boolean;
}

export function SimpleWaveform({ isActive }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resizeCanvas = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      if (isActive) {
        const centerY = canvas.height / 2;
        const width = canvas.width;
        const height = canvas.height;
        const time = Date.now() * 0.005;

        ctx.beginPath();
        ctx.strokeStyle = '#4c1d95';
        ctx.lineWidth = 2;
        
        for (let x = 0; x < width; x++) {
          const frequency = 0.02;
          const amplitude = height * 0.3;
          const y = centerY + 
                    Math.sin(x * frequency + time) * amplitude +
                    Math.sin(x * frequency * 2 + time * 1.5) * amplitude * 0.5;
          
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.strokeStyle = '#e5e7eb';
        ctx.lineWidth = 1;
        const centerY = canvas.height / 2;
        ctx.moveTo(0, centerY);
        ctx.lineTo(canvas.width, centerY);
        ctx.stroke();
      }

      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isActive]);

  return (
    <Card className="m-6 shadow-inner">
      <CardContent>
        <canvas
          ref={canvasRef}
          className="w-full h-24 rounded-lg bg-background"
        />
        {isActive && (
          <p className="text-center text-sm text-primary mt-2">
            正在监听语音...
          </p>
        )}
      </CardContent>
    </Card>
  );
}
