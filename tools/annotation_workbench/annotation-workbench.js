(() => {
  "use strict";

  const PROFILE_TYPES = JSON.parse(document.getElementById("profileData").textContent);
  const STORAGE_PREFIX = "signalminer.annotation-workbench.v1";
  const PSEUDONYM_KEY = `${STORAGE_PREFIX}.pseudonym`;
  const TASK_FIELDS = new Set([
    "dataset_id", "sample_id", "annotator_slot", "split", "annotation_mode",
    "redacted_text", "content_hash", "task_hash", "profile", "suggestion", "fixture",
  ]);
  const PACK_FIELDS = new Set([
    "schema_version", "dataset_id", "split", "annotator_slot", "annotation_mode",
    "tasks", "fixture",
  ]);
  const ANNOTATION_FIELDS = new Set([
    "annotation_id", "dataset_id", "sample_id", "annotator_slot",
    "annotator_pseudonym", "annotation_mode", "has_signals", "signal_count",
    "signals", "review_action", "started_at", "completed_at", "task_hash",
    "content_hash", "fixture",
  ]);
  const SIGNAL_FIELDS = new Set([
    "signal_type", "summary", "evidence_spans", "implicit_need",
    "implicit_need_has_basis", "hallucination", "notes",
  ]);
  const EVIDENCE_FIELDS = new Set(["start", "end", "text"]);
  const FORBIDDEN_SUGGESTION_KEYS = /prediction|model|provider|prompt|confidence|score/i;

  const TYPE_LABELS = {
    feature_request: "功能请求",
    bug_report: "缺陷报告",
    usability_issue: "易用性问题",
    question: "产品问题",
    praise: "具体表扬",
    complaint: "具体投诉",
    churn_risk: "流失风险",
    viral_hook: "爆款钩子",
    content_pattern: "内容模式",
    visual_technique: "视觉技术",
    audio_strategy: "音频策略",
    engagement_trigger: "互动触发",
    platform_algorithm: "平台算法",
    topic_trend: "话题趋势",
    monetization_pattern: "变现模式",
  };

  const DEMO_ASSISTED_PACK = {
    schema_version: "1.0.0",
    dataset_id: "demo_annotation_training",
    split: "development",
    annotator_slot: "assisted",
    annotation_mode: "assisted_review",
    fixture: true,
    tasks: [
      {
        dataset_id: "demo_annotation_training",
        sample_id: "demo_product_001",
        annotator_slot: "assisted",
        split: "development",
        annotation_mode: "assisted_review",
        redacted_text: "希望支持批量导出，同时修复点击提交后偶尔没有反应的问题。",
        content_hash: "1111111111111111111111111111111111111111111111111111111111111111",
        task_hash: "2111111111111111111111111111111111111111111111111111111111111111",
        profile: "product_feedback",
        suggestion: {
          suggestion_label: "suggestion_only",
          suggested_signals: [
            {
              signal_type: "feature_request",
              summary: "用户希望批量导出",
              evidence_spans: [{ start: 0, end: 8, text: "希望支持批量导出" }],
              implicit_need: null,
              implicit_need_has_basis: false,
              hallucination: false,
            },
          ],
        },
        fixture: true,
      },
      {
        dataset_id: "demo_annotation_training",
        sample_id: "demo_product_002",
        annotator_slot: "assisted",
        split: "development",
        annotation_mode: "assisted_review",
        redacted_text: "不错，谢谢。",
        content_hash: "3111111111111111111111111111111111111111111111111111111111111111",
        task_hash: "4111111111111111111111111111111111111111111111111111111111111111",
        profile: "product_feedback",
        suggestion: { suggestion_label: "suggestion_only", suggested_signals: [] },
        fixture: true,
      },
    ],
  };

  const DEMO_BLIND_PACK = {
    schema_version: "1.0.0",
    dataset_id: "demo_annotation_training",
    split: "test",
    annotator_slot: "A",
    annotation_mode: "blind",
    fixture: true,
    tasks: [
      {
        dataset_id: "demo_annotation_training",
        sample_id: "demo_blind_001",
        annotator_slot: "A",
        split: "test",
        annotation_mode: "blind",
        redacted_text: "观众在视频第7秒开始流失，需要把冲突放到前3秒。",
        content_hash: "5111111111111111111111111111111111111111111111111111111111111111",
        task_hash: "6111111111111111111111111111111111111111111111111111111111111111",
        profile: "aigc_video",
        suggestion: null,
        fixture: true,
      },
      {
        dataset_id: "demo_annotation_training",
        sample_id: "demo_blind_emoji",
        annotator_slot: "A",
        split: "test",
        annotation_mode: "blind",
        redacted_text: "开头用🎬快速切换三个场景，完播率明显提高。",
        content_hash: "7111111111111111111111111111111111111111111111111111111111111111",
        task_hash: "8111111111111111111111111111111111111111111111111111111111111111",
        profile: "aigc_video",
        suggestion: null,
        fixture: true,
      },
    ],
  };

  const dom = Object.fromEntries([
    "packInput", "annotationInput", "exportJsonButton", "exportCsvButton",
    "clearWorkspaceButton", "batchLabel", "modeBadge", "taskCountLabel",
    "progressLabel", "progressPercent", "progressFill", "taskList", "emptyState",
    "taskWorkspace", "blindBanner", "samplePosition", "sampleTitle", "sampleMeta",
    "characterCount", "sourceText", "selectionPreview", "addEvidenceButton",
    "suggestionPanel", "suggestionContent", "applySuggestionButton",
    "previousTaskButton", "nextTaskButton", "pseudonymInput", "identityGeneratorToggle",
    "identityGenerator", "identitySeedInput", "generatePseudonymButton", "signalDecision",
    "reviewActionBlock", "signalEditor", "addSignalButton", "validationSummary",
    "saveDraftButton", "completeTaskButton", "saveState", "toast",
    "demoAssistedButton", "demoBlindButton",
  ].map((id) => [id, document.getElementById(id)]));

  const state = {
    packs: [],
    tasks: [],
    activeIndex: 0,
    activeSignalIndex: 0,
    drafts: {},
    filter: "all",
    selectedSpan: null,
    storageKey: null,
    toastTimer: null,
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function codePointLength(text) {
    return Array.from(text).length;
  }

  function codePointSlice(text, start, end) {
    return Array.from(text).slice(start, end).join("");
  }

  function simpleHash(text) {
    let hash = 2166136261;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16).padStart(8, "0");
  }

  function randomId() {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID().replaceAll("-", "");
    return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
  }

  function taskKey(task) {
    return `${task.dataset_id}|${task.sample_id}|${task.annotator_slot}`;
  }

  function activeTask() {
    return state.tasks[state.activeIndex] ?? null;
  }

  function activeDraft() {
    const task = activeTask();
    return task ? state.drafts[taskKey(task)] ?? null : null;
  }

  function createDraft(task) {
    return {
      annotation_id: `ann_${task.sample_id}_${task.annotator_slot}_${randomId().slice(0, 10)}`,
      dataset_id: task.dataset_id,
      sample_id: task.sample_id,
      annotator_slot: task.annotator_slot,
      annotator_pseudonym: "",
      annotation_mode: task.annotation_mode,
      has_signals: null,
      signal_count: 0,
      signals: [],
      review_action: null,
      started_at: nowIso(),
      completed_at: null,
      task_hash: task.task_hash,
      content_hash: task.content_hash,
      fixture: Boolean(task.fixture),
    };
  }

  function ensureDraft(task = activeTask()) {
    if (!task) return null;
    const key = taskKey(task);
    if (!state.drafts[key]) state.drafts[key] = createDraft(task);
    return state.drafts[key];
  }

  function markDirty(draft = activeDraft()) {
    if (!draft) return;
    draft.completed_at = null;
    dom.saveState.textContent = "有未完成修改";
    dom.saveState.classList.remove("saved");
    persistWorkspace();
    renderTaskList();
    renderProgress();
  }

  function showToast(message, isError = false) {
    clearTimeout(state.toastTimer);
    dom.toast.textContent = message;
    dom.toast.classList.toggle("error", isError);
    dom.toast.classList.add("visible");
    state.toastTimer = setTimeout(() => dom.toast.classList.remove("visible"), 3200);
  }

  function unknownKeys(object, allowed) {
    if (!object || typeof object !== "object" || Array.isArray(object)) return [];
    return Object.keys(object).filter((key) => !allowed.has(key));
  }

  function findForbiddenKeys(value, path = "$") {
    const hits = [];
    if (Array.isArray(value)) {
      value.forEach((item, index) => hits.push(...findForbiddenKeys(item, `${path}[${index}]`)));
    } else if (value && typeof value === "object") {
      Object.entries(value).forEach(([key, child]) => {
        if (FORBIDDEN_SUGGESTION_KEYS.test(key)) hits.push(`${path}.${key}`);
        hits.push(...findForbiddenKeys(child, `${path}.${key}`));
      });
    }
    return hits;
  }

  function validatePack(pack, fileName = "任务包") {
    const errors = [];
    if (!pack || typeof pack !== "object" || Array.isArray(pack)) {
      return [`${fileName}：顶层必须是JSON对象`];
    }
    const extraPackFields = unknownKeys(pack, PACK_FIELDS);
    if (extraPackFields.length) errors.push(`${fileName}：未知顶层字段 ${extraPackFields.join(", ")}`);
    if (!Array.isArray(pack.tasks) || pack.tasks.length === 0) {
      errors.push(`${fileName}：tasks必须是非空数组`);
      return errors;
    }
    if (!pack.dataset_id || !pack.annotator_slot || !pack.annotation_mode) {
      errors.push(`${fileName}：缺少dataset_id、annotator_slot或annotation_mode`);
    }
    if (!new Set(["A", "B", "assisted"]).has(pack.annotator_slot)) {
      errors.push(`${fileName}：annotator_slot必须是A、B或assisted`);
    }
    if (!new Set(["blind", "assisted_review"]).has(pack.annotation_mode)) {
      errors.push(`${fileName}：annotation_mode不受支持`);
    }
    pack.tasks.forEach((task, index) => {
      const prefix = `${fileName} tasks[${index}]`;
      if (!task || typeof task !== "object" || Array.isArray(task)) {
        errors.push(`${prefix}不是对象`);
        return;
      }
      const extras = unknownKeys(task, TASK_FIELDS);
      if (extras.length) errors.push(`${prefix}包含未知字段 ${extras.join(", ")}`);
      ["dataset_id", "sample_id", "annotator_slot", "split", "annotation_mode",
        "redacted_text", "content_hash", "task_hash", "profile"].forEach((field) => {
        if (typeof task[field] !== "string" || !task[field]) errors.push(`${prefix}.${field}缺失或无效`);
      });
      if (task.dataset_id !== pack.dataset_id) errors.push(`${prefix}.dataset_id与任务包不一致`);
      if (task.annotator_slot !== pack.annotator_slot) errors.push(`${prefix}.annotator_slot与任务包不一致`);
      if (task.annotation_mode !== pack.annotation_mode) errors.push(`${prefix}.annotation_mode与任务包不一致`);
      if (!PROFILE_TYPES[task.profile]) errors.push(`${prefix}.profile=${task.profile}不受支持`);
      if (task.annotation_mode === "blind" && task.suggestion !== null) {
        errors.push(`${prefix}为盲标任务，但suggestion不是null`);
      }
      if (task.suggestion) {
        const leaks = findForbiddenKeys(task.suggestion, `${prefix}.suggestion`);
        if (leaks.length) errors.push(`${prefix}含禁止展示字段：${leaks.join(", ")}`);
      }
    });
    return errors;
  }

  function normalizePacks(packs) {
    const first = packs[0];
    const errors = [];
    const tasks = [];
    const seen = new Set();
    packs.forEach((pack, index) => {
      if (pack.dataset_id !== first.dataset_id) errors.push(`第${index + 1}个任务包dataset_id不同`);
      if (pack.annotator_slot !== first.annotator_slot) errors.push("A、B或assisted任务包不能混在同一工作区");
      if (pack.annotation_mode !== first.annotation_mode) errors.push("blind和assisted-review任务包不能混用");
      if (Boolean(pack.fixture) !== Boolean(first.fixture)) errors.push("fixture和真实任务包不能混用");
      pack.tasks.forEach((task) => {
        const key = taskKey(task);
        if (seen.has(key)) errors.push(`任务重复：${task.sample_id}/${task.annotator_slot}`);
        seen.add(key);
        tasks.push(task);
      });
    });
    return { errors, tasks };
  }

  function workspaceStorageKey(tasks) {
    const signature = tasks.map((task) => task.task_hash).join("|");
    const first = tasks[0];
    return `${STORAGE_PREFIX}.${first.dataset_id}.${first.annotator_slot}.${simpleHash(signature)}`;
  }

  function persistWorkspace() {
    if (!state.storageKey) return;
    const payload = {
      activeTaskKey: activeTask() ? taskKey(activeTask()) : null,
      drafts: state.drafts,
      savedAt: nowIso(),
    };
    localStorage.setItem(state.storageKey, JSON.stringify(payload));
  }

  function restoreWorkspace() {
    state.drafts = {};
    if (!state.storageKey) return;
    try {
      const payload = JSON.parse(localStorage.getItem(state.storageKey) || "null");
      if (!payload?.drafts) return;
      const taskMap = new Map(state.tasks.map((task) => [taskKey(task), task]));
      Object.entries(payload.drafts).forEach(([key, draft]) => {
        const task = taskMap.get(key);
        if (!task) return;
        if (draft.task_hash === task.task_hash && draft.content_hash === task.content_hash
            && draft.annotation_mode === task.annotation_mode
            && Boolean(draft.fixture) === Boolean(task.fixture)) {
          state.drafts[key] = draft;
        }
      });
      const restoredIndex = state.tasks.findIndex((task) => taskKey(task) === payload.activeTaskKey);
      if (restoredIndex >= 0) state.activeIndex = restoredIndex;
    } catch (error) {
      console.warn("Ignoring corrupt local annotation draft", error);
    }
  }

  async function readJsonFile(file) {
    try {
      return JSON.parse(await file.text());
    } catch (error) {
      throw new Error(`${file.name}不是有效JSON：${error.message}`);
    }
  }

  async function loadPackFiles(files) {
    const packs = [];
    const allErrors = [];
    for (const file of files) {
      try {
        const pack = await readJsonFile(file);
        const errors = validatePack(pack, file.name);
        if (errors.length) allErrors.push(...errors);
        else packs.push(pack);
      } catch (error) {
        allErrors.push(error.message);
      }
    }
    if (allErrors.length) {
      showToast(allErrors.slice(0, 3).join("；"), true);
      console.error("Task pack rejected", allErrors);
      return;
    }
    mountPacks(packs);
  }

  function mountPacks(packs) {
    const validationErrors = packs.flatMap((pack, index) => validatePack(pack, `任务包${index + 1}`));
    const normalized = normalizePacks(packs);
    const errors = [...validationErrors, ...normalized.errors];
    if (errors.length) {
      showToast(errors.slice(0, 3).join("；"), true);
      console.error("Task packs rejected", errors);
      return;
    }
    state.packs = packs;
    state.tasks = normalized.tasks;
    state.activeIndex = 0;
    state.activeSignalIndex = 0;
    state.filter = "all";
    state.selectedSpan = null;
    state.storageKey = workspaceStorageKey(state.tasks);
    restoreWorkspace();

    const firstIncomplete = state.tasks.findIndex((task) => !state.drafts[taskKey(task)]?.completed_at);
    if (firstIncomplete >= 0 && state.drafts[taskKey(state.tasks[state.activeIndex])]?.completed_at) {
      state.activeIndex = firstIncomplete;
    }
    dom.emptyState.hidden = true;
    dom.taskWorkspace.hidden = false;
    [dom.exportJsonButton, dom.exportCsvButton, dom.clearWorkspaceButton,
      dom.pseudonymInput, dom.identityGeneratorToggle, dom.addSignalButton,
      dom.saveDraftButton, dom.completeTaskButton].forEach((element) => { element.disabled = false; });
    dom.signalDecision.disabled = false;
    dom.reviewActionBlock.disabled = false;
    renderAll();
    showToast(`已载入 ${state.tasks.length} 条任务，本地草稿已恢复`);
  }

  function filteredTaskIndices() {
    return state.tasks.map((task, index) => ({ task, index })).filter(({ task }) => {
      const complete = Boolean(state.drafts[taskKey(task)]?.completed_at);
      if (state.filter === "complete") return complete;
      if (state.filter === "pending") return !complete;
      return true;
    });
  }

  function draftStatus(draft) {
    if (draft?.completed_at) return "complete";
    if (draft && (draft.has_signals !== null || draft.signals.length || draft.review_action)) return "progress";
    return "pending";
  }

  function renderTaskList() {
    const rows = filteredTaskIndices();
    if (!rows.length) {
      dom.taskList.innerHTML = '<div class="task-list-empty">当前筛选没有任务</div>';
      return;
    }
    dom.taskList.innerHTML = rows.map(({ task, index }) => {
      const status = draftStatus(state.drafts[taskKey(task)]);
      return `
        <button class="task-item ${index === state.activeIndex ? "active" : ""}" type="button" data-task-index="${index}">
          <span class="task-index">${String(index + 1).padStart(2, "0")}</span>
          <span class="task-copy">
            <strong>${escapeHtml(task.redacted_text)}</strong>
            <span>${escapeHtml(task.split)} · ${escapeHtml(task.profile)}</span>
          </span>
          <span class="task-state-dot ${status}" title="${status}"></span>
        </button>`;
    }).join("");
  }

  function renderProgress() {
    const total = state.tasks.length;
    const complete = state.tasks.filter((task) => state.drafts[taskKey(task)]?.completed_at).length;
    const percent = total ? Math.round((complete / total) * 100) : 0;
    dom.taskCountLabel.textContent = `${total} 条任务`;
    dom.progressLabel.textContent = `完成 ${complete} / ${total}`;
    dom.progressPercent.textContent = `${percent}%`;
    dom.progressFill.style.width = `${percent}%`;
  }

  function renderHeader() {
    const task = activeTask();
    if (!task) return;
    const splits = [...new Set(state.tasks.map((item) => item.split))].join("+");
    dom.batchLabel.textContent = `${task.dataset_id} · ${splits} · ${task.annotator_slot}`;
    const blind = task.annotation_mode === "blind";
    dom.modeBadge.textContent = blind ? `BLIND · SLOT ${task.annotator_slot}` : "ASSISTED REVIEW";
    dom.modeBadge.className = `mode-badge ${blind ? "blind" : "assisted"}`;
  }

  function renderTask() {
    const task = activeTask();
    if (!task) return;
    ensureDraft(task);
    state.activeSignalIndex = Math.min(state.activeSignalIndex, Math.max(0, activeDraft().signals.length - 1));
    state.selectedSpan = null;
    renderSelection();
    dom.samplePosition.textContent = `样本 ${state.activeIndex + 1} / ${state.tasks.length}`;
    dom.sampleTitle.textContent = task.sample_id;
    dom.sourceText.textContent = task.redacted_text;
    dom.characterCount.textContent = `${codePointLength(task.redacted_text)} 字`;
    dom.blindBanner.hidden = task.annotation_mode !== "blind";
    dom.sampleMeta.innerHTML = [
      `<span class="meta-chip">${escapeHtml(task.split)}</span>`,
      `<span class="meta-chip">${escapeHtml(task.profile)}</span>`,
      `<span class="meta-chip">slot ${escapeHtml(task.annotator_slot)}</span>`,
      task.fixture ? '<span class="meta-chip fixture">FIXTURE</span>' : "",
    ].join("");
    renderSuggestion(task);
    dom.reviewActionBlock.hidden = task.annotation_mode !== "assisted_review";
    dom.previousTaskButton.disabled = state.activeIndex === 0;
    dom.nextTaskButton.disabled = state.activeIndex === state.tasks.length - 1;
    renderEditor();
  }

  function renderSuggestion(task) {
    const suggestion = task.annotation_mode === "assisted_review" ? task.suggestion : null;
    const signals = Array.isArray(suggestion?.suggested_signals) ? suggestion.suggested_signals : [];
    dom.suggestionPanel.hidden = !suggestion;
    if (!suggestion) {
      dom.suggestionContent.innerHTML = "";
      return;
    }
    if (!signals.length) {
      dom.suggestionContent.innerHTML = '<p class="suggestion-item">机器建议：没有可提取信号。仍需人工独立确认。</p>';
      return;
    }
    dom.suggestionContent.innerHTML = signals.map((signal) => {
      const evidence = Array.isArray(signal.evidence_spans)
        ? signal.evidence_spans.map((span) => span.text).join("；") : "";
      return `<div class="suggestion-item">
        <span class="suggestion-type">${escapeHtml(signal.signal_type)}</span>
        <strong>${escapeHtml(signal.summary || "未提供摘要")}</strong>
        <span class="suggestion-evidence">「${escapeHtml(evidence)}」</span>
      </div>`;
    }).join("");
  }

  function typeOptions(profile, current) {
    return (PROFILE_TYPES[profile] || []).map((type) => (
      `<option value="${escapeHtml(type)}" ${type === current ? "selected" : ""}>${escapeHtml(TYPE_LABELS[type] || type)} · ${escapeHtml(type)}</option>`
    )).join("");
  }

  function evidenceHtml(spans, signalIndex) {
    if (!spans.length) return '<div class="evidence-empty">划选左侧原文后，点击“添加到当前信号”。</div>';
    return spans.map((span, evidenceIndex) => `
      <div class="evidence-item">
        <span class="evidence-index">${span.start}:${span.end}</span>
        <q title="${escapeHtml(span.text)}">${escapeHtml(span.text)}</q>
        <button type="button" aria-label="删除证据" data-action="remove-evidence" data-signal-index="${signalIndex}" data-evidence-index="${evidenceIndex}">删除</button>
      </div>`).join("");
  }

  function signalCardHtml(signal, index, profile) {
    return `<section class="signal-card ${index === state.activeSignalIndex ? "active" : ""}" data-signal-card="${index}">
      <div class="signal-card-header">
        <strong>信号 ${index + 1}</strong>
        <div class="signal-card-actions">
          <button type="button" data-action="activate-signal" data-signal-index="${index}">设为当前</button>
          <button class="danger-text" type="button" data-action="remove-signal" data-signal-index="${index}">删除</button>
        </div>
      </div>
      <div class="field">
        <label for="signal-type-${index}">信号类型</label>
        <select id="signal-type-${index}" data-signal-index="${index}" data-field="signal_type">
          <option value="">请选择</option>
          ${typeOptions(profile, signal.signal_type)}
        </select>
      </div>
      <div class="field">
        <label for="signal-summary-${index}">摘要要点</label>
        <textarea id="signal-summary-${index}" data-signal-index="${index}" data-field="summary" placeholder="只写原文支持的事实或需求">${escapeHtml(signal.summary)}</textarea>
      </div>
      <div class="field">
        <label>原文证据</label>
        <div class="evidence-list">${evidenceHtml(signal.evidence_spans, index)}</div>
      </div>
      <div class="field">
        <label for="implicit-need-${index}">隐含需求（可选）</label>
        <input id="implicit-need-${index}" data-signal-index="${index}" data-field="implicit_need" value="${escapeHtml(signal.implicit_need || "")}" placeholder="没有就留空">
      </div>
      <div class="field-row">
        <label class="checkbox-row">
          <input type="checkbox" data-signal-index="${index}" data-field="implicit_need_has_basis" ${signal.implicit_need_has_basis ? "checked" : ""}>
          隐含需求有原文依据
        </label>
        <label class="checkbox-row">
          <input type="checkbox" data-signal-index="${index}" data-field="hallucination" ${signal.hallucination ? "checked" : ""}>
          含无依据新增事实
        </label>
      </div>
      <div class="field">
        <label for="signal-notes-${index}">备注（可选）</label>
        <textarea id="signal-notes-${index}" data-signal-index="${index}" data-field="notes" placeholder="边界情况、讽刺、冲突等">${escapeHtml(signal.notes || "")}</textarea>
      </div>
    </section>`;
  }

  function renderEditor() {
    const task = activeTask();
    const draft = activeDraft();
    if (!task || !draft) return;
    document.querySelectorAll("[data-has-signals]").forEach((button) => {
      const selected = String(draft.has_signals) === button.dataset.hasSignals;
      button.classList.toggle("active", selected);
    });
    document.querySelectorAll("[data-review-action]").forEach((button) => {
      button.classList.toggle("active", draft.review_action === button.dataset.reviewAction);
    });
    if (draft.has_signals === false) {
      dom.signalEditor.innerHTML = '<div class="editor-placeholder">已判断为“无信号”。请确认辅助标注处理动作后完成。</div>';
    } else if (!draft.signals.length) {
      dom.signalEditor.innerHTML = '<div class="editor-placeholder">选择“有信号”后添加一条或多条信号。</div>';
    } else {
      dom.signalEditor.innerHTML = draft.signals.map((signal, index) => signalCardHtml(signal, index, task.profile)).join("");
    }
    dom.addSignalButton.disabled = draft.has_signals !== true;
    dom.saveState.textContent = draft.completed_at ? "已完成并本地保存" : "草稿自动保存";
    dom.saveState.classList.toggle("saved", Boolean(draft.completed_at));
    renderValidation([]);
  }

  function renderSelection() {
    if (!state.selectedSpan) {
      dom.selectionPreview.textContent = "请在原文中划选证据";
      dom.addEvidenceButton.disabled = true;
      return;
    }
    const { start, end, text } = state.selectedSpan;
    dom.selectionPreview.textContent = `${start}:${end} · 「${text}」`;
    dom.addEvidenceButton.disabled = !activeDraft()?.signals.length;
  }

  function renderValidation(errors) {
    if (!errors.length) {
      dom.validationSummary.classList.remove("visible");
      dom.validationSummary.innerHTML = "";
      return;
    }
    dom.validationSummary.classList.add("visible");
    dom.validationSummary.innerHTML = `<strong>请修正 ${errors.length} 项</strong><ul>${errors.map((error) => `<li>${escapeHtml(error)}</li>`).join("")}</ul>`;
  }

  function renderAll() {
    renderHeader();
    renderProgress();
    renderTaskList();
    renderTask();
  }

  function captureSelection() {
    const task = activeTask();
    const selection = globalThis.getSelection();
    if (!task || !selection || selection.rangeCount === 0 || selection.isCollapsed) return;
    if (!dom.sourceText.contains(selection.anchorNode) || !dom.sourceText.contains(selection.focusNode)) return;
    const range = selection.getRangeAt(0);
    const prefixRange = range.cloneRange();
    prefixRange.selectNodeContents(dom.sourceText);
    prefixRange.setEnd(range.startContainer, range.startOffset);
    const startUtf16 = prefixRange.toString().length;
    const selectedText = range.toString();
    const start = codePointLength(task.redacted_text.slice(0, startUtf16));
    const end = start + codePointLength(selectedText);
    const exactText = codePointSlice(task.redacted_text, start, end);
    if (!selectedText || exactText !== selectedText) {
      state.selectedSpan = null;
      renderSelection();
      return;
    }
    state.selectedSpan = { start, end, text: exactText };
    renderSelection();
  }

  function blankSignal(task) {
    return {
      signal_type: (PROFILE_TYPES[task.profile] || [""])[0] || "",
      summary: "",
      evidence_spans: [],
      implicit_need: null,
      implicit_need_has_basis: false,
      hallucination: false,
      notes: null,
    };
  }

  function setHasSignals(value) {
    const task = activeTask();
    const draft = ensureDraft(task);
    draft.has_signals = value;
    if (value && draft.signals.length === 0) draft.signals.push(blankSignal(task));
    if (!value) draft.signals = [];
    state.activeSignalIndex = 0;
    markDirty(draft);
    renderEditor();
    renderSelection();
  }

  function addSignal() {
    const task = activeTask();
    const draft = ensureDraft(task);
    if (draft.has_signals !== true) return;
    draft.signals.push(blankSignal(task));
    state.activeSignalIndex = draft.signals.length - 1;
    markDirty(draft);
    renderEditor();
    renderSelection();
  }

  function addSelectedEvidence() {
    const draft = activeDraft();
    if (!draft?.signals.length || !state.selectedSpan) {
      showToast("请先添加信号并在原文中划选证据", true);
      return;
    }
    const signal = draft.signals[state.activeSignalIndex];
    const duplicate = signal.evidence_spans.some((span) => span.start === state.selectedSpan.start
      && span.end === state.selectedSpan.end && span.text === state.selectedSpan.text);
    if (duplicate) {
      showToast("这段证据已经添加过", true);
      return;
    }
    signal.evidence_spans.push({ ...state.selectedSpan });
    signal.evidence_spans.sort((left, right) => left.start - right.start || left.end - right.end);
    state.selectedSpan = null;
    globalThis.getSelection()?.removeAllRanges();
    markDirty(draft);
    renderEditor();
    renderSelection();
  }

  function applySuggestion() {
    const task = activeTask();
    const draft = activeDraft();
    const suggested = task?.suggestion?.suggested_signals;
    if (!task || !draft || task.annotation_mode !== "assisted_review" || !Array.isArray(suggested)) return;
    draft.signals = suggested.map((signal) => ({
      signal_type: String(signal.signal_type || ""),
      summary: String(signal.summary || ""),
      evidence_spans: Array.isArray(signal.evidence_spans)
        ? signal.evidence_spans.map((span) => ({ start: span.start, end: span.end, text: span.text })) : [],
      implicit_need: signal.implicit_need || null,
      implicit_need_has_basis: Boolean(signal.implicit_need_has_basis),
      hallucination: Boolean(signal.hallucination),
      notes: null,
    }));
    draft.has_signals = draft.signals.length > 0;
    draft.review_action = "accepted";
    state.activeSignalIndex = 0;
    markDirty(draft);
    renderEditor();
    showToast("建议已填入，请逐字段人工检查后再完成");
  }

  function validateSignal(signal, task, index) {
    const errors = [];
    const label = `信号${index + 1}`;
    if (!(PROFILE_TYPES[task.profile] || []).includes(signal.signal_type)) errors.push(`${label}：请选择合法信号类型`);
    if (!String(signal.summary || "").trim()) errors.push(`${label}：摘要不能为空`);
    if (!Array.isArray(signal.evidence_spans) || signal.evidence_spans.length === 0) {
      errors.push(`${label}：至少添加一段原文证据`);
    } else {
      signal.evidence_spans.forEach((span, spanIndex) => {
        if (!Number.isInteger(span.start) || !Number.isInteger(span.end) || span.start < 0 || span.end <= span.start) {
          errors.push(`${label}证据${spanIndex + 1}：字符区间无效`);
        } else if (codePointSlice(task.redacted_text, span.start, span.end) !== span.text) {
          errors.push(`${label}证据${spanIndex + 1}：区间与原文不一致`);
        }
      });
    }
    if (signal.implicit_need_has_basis && !String(signal.implicit_need || "").trim()) {
      errors.push(`${label}：勾选“有依据”时必须填写隐含需求`);
    }
    if (signal.implicit_need && !signal.implicit_need_has_basis && !signal.hallucination) {
      errors.push(`${label}：隐含需求无依据时必须标记为无依据新增事实`);
    }
    return errors;
  }

  function validateDraft(draft, task, requireCompleted = false) {
    const errors = [];
    const fields = unknownKeys(draft, ANNOTATION_FIELDS);
    if (fields.length) errors.push(`annotation包含未知字段：${fields.join(", ")}`);
    if (!String(draft.annotator_pseudonym || dom.pseudonymInput.value || "").trim()) errors.push("请填写标注员pseudonym");
    if (typeof draft.has_signals !== "boolean") errors.push("请选择“有信号”或“无信号”");
    if (draft.has_signals === true && draft.signals.length === 0) errors.push("有信号时至少添加一条信号");
    if (draft.has_signals === false && draft.signals.length !== 0) errors.push("无信号时signals必须为空");
    draft.signals.forEach((signal, index) => {
      const extraSignalFields = unknownKeys(signal, SIGNAL_FIELDS);
      if (extraSignalFields.length) errors.push(`信号${index + 1}包含未知字段`);
      errors.push(...validateSignal(signal, task, index));
    });
    if (task.annotation_mode === "assisted_review" && !new Set(["accepted", "modified", "rejected"]).has(draft.review_action)) {
      errors.push("辅助标注必须选择接受、修改或拒绝");
    }
    if (task.annotation_mode === "blind" && draft.review_action !== null) errors.push("盲标任务review_action必须为null");
    if (draft.task_hash !== task.task_hash || draft.content_hash !== task.content_hash) errors.push("任务hash与当前任务不一致");
    if (Boolean(draft.fixture) !== Boolean(task.fixture)) errors.push("fixture来源与任务包不一致");
    if (requireCompleted && !draft.completed_at) errors.push("标注尚未完成");
    return errors;
  }

  function normalizedAnnotation(draft, task) {
    return {
      annotation_id: draft.annotation_id,
      dataset_id: task.dataset_id,
      sample_id: task.sample_id,
      annotator_slot: task.annotator_slot,
      annotator_pseudonym: String(draft.annotator_pseudonym || dom.pseudonymInput.value).trim(),
      annotation_mode: task.annotation_mode,
      has_signals: Boolean(draft.has_signals),
      signal_count: draft.signals.length,
      signals: draft.signals.map((signal) => ({
        signal_type: signal.signal_type,
        summary: String(signal.summary || "").trim(),
        evidence_spans: signal.evidence_spans.map((span) => ({ ...span })),
        implicit_need: String(signal.implicit_need || "").trim() || null,
        implicit_need_has_basis: Boolean(signal.implicit_need_has_basis),
        hallucination: Boolean(signal.hallucination),
        notes: String(signal.notes || "").trim() || null,
      })),
      review_action: task.annotation_mode === "assisted_review" ? draft.review_action : null,
      started_at: draft.started_at,
      completed_at: draft.completed_at,
      task_hash: task.task_hash,
      content_hash: task.content_hash,
      fixture: Boolean(task.fixture),
    };
  }

  function saveDraft() {
    const draft = ensureDraft();
    if (!draft) return;
    draft.annotator_pseudonym = String(dom.pseudonymInput.value || "").trim();
    persistWorkspace();
    dom.saveState.textContent = "草稿已保存";
    dom.saveState.classList.add("saved");
    showToast("草稿已保存在当前浏览器");
  }

  function completeTask() {
    const task = activeTask();
    const draft = ensureDraft(task);
    draft.annotator_pseudonym = String(dom.pseudonymInput.value || "").trim();
    const errors = validateDraft(draft, task);
    renderValidation(errors);
    if (errors.length) {
      showToast("当前标注未通过校验", true);
      return;
    }
    draft.completed_at = nowIso();
    Object.assign(draft, normalizedAnnotation(draft, task));
    persistWorkspace();
    renderAll();
    showToast("当前任务已完成");
    const nextIncomplete = state.tasks.findIndex((item, index) => index > state.activeIndex
      && !state.drafts[taskKey(item)]?.completed_at);
    if (nextIncomplete >= 0) setTimeout(() => selectTask(nextIncomplete), 350);
  }

  function selectTask(index) {
    if (index < 0 || index >= state.tasks.length) return;
    state.activeIndex = index;
    state.activeSignalIndex = 0;
    persistWorkspace();
    renderAll();
    document.querySelector(`.task-item[data-task-index="${index}"]`)?.focus({ preventScroll: true });
  }

  function completedAnnotations() {
    return state.tasks.flatMap((task) => {
      const draft = state.drafts[taskKey(task)];
      if (!draft?.completed_at) return [];
      const errors = validateDraft(draft, task, true);
      return errors.length ? [] : [normalizedAnnotation(draft, task)];
    });
  }

  function downloadFile(name, content, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 500);
  }

  function exportJson() {
    const annotations = completedAnnotations();
    if (!annotations.length) {
      showToast("还没有通过校验的已完成标注", true);
      return;
    }
    const task = state.tasks[0];
    const date = new Date().toISOString().slice(0, 10).replaceAll("-", "");
    const fileName = `human_annotations_${task.dataset_id}_${task.annotator_slot}_${date}.json`;
    downloadFile(fileName, `${JSON.stringify({ annotations }, null, 2)}\n`, "application/json;charset=utf-8");
    showToast(`已导出 ${annotations.length} 条完成记录`);
  }

  function csvCell(value) {
    const text = String(value ?? "");
    return `"${text.replaceAll('"', '""')}"`;
  }

  function exportCsv() {
    const annotations = completedAnnotations();
    if (!annotations.length) {
      showToast("还没有通过校验的已完成标注", true);
      return;
    }
    const taskByKey = new Map(state.tasks.map((task) => [taskKey(task), task]));
    const headers = [
      "annotation_id", "dataset_id", "sample_id", "split", "profile", "annotator_slot",
      "annotation_mode", "has_signals", "signal_index", "signal_type", "summary",
      "evidence", "implicit_need", "implicit_need_has_basis", "hallucination",
      "review_action", "started_at", "completed_at", "fixture",
    ];
    const rows = [headers];
    annotations.forEach((annotation) => {
      const task = taskByKey.get(`${annotation.dataset_id}|${annotation.sample_id}|${annotation.annotator_slot}`);
      const signals = annotation.signals.length ? annotation.signals : [null];
      signals.forEach((signal, index) => rows.push([
        annotation.annotation_id, annotation.dataset_id, annotation.sample_id, task?.split,
        task?.profile, annotation.annotator_slot, annotation.annotation_mode,
        annotation.has_signals, signal ? index + 1 : "", signal?.signal_type || "",
        signal?.summary || "", signal?.evidence_spans?.map((span) => `${span.start}:${span.end} ${span.text}`).join(" | ") || "",
        signal?.implicit_need || "", signal?.implicit_need_has_basis ?? "",
        signal?.hallucination ?? "", annotation.review_action || "", annotation.started_at,
        annotation.completed_at, annotation.fixture,
      ]));
    });
    const csv = `\ufeff${rows.map((row) => row.map(csvCell).join(",")).join("\r\n")}\r\n`;
    const task = state.tasks[0];
    const date = new Date().toISOString().slice(0, 10).replaceAll("-", "");
    downloadFile(`annotation_review_${task.dataset_id}_${task.annotator_slot}_${date}.csv`, csv, "text/csv;charset=utf-8");
  }

  function validateImportedAnnotation(annotation, task) {
    const errors = [];
    const extra = unknownKeys(annotation, ANNOTATION_FIELDS);
    if (extra.length) errors.push(`${annotation.sample_id || "记录"}包含未知annotation字段`);
    if (annotation.dataset_id !== task.dataset_id || annotation.sample_id !== task.sample_id
        || annotation.annotator_slot !== task.annotator_slot || annotation.task_hash !== task.task_hash
        || annotation.content_hash !== task.content_hash || annotation.annotation_mode !== task.annotation_mode
        || Boolean(annotation.fixture) !== Boolean(task.fixture)) {
      errors.push(`${annotation.sample_id || "记录"}与冻结任务身份不一致`);
    }
    if (!Array.isArray(annotation.signals)) errors.push(`${annotation.sample_id || "记录"}.signals不是数组`);
    (annotation.signals || []).forEach((signal, signalIndex) => {
      if (unknownKeys(signal, SIGNAL_FIELDS).length) errors.push(`${annotation.sample_id}信号${signalIndex + 1}含未知字段`);
      (signal.evidence_spans || []).forEach((span) => {
        if (unknownKeys(span, EVIDENCE_FIELDS).length) errors.push(`${annotation.sample_id}证据含未知字段`);
      });
    });
    errors.push(...validateDraft(annotation, task, true));
    return errors;
  }

  async function importAnnotations(file) {
    if (!state.tasks.length) {
      showToast("请先导入对应的冻结任务包", true);
      return;
    }
    try {
      const payload = await readJsonFile(file);
      const rawEntries = Array.isArray(payload) ? payload : payload.annotations;
      if (!Array.isArray(rawEntries)) throw new Error("标注文件必须是数组或包含annotations数组");
      const taskMap = new Map(state.tasks.map((task) => [taskKey(task), task]));
      const errors = [];
      const accepted = [];
      rawEntries.forEach((entry) => {
        const annotation = entry.annotation || entry;
        const key = `${annotation.dataset_id}|${annotation.sample_id}|${annotation.annotator_slot}`;
        const task = taskMap.get(key);
        if (!task) {
          errors.push(`${annotation.sample_id || "未知记录"}不属于当前任务包`);
          return;
        }
        const itemErrors = validateImportedAnnotation(annotation, task);
        if (itemErrors.length) errors.push(...itemErrors);
        else accepted.push([key, annotation]);
      });
      if (errors.length) throw new Error(errors.slice(0, 4).join("；"));
      accepted.forEach(([key, annotation]) => { state.drafts[key] = structuredClone(annotation); });
      if (!dom.pseudonymInput.value && accepted[0]) {
        dom.pseudonymInput.value = accepted[0][1].annotator_pseudonym;
        localStorage.setItem(PSEUDONYM_KEY, dom.pseudonymInput.value);
      }
      persistWorkspace();
      renderAll();
      showToast(`已恢复 ${accepted.length} 条完成标注`);
    } catch (error) {
      showToast(error.message, true);
      console.error("Annotation import rejected", error);
    }
  }

  async function generatePseudonym() {
    const seed = dom.identitySeedInput.value;
    if (!seed.trim()) {
      showToast("请输入只在本地使用的身份种子", true);
      return;
    }
    if (!globalThis.crypto?.subtle) {
      showToast("当前浏览器不支持安全哈希，请手工填写pseudonym", true);
      return;
    }
    const digest = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(seed));
    const hex = Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
    dom.pseudonymInput.value = `anno_${hex.slice(0, 12)}`;
    dom.identitySeedInput.value = "";
    dom.identityGenerator.hidden = true;
    localStorage.setItem(PSEUDONYM_KEY, dom.pseudonymInput.value);
    markDirty();
    showToast("pseudonym已在本地生成，原始输入未保存");
  }

  function clearWorkspace() {
    if (!state.storageKey) return;
    const count = Object.keys(state.drafts).length;
    if (!globalThis.confirm(`确认清空当前批次的 ${count} 条本地草稿？此操作不可撤销。`)) return;
    localStorage.removeItem(state.storageKey);
    state.drafts = {};
    ensureDraft();
    renderAll();
    showToast("当前批次草稿已清空");
  }

  dom.packInput.addEventListener("change", (event) => {
    if (event.target.files.length) loadPackFiles([...event.target.files]);
    event.target.value = "";
  });
  dom.annotationInput.addEventListener("change", (event) => {
    if (event.target.files[0]) importAnnotations(event.target.files[0]);
    event.target.value = "";
  });
  dom.taskList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-task-index]");
    if (button) selectTask(Number(button.dataset.taskIndex));
  });
  document.querySelectorAll("[data-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      state.filter = button.dataset.filter;
      document.querySelectorAll("[data-filter]").forEach((item) => item.classList.toggle("active", item === button));
      renderTaskList();
    });
  });
  document.querySelectorAll("[data-has-signals]").forEach((button) => {
    button.addEventListener("click", () => setHasSignals(button.dataset.hasSignals === "true"));
  });
  document.querySelectorAll("[data-review-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const draft = activeDraft();
      if (!draft) return;
      draft.review_action = button.dataset.reviewAction;
      markDirty(draft);
      renderEditor();
    });
  });
  dom.signalEditor.addEventListener("input", (event) => {
    const target = event.target.closest("[data-signal-index][data-field]");
    if (!target) return;
    const draft = activeDraft();
    const signal = draft?.signals[Number(target.dataset.signalIndex)];
    if (!signal) return;
    signal[target.dataset.field] = target.type === "checkbox" ? target.checked : target.value;
    markDirty(draft);
  });
  dom.signalEditor.addEventListener("change", (event) => {
    const target = event.target.closest("[data-signal-index][data-field]");
    if (!target) return;
    const draft = activeDraft();
    const signal = draft?.signals[Number(target.dataset.signalIndex)];
    if (!signal) return;
    signal[target.dataset.field] = target.type === "checkbox" ? target.checked : target.value;
    markDirty(draft);
  });
  dom.signalEditor.addEventListener("click", (event) => {
    const action = event.target.closest("[data-action]");
    const card = event.target.closest("[data-signal-card]");
    if (card && !action) {
      state.activeSignalIndex = Number(card.dataset.signalCard);
      renderEditor();
      renderSelection();
      return;
    }
    if (!action) return;
    const draft = activeDraft();
    const signalIndex = Number(action.dataset.signalIndex);
    if (action.dataset.action === "activate-signal") {
      state.activeSignalIndex = signalIndex;
    } else if (action.dataset.action === "remove-signal") {
      draft.signals.splice(signalIndex, 1);
      state.activeSignalIndex = Math.max(0, Math.min(state.activeSignalIndex, draft.signals.length - 1));
      if (!draft.signals.length) draft.has_signals = null;
      markDirty(draft);
    } else if (action.dataset.action === "remove-evidence") {
      draft.signals[signalIndex].evidence_spans.splice(Number(action.dataset.evidenceIndex), 1);
      markDirty(draft);
    }
    renderEditor();
    renderSelection();
  });
  document.addEventListener("selectionchange", captureSelection);
  dom.addEvidenceButton.addEventListener("click", addSelectedEvidence);
  dom.addSignalButton.addEventListener("click", addSignal);
  dom.applySuggestionButton.addEventListener("click", applySuggestion);
  dom.saveDraftButton.addEventListener("click", saveDraft);
  dom.completeTaskButton.addEventListener("click", completeTask);
  dom.previousTaskButton.addEventListener("click", () => selectTask(state.activeIndex - 1));
  dom.nextTaskButton.addEventListener("click", () => selectTask(state.activeIndex + 1));
  dom.exportJsonButton.addEventListener("click", exportJson);
  dom.exportCsvButton.addEventListener("click", exportCsv);
  dom.clearWorkspaceButton.addEventListener("click", clearWorkspace);
  dom.demoAssistedButton.addEventListener("click", () => mountPacks([structuredClone(DEMO_ASSISTED_PACK)]));
  dom.demoBlindButton.addEventListener("click", () => mountPacks([structuredClone(DEMO_BLIND_PACK)]));
  dom.identityGeneratorToggle.addEventListener("click", () => {
    dom.identityGenerator.hidden = !dom.identityGenerator.hidden;
    if (!dom.identityGenerator.hidden) dom.identitySeedInput.focus();
  });
  dom.generatePseudonymButton.addEventListener("click", generatePseudonym);
  dom.pseudonymInput.addEventListener("input", () => {
    localStorage.setItem(PSEUDONYM_KEY, dom.pseudonymInput.value.trim());
    markDirty();
  });
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && state.tasks.length) {
      event.preventDefault();
      completeTask();
    } else if (event.altKey && event.key === "ArrowLeft") {
      event.preventDefault();
      selectTask(state.activeIndex - 1);
    } else if (event.altKey && event.key === "ArrowRight") {
      event.preventDefault();
      selectTask(state.activeIndex + 1);
    }
  });

  dom.pseudonymInput.value = localStorage.getItem(PSEUDONYM_KEY) || "";
  globalThis.addEventListener("annotation-workbench:autoload", (event) => {
    const packs = Array.isArray(event.detail) ? event.detail : [];
    if (!packs.length) {
      showToast("默认任务源没有返回任务包", true);
      return;
    }
    mountPacks(packs.map((pack) => structuredClone(pack)));
    if (state.tasks.length) {
      showToast(`已直接载入 ${state.tasks.length} 条 FIXTURE 任务，可开始标注`);
    }
  }, { once: true });
  globalThis.addEventListener("annotation-workbench:autoload-error", (event) => {
    showToast(`默认任务载入失败：${event.detail || "未知错误"}`, true);
  }, { once: true });
  globalThis.AnnotationWorkbenchInternals = Object.freeze({
    codePointLength,
    codePointSlice,
    validatePack,
    validateDraft,
    findForbiddenKeys,
    profileTypes: structuredClone(PROFILE_TYPES),
  });
})();
