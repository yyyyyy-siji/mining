/* ==================================================== Page: Pipeline ======== */

let currentEventSource = null;
let pipelineRunState = null;

function getPipelineStepsConfig(profile) {
  return profile === 'aigc_video' ? [
    { key: 'quality_gate', label: '质量门控', icon: '🚪' },
    { key: 'extraction', label: '爆款技巧提取', icon: '🔬' },
    { key: 'embedding', label: '向量嵌入', icon: '🧬' },
    { key: 'deduplication', label: '语义去重', icon: '🔍' },
    { key: 'clustering', label: '模式聚类', icon: '🏷️' },
    { key: 'pain_point', label: '创作瓶颈', icon: '😣' },
    { key: 'opportunity', label: '爆款公式', icon: '💡' },
    { key: 'requirement', label: '创作指南', icon: '📝' },
  ] : [
    { key: 'quality_gate', label: '质量门控', icon: '🚪' },
    { key: 'extraction', label: '信号提取', icon: '🔬' },
    { key: 'embedding', label: '向量嵌入', icon: '🧬' },
    { key: 'deduplication', label: '语义去重', icon: '🔍' },
    { key: 'clustering', label: '主题聚类', icon: '🏷️' },
    { key: 'pain_point', label: '痛点识别', icon: '😣' },
    { key: 'opportunity', label: '机会卡片', icon: '💡' },
    { key: 'requirement', label: '需求资产生成', icon: '📝' },
  ];
}

function initPipelineStepLog(profile) {
  const log = document.getElementById?.('step-log');
  if (!log) return;
  log.innerHTML = '';
  getPipelineStepsConfig(profile).forEach(s => {
    const item = document.createElement('div');
    item.className = 'step-log-item pending';
    item.id = `step-${s.key}`;
    item.innerHTML = `<span class="step-icon">○</span><span class="step-name">${s.icon} ${s.label}</span><span class="step-detail">等待中</span><span class="step-time"></span>`;
    log.appendChild(item);
  });
}

function renderPipelineStatsHtml(stats) {
  if (!stats) return '';
  const semanticPhase = stats.semantic_phase;
  let statsHtml = Object.entries(stats)
    .filter(([k]) => k !== 'semantic_phase' && k !== 'embedding_status')
    .map(([k, v]) => `<span style="margin-right:16px;font-size:13px"><strong>${escapeHtml(k)}:</strong> ${escapeHtml(v)}</span>`)
    .join('');
  if (semanticPhase === 'skipped') {
    statsHtml = '<div style="margin-bottom:8px;padding:8px 12px;background:rgba(245,158,11,0.12);border-radius:6px;color:var(--warning);font-size:13px">⚠️ 文本提取已完成；语义去重/聚类因未配置真实 Embedding 而跳过</div>' + statsHtml;
  }
  return statsHtml;
}

function isPipelineTerminalStatus(status) {
  return ['completed', 'completed_with_skips', 'failed', 'stopped'].includes(status);
}

function applyPipelineEvent(runId, data, { profile = null } = {}) {
  if (!pipelineRunState || pipelineRunState.runId !== runId) {
    pipelineRunState = {
      runId,
      profile: profile || data.profile || getSelectedProfile(),
      status: 'running',
      progress: 0,
      step: null,
      stepDetails: {},
      message: '',
      stats: null,
      error: null,
      dismissed: false,
    };
  }
  const s = pipelineRunState;
  if (data.profile) s.profile = data.profile;
  if (typeof data.progress === 'number' && Number.isFinite(data.progress)) {
    s.progress = Math.max(0, Math.min(1, data.progress));
  }
  if (data.message) s.message = data.message;
  if (data.error) s.error = data.error;
  if (data.stats && Object.keys(data.stats).length) s.stats = data.stats;
  if (data.step) {
    Object.entries(s.stepDetails).forEach(([prevKey, info]) => {
      if (prevKey !== data.step && ['running', 'processing'].includes(info.status)) {
        info.status = 'completed';
      }
    });
    s.step = data.step;
    s.stepDetails[data.step] = { status: data.status, message: data.message || data.status };
  }
  const isTerminalRun = data.status === 'failed' || (
    ['completed', 'completed_with_skips'].includes(data.status)
    && (!data.step || data.step === 'complete' || s.progress >= 1)
  );
  if (isTerminalRun) {
    s.status = data.status;
    if (s.status !== 'failed') s.progress = 1;
    Object.values(s.stepDetails).forEach(info => {
      if (['running', 'processing'].includes(info.status)) info.status = s.status === 'failed' ? 'failed' : 'completed';
    });
    if (s.status === 'completed') {
      getPipelineStepsConfig(s.profile).forEach(stepCfg => {
        if (!s.stepDetails[stepCfg.key]) {
          s.stepDetails[stepCfg.key] = { status: 'completed', message: '已完成' };
        }
      });
    }
  } else if (['running', 'processing', 'completed'].includes(data.status)) {
    s.status = 'running';
  }
  syncPipelineDOM();
  renderGlobalPipelineStatus();
  return isTerminalRun;
}

function renderGlobalPipelineStatus() {
  const pill = document.getElementById?.('sidebar-pipeline-badge');
  const s = pipelineRunState;
  if (pill) {
    if (!s) {
      pill.hidden = true;
    } else {
      const pct = `${(s.progress * 100).toFixed(0)}%`;
      pill.hidden = false;
      pill.className = `sidebar-pipeline-badge ${s.status}`;
      pill.textContent = s.status === 'running' ? `⏳ ${pct}` : s.status === 'completed' ? '✅ 完成' : s.status === 'completed_with_skips' ? '⚠️ 跳过' : s.status === 'failed' ? '❌ 失败' : '已停';
    }
  }
  const banner = document.getElementById?.('global-pipeline-banner');
  if (!banner) return;
  if (!s || s.dismissed || getRoute() === 'pipeline') {
    banner.hidden = true;
    banner.textContent = '';
    return;
  }
  const pct = (s.progress * 100).toFixed(0);
  const running = s.status === 'running';
  const label = running
    ? `⏳ 管线正在后台运行 (${pct}%)：${s.message || '处理中…'}`
    : s.status === 'completed'
      ? '✅ 后台管线已执行完成！'
      : s.status === 'completed_with_skips'
        ? `⚠️ 后台管线完成（部分跳过）：${s.message || '语义阶段未执行'}`
        : s.status === 'failed'
          ? `❌ 后台管线执行失败：${s.error || s.message || '请查看详情'}`
          : '⏹ 管线实时监听已停止';
  banner.hidden = false;
  banner.className = `global-pipeline-banner status-${s.status}`;
  banner.innerHTML = '';
  const textEl = document.createElement('span');
  textEl.className = 'global-pipeline-text';
  textEl.textContent = label;
  const actions = document.createElement('div');
  actions.className = 'global-pipeline-actions';
  const viewBtn = document.createElement('button');
  viewBtn.type = 'button';
  viewBtn.className = 'btn btn-secondary btn-sm';
  viewBtn.textContent = running ? '查看实时进度' : '前往管线页';
  viewBtn.onclick = () => { location.hash = 'pipeline'; };
  actions.appendChild(viewBtn);
  if (!running) {
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'btn btn-secondary btn-sm';
    closeBtn.textContent = '关闭';
    closeBtn.onclick = () => {
      if (pipelineRunState) pipelineRunState.dismissed = true;
      renderGlobalPipelineStatus();
    };
    actions.appendChild(closeBtn);
  }
  banner.append(textEl, actions);
}

function syncPipelineDOM() {
  const card = document.getElementById?.('pipeline-progress-card');
  const s = pipelineRunState;
  if (!card || !s) return;
  card.style.display = 'block';
  const runBtn = document.getElementById('btn-run-pipeline');
  const stopBtn = document.getElementById('btn-stop-pipeline');
  const isRunning = s.status === 'running';
  if (runBtn) runBtn.style.display = isRunning ? 'none' : 'inline-flex';
  if (stopBtn) stopBtn.style.display = isRunning ? 'inline-flex' : 'none';

  const fill = document.getElementById('progress-fill');
  const pctEl = document.getElementById('progress-pct');
  const statusEl = document.getElementById('progress-status');
  const statsEl = document.getElementById('pipeline-stats');
  const pct = (s.progress * 100);
  if (fill) {
    fill.className = 'progress-bar-fill' + (['completed', 'completed_with_skips'].includes(s.status) ? ' done' : '');
    fill.style.width = `${s.status === 'completed' || s.status === 'completed_with_skips' ? 100 : pct}%`;
    fill.style.background = s.status === 'failed' ? 'var(--danger)' : '';
    if (s.status === 'failed') fill.style.animation = 'none';
  }
  if (pctEl) pctEl.textContent = `${['completed', 'completed_with_skips'].includes(s.status) ? 100 : pct.toFixed(0)}%`;

  if (statusEl) {
    statusEl.textContent = '';
    if (s.status === 'running') {
      const icon = document.createElement('span');
      icon.style.animation = 'pulse 1s infinite';
      icon.textContent = '⏳ ';
      statusEl.append(icon, document.createTextNode(`${s.message || '管线运行中…'} (${s.runId})`));
    } else if (s.status === 'completed') {
      statusEl.textContent = `✅ 管线完成！(${s.runId})`;
    } else if (s.status === 'completed_with_skips') {
      statusEl.textContent = `⚠️ 管线完成（部分跳过）：${s.message || '语义阶段未执行'}`;
    } else if (s.status === 'failed') {
      statusEl.textContent = `❌ ${s.error || s.message || '管线执行失败'}`;
    } else {
      statusEl.textContent = '⏹ 实时进度监听已手动停止（后端任务如未结束可刷新重新追踪）。';
    }
  }

  const log = document.getElementById('step-log');
  if (log && !log.children.length) initPipelineStepLog(s.profile || getSelectedProfile());
  Object.entries(s.stepDetails || {}).forEach(([stepKey, info]) => {
    const item = document.getElementById(`step-${stepKey}`);
    if (!item) return;
    item.classList.remove('pending');
    if (['completed', 'processing', 'running', 'skipped'].includes(info.status)) {
      item.classList.add('active');
      const iconEl = item.querySelector('.step-icon');
      const detailEl = item.querySelector('.step-detail');
      if (iconEl) iconEl.textContent = info.status === 'completed' ? '✅' : info.status === 'skipped' ? '⚠️' : '⏳';
      if (detailEl) detailEl.textContent = info.message || info.status;
    }
  });
  if (statsEl && s.stats) statsEl.innerHTML = renderPipelineStatsHtml(s.stats);
}

async function syncActivePipelineFromServer() {
  try {
    const response = await apiGet('/pipeline/runs', { limit: 5 });
    const runs = Array.isArray(response?.runs) ? response.runs : [];
    const active = runs.find(r => r.status === 'running');
    const target = active || (!pipelineRunState ? runs.find(r => r.live) : runs.find(r => r.id === pipelineRunState.runId));
    if (!target) return;
    const snap = target.live || {};
    const steps = snap.steps || {};
    const latest = snap.latest || {};
    pipelineRunState = {
      runId: target.id,
      profile: target.profile || getSelectedProfile(),
      status: target.status || latest.status || 'running',
      progress: typeof latest.progress === 'number' ? latest.progress : (isPipelineTerminalStatus(target.status) ? 1 : 0),
      step: latest.step || null,
      stepDetails: Object.fromEntries(Object.entries(steps).map(([k, v]) => [k, { status: v.status, message: v.message || v.status }])),
      message: latest.message || (target.status === 'running' ? '管线运行中…' : ''),
      stats: (target.stats && Object.keys(target.stats).length ? target.stats : latest.stats) || null,
      error: target.error || latest.error || null,
      dismissed: pipelineRunState?.runId === target.id ? Boolean(pipelineRunState.dismissed) : (target.status !== 'running'),
    };
    syncPipelineDOM();
    renderGlobalPipelineStatus();
    if (pipelineRunState.status === 'running' && !currentEventSource && typeof EventSource !== 'undefined') {
      startSSEStream(pipelineRunState.runId);
    }
  } catch (_error) {
    // Non-fatal: keep existing local state if status lookup fails
  }
}

async function renderPipelinePage(container) {
  const selectedProfile = getSelectedProfile();
  const profileCfg = getProfileConfig();
  container.innerHTML = `
    <div class="card">
      <div class="section-title">⚙️ 运行管线</div>
      <p style="margin-bottom:16px;color:var(--text-secondary)">${escapeHtml(profileCfg.description)}</p>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">每条反馈信号数 (1–10)</label>
          <input class="form-input" id="pipe-max-signals" type="number" min="1" max="10" value="5">
          <p class="discovery-hint" style="margin-top:6px">单条原始反馈最多提取的信号上限（默认 5）。短内容只提 1 条；长帖/多评论最多保留该数量，调小更聚焦，调大更细致。</p>
        </div>
      </div>
      <button class="btn btn-primary" id="btn-run-pipeline">🚀 启动管线</button>
      <button class="btn btn-secondary" id="btn-stop-pipeline" style="display:none">⏹ 隐藏/停止追踪</button>
    </div>
    <div class="card" id="pipeline-progress-card" style="display:none">
      <div class="section-title">📊 实时进度</div>
      <div class="progress-bar-container">
        <div class="progress-bar-fill" id="progress-fill" style="width:0%"><span class="progress-text" id="progress-pct"></span></div>
      </div>
      <div class="progress-status" id="progress-status"></div>
      <div class="step-log" id="step-log"></div>
      <div id="pipeline-stats" style="margin-top:16px"></div>
    </div>
  `;

  initPipelineStepLog(selectedProfile);
  if (pipelineRunState) {
    syncPipelineDOM();
  }
  syncActivePipelineFromServer();

  document.getElementById('btn-run-pipeline').onclick = async () => {
    if (currentEventSource) { currentEventSource.close(); currentEventSource = null; }

    const maxSignals = parseInt(document.getElementById('pipe-max-signals').value) || 5;

    try {
      const pipeReq = {
        max_signals: maxSignals,
        profile: getSelectedProfile(),
      };
      const writeVersion = getEffectiveWriteVersion();
      if (writeVersion !== 'default') pipeReq.version_id = writeVersion;
      const { run_id } = await apiPost('/pipeline/run', pipeReq);
      showToast(`管线已启动 (${run_id})`, 'info');
      pipelineRunState = {
        runId: run_id,
        profile: getSelectedProfile(),
        status: 'running',
        progress: 0,
        step: 'queued',
        stepDetails: {},
        message: '正在启动管线…',
        stats: null,
        error: null,
        dismissed: false,
      };
      initPipelineStepLog(pipelineRunState.profile);
      syncPipelineDOM();
      renderGlobalPipelineStatus();
      startSSEStream(run_id);
    } catch (e) {
      showToast(`启动失败: ${e.message}`, 'danger');
    }
  };

  document.getElementById('btn-stop-pipeline').onclick = () => {
    if (currentEventSource) { currentEventSource.close(); currentEventSource = null; }
    if (pipelineRunState) {
      pipelineRunState.status = 'stopped';
      syncPipelineDOM();
      renderGlobalPipelineStatus();
    }
    showToast('已停止前端进度追踪', 'warning');
  };
}

function startSSEStream(runId) {
  if (typeof EventSource === 'undefined') return;
  if (currentEventSource) {
    currentEventSource.close();
    currentEventSource = null;
  }
  const source = new EventSource(`${API_BASE}/pipeline/stream/${runId}`);
  currentEventSource = source;

  source.onmessage = (event) => {
    const data = JSON.parse(event.data);
    const isTerminal = applyPipelineEvent(runId, data);

    if (isTerminal && data.status === 'completed') {
      source.close();
      currentEventSource = null;
      showToast('管线执行完成！', 'success');
    } else if (isTerminal && data.status === 'completed_with_skips') {
      source.close();
      currentEventSource = null;
      showToast('文本提取已完成；语义去重/聚类未执行', 'warning');
    } else if (isTerminal && data.status === 'failed') {
      source.close();
      currentEventSource = null;
      showToast('管线执行失败', 'danger');
    }
  };

  source.onerror = async () => {
    source.close();
    currentEventSource = null;
    try {
      const latest = await apiGet(`/pipeline/runs/${encodeURIComponent(runId)}`);
      if (latest) {
        const snap = latest.live || {};
        const end = snap.latest || {};
        applyPipelineEvent(runId, {
          status: latest.status,
          progress: typeof end.progress === 'number' ? end.progress : (isPipelineTerminalStatus(latest.status) ? 1 : pipelineRunState?.progress || 0),
          step: end.step,
          message: end.message || latest.error || '',
          stats: latest.stats && Object.keys(latest.stats).length ? latest.stats : end.stats,
          error: latest.error || end.error,
        });
        if (latest.status === 'running') {
          showToast('SSE 连接重连中…', 'warning');
          setTimeout(() => {
            if (pipelineRunState?.runId === runId && pipelineRunState.status === 'running' && !currentEventSource) {
              startSSEStream(runId);
            }
          }, 1500);
        }
        return;
      }
    } catch (_error) {}
    showToast('SSE 连接中断', 'warning');
  };
}

