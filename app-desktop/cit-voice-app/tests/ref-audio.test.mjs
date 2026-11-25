import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

// Logic chọn đoạn giọng mẫu (issue #2), chạy thật không cần trình duyệt.
const source = await readFile(
  new URL("../src/features/tts/ref-audio.ts", import.meta.url),
  "utf8"
);
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
});
const ref = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);

const SR = 1000; // tần số nhỏ cho test nhanh; logic tính theo giây

/** ``seconds`` giây, im lặng tới ``voiceFrom`` rồi có tiếng. */
function clip(seconds, voiceFrom = 0) {
  const s = new Float32Array(seconds * SR);
  for (let i = Math.round(voiceFrom * SR); i < s.length; i++) {
    s[i] = 0.5;
  }
  return s;
}

test("đoạn mặc định dài đúng phần mô hình dùng, bắt đầu ngay trước tiếng đầu tiên", () => {
  const sel = ref.defaultSelection(clip(60, 20), SR);
  assert.equal(sel.length, ref.REF_USED_SECONDS);
  assert.ok(Math.abs(sel.start - 19.9) < 1e-6, `start=${sel.start}`);
});

test("file ngắn hơn đoạn mặc định thì chọn cả file", () => {
  const sel = ref.defaultSelection(clip(5), SR);
  assert.deepEqual(sel, { start: 0, length: 5 });
});

test("giới hạn đoạn chọn trong file và trong 3–15 giây", () => {
  assert.deepEqual(ref.clampSelection({ start: 50, length: 10 }, 55), {
    start: 45,
    length: 10,
  });
  assert.deepEqual(ref.clampSelection({ start: -4, length: 10 }, 55), {
    start: 0,
    length: 10,
  });
  assert.equal(
    ref.clampSelection({ start: 0, length: 60 }, 120).length,
    ref.REF_MAX_SECONDS
  );
  assert.equal(
    ref.clampSelection({ start: 0, length: 1 }, 120).length,
    ref.REF_MIN_SECONDS
  );
  // File ngắn hơn mức tối thiểu: lấy cả file, không âm.
  assert.deepEqual(ref.clampSelection({ start: 1, length: 3 }, 2), {
    start: 0,
    length: 2,
  });
});

test("dạng sóng lấy biên độ đỉnh từng khoảng", () => {
  const s = new Float32Array([0, 0.2, -0.9, 0.1, 0.3, 0]);
  assert.deepEqual(
    Array.from(ref.computePeaks(s, 3)).map((v) => +v.toFixed(2)),
    [0.2, 0.9, 0.3]
  );
  assert.equal(ref.computePeaks(new Float32Array(0), 10).length, 10);
});

test("WAV chứa đúng đoạn chọn, mono 16-bit", async () => {
  const s = new Float32Array(SR * 4);
  s.fill(0.25, SR, SR * 2); // giây thứ 2 có tiếng
  const blob = ref.encodeWav(s, SR, SR, SR * 2);
  const buf = new DataView(await blob.arrayBuffer());
  assert.equal(blob.size, 44 + SR * 2);
  assert.equal(buf.getUint16(22, true), 1); // mono
  assert.equal(buf.getUint32(24, true), SR);
  assert.equal(buf.getUint16(34, true), 16);
  assert.equal(buf.getInt16(44, true), Math.round(0.25 * 0x7f_ff - 0.5));
});
