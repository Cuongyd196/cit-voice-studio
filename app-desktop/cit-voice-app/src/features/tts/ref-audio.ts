// Giọng mẫu để nhân bản. Engine chỉ dùng 8 giây đầu của đoạn gửi lên (sau khi cắt
// im lặng hai đầu), nên mặc định chọn đúng 8 giây: người dùng nghe đoạn chọn là
// nghe đúng thứ mô hình học. Cho chọn tới 15 giây (giới hạn của máy chủ) nhưng
// phần quá 8 giây không được dùng - giao diện nói rõ điều này.
export const REF_MAX_SECONDS = 15;
export const REF_MIN_SECONDS = 3;
export const REF_USED_SECONDS = 8;

// Phần đầu file được giải mã để người dùng chọn đoạn. File ghi âm dài hàng giờ
// không giải mã trọn (trang treo, xem audio-engine.decodeReferenceAudio), và
// mẫu tốt thường nằm ở vài phút đầu.
export const REF_EDIT_MAX_SECONDS = 120;

const VOICE_THRESHOLD = 0.01; // ~ -40 dBFS: dưới mức này coi là im lặng / ồn nền
const LEAD_SECONDS = 0.1; // giữ chút im lặng trước tiếng đầu tiên

/**
 * ``[start, end)`` của đoạn cần giữ: bắt đầu ngay trước mẫu có tiếng đầu tiên,
 * dài tối đa ``maxSeconds``. Toàn im lặng thì lấy từ đầu.
 */
export function voicedWindow(
  samples: Float32Array,
  sampleRate: number,
  maxSeconds: number = REF_MAX_SECONDS
): [number, number] {
  let first = 0;
  while (
    first < samples.length &&
    Math.abs(samples[first]) <= VOICE_THRESHOLD
  ) {
    first++;
  }
  if (first >= samples.length) {
    first = 0;
  }
  const start = Math.max(0, first - Math.round(LEAD_SECONDS * sampleRate));
  const end = Math.min(
    samples.length,
    start + Math.round(maxSeconds * sampleRate)
  );
  return [start, end];
}

export interface RefSelection {
  length: number; // giây
  start: number; // giây
}

/**
 * Đưa đoạn chọn về hợp lệ với file dài ``duration`` giây: độ dài trong
 * [REF_MIN_SECONDS, REF_MAX_SECONDS] (file ngắn hơn mức tối thiểu thì lấy cả
 * file) và không tràn ra ngoài file.
 */
export function clampSelection(
  sel: RefSelection,
  duration: number
): RefSelection {
  const maxLen = Math.min(REF_MAX_SECONDS, duration);
  const minLen = Math.min(REF_MIN_SECONDS, maxLen);
  const length = Math.min(maxLen, Math.max(minLen, sel.length));
  const start = Math.min(Math.max(0, sel.start), duration - length);
  return { start: Math.max(0, start), length };
}

/** Đoạn chọn mặc định: ``REF_USED_SECONDS`` giây bắt đầu từ chỗ có tiếng đầu tiên. */
export function defaultSelection(
  samples: Float32Array,
  sampleRate: number
): RefSelection {
  const duration = samples.length / sampleRate;
  const [start] = voicedWindow(samples, sampleRate, REF_USED_SECONDS);
  return clampSelection(
    { start: start / sampleRate, length: REF_USED_SECONDS },
    duration
  );
}

/**
 * Biên độ đỉnh của ``buckets`` khoảng đều nhau, để vẽ dạng sóng. Tính một lần
 * cho cả file; vẽ lại khi đổi đoạn chọn không phải quét lại hàng triệu mẫu.
 */
export function computePeaks(
  samples: Float32Array,
  buckets: number
): Float32Array {
  const peaks = new Float32Array(Math.max(0, buckets));
  if (buckets <= 0 || samples.length === 0) {
    return peaks;
  }
  const step = samples.length / buckets;
  for (let b = 0; b < buckets; b++) {
    const from = Math.floor(b * step);
    const to = Math.min(
      samples.length,
      Math.max(from + 1, Math.floor((b + 1) * step))
    );
    let peak = 0;
    for (let i = from; i < to; i++) {
      const v = Math.abs(samples[i]);
      if (v > peak) {
        peak = v;
      }
    }
    peaks[b] = peak;
  }
  return peaks;
}

/** WAV 16-bit PCM mono của ``samples[start, end)``. */
export function encodeWav(
  samples: Float32Array,
  sampleRate: number,
  start = 0,
  end: number = samples.length
): Blob {
  const from = Math.max(0, Math.min(samples.length, Math.round(start)));
  const to = Math.max(from, Math.min(samples.length, Math.round(end)));
  const n = to - from;
  const buffer = new ArrayBuffer(44 + n * 2);
  const view = new DataView(buffer);
  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };
  writeString(0, "RIFF");
  view.setUint32(4, 36 + n * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeString(36, "data");
  view.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) {
    const s = Math.max(-1, Math.min(1, samples[from + i]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x80_00 : s * 0x7f_ff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}
