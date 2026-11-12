import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import { runInNewContext } from "node:vm";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const source = await readFile(
  new URL(
    "../src/features/tts/components/model-operation-status.tsx",
    import.meta.url
  ),
  "utf8"
);
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.ReactJSX,
  },
});
const exports = {};
runInNewContext(outputText, {
  exports,
  require: createRequire(import.meta.url),
});
const initial = {
  state: "idle",
  model_id: "turbo",
  percent: 0,
  done_bytes: 0,
  total_bytes: 0,
  current_file: "",
  message: "",
};
function render(status, props = {}) {
  return renderToStaticMarkup(
    createElement(exports.ModelOperationStatus, {
      busy: false,
      cancelling: false,
      error: null,
      modelName: "Turbo FP32",
      onCancel() {},
      onRetry() {},
      status: { ...initial, ...status },
      ...props,
    })
  );
}

test("Chỉ hiện % khi đã biết dung lượng tải", () => {
  const preparing = render({ state: "downloading" });
  assert.doesNotMatch(preparing, /aria-valuenow/);
  const downloading = render({
    state: "downloading",
    percent: 37,
    done_bytes: 37 * 1024 ** 2,
    total_bytes: 100 * 1024 ** 2,
  });
  assert.match(downloading, /aria-valuenow="37"/);
  assert.match(downloading, /37 MB/);
  assert.match(downloading, /Turbo FP32/);
});

test("Nạp mô hình không hiển thị 100% tải thành tiến độ áp dụng", () => {
  const applying = render({
    state: "applying",
    percent: 100,
    total_bytes: 100,
  });
  assert.match(applying, /Đang áp dụng mô hình/);
  assert.doesNotMatch(applying, /aria-valuenow|100%|Huỷ tải|vừa tải/);
});

test("GPU và huỷ tải dùng trạng thái không xác định, khoá nút khi đang huỷ", () => {
  const gpu = render({
    state: "downloading",
    phase: "gpu_setup",
    percent: 100,
    total_bytes: 100,
  });
  assert.match(gpu, /Đang cài bộ hỗ trợ GPU/);
  assert.doesNotMatch(gpu, /aria-valuenow/);
  const cancelling = render({ state: "downloading" }, { cancelling: true });
  assert.match(cancelling, /Đang huỷ/);
  assert.match(cancelling, /disabled/);
});

test("Hiện thông báo thành công, lỗi khôi phục từ server và nút thử lại", () => {
  assert.equal(render({ state: "idle" }), "");
  assert.match(
    render({ state: "ready", message: "Đã áp dụng" }),
    /Mô hình đã sẵn sàng/
  );
  const failure = render({ state: "error", message: "Không đủ bộ nhớ" });
  assert.match(failure, /role="alert"/);
  assert.match(failure, /Không đủ bộ nhớ/);
  assert.match(failure, /Thử lại/);
});
