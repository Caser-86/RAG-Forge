(function () {
  "use strict";

  const state = {
    apiKey: "",
    latestTraceId: "",
    lastQuery: "",
    history: [],
    requestSerial: 0,
    activeController: null,
  };

  const $ = (id) => document.getElementById(id);
  const conversation = $("conversation");
  const queryInput = $("queryInput");
  const sendButton = $("sendButton");
  const retryButton = $("retryButton");
  const saveButton = $("saveButton");
  const modelSelect = $("modelSelect");
  const errorMessage = $("errorMessage");
  const MAX_HISTORY_MESSAGES = 20;
  const MAX_HISTORY_CHARS = 12000;
  const MAX_HISTORY_ITEM_CHARS = 2000;
  let isComposing = false;

  function setError(message) {
    errorMessage.textContent = message || "";
    errorMessage.hidden = !message;
    retryButton.hidden = !message || !state.lastQuery;
  }

  function setHealth(status, text) {
    const dot = $("healthDot");
    dot.className = "health-dot" + (status === "error" ? " is-error" : status === "pending" ? " is-pending" : "");
    $("healthText").textContent = text;
  }

  function headers() {
    const result = { "Content-Type": "application/json" };
    if (state.apiKey) result["X-API-Key"] = state.apiKey;
    return result;
  }

  function formatErrorDetail(detail) {
    if (Array.isArray(detail)) {
      return detail.map((item) => {
        if (item && typeof item.msg === "string") return item.msg;
        return typeof item === "string" ? item : "请求参数无效";
      }).join("；");
    }
    return typeof detail === "string" ? detail : "服务请求失败";
  }

  async function requestJson(url, options) {
    const opts = options || {};
    const response = await fetch(url, { ...opts, headers: { ...headers(), ...(opts.headers || {}) } });
    let body = {};
    try { body = await response.json(); } catch (_) { body = {}; }
    if (!response.ok) throw new Error(formatErrorDetail(body.detail) + "（HTTP " + response.status + "）");
    return body;
  }

  function boundedHistory() {
    let remaining = MAX_HISTORY_CHARS;
    const result = [];
    for (let index = state.history.length - 1; index >= 0 && result.length < MAX_HISTORY_MESSAGES; index -= 1) {
      const item = state.history[index];
      if (!item || (item.role !== "user" && item.role !== "assistant")) continue;
      const raw = String(item.content || "");
      if (!raw || remaining <= 0) continue;
      const itemLimit = Math.min(MAX_HISTORY_ITEM_CHARS, remaining);
      const clipped = raw.length > itemLimit;
      const content = clipped
        ? "[历史消息已裁剪]\n" + raw.slice(raw.length - Math.max(0, itemLimit - 10))
        : raw;
      if (!content.trim()) continue;
      result.unshift({ role: item.role, content });
      remaining -= content.length;
    }
    return result;
  }

  function resetRequestState() {
    if (state.activeController) state.activeController.abort();
    state.activeController = null;
    state.requestSerial += 1;
    sendButton.disabled = modelSelect.disabled;
  }

  function switchView(view) {
    document.querySelectorAll("[data-view-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.viewPanel !== view;
      panel.classList.toggle("is-active", panel.dataset.viewPanel === view);
    });
    document.querySelectorAll(".view-tab").forEach((tab) => {
      const active = tab.dataset.view === view;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
    });
  }

  function configureModels(catalog) {
    modelSelect.replaceChildren();
    const models = Array.isArray(catalog.generation) ? catalog.generation : [];
    models.forEach((model) => {
      const option = document.createElement("option");
      option.value = model;
      option.textContent = model;
      modelSelect.append(option);
    });
    modelSelect.disabled = models.length === 0;
    sendButton.disabled = models.length === 0;
    $("modelHint").textContent = models.length ? (models.length + " 个可用 allowlist 模型") : "没有发现可用生成模型";
    if (catalog.reranker_available === false && catalog.reranker_enabled) {
      const rerankOption = document.querySelector('#modeSelect option[value="hybrid_rerank"]');
      if (rerankOption) rerankOption.textContent = "Hybrid + Rerank · 当前不可用";
    }
  }

  async function bootstrap() {
    setHealth("pending", "CONNECTING");
    const [modelsResult, healthResult] = await Promise.allSettled([
      requestJson("/api/models"),
      requestJson("/api/health"),
    ]);
    if (modelsResult.status === "fulfilled") {
      configureModels(modelsResult.value);
    } else {
      modelSelect.replaceChildren();
      modelSelect.disabled = true;
      sendButton.disabled = true;
      $("modelHint").textContent = modelsResult.reason.message;
    }
    if (healthResult.status === "fulfilled") {
      setHealth("ok", "READY · " + (healthResult.value.indexed_chunks || 0) + " CHUNKS");
    } else {
      setHealth("error", "OFFLINE");
    }
    if (modelsResult.status === "rejected" && healthResult.status === "rejected") {
      setError("无法连接本地 API：" + modelsResult.reason.message);
    } else {
      setError("");
    }
  }

  function addMessage(kind, text, label) {
    $("emptyState")?.remove();
    const article = document.createElement("article");
    article.className = "message " + kind;
    const marker = document.createElement("span");
    marker.className = "message-label";
    marker.textContent = label;
    const body = document.createElement("div");
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    body.append(paragraph);
    article.append(marker, body);
    conversation.append(article);
    return { article, body };
  }

  function safeHttpUrl(raw) {
    if (typeof raw !== "string" || !raw.trim()) return null;
    try {
      const parsed = new URL(raw, window.location.origin);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
      if (raw.trim().toLowerCase().startsWith("javascript:")) return null;
      return parsed.href;
    } catch (_) { return null; }
  }

  function renderCitations(body, details) {
    if (!Array.isArray(details) || !details.length) return;
    const list = document.createElement("div");
    list.className = "citation-list";
    details.forEach((detail) => {
      const url = safeHttpUrl(detail.url);
      const chip = url ? document.createElement("a") : document.createElement("span");
      chip.className = "citation-chip";
      if (url) {
        chip.href = url;
        chip.target = "_blank";
        chip.rel = "noopener noreferrer";
      }
      const index = document.createElement("strong");
      index.textContent = "[" + String(detail.index || "?") + "]";
      const title = document.createElement("small");
      title.textContent = detail.title || detail.source || detail.chunk_id || "stored evidence";
      chip.append(index, title);
      list.append(chip);
    });
    body.append(list);
  }

  function renderAnswer(body, answer) {
    body.replaceChildren();
    const paragraph = document.createElement("p");
    paragraph.textContent = answer.answer || "";
    body.append(paragraph);
    renderCitations(body, answer.citation_details);
    if (answer.refused) {
      const note = document.createElement("span");
      note.className = "refusal-note";
      note.textContent = "REFUSED · " + (answer.refusal_reason || "evidence gate");
      body.append(note);
    }
    const meta = document.createElement("small");
    meta.className = "control-note";
    const supportNote = answer.citation_support_status === "unverified"
      ? " · 事实支撑未人工审核"
      : answer.citation_support_status === "verified" ? " · 事实支撑已审核" : "";
    meta.textContent = "模型：" + (answer.model || "unknown")
      + (answer.grounded ? " · 引用编号已校验" : "") + supportNote;
    body.append(meta);
  }

  async function loadTrace(traceId, serial) {
    if (!traceId) return;
    try {
      const record = await requestJson("/api/traces/" + encodeURIComponent(traceId));
      if (serial !== state.requestSerial && serial !== 0) return;
      state.latestTraceId = traceId;
      renderTrace(record);
    } catch (error) {
      if (serial === state.requestSerial || serial === 0) setError("回答已返回，但 Trace 不可用：" + error.message);
    }
  }

  function renderTrace(record) {
    switchView("debug");
    $("debugEmpty").hidden = true;
    $("debugContent").hidden = false;
    $("debugTraceId").textContent = record.trace_id || "unknown trace";
    const timings = record.timings || {};
    const metrics = $("debugMetrics");
    metrics.replaceChildren();
    ["embedding", "dense", "sparse", "fusion", "rerank", "generation", "total"].forEach((name) => {
      const item = document.createElement("div");
      item.className = "metric";
      const value = document.createElement("strong");
      value.textContent = timings[name] == null ? "—" : Number(timings[name]).toFixed(1) + "ms";
      const label = document.createElement("span");
      label.textContent = name;
      item.append(value, label);
      metrics.append(item);
    });
    const candidates = $("debugCandidates");
    candidates.replaceChildren();
    (Array.isArray(record.candidates) ? record.candidates : []).forEach((candidate) => {
      const row = document.createElement("div");
      row.className = "candidate";
      const info = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = candidate.title || candidate.chunk_id || "evidence";
      const source = document.createElement("small");
      source.textContent = candidate.source || candidate.document_id || "stored source";
      info.append(title, source);
      const score = document.createElement("span");
      score.className = "candidate-score";
      score.textContent = candidate.rerank_score != null ? "rerank " + Number(candidate.rerank_score).toFixed(4) : candidate.fused_score != null ? "rrf " + Number(candidate.fused_score).toFixed(4) : candidate.dense_score != null ? "cos " + Number(candidate.dense_score).toFixed(4) : "unscored";
      row.append(info, score);
      candidates.append(row);
    });
    $("debugContext").textContent = record.final_context || "（本次没有发送 context）";
    $("debugRaw").textContent = record.raw_output || "（没有原始模型输出；可能在生成前拒答）";
  }

  async function submit(event) {
    event.preventDefault();
    const query = queryInput.value.trim();
    if (!query || modelSelect.disabled) return;
    if (state.activeController) state.activeController.abort();
    const serial = ++state.requestSerial;
    state.lastQuery = query;
    state.activeController = new AbortController();
    setError("");
    addMessage("user", query, "YOU");
    const pending = addMessage("assistant pending", "检索本地证据…", "RAG-FORGE");
    sendButton.disabled = true;
    try {
      const answer = await requestJson("/api/chat", {
        method: "POST",
        signal: state.activeController.signal,
        body: JSON.stringify({
          query,
          generation_model: modelSelect.value,
          retrieval_mode: $("modeSelect").value,
          top_k: Number($("topK").value),
          rewrite: $("rewriteToggle").checked,
          history: boundedHistory(),
        }),
      });
      if (serial !== state.requestSerial) return;
      pending.article.classList.remove("pending");
      renderAnswer(pending.body, answer);
      state.history.push({ role: "user", content: query });
      state.history.push({ role: "assistant", content: answer.answer || "" });
      state.history = state.history.slice(-20);
      state.latestTraceId = answer.trace_id || "";
      saveButton.disabled = !state.latestTraceId;
      queryInput.value = "";
      await loadTrace(state.latestTraceId, serial);
      switchView("chat");
    } catch (error) {
      if (error.name === "AbortError" || serial !== state.requestSerial) return;
      pending.article.remove();
      setError(error.message);
    } finally {
      if (serial === state.requestSerial) {
        sendButton.disabled = modelSelect.disabled;
        state.activeController = null;
      }
    }
  }

  $("chatForm").addEventListener("submit", submit);
  queryInput.addEventListener("keydown", (event) => {
    if (isComposing || event.isComposing) return;
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("chatForm").requestSubmit(); }
  });
  queryInput.addEventListener("compositionstart", () => { isComposing = true; });
  queryInput.addEventListener("compositionend", () => { isComposing = false; });
  $("clearButton").addEventListener("click", () => {
    resetRequestState();
    state.history = [];
    state.latestTraceId = "";
    state.lastQuery = "";
    saveButton.disabled = true;
    queryInput.value = "";
    conversation.replaceChildren();
    const empty = document.createElement("div");
    empty.id = "emptyState";
    empty.className = "empty-state";
    empty.textContent = "会话已清空。输入一个问题，重新开始。";
    conversation.append(empty);
    setError("");
  });
  retryButton.addEventListener("click", () => {
    queryInput.value = state.lastQuery;
    $("chatForm").requestSubmit();
  });
  saveButton.addEventListener("click", async () => {
    if (!state.latestTraceId) return;
    try {
      const response = await fetch("/api/export/" + encodeURIComponent(state.latestTraceId) + "?format=markdown", {
        headers: headers(),
      });
      if (!response.ok) {
        let body = {};
        try { body = await response.json(); } catch (_) { body = {}; }
        throw new Error(formatErrorDetail(body.detail) + "（HTTP " + response.status + "）");
      }
      const blob = await response.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "ragforge-result.md";
      document.body.append(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);
    } catch (error) {
      setError("结果保存失败：" + error.message);
    }
  });
  $("saveKeyButton").addEventListener("click", () => {
    state.apiKey = $("apiKeyInput").value.trim();
    $("settingsNotice").textContent = state.apiKey ? "已在当前页内存启用" : "当前未设置 key";
    bootstrap();
  });
  $("clearKeyButton").addEventListener("click", () => {
    state.apiKey = "";
    $("apiKeyInput").value = "";
    $("settingsNotice").textContent = "已清除";
    bootstrap();
  });
  document.querySelectorAll(".view-tab").forEach((tab) => tab.addEventListener("click", () => switchView(tab.dataset.view)));
  bootstrap();
}());
