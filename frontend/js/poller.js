class JobPoller {
  constructor(runId, { onProgress, onComplete, onError }) {
    this.runId = runId;
    this.callbacks = { onProgress, onComplete, onError };
    this.polling = false;
    this.timeoutLimit = 600; // 10 minutes (in seconds)
    this.elapsed = 0;
  }

  async poll() {
    if (!this.polling) return;

    try {
      const resp = await fetch(`/api/status/${this.runId}`);
      if (!resp.ok) throw new Error('Failed to fetch status');
      const data = await resp.json();

      if (data.error) {
        this.stop();
        this.callbacks.onError(data.error);
        return;
      }

      this.callbacks.onProgress(data.stage, data.progress);

      if (data.status === 'completed') {
        this.stop();
        this.callbacks.onComplete(data.jobs || []);
        return;
      } else if (data.status === 'failed') {
        this.stop();
        this.callbacks.onError(data.stage);
        return;
      }
    } catch (e) {
      this.stop();
      this.callbacks.onError(e.message);
      return;
    }

    this.elapsed += 2;
    if (this.elapsed >= this.timeoutLimit) {
      this.stop();
      this.callbacks.onError("Polling timed out after 10 minutes");
      return;
    }

    if (this.polling) {
      setTimeout(() => this.poll(), 2000);
    }
  }

  start() {
    this.polling = true;
    this.elapsed = 0;
    this.poll();
  }

  stop() {
    this.polling = false;
  }
}
