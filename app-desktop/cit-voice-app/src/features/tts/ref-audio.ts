// Giọng mẫu để nhân bản: engine chỉ dùng tối đa 8 giây có tiếng (sau khi cắt im
// lặng hai đầu). Giữ 15 giây là dư, và file ghi âm dài hàng giờ không phải gửi
// trọn lên server (60 phút = 330 MB WAV) chỉ để lấy vài giây đầu.
export const REF_MAX_SECONDS = 15;

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
