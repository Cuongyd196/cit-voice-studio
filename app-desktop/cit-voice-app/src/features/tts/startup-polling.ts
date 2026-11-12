type StartupResult = "loading" | "ready" | "failed";

export function startStartupPolling({
  check,
  onConnectionError,
  intervalMs = 1200,
  maxFailures = 25,
}: {
  check: (signal: AbortSignal) => Promise<StartupResult>;
  onConnectionError: (error: unknown, willRetry: boolean) => void;
  intervalMs?: number;
  maxFailures?: number;
}): () => void {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let failures = 0;

  const poll = async () => {
    try {
      const result = await check(controller.signal);
      if (controller.signal.aborted || result !== "loading") {
        return;
      }
      // A responding server is healthy even if first-run model preparation is slow.
      failures = 0;
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      failures += 1;
      const willRetry = failures < maxFailures;
      onConnectionError(error, willRetry);
      if (!willRetry) {
        return;
      }
    }
    if (!controller.signal.aborted) {
      timer = setTimeout(poll, intervalMs);
    }
  };

  void poll();
  return () => {
    controller.abort();
    clearTimeout(timer);
  };
}
