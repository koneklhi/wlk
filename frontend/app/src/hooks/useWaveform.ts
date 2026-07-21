/**
 * @fileoverview 실시간 오디오 waveform 렌더링 — requestAnimationFrame 기반 canvas 직접 그리기
 *
 * AnalyserNode → requestAnimationFrame → canvas ref 직접 그리기
 * React는 isActive 변경 시RAF 시작/중단만 관리
 */
import { useCallback, useEffect, useRef } from 'react';

export function useWaveform(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  analyserNode: AnalyserNode | null,
  isActive: boolean,
) {
  const animationRef = useRef<number>(0);

  const draw = useCallback(() => {
    if (!analyserNode || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const bufferLength = analyserNode.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    analyserNode.getByteTimeDomainData(dataArray);

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const logicalWidth = canvas.width / dpr;
    const logicalHeight = canvas.height / dpr;

    ctx.clearRect(0, 0, logicalWidth, logicalHeight);

    ctx.lineWidth = 2;
    ctx.strokeStyle = '#7CC5FA';
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();

    const sliceWidth = logicalWidth / bufferLength;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
      const v = (dataArray[i] - 128) / 128.0;
      const y = logicalHeight / 2 + v * logicalHeight * 0.4;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
      x += sliceWidth;
    }

    ctx.stroke();
  }, [canvasRef, analyserNode]);

  useEffect(() => {
    if (!isActive) return;

    const renderFrame = () => {
      draw();
      animationRef.current = requestAnimationFrame(renderFrame);
    };
    renderFrame();

    return () => {
      cancelAnimationFrame(animationRef.current);
    };
  }, [isActive, draw]);
}
