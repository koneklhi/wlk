let sampleRate = 48000;
let targetSampleRate = 16000;
// 0.5초 단위로 묶어 전송 — test_client.py 의 chunk_duration=0.5 와 동일한 크기
const chunkDuration = 0.5;
let accumBuffer = [];
let accumSize = 0;

self.onmessage = function (e) {
  switch (e.data.command) {
    case 'init':
      init(e.data.config);
      break;
    case 'record':
      record(e.data.buffer);
      break;
  }
};

function init(config) {
  sampleRate = config.sampleRate;
  targetSampleRate = config.targetSampleRate || 16000;
  accumBuffer = [];
  accumSize = 0;
}

function record(inputBuffer) {
  const buffer = new Float32Array(inputBuffer);
  accumBuffer.push(buffer);
  accumSize += buffer.length;

  // 네이티브 샘플레이트 기준 0.5초 분량이 쌓이면 리샘플 후 전송
  const samplesNeeded = Math.round(sampleRate * chunkDuration);

  while (accumSize >= samplesNeeded) {
    const chunk = new Float32Array(samplesNeeded);
    let offset = 0;
    let remaining = samplesNeeded;

    while (remaining > 0) {
      const first = accumBuffer[0];
      if (first.length <= remaining) {
        chunk.set(first, offset);
        offset += first.length;
        remaining -= first.length;
        accumSize -= first.length;
        accumBuffer.shift();
      } else {
        chunk.set(first.subarray(0, remaining), offset);
        accumBuffer[0] = first.subarray(remaining);
        accumSize -= remaining;
        remaining = 0;
      }
    }

    const resampledBuffer = resample(chunk, sampleRate, targetSampleRate);
    const pcmBuffer = toPCM(resampledBuffer);
    self.postMessage({ buffer: pcmBuffer }, [pcmBuffer]);
  }
}

function resample(buffer, from, to) {
    if (from === to) {
        return buffer;
    }
    const ratio = from / to;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;
    while (offsetResult < result.length) {
        const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
        let accum = 0, count = 0;
        for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
            accum += buffer[i];
            count++;
        }
        result[offsetResult] = accum / count;
        offsetResult++;
        offsetBuffer = nextOffsetBuffer;
    }
    return result;
}

function toPCM(input) {
  const buffer = new ArrayBuffer(input.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }
  return buffer;
}
