import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

// Chạy logic phát thật với bộ phát giả, không cần tải mô hình hoặc phát loa.
const source = await readFile(
  new URL("../src/features/tts/playback.ts", import.meta.url),
  "utf8"
);
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
});
const { toggleAudioPlayback, pauseOtherAudio } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);

function player() {
  return {
    paused: true,
    ended: false,
    currentTime: 0,
    playCalls: 0,
    pauseCalls: 0,
    async play() {
      this.playCalls += 1;
      this.paused = false;
      this.ended = false;
    },
    pause() {
      this.pauseCalls += 1;
      this.paused = true;
    },
  };
}

test("Play lịch sử và Play thanh dưới bật/tạm dừng cùng một bộ phát", async () => {
  const audio = player();
  const historyPlay = () => toggleAudioPlayback(audio);
  const footerPlay = () => toggleAudioPlayback(audio);
  await historyPlay();
  assert.equal(audio.paused, false);
  audio.currentTime = 4;
  await footerPlay();
  assert.equal(audio.paused, true);
  await historyPlay();
  assert.equal(audio.paused, false);
  assert.equal(audio.currentTime, 4);
  assert.equal(audio.playCalls, 2);
});

test("Phát lại bản đã kết thúc bắt đầu từ giây 0", async () => {
  const audio = player();
  audio.ended = true;
  audio.currentTime = 18;
  await toggleAudioPlayback(audio);
  assert.equal(audio.currentTime, 0);
  assert.equal(audio.paused, false);
});

test("Chuyển giữa kết quả nhân bản và bộ phát chung không phát chồng", async () => {
  const footer = player();
  const clone = player();
  const reference = player();
  const all = [footer, clone, reference];
  await clone.play();
  await reference.play();
  await toggleAudioPlayback(footer);
  pauseOtherAudio(footer, all);
  assert.deepEqual(
    all.map((audio) => audio.paused),
    [false, true, true]
  );
  await clone.play();
  pauseOtherAudio(clone, all);
  assert.deepEqual(
    all.map((audio) => audio.paused),
    [true, false, true]
  );
});

test("Sự kiện play cũ không dừng bản ghi mới đang phát", async () => {
  const oldPlayer = player();
  const current = player();
  await current.play();
  pauseOtherAudio(oldPlayer, [oldPlayer, current]);
  assert.equal(current.paused, false);
  assert.equal(current.pauseCalls, 0);
});

test("Bấm Play rồi Pause nhanh xử lý lệnh phát đang chờ", async () => {
  const audio = player();
  let rejectPlay;
  audio.play = () => {
    audio.paused = false;
    return new Promise((_, reject) => {
      rejectPlay = reject;
    });
  };
  audio.pause = () => {
    audio.paused = true;
    rejectPlay(Object.assign(new Error("Đã dừng"), { name: "AbortError" }));
  };
  const pending = toggleAudioPlayback(audio);
  await toggleAudioPlayback(audio);
  await pending;
  assert.equal(audio.paused, true);
});

test("Lỗi trình duyệt từ chối phát không tạo unhandled rejection", async () => {
  const audio = player();
  audio.play = async () => {
    throw new Error("Playback denied");
  };
  const originalWarn = console.warn;
  let warnings = 0;
  console.warn = () => {
    warnings += 1;
  };
  try {
    await assert.doesNotReject(toggleAudioPlayback(audio));
    assert.equal(audio.paused, true);
    assert.equal(warnings, 1);
  } finally {
    console.warn = originalWarn;
  }
});
