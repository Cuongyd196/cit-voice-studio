/** Bật/tạm dừng bộ phát chung; phát lại từ đầu nếu bản ghi đã kết thúc. */
export async function toggleAudioPlayback(
  audio: HTMLAudioElement
): Promise<void> {
  if (!(audio.paused || audio.ended)) {
    audio.pause();
    return;
  }
  if (audio.ended) {
    audio.currentTime = 0;
  }
  try {
    await audio.play();
  } catch (error) {
    // Đổi bản ghi hoặc bấm dừng nhanh có thể huỷ lệnh play đang chờ.
    if (!(error instanceof Error && error.name === "AbortError")) {
      console.warn("Không thể phát âm thanh:", error);
    }
  }
}

/** Áp dụng cho cả nghe mẫu và nghe kết quả: chỉ một bộ phát được phát. */
export function pauseOtherAudio(
  active: HTMLAudioElement,
  players: Iterable<HTMLAudioElement>
): void {
  // Bỏ qua sự kiện play cũ đã nằm trong hàng đợi sau khi đổi bản ghi nhanh.
  if (active.paused) {
    return;
  }
  for (const player of players) {
    if (player !== active && !player.paused) {
      player.pause();
    }
  }
}
