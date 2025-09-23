(() => {
  const state = {
    urls: [],
    duplicates: [],
    invalid: [],
    taskId: null,
    markdown: "",
    topics: [],
    eventSource: null,
  };

  const elements = {
    form: document.querySelector("#generation-form"),
    urlInput: document.querySelector("#url-input"),
    fileInput: document.querySelector("#file-input"),
    uploadClearBtn: document.querySelector("#upload-clear-btn"),
    includeSubtopics: document.querySelector("#include-subtopics"),
    maxRecLength: document.querySelector("#max-rec-length"),
    urlCount: document.querySelector("#url-count"),
    duplicateCount: document.querySelector("#duplicate-count"),
    invalidCount: document.querySelector("#invalid-count"),
    invalidList: document.querySelector("#invalid-list"),
    message: document.querySelector("#form-message"),
    generateBtn: document.querySelector("#generate-btn"),
    resetBtn: document.querySelector("#reset-btn"),
    downloadBtn: document.querySelector("#download-btn"),
    copyBtn: document.querySelector("#copy-btn"),
    progressBar: document.querySelector("#progress-bar"),
    progressText: document.querySelector("#progress-text"),
    statusText: document.querySelector("#status-text"),
    preview: document.querySelector("#markdown-preview"),
    rawToggle: document.querySelector("#raw-toggle"),
    rawTextarea: document.querySelector("#markdown-raw"),
    statusFooter: document.querySelector("#task-id-display"),
    topicsDisplay: document.querySelector("#topics-display"),
    connectionStatus: document.querySelector("#connection-status"),
  };

  const TRACKING_PREFIXES = ["utm_", "utm-", "ref", "gclid", "fbclid"];
  const MAX_FILE_SIZE = 5 * 1024 * 1024;

  function setMessage(text, level = "info") {
    if (!elements.message) return;
    elements.message.textContent = text ?? "";
    elements.message.className = "";
    if (text) {
      elements.message.classList.add(level === "error" ? "error" : level === "success" ? "success" : "info");
    }
  }

  function updateConnectionStatus(text, variant = "info") {
    const pill = elements.connectionStatus;
    if (!pill) return;
    pill.textContent = text;
    pill.className = `status-pill ${variant}`;
  }

  function normaliseUrl(raw) {
    const url = new URL(raw.trim());
    url.protocol = url.protocol.toLowerCase();
    url.hostname = url.hostname.toLowerCase();
    url.pathname = url.pathname.replace(/\/{2,}/g, "/");
    if (url.pathname.length > 1) {
      url.pathname = url.pathname.replace(/\/$/, "");
    }
    const params = Array.from(url.searchParams.entries()).filter(([key]) => {
      const lowered = key.toLowerCase();
      return !TRACKING_PREFIXES.some((prefix) => lowered.startsWith(prefix));
    });
    params.sort(([a], [b]) => a.localeCompare(b));
    const search = new URLSearchParams(params);
    url.search = search.toString();
    url.hash = "";
    return url.toString();
  }

  function analyseInput(text) {
    const urls = [];
    const invalid = [];
    const seen = new Map();
    const duplicates = new Set();

    text.split(/\r?\n/).forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) {
        return;
      }
      try {
        const normalised = normaliseUrl(trimmed);
        if (seen.has(normalised)) {
          duplicates.add(normalised);
        } else {
          seen.set(normalised, true);
          urls.push(normalised);
        }
      } catch (error) {
        invalid.push(trimmed);
      }
    });

    return { urls, invalid, duplicates: Array.from(duplicates) };
  }

  function updateStats(stats) {
    const { urls, invalid, duplicates } = stats;
    elements.urlCount.textContent = `${urls.length} URL${urls.length === 1 ? "" : "s"}`;
    elements.duplicateCount.textContent = `${duplicates.length} duplicate${duplicates.length === 1 ? "" : "s"}`;
    elements.invalidCount.textContent = `${invalid.length} invalid`;
    renderInvalidList(invalid);
  }

  function renderInvalidList(invalid) {
    if (!elements.invalidList) return;
    if (!invalid.length) {
      elements.invalidList.hidden = true;
      elements.invalidList.innerHTML = "";
      return;
    }
    elements.invalidList.hidden = false;
    elements.invalidList.innerHTML = invalid.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function handleInputChange() {
    const stats = analyseInput(elements.urlInput.value);
    state.urls = stats.urls;
    state.invalid = stats.invalid;
    state.duplicates = stats.duplicates;
    updateStats(stats);
  }

  function resetPreview() {
    state.markdown = "";
    state.topics = [];
    elements.preview.innerHTML = '<p class="empty-message">Generated markdown will appear here once the task completes.</p>';
    elements.rawTextarea.value = "";
    elements.rawToggle.hidden = true;
    elements.downloadBtn.disabled = true;
    elements.copyBtn.disabled = true;
    elements.progressBar.value = 0;
    elements.progressBar.max = 1;
    elements.progressText.textContent = "";
    elements.statusText.textContent = "Waiting for input…";
    elements.statusText.className = "";
    elements.statusFooter.textContent = "Task: —";
    elements.topicsDisplay.textContent = "";
    updateConnectionStatus("Idle", "info");
  }

  function resetAll() {
    elements.form.reset();
    elements.urlInput.value = "";
    elements.fileInput.value = "";
    state.urls = [];
    state.invalid = [];
    state.duplicates = [];
    state.taskId = null;
    closeEventStream();
    setMessage("");
    renderInvalidList([]);
    updateStats({ urls: [], invalid: [], duplicates: [] });
    resetPreview();
  }

  function setLoading(isLoading) {
    elements.generateBtn.disabled = isLoading;
    elements.resetBtn.disabled = isLoading;
    elements.generateBtn.textContent = isLoading ? "Starting…" : "Generate newsletter";
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const stats = analyseInput(elements.urlInput.value);
    if (!stats.urls.length) {
      setMessage("Add at least one valid URL before generating.", "error");
      return;
    }

    state.urls = stats.urls;
    state.invalid = stats.invalid;
    state.duplicates = stats.duplicates;
    setMessage("");
    setLoading(true);
    resetPreview();
    updateConnectionStatus("Connecting…", "info");

    const payload = { urls: state.urls };
    const options = {};
    if (elements.includeSubtopics.checked) {
      options.include_subtopics = true;
    }
    const maxLength = parseInt(elements.maxRecLength.value, 10);
    if (!Number.isNaN(maxLength) && maxLength > 0) {
      options.max_recommendation_length = maxLength;
    }
    if (Object.keys(options).length) {
      payload.options = options;
    }

    try {
      const response = await fetch("/api/v1/newsletter/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const detail = await safeJson(response);
        throw new Error(detail?.detail ?? "Failed to enqueue task");
      }

      const data = await response.json();
      state.taskId = data.task_id;
      elements.statusFooter.textContent = `Task: ${state.taskId}`;
      setMessage("Task started. Tracking progress…", "success");
      openEventStream(state.taskId);
    } catch (error) {
      setMessage(error?.message ?? "Unable to start task.", "error");
      updateConnectionStatus("Disconnected", "error");
    } finally {
      setLoading(false);
    }
  }

  async function safeJson(response) {
    try {
      return await response.json();
    } catch (error) {
      return null;
    }
  }

  async function handleFileUpload(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setMessage("File exceeds 5MB limit.", "error");
      event.target.value = "";
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    setMessage(`Uploading ${file.name}…`, "info");

    try {
      const response = await fetch("/api/v1/newsletter/upload", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const detail = await safeJson(response);
        throw new Error(detail?.detail ?? "Upload failed.");
      }
      const data = await response.json();
      elements.urlInput.value = data.urls.join("\n");
      handleInputChange();
      if (Array.isArray(data.invalid_urls) && data.invalid_urls.length) {
        renderInvalidList(data.invalid_urls);
      }
      const invalidCount = data.invalid_urls?.length ?? 0;
      setMessage(
        `Parsed ${data.urls.length} URL${data.urls.length === 1 ? "" : "s"}${invalidCount ? ` • ${invalidCount} invalid skipped` : ""}.`,
        "success",
      );
    } catch (error) {
      setMessage(error?.message ?? "Failed to process upload.", "error");
    }
  }

  function updateStatus(payload) {
    if (!payload) return;
    const { status, progress, error } = payload;

    elements.statusText.textContent = statusLabel(status, error);
    elements.statusText.className = status;

    const total = progress?.total_urls ?? 0;
    const processed = progress?.processed ?? 0;
    const failed = progress?.failed ?? 0;
    elements.progressBar.max = Math.max(total, 1);
    elements.progressBar.value = Math.min(processed, elements.progressBar.max);

    if (total > 0) {
      const percent = Math.round((processed / total) * 100);
      const failureSuffix = failed ? ` • failed: ${failed}` : "";
      elements.progressText.textContent = `${processed}/${total} processed (${percent}%)${failureSuffix}`;
    } else {
      elements.progressText.textContent = "";
    }

    if (status === "completed") {
      updateConnectionStatus("Completed", "success");
    } else if (status === "failed") {
      updateConnectionStatus("Failed", "error");
      if (error) {
        setMessage(error, "error");
      }
    } else {
      updateConnectionStatus("Streaming", "info");
    }
  }

  function statusLabel(status, error) {
    switch (status) {
      case "processing":
        return "Processing…";
      case "completed":
        return "Completed";
      case "failed":
        return error ? `Failed: ${error}` : "Failed";
      default:
        return "Pending";
    }
  }

  function openEventStream(taskId) {
    closeEventStream();
    try {
      const source = new EventSource(`/api/v1/newsletter/events/${taskId}`);
      state.eventSource = source;

      source.onopen = () => {
        updateConnectionStatus("Connected", "success");
      };

      source.addEventListener("status", async (event) => {
        const payload = JSON.parse(event.data);
        updateStatus(payload);
        if (payload.status === "completed") {
          await fetchResult(taskId);
        } else if (payload.status === "failed") {
          closeEventStream();
        }
      });

      source.addEventListener("end", async (event) => {
        const payload = JSON.parse(event.data);
        updateStatus(payload);
        if (payload.status === "completed") {
          await fetchResult(taskId);
        }
        closeEventStream();
      });

      source.onerror = () => {
        updateConnectionStatus("Disconnected", "warning");
        source.close();
        state.eventSource = null;
      };
    } catch (error) {
      updateConnectionStatus("Disconnected", "error");
      setMessage("Unable to establish SSE connection.", "error");
    }
  }

  function closeEventStream() {
    if (state.eventSource) {
      state.eventSource.close();
      state.eventSource = null;
    }
  }

  async function fetchResult(taskId) {
    try {
      const response = await fetch(`/api/v1/newsletter/result/${taskId}`);
      if (!response.ok) {
        const detail = await safeJson(response);
        throw new Error(detail?.detail ?? "Result not available.");
      }
      const data = await response.json();
      state.markdown = data.markdown_content ?? "";
      state.topics = data.metadata?.topics ?? [];
      renderMarkdown(state.markdown);
      renderTopics(state.topics, data.metadata?.total_processed ?? 0);
      setMessage("Markdown ready!", "success");
    } catch (error) {
      setMessage(error?.message ?? "Unable to fetch result.", "error");
    }
  }

  function renderMarkdown(markdown) {
    if (!markdown) {
      resetPreview();
      return;
    }
    const parsed = typeof marked !== "undefined" ? marked.parse(markdown) : markdown;
    const safeHtml = typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(parsed) : parsed;
    elements.preview.innerHTML = safeHtml;
    elements.rawTextarea.value = markdown;
    elements.rawToggle.hidden = false;
    elements.downloadBtn.disabled = false;
    elements.copyBtn.disabled = false;
  }

  function renderTopics(topics, total) {
    if (!topics || !topics.length) {
      elements.topicsDisplay.textContent = "";
      return;
    }
    elements.topicsDisplay.textContent = `Topics (${total} total): ${topics.join(", ")}`;
  }

  function handleDownload() {
    if (!state.markdown) {
      return;
    }
    const blob = new Blob([state.markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `newsletter_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async function handleCopy() {
    if (!state.markdown) {
      return;
    }
    try {
      await navigator.clipboard.writeText(state.markdown);
      setMessage("Markdown copied to clipboard!", "success");
    } catch (error) {
      setMessage("Clipboard copy failed.", "error");
    }
  }

  elements.urlInput.addEventListener("input", handleInputChange);
  elements.form.addEventListener("submit", handleSubmit);
  elements.fileInput.addEventListener("change", handleFileUpload);
  elements.uploadClearBtn.addEventListener("click", () => {
    elements.fileInput.value = "";
    renderInvalidList([]);
    setMessage("Upload selection cleared.");
  });
  elements.resetBtn.addEventListener("click", resetAll);
  elements.downloadBtn.addEventListener("click", handleDownload);
  elements.copyBtn.addEventListener("click", handleCopy);

  window.addEventListener("beforeunload", () => {
    closeEventStream();
  });

  // Initialise UI state
  resetPreview();
  handleInputChange();
})();
