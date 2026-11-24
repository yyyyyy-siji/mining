/* ================================================================ API ======= */

function getApiKey() {
  return localStorage.getItem('signalminer_api_key') || '';
}

function getAuthHeaders() {
  const key = getApiKey();
  return key ? { 'X-API-Key': key } : {};
}

async function apiGet(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const url = `${API_BASE}${path}${qs ? '?' + qs : ''}`;
  const res = await fetch(url, { headers: getAuthHeaders() });
  if (res.status === 401) {
    promptApiKey();
    throw new Error('需要 API Key 认证');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || (typeof err.detail === 'string' ? err.detail : `API ${res.status}: ${res.statusText}`));
  }
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(body),
  });
  if (res.status === 401) {
    promptApiKey();
    throw new Error('需要 API Key 认证');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || (typeof err.detail === 'string' ? err.detail : `API ${res.status}`));
  }
  return res.json();
}

async function apiPatch(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(body),
  });
  if (res.status === 401) {
    promptApiKey();
    throw new Error('需要 API Key 认证');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || (typeof err.detail === 'string' ? err.detail : `API ${res.status}`));
  }
  return res.json();
}

async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (res.status === 401) {
    promptApiKey();
    throw new Error('需要 API Key 认证');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || (typeof err.detail === 'string' ? err.detail : `API ${res.status}`));
  }
  return res.json();
}

function promptApiKey() {
  const key = prompt('请输入 API Key:');
  if (key) {
    localStorage.setItem('signalminer_api_key', key);
    showToast('API Key 已保存，正在刷新…', 'info');
    setTimeout(() => location.reload(), 500);
  }
}

/* ============================================================ Components === */

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('removing');
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function showSkeleton(container, count = 3) {
  for (let i = 0; i < count; i++) {
    const div = document.createElement('div');
    div.className = 'skeleton skeleton-card';
    container.appendChild(div);
  }
}

function createBadge(text, variant = 'default') {
  const span = document.createElement('span');
  span.className = `badge badge-${variant}`;
  span.textContent = text;
  return span;
}

function createExpandableCard(headerHTML, bodyHTML) {
  const card = document.createElement('div');
  card.className = 'card card-expandable';

  const header = document.createElement('div');
  header.className = 'card-header';
  header.innerHTML = headerHTML;

  const toggle = document.createElement('button');
  toggle.className = 'expand-toggle';
  toggle.innerHTML = '▼';
  toggle.onclick = () => {
    card.classList.toggle('expanded');
    toggle.classList.toggle('open');
  };

  if (typeof headerHTML === 'string' && !headerHTML.includes('expand-toggle')) {
    header.appendChild(toggle);
  }

  const body = document.createElement('div');
  body.className = 'card-body';
  body.innerHTML = bodyHTML;

  card.appendChild(header);
  card.appendChild(body);
  return card;
}

function showEmpty(container, icon, title, desc) {
  container.innerHTML = '';
  const div = document.createElement('div');
  div.className = 'empty-state';
  div.innerHTML = `
    <div class="empty-state-icon">${icon}</div>
    <div class="empty-state-title">${title}</div>
    <div class="empty-state-desc">${desc}</div>
  `;
  container.appendChild(div);
}

function confidenceColor(conf) {
  if (conf >= 0.8) return '#10b981';
  if (conf >= 0.6) return '#f59e0b';
  return '#ef4444';
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function createSourceLink(url, text = '查看原始来源') {
  const safeUrl = discoverySourceUrl(url);
  if (!safeUrl) return createSourceUnavailable('来源链接不可打开');
  const a = document.createElement('a');
  a.href = safeUrl;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.textContent = text;
  a.className = 'source-action source-action-link';
  return a;
}

function createSourceUnavailable(text = '演示数据无真实来源') {
  const span = document.createElement('span');
  span.className = 'source-action source-action-disabled';
  span.textContent = `🔗 ${text}`;
  span.title = '该记录保留了来源字段，但不是可验证、可打开的真实原始页面。';
  return span;
}

function sourceStatusHtml(sourceUrl, externalUrl, text = '查看原始来源') {
  sourceUrl = discoverySourceUrl(sourceUrl);
  if (sourceUrl) {
    return `<div class="source-row"><a class="source-action source-action-link" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">🔗 ${escapeHtml(text)}</a></div>`;
  }
  if (externalUrl) {
    return '<div class="source-row"><span class="source-action source-action-disabled" title="该记录保留了来源字段，但不是可验证、可打开的真实原始页面。">🔗 演示数据无真实来源</span></div>';
  }
  return '';
}

function sourceButtonHtml(sourceUrl, externalUrl, text = '数据来源') {
  sourceUrl = discoverySourceUrl(sourceUrl);
  if (sourceUrl) {
    return `<a class="source-action source-action-link source-action-compact" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">🔗 ${escapeHtml(text)}</a>`;
  }
  const label = externalUrl ? '来源不可打开' : '未记录来源';
  const title = externalUrl
    ? '该记录保留了来源字段，但不是可验证、可打开的真实原始页面。'
    : '该记录没有保存原始页面 URL。';
  return `<button class="source-action source-action-disabled source-action-compact" type="button" disabled title="${escapeHtml(title)}">🔗 ${label}</button>`;
}

function appendSourceStatus(parent, sourceUrl, externalUrl, text = '查看原始来源') {
  const row = document.createElement('div');
  row.className = 'source-row';
  if (sourceUrl) {
    row.appendChild(createSourceLink(sourceUrl, `🔗 ${text}`));
  } else if (externalUrl) {
    row.appendChild(createSourceUnavailable());
  } else {
    return;
  }
  parent.appendChild(row);
}

const CONTENT_NATURE_LABELS = {
  original_text: '原始正文', api_excerpt: 'API 摘要（检索线索）',
  curated_comment: '精选评论（检索线索）', ocr_text: '截图 OCR 文本',
  manual_text: '人工提供文本，未联网核验', unknown: '内容性质未知',
};
const LOCATOR_LABELS = { item: '条目定位（未保证网页仍可达）', parent_page: '仅定位父页面，不能直达该评论', unknown: '定位等级未知' };
const SNAPSHOT_LABELS = { verified: '留存快照完整性一致', mismatch: '快照核对不一致，请勿作为证据', not_recorded: '历史文本，未记录快照' };

function sourceEvidenceFields(record = {}) {
  return { ...record, ...(record.source_evidence || record.context?.source_evidence || {}) };
}

function sourceEvidenceDescription(record = {}) {
  const source = sourceEvidenceFields(record);
  const status = record.snapshot_verification?.status || record.snapshot_status || source.snapshot_status || 'not_recorded';
  return `${CONTENT_NATURE_LABELS[source.content_nature] || CONTENT_NATURE_LABELS.unknown} · ${LOCATOR_LABELS[source.locator_level] || LOCATOR_LABELS.unknown} · ${SNAPSHOT_LABELS[status] || '快照核对状态未知'}`;
}

function sourceEvidenceLinkLabel(record = {}) {
  const source = sourceEvidenceFields(record);
  if (source.locator_level === 'parent_page') return '打开父页面（不能直达该评论）';
  if (source.locator_level === 'item') return '打开来源条目';
  return '打开来源页面（定位等级未知）';
}

function downloadSourceJson(value, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function appendSourceSnapshot(parent, feedbackId, initial = null) {
  const profile = getSelectedProfile();
  const box = document.createElement('section');
  box.className = 'source-evidence-panel';
  const meta = document.createElement('p');
  meta.className = 'discovery-hint';
  if (initial) meta.textContent = sourceEvidenceDescription(initial);
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'btn btn-secondary btn-sm';
  button.textContent = '查看来源详情 / 快照';
  const output = document.createElement('div');
  box.append(meta, button, output);
  parent.appendChild(box);
  let busy = false;
  const active = () => box.isConnected && getSelectedProfile() === profile;
  button.onclick = async () => {
    if (busy || !active()) return;
    busy = true;
    button.disabled = true;
    output.textContent = '正在读取留存来源…';
    try {
      const detail = await apiGet(`/feedback/${encodeURIComponent(feedbackId)}`);
      if (!active()) return;
      if (detail.id !== feedbackId) throw new Error('反馈 ID 与来源请求不一致');
      meta.textContent = sourceEvidenceDescription(detail);
      const snapshot = await apiGet(`/feedback/${encodeURIComponent(feedbackId)}/source-snapshot`);
      if (!active()) return;
      if (snapshot.feedback_id && snapshot.feedback_id !== feedbackId) throw new Error('快照反馈 ID 与来源请求不一致');
      meta.textContent = sourceEvidenceDescription(snapshot);
      output.textContent = '';
      const note = document.createElement('p');
      note.className = 'discovery-hint';
      note.textContent = '哈希核对仅说明当前内容与留存快照是否一致，不能证明平台真实性、原网页可达或市场需求成立。';
      const pre = document.createElement('pre');
      pre.className = 'source-snapshot-json';
      pre.textContent = JSON.stringify(snapshot, null, 2);
      const download = document.createElement('button');
      download.type = 'button';
      download.className = 'btn btn-secondary btn-sm';
      download.textContent = '下载完整来源快照 JSON';
      download.onclick = () => { if (active()) downloadSourceJson(snapshot, `mining-source-${feedbackId}.json`); };
      output.append(note, pre, download);
      button.textContent = '重新读取来源 / 核对快照';
    } catch (error) {
      if (active()) output.textContent = `来源快照读取失败：${error.message}。可重试。`;
    } finally {
      busy = false;
      if (active()) button.disabled = false;
    }
  };
}

// Search leads are transient references; never prefill the original-text field.
let pendingSourceLead = null;

