"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

function load(name, overrides = {}) {
  const timers = new Map();
  let nextId = 0;
  const exports = {};
  const source = fs.readFileSync(
    path.join(__dirname, "../src/features/tts", name),
    "utf8"
  );
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
  });
  vm.runInNewContext(outputText, {
    exports,
    AbortController,
    console,
    setTimeout: (callback) => {
      timers.set(++nextId, callback);
      return nextId;
    },
    clearTimeout: (id) => timers.delete(id),
    ...overrides,
  });
  return {
    ...exports,
    timers,
    async tick() {
      const entry = timers.entries().next().value;
      assert.ok(entry, "Expected a retry or request timeout");
      timers.delete(entry[0]);
      await entry[1]();
    },
  };
}

test("first-run preparation keeps polling past 200 checks and recovers after a timeout", async () => {
  const polling = load("startup-polling.ts");
  let calls = 0;
  const errors = [];
  polling.startStartupPolling({
    check: async () => {
      calls += 1;
      if (calls === 302) {
        throw new Error("temporary timeout");
      }
      return calls < 304 ? "loading" : "ready";
    },
    onConnectionError: (_, retry) => errors.push(retry),
  });
  await new Promise(setImmediate);
  while (polling.timers.size) {
    await polling.tick();
  }
  assert.equal(calls, 304);
  assert.deepEqual(errors, [true]);
});

test("connection budget resets after a loading response; retry starts a fresh loop", async () => {
  const polling = load("startup-polling.ts");
  let calls = 0;
  const errors = [];
  const options = {
    maxFailures: 2,
    check: async () => {
      calls += 1;
      if (calls === 2) {
        return "loading";
      }
      if (calls >= 6) {
        return "ready";
      }
      throw new Error("offline");
    },
    onConnectionError: (_, retry) => errors.push(retry),
  };
  polling.startStartupPolling(options);
  await new Promise(setImmediate);
  while (polling.timers.size) {
    await polling.tick();
  }
  assert.equal(calls, 4);
  assert.deepEqual(errors, [true, true, false]);
  polling.startStartupPolling(options);
  await new Promise(setImmediate);
  await polling.tick();
  assert.equal(calls, 6);
  assert.equal(polling.timers.size, 0);
});

test("cancel during an in-flight request prevents stale retries", async () => {
  const polling = load("startup-polling.ts");
  let resolve;
  let signal;
  const stop = polling.startStartupPolling({
    check: (value) => {
      signal = value;
      return new Promise((done) => {
        resolve = done;
      });
    },
    onConnectionError: () =>
      assert.fail("cancelled check must not report errors"),
  });
  stop();
  resolve("loading");
  await new Promise(setImmediate);
  assert.equal(signal.aborted, true);
  assert.equal(polling.timers.size, 0);
});

test("explicit model failure stops polling", async () => {
  const polling = load("startup-polling.ts");
  polling.startStartupPolling({
    check: async () => "failed",
    onConnectionError: () =>
      assert.fail("model failure is not a connection error"),
  });
  await new Promise(setImmediate);
  assert.equal(polling.timers.size, 0);
});

for (const method of ["checkServerHealth", "fetchVoices"]) {
  test(`${method} times out even if headers arrive but response body stalls`, async () => {
    const requests = [];
    const api = load("api.ts", {
      fetch: async (url, { signal }) => {
        requests.push(url);
        return {
          ok: true,
          json: () =>
            new Promise((_, reject) => {
              signal.addEventListener(
                "abort",
                () => reject(new Error("aborted")),
                { once: true }
              );
            }),
        };
      },
    });
    const pending = api[method]("http://127.0.0.1:8002");
    await new Promise(setImmediate);
    const rejection = assert.rejects(pending, /aborted/);
    await api.tick();
    await rejection;
    assert.equal(requests.length, 1, "No unbounded fallback request");
    assert.equal(api.timers.size, 0);
  });
}

test("cancelling a health check aborts its network request", async () => {
  const api = load("api.ts", {
    fetch: (_, { signal }) =>
      new Promise((_, reject) => {
        signal.addEventListener("abort", () => reject(new Error("aborted")), {
          once: true,
        });
      }),
  });
  const controller = new AbortController();
  const pending = api.checkServerHealth(
    "http://127.0.0.1:8002",
    controller.signal
  );
  controller.abort();
  await assert.rejects(pending, /aborted/);
  assert.equal(api.timers.size, 0);
});
