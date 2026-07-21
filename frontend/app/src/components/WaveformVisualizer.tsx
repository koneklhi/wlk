/**
 * @fileoverview 실시간 오디오 waveform canvas 컴포넌트
 *
 * ResizeObserver로 컨테이너 크기 추적 → canvas 물리 크기 동기화
 * useWaveform 훅이 requestAnimationFrame으로 직접 그리기
 */
import { useWaveform } from '@/hooks/useWaveform';
import { useEffect, useRef } from 'react';

interface WaveformVisualizerProps {
  analyserNode: AnalyserNode | null;
  isActive: boolean;
}

export const WaveformVisualizer = ({ analyserNode, isActive }: WaveformVisualizerProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useWaveform(canvasRef, analyserNode, isActive);

  // ResizeObserver: 컨테이너 크기 → canvas 물리 크기(dpr 포함) 동기화
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        const dpr = window.devicePixelRatio || 1;

        canvas.width = width * dpr;
        canvas.height = height * dpr;

        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
      }
    });

    resizeObserver.observe(container);

    return () => resizeObserver.disconnect();
  }, []);

  return (
    <div ref={containerRef} className="w-full relative rounded-lg border border-border bg-muted/20" style={{ height: '100px' }}>
      <canvas ref={canvasRef} className="block w-full h-full rounded-lg" />
    </div>
  );
};
