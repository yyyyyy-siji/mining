/* =============================================================================
   SignalMiner SPA — Routing + API + Components + SSE + Evidence Chain
   ============================================================================= */

const API_BASE = '/api/v1';

const PROFILE_STORAGE_KEY = 'signalminer_profile';
const PROFILE_OPTIONS = {
  product_feedback: {
    label: '🏭 用户反馈挖矿',
    shortLabel: '用户反馈挖矿',
    description: '用户反馈 → 信号提取 → 主题聚类 → 痛点 → 机会 → 需求候选',
    importTitle: '✍️ 手动输入反馈',
    signalTypes: ['feature_request', 'bug_report', 'usability_issue', 'complaint', 'churn_risk', 'question', 'praise'],
  },
  aigc_video: {
    label: '🎬 AIGC视频爆款挖掘',
    shortLabel: 'AIGC视频爆款挖掘',
    description: 'AIGC视频数据 → 爆款技巧信号 → 模式聚类 → 创作瓶颈 → 爆款公式 → 创作指南',
    importTitle: '🎬 录入 AIGC 视频样本',
    signalTypes: [
      'viral_hook',
      'content_pattern',
      'visual_technique',
      'audio_strategy',
      'engagement_trigger',
      'platform_algorithm',
      'topic_trend',
      'monetization_pattern',
    ],
  },
};

const CAPTURE_METHOD_OPTIONS = {
  official_api: '官方 API / 开放平台',
  crawler: '合规公开页面爬取',
  browser_screenshot: '浏览器截图 / OCR / 人工识别',
  manual_browser: '人工浏览记录',
  webhook: 'Webhook / 外部系统推送',
};

const SOURCE_OPTION_GROUPS = {
  product_feedback: [
    {
      label: '博客 / 社区',
      options: [
        ['weibo', '微博'],
        ['zhihu', '知乎'],
        ['xiaohongshu', '小红书'],
        ['tieba', '百度贴吧'],
        ['csdn', 'CSDN'],
        ['juejin', '掘金'],
        ['cnblogs', '博客园'],
        ['weixin_mp', '微信公众号'],
        ['bilibili', '哔哩哔哩评论'],
      ],
    },
    {
      label: '搜索引擎',
      options: [
        ['baidu_search', '百度搜索结果'],
        ['sogou_search', '搜狗搜索结果'],
        ['so360_search', '360 搜索结果'],
        ['google_search', 'Google 搜索结果'],
        ['bing_search', 'Bing 搜索结果'],
      ],
    },
    {
      label: '购物 / 评价',
      options: [
        ['taobao', '淘宝'],
        ['tmall', '天猫'],
        ['jd', '京东'],
        ['pinduoduo', '拼多多'],
        ['app_review', '应用商店评价'],
      ],
    },
    {
      label: '二手交易',
      options: [
        ['xianyu', '闲鱼'],
        ['zhuanzhuan', '转转'],
        ['aihuishou', '爱回收'],
      ],
    },
    {
      label: '海外 / 研发 / 自定义',
      options: [
        ['github', 'GitHub Issues / Discussions'],
        ['manual', '手动录入'],
        ['support_ticket', '客服工单'],
        ['csv', 'CSV 行数据'],
        ['json', 'JSON 项数据'],
        ['api', '外部 API'],
        ['webhook', 'Webhook'],
      ],
    },
  ],
  aigc_video: [
    {
      label: '国内视频 / 短视频',
      options: [
        ['video_douyin', '抖音'],
        ['video_bilibili', '哔哩哔哩'],
        ['video_kuaishou', '快手'],
        ['video_xiaohongshu', '小红书'],
        ['video_youku', '优酷'],
        ['video_iqiyi', '爱奇艺'],
        ['video_tencent', '腾讯视频'],
      ],
    },
    {
      label: '海外 / 自定义',
      options: [
        ['video_youtube', 'YouTube'],
        ['video_manual', '其他视频网站'],
      ],
    },
  ],
};

const SOURCE_METHOD_GUIDES = {
  video_douyin: {
    methods: ['official_api', 'manual_browser', 'browser_screenshot'],
    guide: '抖音优先使用开放平台授权接口；页面受限时用浏览器打开视频页并截图/OCR，可导入的 URL 必须是原视频页。',
  },
  video_bilibili: {
    methods: ['official_api', 'crawler', 'manual_browser', 'browser_screenshot'],
    guide: 'B 站可用开放平台或公开页面采集；每条样本保留 BV 视频页或评论所在页 URL。',
  },
  video_kuaishou: {
    methods: ['official_api', 'manual_browser', 'browser_screenshot'],
    guide: '快手优先开放平台授权；页面受限时用浏览器可见内容截图/OCR，并保留视频页 URL。',
  },
  video_xiaohongshu: {
    methods: ['official_api', 'manual_browser', 'browser_screenshot'],
    guide: '小红书优先开放平台/蒲公英授权；页面受限时记录笔记页 URL，并用截图/OCR 提取评论。',
  },
  video_youtube: {
    methods: ['official_api', 'manual_browser'],
    guide: 'YouTube 可用 Data API 或人工浏览记录；必须保留视频页 URL。',
  },
  video_youku: {
    methods: ['manual_browser', 'browser_screenshot'],
    guide: '优酷页面限制较多，按浏览器打开、截图/OCR 或人工记录处理，保留视频页 URL。',
  },
  video_iqiyi: {
    methods: ['manual_browser', 'browser_screenshot'],
    guide: '爱奇艺页面限制较多，按浏览器打开、截图/OCR 或人工记录处理，保留视频页 URL。',
  },
  video_tencent: {
    methods: ['manual_browser', 'browser_screenshot'],
    guide: '腾讯视频页面限制较多，按浏览器打开、截图/OCR 或人工记录处理，保留视频页 URL。',
  },
  video_manual: {
    methods: ['manual_browser', 'browser_screenshot'],
    guide: '其他视频网站必须保留真实视频页 URL；不能用平台首页、搜索页或示例链接替代。',
  },
  weibo: {
    methods: ['crawler', 'manual_browser', 'browser_screenshot'],
    guide: '微博公开内容可页面采集；登录/反爬限制时用截图/OCR，保留微博详情页 URL。',
  },
  zhihu: {
    methods: ['manual_browser', 'browser_screenshot', 'official_api'],
    guide: '知乎官方搜索只提供摘要和精选评论线索；在「数据源」检索后，请取得并补充原文。人工提供材料未联网核验，须保留原页面 URL。',
  },
  xiaohongshu: {
    methods: ['official_api', 'manual_browser', 'browser_screenshot'],
    guide: '小红书优先开放平台授权；页面受限时用浏览器截图/OCR，保留笔记页 URL。',
  },
  tieba: {
    methods: ['crawler', 'manual_browser', 'browser_screenshot'],
    guide: '贴吧公开帖子可页面采集；保留帖子或楼层所在 URL。',
  },
  csdn: {
    methods: ['crawler', 'manual_browser', 'browser_screenshot'],
    guide: 'CSDN 公开博客页可抓取或人工记录；保留文章或评论页 URL。',
  },
  juejin: {
    methods: ['crawler', 'manual_browser', 'browser_screenshot'],
    guide: '掘金公开文章/沸点可页面采集；保留原始内容页 URL。',
  },
  cnblogs: {
    methods: ['official_api', 'manual_browser'],
    guide: '博客园优先 Open API；也可人工浏览公开文章，保留文章 URL。',
  },
  weixin_mp: {
    methods: ['manual_browser', 'browser_screenshot'],
    guide: '微信公众号页面限制较多，采用浏览器打开、截图/OCR 或人工摘录，保留文章 URL。',
  },
  bilibili: {
    methods: ['official_api', 'crawler', 'manual_browser', 'browser_screenshot'],
    guide: 'B 站评论/视频反馈可走开放平台或公开页面；每条数据保留 B 站原始页面 URL。',
  },
  baidu_search: {
    methods: ['official_api', 'manual_browser', 'browser_screenshot'],
    guide: '百度搜索来源必须保存搜索结果落地页 URL，不把搜索结果列表页当作证据。',
  },
  sogou_search: {
    methods: ['official_api', 'manual_browser', 'browser_screenshot'],
    guide: '搜狗搜索来源必须保存搜索结果落地页 URL，不把搜索结果列表页当作证据。',
  },
  so360_search: {
    methods: ['official_api', 'manual_browser', 'browser_screenshot'],
    guide: '360 搜索来源必须保存搜索结果落地页 URL，不把搜索结果列表页当作证据。',
  },
  google_search: {
    methods: ['official_api', 'manual_browser', 'browser_screenshot'],
    guide: 'Google 搜索可用官方搜索 API；每条数据保存结果落地页 URL，而不是 google.com/search。',
  },
  bing_search: {
    methods: ['official_api', 'manual_browser', 'browser_screenshot'],
    guide: 'Bing 搜索来源必须保存结果落地页 URL，不把搜索结果列表页当作证据。',
  },
  taobao: {
    methods: ['manual_browser', 'browser_screenshot'],
    guide: '淘宝商品/评价页面限制较多，采用浏览器打开、截图/OCR 或人工记录，保留商品/评价页 URL。',
  },
  tmall: {
    methods: ['manual_browser', 'browser_screenshot'],
    guide: '天猫商品/评价页面限制较多，采用浏览器打开、截图/OCR 或人工记录，保留商品/评价页 URL。',
  },
  jd: {
    methods: ['official_api', 'manual_browser', 'browser_screenshot'],
    guide: '京东优先开放平台授权接口；页面受限时用截图/OCR，保留商品或评价页 URL。',
  },
  pinduoduo: {
    methods: ['manual_browser', 'browser_screenshot'],
    guide: '拼多多页面/账号限制较多，采用浏览器打开、截图/OCR 或人工记录，保留商品页 URL。',
  },
  xianyu: {
    methods: ['official_api', 'manual_browser', 'browser_screenshot'],
    guide: '闲鱼优先开放平台/TOP 权限接口；页面受限时用截图/OCR，保留商品页 URL。',
  },
  zhuanzhuan: {
    methods: ['manual_browser', 'browser_screenshot'],
    guide: '转转页面限制较多，采用浏览器打开、截图/OCR 或人工记录，保留商品页 URL。',
  },
  aihuishou: {
    methods: ['manual_browser', 'browser_screenshot'],
    guide: '爱回收采用浏览器打开、截图/OCR 或人工记录，保留商品/报价页 URL。',
  },
  github: {
    methods: ['official_api', 'manual_browser'],
    guide: 'GitHub 优先 REST API；保留 issue、discussion、PR 或 comment 的 html_url。',
  },
  manual: {
    methods: ['manual_browser', 'browser_screenshot'],
    guide: '手动录入也必须填写真实原始页面 URL，不能用示例页、平台首页或空 URL。',
  },
  support_ticket: {
    methods: ['webhook', 'manual_browser'],
    guide: '客服工单需要填写可点击的工单系统 URL 或客户原始反馈页 URL。',
  },
  app_review: {
    methods: ['manual_browser', 'browser_screenshot'],
    guide: '应用评价需要填写评价详情页、应用商店页面或可打开的原始来源 URL。',
  },
  csv: {
    methods: ['manual_browser', 'webhook'],
    guide: 'CSV 每一行必须带 external_url/source_url/url/link 字段。',
  },
  json: {
    methods: ['manual_browser', 'webhook'],
    guide: 'JSON 每一项必须带 external_url/source_url/url/link 字段。',
  },
  api: {
    methods: ['official_api', 'webhook', 'manual_browser'],
    guide: '外部 API 数据必须提供原始页面 URL 或源系统可点击 URL。',
  },
  webhook: {
    methods: ['webhook', 'manual_browser'],
    guide: 'Webhook payload 必须携带原始页面 URL 或源系统可点击 URL。',
  },
};

/* ================================================================ Routing ==== */

const ROUTES = {
  'versions':      { title: '🗂️ 版本管理',      render: renderVersionsPage },
  'connectors':    { title: '📥 采集与导入',    render: renderConnectorsPage },
  'feedback':      { title: '📋 原始反馈',      render: renderFeedbackPage },
  'signals':       { title: '🔬 提取信号',      render: renderSignalsPage },
  'themes':        { title: '🏷️ 主题聚类',     render: renderThemesPage },
  'painpoints':    { title: '😣 痛点',           render: renderPainPointsPage },
  'opportunities': { title: '💡 机会卡片',      render: renderOpportunitiesPage },
  'requirements':  { title: '📝 需求候选',      render: renderRequirementsPage },
  'pipeline':      { title: '⚙️ 运行管线',     render: renderPipelinePage },
  'settings':      { title: '🎛️ 模型设置',      render: renderModelSettingsPage },
  'import':        { title: '📥 手动导入',      render: renderImportPage, hiddenInSidebar: true },
};

const VERSION_STORAGE_KEY = 'signalminer_version_id';
let cachedVersions = [
  { id: 'default', name: '默认版本（历史数据）', description: '', status: 'active', is_default: true, stats: {} },
];

function getSelectedVersion() {
  const stored = localStorage.getItem(VERSION_STORAGE_KEY);
  return stored && stored.trim() ? stored.trim() : 'default';
}

function setSelectedVersion(versionId) {
  if (!versionId || !String(versionId).trim()) return;
  localStorage.setItem(VERSION_STORAGE_KEY, String(versionId).trim());
}

function getEffectiveWriteVersion() {
  const v = getSelectedVersion();
  return v === 'all' ? 'default' : v;
}

function getVersionLabel(versionId = getSelectedVersion()) {
  if (versionId === 'all') return '全部版本（汇总）';
  const found = cachedVersions.find(v => v.id === versionId);
  return found ? found.name : (versionId === 'default' ? '默认版本（历史数据）' : versionId);
}

async function refreshVersionsCache() {
  try {
    const res = await apiGet('/versions');
    if (Array.isArray(res?.versions) && res.versions.length) {
      cachedVersions = res.versions;
      const sel = document.getElementById('version-select');
      if (sel) populateVersionSelect(sel, getSelectedVersion(), true);
    }
  } catch (_err) {
    // Non-fatal in offline tests or before server ready
  }
}

function populateVersionSelect(selectEl, selectedValue, includeAll = false) {
  if (!selectEl) return;
  selectEl.textContent = '';
  const activeVersions = cachedVersions.filter(v => v.status !== 'archived' || v.id === selectedValue);
  activeVersions.forEach(v => {
    const opt = document.createElement('option');
    opt.value = v.id;
    const count = v.stats && Number.isFinite(v.stats.feedback_count) ? ` (${v.stats.feedback_count})` : '';
    opt.textContent = `${v.name}${count}`;
    selectEl.appendChild(opt);
  });
  if (includeAll) {
    const allOpt = document.createElement('option');
    allOpt.value = 'all';
    allOpt.textContent = '🌐 全部版本（汇总只读）';
    selectEl.appendChild(allOpt);
  }
  const opts = Array.from(selectEl.options || selectEl.querySelectorAll?.('option') || []);
  const hasMatch = opts.some(o => o.value === selectedValue);
  selectEl.value = hasMatch ? selectedValue : (activeVersions[0]?.id || 'default');
}

function getRoute() {
  return location.hash.slice(1) || 'connectors';
}

function getSelectedProfile() {
  const stored = localStorage.getItem(PROFILE_STORAGE_KEY);
  return Object.prototype.hasOwnProperty.call(PROFILE_OPTIONS, stored) ? stored : 'product_feedback';
}

function setSelectedProfile(profile) {
  if (!Object.prototype.hasOwnProperty.call(PROFILE_OPTIONS, profile)) return;
  localStorage.setItem(PROFILE_STORAGE_KEY, profile);
}

function getProfileConfig() {
  return PROFILE_OPTIONS[getSelectedProfile()];
}

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

/* ============================================================ Navigation ==== */

function buildSidebar() {
  const nav = document.getElementById('sidebar-nav');
  nav.innerHTML = '';
  const current = getRoute();
  const selectedProfile = getSelectedProfile();

  const profileSwitcher = document.createElement('div');
  profileSwitcher.className = 'profile-switcher';
  profileSwitcher.innerHTML = `
    <label class="profile-switcher-label" for="profile-select">挖掘模式</label>
    <select class="form-select profile-select" id="profile-select">
      ${Object.entries(PROFILE_OPTIONS).map(([key, cfg]) =>
        `<option value="${key}" ${key === selectedProfile ? 'selected' : ''}>${cfg.label}</option>`
      ).join('')}
    </select>
  `;
  nav.appendChild(profileSwitcher);

  document.getElementById('profile-select').onchange = (event) => {
    setSelectedProfile(event.target.value);
    navigate();
  };

  const versionSwitcher = document.createElement('div');
  versionSwitcher.className = 'profile-switcher version-switcher';
  versionSwitcher.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
      <label class="profile-switcher-label" for="version-select" style="margin-bottom:0">当前版本</label>
      <button type="button" class="btn btn-secondary btn-sm" id="btn-quick-new-version" style="padding:2px 8px;font-size:11px" title="快速新建版本">+ 新建</button>
    </div>
    <select class="form-select profile-select" id="version-select"></select>
  `;
  nav.appendChild(versionSwitcher);
  const versionSelectEl = document.getElementById('version-select');
  populateVersionSelect(versionSelectEl, getSelectedVersion(), true);
  versionSelectEl.onchange = (event) => {
    setSelectedVersion(event.target.value);
    navigate();
  };
  document.getElementById('btn-quick-new-version').onclick = async () => {
    const name = typeof prompt === 'function' ? prompt('请输入新版本名称（如：v2-竞品调研-202611）：') : '';
    if (!name || !name.trim()) return;
    try {
      const created = await apiPost('/versions', { name: name.trim(), description: '' });
      setSelectedVersion(created.id);
      await refreshVersionsCache();
      showToast(`已创建并切换到版本「${created.name}」`, 'success');
      navigate();
    } catch (e) {
      showToast(`创建版本失败：${e.message}`, 'danger');
    }
  };
  refreshVersionsCache();

  Object.entries(ROUTES).forEach(([key, cfg]) => {
    if (cfg.hiddenInSidebar) return;
    const item = document.createElement('div');
    item.className = 'sidebar-nav-item' + (key === current ? ' active' : '');
    item.dataset.route = key;
    item.textContent = cfg.title;
    if (key === 'pipeline') {
      const pill = document.createElement('span');
      pill.id = 'sidebar-pipeline-badge';
      pill.className = 'sidebar-pipeline-badge';
      pill.hidden = true;
      item.appendChild(pill);
    }
    item.onclick = () => {
      location.hash = key;
    };
    nav.appendChild(item);
  });

  const llmStatus = document.createElement('div');
  llmStatus.className = 'llm-status-card';
  llmStatus.innerHTML = '<div class="llm-status-title">AI 模型</div><div class="llm-status-loading">正在读取能力…</div>';
  nav.appendChild(llmStatus);
  loadLLMStatus(llmStatus);
  renderGlobalPipelineStatus();
}

async function loadLLMStatus(container) {
  try {
    const data = await apiGet('/llm/capabilities');
    if (!container.isConnected) return;
    const primary = data.primary;
    const multimodal = data.multimodal;
    const embedding = data.embedding || { enabled: false };
    const primaryModalities = (primary.input_modalities || []).join(' / ') || 'text';
    const mediaDetail = multimodal.enabled
      ? `${escapeHtml(multimodal.provider)} · ${escapeHtml(multimodal.model)}<br><span>${escapeHtml((multimodal.input_modalities || []).join(' / '))}</span>`
      : '未启用<br><span>可在模型设置中开启</span>';
    const embDetail = embedding.enabled
      ? `${escapeHtml(embedding.provider)} · ${escapeHtml(embedding.model)}<br><span>语义去重与聚类已就绪 ✓</span>`
      : '未启用<br><span>可在模型设置配置本机或云端向量</span>';
    container.innerHTML = `
      <div class="llm-status-title">AI 模型能力</div>
      <div class="llm-status-row">
        <span class="llm-status-dot active"></span>
        <div><strong>主模型</strong><br>${escapeHtml(primary.provider)} · ${escapeHtml(primary.model)}<br><span>${escapeHtml(primaryModalities)}${primary.supports_multimodal ? ' · 多模态 ✓' : ''}</span></div>
      </div>
      <div class="llm-status-row">
        <span class="llm-status-dot ${multimodal.enabled ? 'active' : ''}"></span>
        <div><strong>多模态模型</strong><br>${mediaDetail}</div>
      </div>
      <div class="llm-status-row">
        <span class="llm-status-dot ${embedding.enabled ? 'active' : ''}"></span>
        <div><strong>Embedding 向量</strong><br>${embDetail}</div>
      </div>
    `;
  } catch (_error) {
    if (container.isConnected) {
      container.innerHTML = '<div class="llm-status-title">AI 模型能力</div><div class="llm-status-loading">暂时无法读取</div>';
    }
  }
}

function navigate() {
  const route = getRoute();
  const cfg = ROUTES[route];
  if (!cfg) {
    location.hash = 'connectors';
    return;
  }
  buildSidebar();
  document.title = `${cfg.title} — SignalMiner`;

  const content = document.getElementById('content-area');
  content.innerHTML = '';
  const header = document.createElement('div');
  header.className = 'page-header';
  const profile = getProfileConfig();
  header.innerHTML = `<h1>${cfg.title}</h1><p><span class="profile-pill">${escapeHtml(profile.shortLabel)}</span><span class="version-pill">🗂️ ${escapeHtml(getVersionLabel())}</span> ${escapeHtml(profile.description)}</p>`;
  content.appendChild(header);

  const banner = document.createElement('div');
  banner.id = 'global-pipeline-banner';
  banner.className = 'global-pipeline-banner';
  banner.hidden = true;
  content.appendChild(banner);

  const pageBody = document.createElement('div');
  pageBody.id = 'page-body';
  content.appendChild(pageBody);

  cfg.render(pageBody);
  renderGlobalPipelineStatus();
}

function renderSourceOptionGroups(profile) {
  const groups = SOURCE_OPTION_GROUPS[profile] || SOURCE_OPTION_GROUPS.product_feedback;
  return groups.map(group => `
    <optgroup label="${escapeHtml(group.label)}">
      ${group.options.map(([value, label]) =>
        `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`
      ).join('')}
    </optgroup>
  `).join('');
}

function getSourceMethodGuide(sourceType) {
  return SOURCE_METHOD_GUIDES[sourceType] || {
    methods: ['manual_browser', 'browser_screenshot'],
    guide: '该来源尚未单独建模，仍必须填写真实可点击原始 URL。',
  };
}

function renderCaptureMethodOptions(sourceType, selectedMethod = 'manual_browser') {
  const guide = getSourceMethodGuide(sourceType);
  const fallback = guide.methods.includes('manual_browser') ? 'manual_browser' : guide.methods[0];
  const selected = guide.methods.includes(selectedMethod) ? selectedMethod : fallback;
  return guide.methods.map(method => (
    `<option value="${escapeHtml(method)}" ${method === selected ? 'selected' : ''}>${escapeHtml(CAPTURE_METHOD_OPTIONS[method] || method)}</option>`
  )).join('');
}

function updateSourceAcquisitionControls() {
  const sourceSelect = document.getElementById('import-source');
  const methodSelect = document.getElementById('import-capture-method');
  const guideEl = document.getElementById('source-method-guide');
  const screenshotHintEl = document.getElementById('browser-screenshot-hint');
  if (!sourceSelect || !methodSelect || !guideEl) return;

  const guide = getSourceMethodGuide(sourceSelect.value);
  methodSelect.innerHTML = renderCaptureMethodOptions(sourceSelect.value, methodSelect.value);
  guideEl.textContent = guide.guide;

  // browser_screenshot 额外提示
  if (screenshotHintEl) {
    screenshotHintEl.style.display = methodSelect.value === 'browser_screenshot' ? 'block' : 'none';
  }

  methodSelect.onchange = () => {
    guideEl.textContent = getSourceMethodGuide(sourceSelect.value).guide;
    if (screenshotHintEl) {
      screenshotHintEl.style.display = methodSelect.value === 'browser_screenshot' ? 'block' : 'none';
    }
  };
}

/* ==================================================== Page: Import ========== */

async function renderImportPage(container) {
  const profile = getSelectedProfile();
  const profileCfg = getProfileConfig();
  const isVideoProfile = profile === 'aigc_video';
  let sourceLead = !isVideoProfile ? pendingSourceLead : null;
  if (sourceLead) pendingSourceLead = null;

  container.innerHTML = `
    <div class="card">
      <div class="section-title">${profileCfg.importTitle}</div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">${isVideoProfile ? '视频平台 / 网站' : '来源网站'}</label>
          <select class="form-select" id="import-source">
            ${renderSourceOptionGroups(profile)}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">数据获得方法</label>
          <select class="form-select" id="import-capture-method"></select>
        </div>
      </div>
      <div class="source-method-guide" id="source-method-guide"></div>
      <div id="browser-screenshot-hint" style="display:none;margin-top:4px;padding:6px 10px;background:#fff3cd;border:1px solid #ffc107;border-radius:4px;font-size:13px;color:#856404;">
        ⚠️ 截图/OCR 方法必须填写「截图路径」或在「来源备注」中说明截图内容，否则无法提交。
      </div>
      <div class="form-group">
        <label class="form-label">来源备注（可选）</label>
        <input class="form-input" id="import-source-note" placeholder="如：开放平台拉取 / 页面截图 OCR / 人工浏览时间">
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">${isVideoProfile ? '创作者名' : '用户名'}</label>
          <input class="form-input" id="import-author" placeholder="${isVideoProfile ? '如：账号名' : '如：张三'}">
        </div>
        <div class="form-group" ${isVideoProfile ? 'style="display:none"' : ''}>
          <label class="form-label">邮箱（可选）</label>
          <input class="form-input" id="import-email" placeholder="zhangsan@example.com">
        </div>
      </div>
      ${isVideoProfile ? `
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">播放量</label>
          <input class="form-input" id="import-views" type="number" min="0" step="1" value="0">
        </div>
        <div class="form-group">
          <label class="form-label">点赞量</label>
          <input class="form-input" id="import-likes" type="number" min="0" step="1" value="0">
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">视频链接（必填，真实可打开）</label>
        <input class="form-input" id="import-video-url" placeholder="https://...">
      </div>
      ` : ''}
      <div class="form-group">
        <label class="form-label">${isVideoProfile ? '视频标题' : '标题'}</label>
        <input class="form-input" id="import-subject" placeholder="${isVideoProfile ? '视频标题...' : '反馈标题...'}">
      </div>
      <div class="form-group">
        <label class="form-label">${isVideoProfile ? '视频文案 / 简介 / 评论摘要' : '正文'}</label>
        <textarea class="form-textarea" id="import-text" placeholder="${isVideoProfile ? '粘贴视频标题、描述、字幕、评论或爆款观察...' : '请输入反馈内容...'}"></textarea>
      </div>
      <div class="form-group" ${isVideoProfile ? 'style="display:none"' : ''}>
        <label class="form-label">真实来源 URL（必填，可点击）</label>
        <input class="form-input" id="import-external-url" placeholder="https://...">
      </div>
      <details class="source-import-fields">
        <summary>来源信息与内容性质（未知可留空）</summary>
        <p class="discovery-hint">默认是「人工提供文本，未联网核验」。摘要、精选评论不能直接作为机会分析的原文依据；来源时间请填写含时区的 ISO 时间。</p>
        <div class="form-row">
          <label class="form-label">内容性质<select class="form-select" id="import-content-nature"><option value="manual_text">人工提供文本，未联网核验</option><option value="original_text">原始正文</option><option value="ocr_text">截图 OCR 文本</option><option value="api_excerpt">API 摘要（线索）</option><option value="curated_comment">精选评论（线索）</option><option value="unknown">未知</option></select></label>
          <label class="form-label">正文来源字段<select class="form-select" id="import-text-origin"><option value="user_provided">用户提供，未联网核验</option><option value="body">对象正文</option><option value="title">对象自身标题（无正文）</option><option value="ocr">截图 OCR</option><option value="unknown">未知</option></select></label>
          <label class="form-label">定位等级<select class="form-select" id="import-locator-level"><option value="unknown">未知</option><option value="item">条目</option><option value="parent_page">仅父页面（不能直达评论）</option></select></label>
        </div>
        <div class="form-row">
          <label class="form-label">实体类型<select class="form-select" id="import-entity-type"><option value="unknown">未知</option><option value="post">帖子</option><option value="comment">评论</option><option value="answer">回答</option><option value="article">文章</option><option value="video">视频</option></select></label>
          <label class="form-label">平台对象 / 评论 ID<input class="form-input" id="import-external-id" placeholder="没有独立 ID 就留空"></label>
          <label class="form-label">覆盖范围<input class="form-input" id="import-coverage-scope" placeholder="如：完整正文 / 部分摘录"></label>
        </div>
        <div class="form-row">
          <label class="form-label">父页面对象 ID<input class="form-input" id="import-parent-id"></label>
          <label class="form-label">父页面 URL<input class="form-input" id="import-parent-url" placeholder="https://..."></label>
        </div>
        <div class="form-row">
          <label class="form-label">父评论 ID<input class="form-input" id="import-parent-comment-id"></label>
          <label class="form-label">父评论 URL<input class="form-input" id="import-parent-comment-url" placeholder="https://..."></label>
        </div>
        <div class="form-row">
          <label class="form-label">源创建时间<input class="form-input" id="import-source-created-at" placeholder="2026-11-05T09:00:00+08:00"></label>
          <label class="form-label">源更新时间<input class="form-input" id="import-source-updated-at" placeholder="未知留空，不替代创建时间"></label>
          <label class="form-label">采集时间<input class="form-input" id="import-source-captured-at" placeholder="含时区 ISO 时间；未知留空"></label>
        </div>
        <div class="form-row">
          <label class="form-label">采集版本<input class="form-input" id="import-capture-version"></label>
          <label class="form-label">截图路径（可选）<input class="form-input" id="import-screenshot-path"></label>
        </div>
      </details>
      <button class="btn btn-primary" id="btn-import-single">${isVideoProfile ? '🎬 提交视频样本' : '📨 提交反馈'}</button>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="section-title">📦 批量导入 JSON</div>
      <div class="file-drop-zone" id="file-drop-zone">
        <div class="file-drop-zone-icon">📂</div>
        <p>拖拽 JSON 文件到此处，或点击上传</p>
        <input type="file" id="file-input" accept=".json" style="display:none">
      </div>
      <details style="margin-top:8px;font-size:13px;color:var(--text-muted, #666);">
        <summary style="cursor:pointer;font-weight:600;">📋 证据包字段说明（每项必须包含）</summary>
        <div style="padding:8px 0;line-height:1.7;">
          <strong>必填：</strong><code>source_type</code>, <code>external_url</code>, <code>capture_method</code>, <code>text</code><br>
          <strong>可选：</strong><code>subject</code>, <code>author_name</code>, <code>source_note</code>, <code>screenshot_path</code>, <code>ocr_text</code>, <code>source_captured_at</code>, <code>raw_payload</code>；来源字段包括 <code>external_id</code>、<code>entity_type</code>、<code>parent_id</code> / <code>parent_url</code>、<code>parent_comment_id</code> / <code>parent_comment_url</code>、<code>source_created_at</code> / <code>source_updated_at</code>、<code>locator_level</code>、<code>content_nature</code>、<code>coverage_scope</code>、<code>capture_version</code>、<code>text_origin</code>。默认人工提供，未联网核验。<br>
          <span style="color:#b91c1c;">⚠ browser_screenshot 方法必须填写 screenshot_path 或 source_note</span>
        </div>
      </details>
      <div id="batch-result"></div>
    </div>
  `;

  updateSourceAcquisitionControls();
  document.getElementById('import-source').onchange = updateSourceAcquisitionControls;
  if (sourceLead) {
    const fill = (id, value) => { if (value != null) document.getElementById(id).value = String(value); };
    fill('import-source', 'zhihu');
    fill('import-capture-method', 'manual_browser');
    fill('import-subject', sourceLead.title);
    fill('import-external-url', sourceLead.source_url);
    fill('import-external-id', sourceLead.external_id);
    const entity = sourceLead.entity_type === 'question' ? 'post' : sourceLead.entity_type;
    fill('import-entity-type', ['post', 'comment', 'answer', 'article', 'video'].includes(entity) ? entity : 'unknown');
    fill('import-source-created-at', sourceLead.source_created_at);
    fill('import-source-updated-at', sourceLead.source_updated_at);
    fill('import-source-note', '来自知乎官方搜索线索；正文由用户另行提供，未联网核验；摘要和精选评论仅供参考。');
    updateSourceAcquisitionControls();
  }

  document.getElementById('btn-import-single').onclick = async () => {
    const sourceType = document.getElementById('import-source').value;
    const captureMethod = document.getElementById('import-capture-method').value;
    const author = document.getElementById('import-author').value.trim() || undefined;
    const email = document.getElementById('import-email')?.value || undefined;
    const subject = document.getElementById('import-subject').value || undefined;
    const sourceNote = document.getElementById('import-source-note').value.trim() || undefined;
    const text = document.getElementById('import-text').value.trim();

    if (!text) { showToast('请输入反馈内容', 'warning'); return; }

    const externalUrl = document.getElementById('import-external-url')?.value.trim() || undefined;
    const videoUrl = document.getElementById('import-video-url')?.value.trim() || undefined;
    const views = parseInt(document.getElementById('import-views')?.value || '0', 10) || 0;
    const likes = parseInt(document.getElementById('import-likes')?.value || '0', 10) || 0;
    const sourceUrl = isVideoProfile ? videoUrl : externalUrl;
    if (!sourceUrl) {
      showToast('必须提供真实可点击来源 URL', 'warning');
      return;
    }
    if (!/^https?:\/\//i.test(sourceUrl)) {
      showToast('来源 URL 必须以 http(s) 开头', 'warning');
      return;
    }
    const payload = {
      source_type: sourceType,
      text,
      subject,
      author_name: author,
      author_email: email,
      pipeline_profile: profile,
      external_url: sourceUrl,
      capture_method: captureMethod,
      source_note: sourceNote,
      content_nature: document.getElementById('import-content-nature').value,
      text_origin: document.getElementById('import-text-origin').value,
      locator_level: document.getElementById('import-locator-level').value,
      entity_type: document.getElementById('import-entity-type').value,
    };
    const sourceInputs = {
      external_id: 'external-id', parent_id: 'parent-id', parent_url: 'parent-url',
      parent_comment_id: 'parent-comment-id', parent_comment_url: 'parent-comment-url',
      source_created_at: 'source-created-at', source_updated_at: 'source-updated-at',
      source_captured_at: 'source-captured-at', coverage_scope: 'coverage-scope',
      capture_version: 'capture-version', screenshot_path: 'screenshot-path',
    };
    for (const [field, suffix] of Object.entries(sourceInputs)) {
      const value = document.getElementById(`import-${suffix}`).value.trim();
      if (!value) continue;
      if (field.endsWith('_at') && (!/(Z|[+-]\d{2}:\d{2})$/i.test(value) || Number.isNaN(Date.parse(value)))) {
        showToast('来源时间必须是含时区的 ISO 时间，例如 2026-11-05T09:00:00+08:00', 'warning');
        return;
      }
      if (field.endsWith('_url') && !discoverySourceUrl(value)) {
        showToast('父页面 / 父评论 URL 必须是有效的 http(s) 链接', 'warning');
        return;
      }
      payload[field] = value;
    }
    if (sourceLead) payload.raw_payload = { zhihu_search_lead: sourceLead };

    if (isVideoProfile) {
      payload.video_url = videoUrl;
      payload.views = views;
      payload.likes = likes;
      payload.platform = sourceType.startsWith('video_') ? sourceType.replace('video_', '') : sourceType;
    }

    try {
      const writeVersion = getEffectiveWriteVersion();
      if (writeVersion !== 'default') payload.version_id = writeVersion;
      const result = await apiPost('/feedback/ingest', payload);
      if (!container.isConnected || getSelectedProfile() !== profile) return;
      sourceLead = null;
      showToast(`✅ 已提交 (ID: ${result.feedback_id || result.id})`, 'success');
      document.getElementById('import-text').value = '';
      document.getElementById('import-subject').value = '';
      document.getElementById('import-source-note').value = '';
      Object.values(sourceInputs).forEach(suffix => { document.getElementById(`import-${suffix}`).value = ''; });
      document.getElementById('import-content-nature').value = 'manual_text';
      document.getElementById('import-text-origin').value = 'user_provided';
      document.getElementById('import-locator-level').value = 'unknown';
      document.getElementById('import-entity-type').value = 'unknown';
      if (isVideoProfile) {
        document.getElementById('import-video-url').value = '';
      } else {
        document.getElementById('import-external-url').value = '';
      }
    } catch (e) {
      if (container.isConnected && getSelectedProfile() === profile) showToast(`❌ ${e.message}`, 'danger');
    }
  };

  const dropZone = document.getElementById('file-drop-zone');
  const fileInput = document.getElementById('file-input');

  dropZone.onclick = () => fileInput.click();
  dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('dragover'); };
  dropZone.ondragleave = () => dropZone.classList.remove('dragover');
  dropZone.ondrop = async (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (!file) return;
    await uploadBatchFile(file);
  };
  fileInput.onchange = async () => {
    if (fileInput.files[0]) await uploadBatchFile(fileInput.files[0]);
  };

  async function uploadBatchFile(file) {
    const text = await file.text();
    if (!container.isConnected || getSelectedProfile() !== profile) return;
    let items;
    try { items = JSON.parse(text); } catch {
      showToast('文件不是有效的 JSON', 'danger');
      return;
    }
    if (!Array.isArray(items)) items = [items];
    // Normalize URL fields: map common field names to external_url
    items = items.map(item => {
      if (!item.source_type && item.source) item.source_type = item.source;
      if (!item.text) item.text = item.content || item.body || item.feedback || item.caption || item.description || '';
      if (!item.external_url) {
        item.external_url = item.source_url || item.url || item.video_url || item.link || undefined;
      }
      item.capture_method = item.capture_method || item.collection_method || item.acquisition_method || 'manual_browser';
      item.source_note = item.source_note || item.note || item.provenance_note || undefined;
      item.content_nature = item.content_nature || 'manual_text';
      item.text_origin = item.text_origin || 'user_provided';
      item.locator_level = item.locator_level || 'unknown';
      item.pipeline_profile = item.pipeline_profile || profile;
      if (isVideoProfile) {
        item.source_type = item.source_type || (item.platform ? `video_${item.platform}` : 'video_manual');
        item.video_url = item.video_url || item.external_url;
        item.views = Number(item.views || 0);
        item.likes = Number(item.likes || 0);
        item.platform = item.platform || (item.source_type.startsWith('video_') ? item.source_type.replace('video_', '') : item.source_type);
      }
      return item;
    });
    const missingUrlIndex = items.findIndex(item => !item.external_url);
    if (missingUrlIndex !== -1) {
      showToast(`第 ${missingUrlIndex + 1} 条缺少真实来源 URL`, 'danger');
      return;
    }
    try {
      const result = await apiPost('/feedback/batch', items);
      if (!container.isConnected || getSelectedProfile() !== profile) return;
      document.getElementById('batch-result').innerHTML = `
        <div style="margin-top:16px;padding:12px;background:rgba(16,185,129,0.1);border-radius:8px;color:var(--success)">
          ✅ 批量导入完成：${result.ingested} 条
        </div>
      `;
    } catch (e) {
      if (container.isConnected && getSelectedProfile() === profile) showToast(`❌ 批量导入失败: ${e.message}`, 'danger');
    }
  }
}

/* ==================================================== Page: Feedback ======== */

async function renderFeedbackPage(container) {
  const profile = getSelectedProfile();
  let revision = 0;
  container.innerHTML = '<div class="filters-bar"><button class="btn btn-secondary" id="btn-refresh-fb">🔄 刷新</button></div><div id="fb-list"></div>';

  async function load() {
    const token = ++revision;
    const listEl = container.querySelector('#fb-list');
    listEl.innerHTML = '';
    showSkeleton(listEl, 5);
    try {
      const data = await apiGet('/feedback', { limit: 100, profile: getSelectedProfile(), version_id: getSelectedVersion() });
      if (!container.isConnected || token !== revision || getSelectedProfile() !== profile) return;
      listEl.innerHTML = '';
      if (!data.length) return showEmpty(listEl, '📭', '暂无原始反馈', '导入数据后这里会显示所有原始反馈');

      data.forEach(fb => {
        const text = (fb.text_preview || fb.content?.text || '').slice(0, 200);
        const signalCount = fb.signal_count || 0;
        const stateIcon = { pending: '⏳', completed: '✅', failed: '❌', dismissed: '🗑️' }[fb.processing_state] || '📌';
        const stateBadge = createBadge(`${stateIcon} ${fb.processing_state}`, fb.processing_state === 'completed' ? 'success' : fb.processing_state === 'failed' ? 'danger' : 'default');

        const fbSourceButtonHtml = sourceButtonHtml(fb.source_url, fb.external_url, '数据来源');

        const card = createExpandableCard(
          `<div><div style="font-weight:600;margin-bottom:4px">${escapeHtml(text.slice(0, 80))}${text.length > 80 ? '…' : ''}</div>
           <div style="font-size:12px;color:var(--text-muted)">${escapeHtml(String(fb.source_type || '未知'))} · ${escapeHtml(fb.author?.name || '未知作者')} · ${signalCount} 个信号</div></div>
           <div class="card-header-actions">${fbSourceButtonHtml}${stateBadge.outerHTML}</div>`,
          `<p style="white-space:pre-wrap">${escapeHtml(text)}</p>
           <div style="margin-top:8px;font-size:12px;color:var(--text-muted)">ID: ${escapeHtml(String(fb.id))} · created: ${escapeHtml(fb.created_at || '—')}</div>`
        );
        appendSourceSnapshot(card.children[1], fb.id);
        listEl.appendChild(card);
      });
    } catch (e) {
      if (container.isConnected && token === revision && getSelectedProfile() === profile) showToast(`加载失败: ${e.message}`, 'danger');
    }
  }

  document.getElementById('btn-refresh-fb').onclick = load;
  load();
}

/* ==================================================== Page: Signals ========= */

async function renderSignalsPage(container) {
  const signalTypes = getProfileConfig().signalTypes;
  container.innerHTML = `
    <div class="filters-bar">
      <div class="form-group"><label class="form-label">信号类型</label><select class="form-select" id="sig-type"><option value="">全部</option>${signalTypes.map(t => `<option value="${t}">${t}</option>`).join('')}</select></div>
      <div class="form-group"><label class="form-label">最低模型自评分（未校准，仅查看筛选）: <span id="sig-conf-val">0.00</span></label><input type="range" class="form-input" id="sig-conf" min="0" max="1" step="0.05" value="0" style="padding:0"></div>
      <button class="btn btn-secondary btn-sm" id="btn-filter-sig">🔍 筛选</button>
    </div>
    <div id="sig-list"></div>
  `;

  const confSlider = document.getElementById('sig-conf');
  confSlider.oninput = () => document.getElementById('sig-conf-val').textContent = parseFloat(confSlider.value).toFixed(2);

  async function load() {
    const listEl = document.getElementById('sig-list');
    listEl.innerHTML = '';
    showSkeleton(listEl, 5);
    try {
      const params = { limit: 200, profile: getSelectedProfile() };
      const typeVal = document.getElementById('sig-type').value;
      if (typeVal) params.signal_type = typeVal;
      const confVal = parseFloat(document.getElementById('sig-conf').value);
      if (confVal > 0) params.min_model_self_score = confVal;
      params.version_id = getSelectedVersion();
      const data = await apiGet('/signals', params);
      listEl.innerHTML = '';
      if (!data.length) return showEmpty(listEl, '🔍', '暂无匹配信号', '尝试调整筛选条件');

      data.forEach(sig => {
        const conf = sig.confidence || 0;
        const confColor = confidenceColor(conf);
        const evidence = (sig.evidence || []).join(' · ');
        // P13-1: honest confidence display — model self-report, not calibrated
        const evidenceStatus = sig.evidence_validation_status || 'not_checked';
        const evidenceBadge = {
          verified: '<span class="badge badge-success" style="font-size:11px">证据已验证</span>',
          partial: '<span class="badge badge-warning" style="font-size:11px">证据部分匹配</span>',
          invalid: '<span class="badge badge-danger" style="font-size:11px">证据未匹配</span>',
          not_checked: '',
        }[evidenceStatus] || '';
        const confLabel = sig.calibrated_confidence != null
          ? `校准 ${(sig.calibrated_confidence * 100).toFixed(0)}%`
          : `模型自评 ${conf.toFixed(2)}（未校准）`;
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
          <div class="card-header">
            <div>
              <div class="card-title">${sig.summary}</div>
              <div class="card-subtitle">${sig.signal_type} · ${sig.source_type || '—'}</div>
            </div>
            <span class="badge" style="color:${confColor};background:${confColor}15">${confLabel}</span>
          </div>
          <div class="card-body">
            ${evidence ? `<div style="margin-bottom:8px"><strong>证据:</strong> «${evidence}» ${evidenceBadge}</div>` : ''}
            ${sig.implicit_need ? `<div style="color:var(--accent-secondary)"><strong>隐含需求:</strong> ${sig.implicit_need}</div>` : ''}
            ${sourceStatusHtml(sig.source_url, sig.external_url, '查看原始来源')}
            ${!sig.source_url && !sig.external_url && sig.source_type ? `<div style="margin-top:4px;font-size:12px;color:var(--text-muted)">📎 来源平台: ${escapeHtml(sig.source_type)}</div>` : ''}
          </div>
        `;
        listEl.appendChild(card);
      });
    } catch (e) {
      showToast(`加载失败: ${e.message}`, 'danger');
    }
  }

  document.getElementById('btn-filter-sig').onclick = load;
  load();
}

/* ==================================================== Page: Themes =========== */

async function renderThemesPage(container) {
  container.innerHTML = '<div class="card-grid-2" id="theme-grid"></div>';
  const grid = document.getElementById('theme-grid');
  showSkeleton(grid, 4);
  try {
    const data = await apiGet('/themes', { limit: 50, profile: getSelectedProfile(), version_id: getSelectedVersion() });
    grid.innerHTML = '';
    if (!data.length) return showEmpty(grid, '🏷️', '暂无主题', '运行管线以生成主题聚类');

    data.forEach(theme => {
      const card = document.createElement('div');
      card.className = 'card card-expandable';
      card.innerHTML = `
        <div class="card-header">
          <div style="flex:1">
            <div class="card-title">${theme.name}</div>
            <div class="card-subtitle">${theme.signal_count} 个信号 · ${theme.status}</div>
          </div>
          <button class="expand-toggle">▼</button>
        </div>
        <div class="card-body">
          <p>${theme.description}</p>
          ${(theme.representative_quotes || []).map(q => `<div class="evidence-quote">«${q}»</div>`).join('')}
        </div>
      `;
      const toggle = card.querySelector('.expand-toggle');
      toggle.onclick = () => { card.classList.toggle('expanded'); toggle.classList.toggle('open'); };
      grid.appendChild(card);
    });
  } catch (e) { showToast(`加载失败: ${e.message}`, 'danger'); }
}

/* ==================================================== Page: Pain Points ===== */

async function renderPainPointsPage(container) {
  container.innerHTML = '<div class="filters-bar"><div class="form-group"><label class="form-label">严重度</label><select class="form-select" id="pp-sev"><option value="">全部</option><option>critical</option><option>high</option><option>medium</option><option>low</option></select></div><button class="btn btn-secondary btn-sm" id="btn-pp-filter">🔍</button></div><div id="pp-list"></div>';

  async function load() {
    const listEl = document.getElementById('pp-list');
    listEl.innerHTML = '';
    showSkeleton(listEl, 4);
    try {
      const data = await apiGet('/pain-points', { limit: 50, profile: getSelectedProfile(), version_id: getSelectedVersion() });
      listEl.innerHTML = '';
      if (!data.length) return showEmpty(listEl, '😌', '暂无痛点', '运行管线以识别用户痛点');

      const sevIcon = { critical: '🔴', high: '🟠', medium: '🟡', low: '🟢' };
      const sevFilter = document.getElementById('pp-sev').value;

      data.filter(pp => !sevFilter || pp.severity === sevFilter).forEach(pp => {
        const badge = createBadge(`${sevIcon[pp.severity] || ''} ${pp.severity}`, pp.severity === 'critical' ? 'danger' : pp.severity === 'high' ? 'warning' : 'info');
        const card = createExpandableCard(
          `<div><div class="card-title">${pp.description}</div><div class="card-subtitle">${pp.user_segment} · ${pp.frequency}</div></div>${badge.outerHTML}`,
          `<p><strong>业务影响:</strong> ${pp.business_impact}</p>${(pp.evidence_quotes || []).map(q => `<div class="evidence-quote">«${q}»</div>`).join('')}`
        );
        listEl.appendChild(card);
      });
    } catch (e) { showToast(`加载失败: ${e.message}`, 'danger'); }
  }

  document.getElementById('btn-pp-filter').onclick = load;
  load();
}

/* ==================================================== Page: Opportunities == */

// Kept only for this browser session; these previews never alter stored assets.
const opportunityDiscoverySession = { selected: new Map(), result: null, materials: [], decisions: [], requireUnmetEvidence: true };

function discoverySourceUrl(value) {
  try {
    const url = new URL(String(value || ''));
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
  } catch (_error) {
    return null;
  }
}

function renderOpportunityDiscovery(panel) {
  const session = opportunityDiscoverySession;
  const selected = session.selected;
  const pageSize = 20;
  let offset = 0;
  let rows = [];
  let loading = false;
  let generating = false;
  let hasNext = false;
  panel.innerHTML = `
    <h2 class="section-title">从真实材料发现产品机会</h2>
    <p class="discovery-hint">选择已导入的产品反馈，每批最多 30 条。结果是至多 3 个待验证的候选，也可能没有值得跟进的机会。</p>
    <p class="discovery-hint">还没有材料？先去<a href="#connectors">数据源</a>连接已登录 Chrome，预览国内社区原文并选择导入，也可在「导入反馈」录入原文或 JSON。这里只分析你勾选的材料。</p>
    <label class="community-material-select"><input data-role="require-unmet" type="checkbox" checked><span>只推荐有当前困难与尚存缺口依据的候选</span></label>
    <p class="discovery-hint" data-role="quality-note"></p>
    <div class="discovery-toolbar">
      <span data-role="count" aria-live="polite"></span>
      <button class="btn btn-secondary btn-sm" data-role="clear" type="button">清空选择</button>
      <button class="btn btn-secondary btn-sm" data-role="refresh" type="button">刷新材料 / 重试</button>
      <button class="btn btn-primary btn-sm" data-role="discover" type="button">发现机会</button>
    </div>
    <div data-role="error" class="discovery-error" role="alert"></div>
    <div data-role="materials" aria-live="polite"></div>
    <div class="discovery-toolbar">
      <button class="btn btn-secondary btn-sm" data-role="previous" type="button">上一页</button>
      <span data-role="page" class="discovery-hint"></span>
      <button class="btn btn-secondary btn-sm" data-role="next" type="button">下一页</button>
    </div>
    <div data-role="results" aria-live="polite"></div>
  `;
  const find = role => panel.querySelector(`[data-role="${role}"]`);
  const errorEl = find('error');
  const materialsEl = find('materials');
  const resultsEl = find('results');
  const escaped = value => escapeHtml(String(value ?? ''));
  const qualityControl = find('require-unmet');
  if (qualityControl) qualityControl.checked = session.requireUnmetEvidence !== false;

  function updateQualityNote() {
    const note = find('quality-note');
    if (note) note.textContent = qualityControl?.checked ? '严格候选预览：当前困难、明确剩余缺口都须有本批原文支持；已有办法若被提及也须有依据。角色归类仍为模型判断，语义待核实、市场未验证。切换后需重新点击「发现机会」。' : '宽松线索预览：未启用当前困难与尚存缺口门禁，可能包含已解决问题或产品能力复述；不代表值得开发。切换后需重新点击「发现机会」。';
  }

  function updateControls() {
    find('count').textContent = `已选 ${selected.size} / 30 条（跨页保留）`;
    find('clear').disabled = generating || selected.size === 0;
    find('refresh').disabled = loading || generating;
    find('discover').disabled = generating || loading || selected.size === 0;
    find('discover').textContent = generating ? '正在分析所选材料…' : '发现机会';
    find('previous').disabled = loading || generating || offset === 0;
    find('next').disabled = loading || generating || !hasNext;
    if (qualityControl) qualityControl.disabled = generating;
    materialsEl.querySelectorAll('input[type="checkbox"]').forEach(input => {
      input.disabled = generating || loading || (!input.checked && selected.size >= 30);
    });
  }

  function renderMaterials() {
    materialsEl.innerHTML = '';
    find('page').textContent = `第 ${Math.floor(offset / pageSize) + 1} 页 · 本页 ${rows.length} 条`;
    if (!rows.length) {
      materialsEl.innerHTML = '<p class="discovery-hint">本页暂无产品反馈。可返回上一页，或先在「数据导入」导入真实材料后刷新。</p>';
    }
    rows.forEach(fb => {
      const row = document.createElement('div');
      row.className = 'discovery-material';
      const label = document.createElement('label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = selected.has(fb.id);
      checkbox.onchange = () => {
        if (checkbox.checked && selected.size < 30) selected.set(fb.id, fb);
        else {
          selected.delete(fb.id);
          checkbox.checked = false;
        }
        updateControls();
      };
      const description = document.createElement('div');
      description.className = 'discovery-material-text';
      description.innerHTML = `<strong>${escaped(fb.subject || fb.text_preview || '无标题材料')}</strong>
        <p>${escaped(fb.text_preview || '')}</p>
        <span class="discovery-hint">${escaped(fb.source_type)} · 导入时间 ${escaped(fb.created_at || '未知')}</span>`;
      label.append(checkbox, description);
      row.appendChild(label);
      const source = document.createElement('div');
      source.innerHTML = sourceButtonHtml(discoverySourceUrl(fb.source_url), fb.external_url);
      row.appendChild(source);
      materialsEl.appendChild(row);
    });
    updateControls();
  }

  async function loadMaterials(nextOffset = offset) {
    loading = true;
    errorEl.textContent = '';
    updateControls();
    materialsEl.innerHTML = '<p class="discovery-hint">正在读取已导入的产品反馈…</p>';
    try {
      const data = await apiGet('/feedback', { profile: 'product_feedback', version_id: getSelectedVersion(), limit: pageSize + 1, offset: nextOffset });
      if (!panel.isConnected) return;
      if (!Array.isArray(data)) throw new Error('材料列表格式异常，请重试');
      offset = nextOffset;
      rows = data.slice(0, pageSize);
      hasNext = data.length > pageSize;
      renderMaterials();
    } catch (error) {
      if (!panel.isConnected) return;
      errorEl.textContent = `材料加载失败：${error.message}。点击「刷新材料 / 重试」可重试。`;
      renderMaterials();
    } finally {
      loading = false;
      if (panel.isConnected) updateControls();
    }
  }

  function exportResult() {
    const result = session.result;
    const lines = ['MINING 产品机会候选清单', '候选预览，未保存为机会资产；模型归纳与方案均待人工核实。',
      `质量模式：${result.require_unmet_evidence === true ? '严格候选预览（当前困难与尚存缺口门禁）' : '宽松 / 兼容线索预览（未启用缺口门禁）'}`,
      '语义待核实；市场未验证。结构与逐字匹配不能证明需求普遍、语义正确或付费意愿。',
      `选择 ${result.selected_count} 条；分析 ${result.analyzed_count} 条；完全相同原文重复 ${result.duplicate_count} 条。`,
      String(result.message || ''), '', '本批所选材料：'];
    session.materials.forEach((fb, index) => lines.push(`${index + 1}. ${fb.subject || fb.text_preview || fb.id}`, `来源：${discoverySourceUrl(fb.source_url) || fb.external_url || '未记录来源'}；ID：${fb.id}`));
    (result.candidates || []).slice(0, 3).forEach((candidate, index) => {
      const decision = session.decisions[index] || {};
      lines.push('', `候选 ${index + 1}：${candidate.title}`, '系统归纳与建议（推断）：',
        `人群：${candidate.user_segment}`, `场景：${candidate.scenario}`, `痛点：${candidate.pain_point}`,
        `最小设想：${candidate.minimum_idea}`, `提出理由：${candidate.reasoning}`, '原文依据：');
      (candidate.evidence || []).forEach(evidence => lines.push(`「${evidence.quote}」`,
        `来源：${discoverySourceUrl(evidence.source_url) || '来源不可打开'}；反馈 ID：${evidence.feedback_id}`,
        sourceEvidenceDescription(evidence), `证据元信息：${JSON.stringify(evidence)}`));
      const assessment = candidate.need_assessment;
      if (assessment) {
        lines.push(`缺口判断依据：${assessmentBasisLabel(assessment.basis)}（模型判断，语义待核实）`);
        for (const [role, label] of assessmentRoles()) {
          const part = assessment[role] || {};
          lines.push(`${label}：${part.statement || part.description || '未知 / 未提供'}${part.status ? `；状态：${assessmentStatusLabel(part.status)}` : ''}`);
          (part.evidence || []).forEach(evidence => lines.push(`${label}原话：「${evidence.quote}」`, `来源：${discoverySourceUrl(evidence.source_url) || '来源不可打开'}；反馈 ID：${evidence.feedback_id}`, sourceEvidenceDescription(evidence), `角色证据元信息：${JSON.stringify(evidence)}`));
        }
      } else lines.push('缺口评估：未提供结构化角色依据，不代表已核实当前需求。');
      lines.push('待验证问题：', ...(candidate.validation_questions || []).map(question => `- ${question}`),
        `我的判断：${decision.action || '尚未判断'}`, `原因 / 下一步：${decision.note || '未填写'}`);
    });
    lines.push('', '限制：', ...(result.limitations || []));
    (result.excluded || []).forEach(item => lines.push(`排除：${item.feedback_id || (item.candidate_index == null ? '材料 / 候选' : `候选 ${item.candidate_index}`)}；${item.reason}`));
    const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'mining-opportunity-candidates.txt';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function renderResults() {
    const result = session.result;
    resultsEl.innerHTML = '';
    if (!result) return;
    const summary = document.createElement('div');
    summary.className = 'discovery-summary';
    summary.innerHTML = `<h3>本次候选预览 · 未保存为机会资产</h3>
      <p>${escaped(result.message || '')}</p>
      <p class="discovery-hint">本次质量模式：${result.require_unmet_evidence === true ? '严格候选预览（当前困难与尚存缺口门禁）' : '宽松 / 兼容线索预览（未启用缺口门禁）'}。语义待核实，市场未验证。</p>
      <p class="discovery-hint">选择 ${escaped(result.selected_count)} 条；分析 ${escaped(result.analyzed_count)} 条；完全相同原文重复 ${escaped(result.duplicate_count)} 条。调整材料后需重新点击「发现机会」。</p>
      <p class="discovery-hint">本结果仅做文本归纳，未进行语义去重或市场验证。人群、场景与痛点也是模型归纳，请核对原话；不能据此认定需求普遍或用户愿意付费。</p>
      <p class="discovery-hint">人工判断仅保留在当前浏览器页面中，刷新或关闭页面会丢失，请先导出清单。</p>`;
    const exportButton = document.createElement('button');
    exportButton.type = 'button';
    exportButton.className = 'btn btn-secondary btn-sm';
    exportButton.textContent = '下载候选与人工判断清单';
    exportButton.onclick = exportResult;
    summary.appendChild(exportButton);
    resultsEl.appendChild(summary);
    const candidates = (result.candidates || []).slice(0, 3);
    if (!candidates.length) {
      const empty = document.createElement('p');
      empty.className = 'discovery-hint';
      empty.textContent = '本批暂无值得跟进的机会。可补充更具体的困难、现有替代做法及原文来源后重新分析。';
      resultsEl.appendChild(empty);
    }
    candidates.forEach((candidate, index) => {
      const card = document.createElement('article');
      card.className = 'card discovery-candidate';
      card.innerHTML = `<h3>${index + 1}. ${escaped(candidate.title)}</h3>
        <div data-need-assessment="panel"></div>
        <section><h4>原文依据</h4>${(candidate.evidence || []).map((evidence, evidenceIndex) => `
          <div data-source-evidence="${evidenceIndex}">
          <blockquote class="evidence-quote">${escaped(evidence.quote)}</blockquote>
          <div class="discovery-hint">${escaped(evidence.source_type)} · ${escaped(evidence.feedback_id)} · 引文匹配字段：${escaped(evidence.quote_field || '未记录')}${evidence.source_created_at ? ` · 源创建时间 ${escaped(evidence.source_created_at)}` : ''}${evidence.source_captured_at ? ` · 采集时间 ${escaped(evidence.source_captured_at)}` : ''}</div>
          ${sourceButtonHtml(discoverySourceUrl(evidence.source_url), evidence.external_url, sourceEvidenceLinkLabel(evidence))}</div>`).join('')}</section>
        <section><h4>系统归纳与建议（推断，待确认）</h4>
          <p><strong>目标人群：</strong>${escaped(candidate.user_segment)}</p>
          <p><strong>使用场景：</strong>${escaped(candidate.scenario)}</p>
          <p><strong>具体痛点：</strong>${escaped(candidate.pain_point)}</p>
          <p><strong>最小产品 / 功能设想：</strong>${escaped(candidate.minimum_idea)}</p>
          <p><strong>提出理由：</strong>${escaped(candidate.reasoning)}</p></section>
        <section><h4>待验证问题</h4><ul>${(candidate.validation_questions || []).map(question => `<li>${escaped(question)}</li>`).join('')}</ul></section>`;
      (candidate.evidence || []).forEach((evidence, evidenceIndex) => {
        appendSourceSnapshot(card.querySelector(`[data-source-evidence="${evidenceIndex}"]`), evidence.feedback_id, evidence);
      });
      renderNeedAssessment(card, candidate.need_assessment);
      const review = document.createElement('section');
      review.className = 'discovery-review';
      review.innerHTML = '<h4>我的判断（仅本次会话）</h4>';
      const decision = session.decisions[index] || { action: '', note: '' };
      session.decisions[index] = decision;
      const actionLabel = document.createElement('label');
      actionLabel.className = 'form-label';
      actionLabel.textContent = '后续行动';
      const select = document.createElement('select');
      select.className = 'form-select';
      ['', '继续找用户了解', '做一个小原型', '放弃'].forEach(action => {
        const option = document.createElement('option');
        option.value = action;
        option.textContent = action || '尚未判断';
        select.appendChild(option);
      });
      select.value = decision.action;
      select.onchange = () => { decision.action = select.value; };
      actionLabel.appendChild(select);
      const noteLabel = document.createElement('label');
      noteLabel.className = 'form-label';
      noteLabel.textContent = '判断原因 / 下一步要验证什么';
      const note = document.createElement('textarea');
      note.className = 'form-textarea';
      note.rows = 2;
      note.value = decision.note;
      note.oninput = () => { decision.note = note.value; };
      noteLabel.appendChild(note);
      review.append(actionLabel, noteLabel);
      card.appendChild(review);
      resultsEl.appendChild(card);
    });
    const notices = document.createElement('div');
    notices.className = 'discovery-hint';
    notices.innerHTML = (result.limitations || []).map(item => `<p>限制：${escaped(item)}</p>`).join('') +
      (result.excluded || []).map(item => `<p>已排除 ${escaped(item.feedback_id || (item.candidate_index == null ? '材料 / 候选' : `候选 ${item.candidate_index}`))}：${escaped(item.reason)}</p>`).join('');
    resultsEl.appendChild(notices);
  }

  function assessmentRoles() { return [['current_difficulty', '当前困难'], ['current_solution', '已有办法'], ['remaining_gap', '尚存缺口']]; }
  function assessmentStatusLabel(value) { return { mentioned: '原文已提及', unknown: '未知', explicit: '原文明确不足', already_addressed: '原文显示已解决' }[value] || '未知'; }
  function assessmentBasisLabel(value) { return { current_complaint: '当前困难 / 抱怨', feature_request: '直接功能请求', historical_resolved: '历史困难已解决', solution_praise: '现有方案赞美', unknown: '未知' }[value] || '未知'; }
  function renderNeedAssessment(card, assessment) {
    const target = card.querySelector('[data-need-assessment="panel"]') || card;
    const section = document.createElement('section');
    const title = document.createElement('h4'); title.textContent = '当前困难与尚存缺口（模型判断，语义待核实）'; section.appendChild(title);
    if (!assessment) {
      const note = document.createElement('p'); note.className = 'discovery-hint'; note.textContent = '未提供结构化角色依据；这是宽松 / 兼容线索，不代表当前仍有未满足需求。'; section.appendChild(note); target.appendChild(section); return;
    }
    const basis = document.createElement('p'); basis.className = 'discovery-hint'; basis.textContent = `判断依据：${assessmentBasisLabel(assessment.basis)}。市场未验证。`; section.appendChild(basis);
    for (const [role, label] of assessmentRoles()) {
      const part = assessment[role] || {}, block = document.createElement('div');
      const heading = document.createElement('p'); const strong = document.createElement('strong'); strong.textContent = `${label}：`; heading.appendChild(strong);
      const description = document.createElement('span'); description.textContent = `${part.statement || part.description || '未知 / 未提供'}${part.status ? `（${assessmentStatusLabel(part.status)}）` : ''}`; heading.appendChild(description); block.appendChild(heading);
      const evidenceList = Array.isArray(part.evidence) ? part.evidence : [];
      if (!evidenceList.length) { const note = document.createElement('p'); note.className = 'discovery-hint'; note.textContent = '该角色未提供本批原话；未知内容不能据此补全。'; block.appendChild(note); }
      evidenceList.forEach(evidence => {
        const quote = document.createElement('blockquote'); quote.className = 'evidence-quote'; quote.textContent = evidence.quote; block.appendChild(quote);
        const meta = document.createElement('p'); meta.className = 'discovery-hint'; meta.textContent = `${evidence.source_type || '未知来源'} · ${evidence.feedback_id || '未知反馈 ID'} · 引文匹配字段：${evidence.quote_field || '未记录'}`; block.appendChild(meta);
        block.appendChild(createSourceLink(evidence.source_url, sourceEvidenceLinkLabel(evidence)));
        appendSourceSnapshot(block, evidence.feedback_id, evidence);
      });
      section.appendChild(block);
    }
    target.appendChild(section);
  }

  find('clear').onclick = () => { selected.clear(); renderMaterials(); };
  find('refresh').onclick = () => loadMaterials();
  find('previous').onclick = () => loadMaterials(Math.max(0, offset - pageSize));
  find('next').onclick = () => loadMaterials(offset + pageSize);
  if (qualityControl) qualityControl.onchange = () => { if (generating) return; session.requireUnmetEvidence = qualityControl.checked; updateQualityNote(); };
  find('discover').onclick = async () => {
    if (!selected.size || selected.size > 30 || generating) return;
    generating = true;
    errorEl.textContent = '';
    updateControls();
    const materials = [...selected.values()];
    const requireUnmet = qualityControl?.checked === true;
    try {
      const request = { feedback_ids: materials.map(fb => fb.id) };
      if (qualityControl) request.require_unmet_evidence = requireUnmet;
      const result = await apiPost('/opportunities/discover', request);
      if (!panel.isConnected || getSelectedProfile() !== 'product_feedback' || session.selected !== selected) return;
      if (requireUnmet && result.require_unmet_evidence !== true) throw new Error('服务未确认当前困难与尚存缺口门禁已启用，请检查版本后重试');
      if (requireUnmet && (!Array.isArray(result.candidates) || result.candidates.some(candidate => !candidate.need_assessment))) throw new Error('严格候选缺少结构化角色依据，未展示为推荐结果');
      session.result = result;
      session.materials = materials;
      session.decisions = [];
      if (panel.isConnected) renderResults();
    } catch (error) {
      if (panel.isConnected) errorEl.textContent = `机会发现失败：${error.message}。选择已保留，可再次点击「发现机会」重试；下方已有结果属于上一次分析。`;
    } finally {
      generating = false;
      if (panel.isConnected) updateControls();
    }
  };
  updateQualityNote();
  renderResults();
  loadMaterials();
}

async function renderOpportunitiesPage(container) {
  const profile = getSelectedProfile();
  container.innerHTML = `${profile === 'product_feedback' ? '<section class="card discovery-panel" id="opp-discovery"></section><h2 class="section-title">历史机会资产</h2><p class="discovery-hint">以下为既有管线生成的历史资产，机器处理状态不代表人工已审核。</p>' : ''}<div id="opp-list"></div>`;
  if (profile === 'product_feedback') renderOpportunityDiscovery(container.querySelector('#opp-discovery'));
  const listEl = container.querySelector('#opp-list');
  showSkeleton(listEl, 4);
  try {
    const data = await apiGet('/opportunities', { limit: 50, profile: getSelectedProfile(), version_id: getSelectedVersion() });
    listEl.innerHTML = '';
    if (!data.length) return showEmpty(listEl, '💡', '暂无历史机会资产', profile === 'product_feedback' ? '可先在上方选择真实材料，预览本批候选机会' : '运行管线以识别产品机会');

    data.forEach(opp => {
      // Build card manually to hook into expand for lazy-load
      const card = document.createElement('div');
      card.className = 'card card-expandable';

      const header = document.createElement('div');
      header.className = 'card-header';
      header.innerHTML = `<div class="card-title">${escapeHtml(opp.jtbd_statement)}</div>`;

      const toggle = document.createElement('button');
      toggle.className = 'expand-toggle';
      toggle.innerHTML = '▼';

      const body = document.createElement('div');
      body.className = 'card-body';
      body.innerHTML = `<p>${escapeHtml(opp.description)}</p>
         ${(opp.assumptions || []).map(a => `<div style="margin:4px 0;color:var(--warning)">⚠ 假设: ${escapeHtml(a)}</div>`).join('')}
         <div style="margin-top:8px;font-size:12px;color:var(--text-muted)">优先级: ${escapeHtml(JSON.stringify(opp.priority))}</div>
         <div class="opp-evidence-placeholder" id="opp-ev-${opp.id}" style="margin-top:12px"></div>`;

      let evidenceLoaded = false;
      toggle.onclick = async () => {
        card.classList.toggle('expanded');
        toggle.classList.toggle('open');

        // Lazy-load supporting evidence on first expand
        if (!evidenceLoaded && card.classList.contains('expanded')) {
          evidenceLoaded = true;
          const placeholder = document.getElementById(`opp-ev-${opp.id}`);
          if (placeholder) {
            placeholder.innerHTML = '<div class="skeleton skeleton-row" style="height:40px"></div>';
            try {
              const detail = await apiGet(`/opportunities/${opp.id}`);
              const evidence = detail.supporting_evidence || [];
              if (evidence.length) {
                let evHtml = '<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border)"><strong>📎 支撑证据链:</strong></div>';
                evidence.forEach(ev => {
                  const quote = ev.quote || ev.signal_summary || '';
                  const srcType = ev.source_type || '';
                  const sigId = ev.signal_id || '';
                  evHtml += `<div style="margin:6px 0;font-size:13px">💬 <em>${escapeHtml(quote)}</em></div>
                    <div style="font-size:11px;color:var(--text-muted);margin-bottom:2px">Signal: ${escapeHtml(sigId)} [${escapeHtml(srcType)}]${ev.author_segment ? ' · ' + escapeHtml(ev.author_segment) : ''}</div>`;
                  evHtml += sourceStatusHtml(ev.source_url, ev.external_url, '查看原始来源');
                });
                placeholder.innerHTML = evHtml;
              } else {
                placeholder.innerHTML = '<div style="font-size:12px;color:var(--text-muted);margin-top:8px">暂无支撑证据</div>';
              }
            } catch (e) {
              placeholder.innerHTML = `<div style="color:var(--danger);font-size:12px">加载失败: ${escapeHtml(e.message)}</div>`;
            }
          }
        }
      };

      header.appendChild(toggle);
      card.appendChild(header);
      card.appendChild(body);
      listEl.appendChild(card);
    });
  } catch (e) { showToast(`加载失败: ${e.message}`, 'danger'); }
}

/* ==================================================== Page: Requirements ==== */

async function renderRequirementsPage(container) {
  container.innerHTML = '<div id="req-list"></div>';
  const listEl = document.getElementById('req-list');
  showSkeleton(listEl, 3);
  try {
    const data = await apiGet('/requirements', { limit: 50, profile: getSelectedProfile(), version_id: getSelectedVersion() });
    listEl.innerHTML = '';
    if (!data.length) return showEmpty(listEl, '📝', '暂无需求候选', '运行管线以生成需求资产');

    data.forEach(req => {
      const stories = (req.user_stories || []).map(s =>
        `<tr><td>${s.role}</td><td>${s.action}</td><td>${s.benefit}</td></tr>`
      ).join('');

      // Build evidence chain preview
      const evidenceCount = (req.evidence_trail || []).length;
      const evPreview = evidenceCount > 0
        ? `<span class="badge badge-info">📎 ${evidenceCount} 条证据</span>`
        : '<span class="badge badge-default">无证据</span>';

      const card = createExpandableCard(
        `<div style="flex:1">
          <div class="card-title">${req.title}</div>
          <div class="card-subtitle">${(req.acceptance_criteria || []).length} 条验收标准 · ${stories ? '含用户故事' : '无用户故事'}</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px">${evPreview}<button class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); loadEvidenceChain('${req.id}', this)" title="查看证据链">🔗 追溯</button></div>`,
        `<div class="section-title" style="font-size:14px">📋 用户故事</div>
         <div class="table-container"><table class="table"><thead><tr><th>角色</th><th>行为</th><th>价值</th></tr></thead><tbody>${stories || '<tr><td colspan="3">—</td></tr>'}</tbody></table></div>
         <div class="section-title" style="font-size:14px;margin-top:16px">✅ 验收标准</div>
         <ul style="padding-left:20px">${(req.acceptance_criteria || []).map(a => `<li style="margin-bottom:4px">${a}</li>`).join('') || '<li>—</li>'}</ul>
         ${req.decision_reasoning ? `<div class="section-title" style="font-size:14px;margin-top:16px">🧠 决策理由</div><p>${req.decision_reasoning}</p>` : ''}
         <div id="evidence-chain-${req.id}" style="margin-top:16px"></div>`
      );
      listEl.appendChild(card);
    });
  } catch (e) { showToast(`加载失败: ${e.message}`, 'danger'); }
}

/* ==================================================== Evidence Chain ======== */

function revealEvidenceChainContainer(container) {
  const card = container.closest('.card-expandable');
  if (!card) return;
  card.classList.add('expanded');
  const toggle = card.querySelector('.expand-toggle');
  if (toggle) toggle.classList.add('open');
}

window.loadEvidenceChain = async function (reqId, trigger) {
  const container = document.getElementById(`evidence-chain-${reqId}`);
  if (!container) return;
  revealEvidenceChainContainer(container);
  if (container.dataset.loaded === 'true') {
    container.scrollIntoView({ block: 'nearest' });
    return;
  }
  if (container.dataset.loading === 'true') return;

  container.dataset.loading = 'true';
  const originalTriggerText = trigger?.textContent;
  if (trigger) {
    trigger.disabled = true;
    trigger.textContent = '⏳ 加载中';
  }
  container.innerHTML = '<div class="skeleton skeleton-row" style="height:60px"></div><div class="skeleton skeleton-row" style="height:60px"></div>';
  try {
    const data = await apiGet(`/requirements/${reqId}/evidence-trail`);
    container.innerHTML = '';

    const links = data.evidence_links || [];
    if (!links.length) {
      container.innerHTML = '<p style="color:var(--text-muted);padding:12px">暂无证据链数据</p>';
      container.dataset.loaded = 'true';
      return;
    }

    const chain = document.createElement('div');
    chain.className = 'evidence-chain';

    // Requirement header
    const reqNode = document.createElement('div');
    reqNode.className = 'evidence-node level-requirement';
    reqNode.innerHTML = `<div class="evidence-node-header">📝 需求: ${data.title}</div>`;
    chain.appendChild(reqNode);

    links.forEach(link => {
      const node = document.createElement('div');
      node.className = `evidence-node level-signal`;
      const conf = link.confidence || 0;
      const confColor = confidenceColor(conf);
      node.innerHTML = `
        <div class="evidence-node-header">
          🔬 <span style="flex:1">${link.signal_summary || '信号'}</span>
          <span class="badge" style="color:${confColor};background:${confColor}15">模型自评 ${conf.toFixed(2)}</span>
        </div>
        <div class="evidence-node-body">
          <div><strong>类型:</strong> ${link.signal_type || '—'} · <strong>来源:</strong> ${link.source_type || '—'}</div>
          ${link.author_segment ? `<div><strong>用户:</strong> ${link.author_segment}</div>` : ''}
          ${link.quote ? `<div class="evidence-quote">«${link.quote}»</div>` : ''}
          <div style="margin-top:4px;font-size:11px;color:var(--text-muted)">
            ${link.raw_feedback_preview ? `原文预览: ${link.raw_feedback_preview.slice(0, 100)}…` : ''}
          </div>
        </div>
      `;

      // Append source state if available.
      const bodyEl = node.querySelector('.evidence-node-body');
      if (bodyEl) {
        appendSourceStatus(bodyEl, link.source_url, link.external_url, '查看原始来源');
      }

      chain.appendChild(node);
    });

    // Validation summary
    const validation = data.validation || {};
    const validBadge = validation.is_valid
      ? '<span class="badge badge-success">✅ 证据链完整</span>'
      : `<span class="badge badge-warning">⚠ ${validation.broken_links?.length || 0} 个断裂链接</span>`;

    const valNode = document.createElement('div');
    valNode.style.cssText = 'padding:12px;margin-top:8px;font-size:13px;';
    valNode.innerHTML = `${validBadge} ${validation.total_links || 0} 条证据，${validation.valid_links || 0} 条有效`;
    chain.appendChild(valNode);

    container.appendChild(chain);
    container.dataset.loaded = 'true';
  } catch (e) {
    container.innerHTML = `<p style="color:var(--danger)">证据链加载失败: ${e.message}</p>`;
  } finally {
    delete container.dataset.loading;
    if (trigger) {
      trigger.disabled = false;
      trigger.textContent = originalTriggerText || '🔗 追溯';
    }
  }
};

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

/* ==================================================== Page: Connectors ====== */

function renderCommunitySamplesPanel(panel) {
  // This preview and its import receipt belong to this mounted page only.
  let revision = 0;
  let previewing = false;
  let importing = false;
  let readingImported = false;
  let items = [];
  let summary = null;
  let selected = new Set();
  let imported = null;
  const isActive = () => panel.isConnected && getSelectedProfile() === 'product_feedback' && getRoute() === 'connectors';
  panel.innerHTML = `
    <h2 class="section-title">从公开社区取得第一批材料</h2>
    <p class="discovery-hint">先预览原始帖子或评论，再勾选导入。采集预览不入库、不调用模型；导入后也不会自动分析。</p>
    <div class="community-controls">
      <label class="form-label">来源<select class="form-select" data-community="source"><option value="v2ex">V2EX 公开订阅</option><option value="hn">Hacker News</option></select></label>
      <label class="form-label" data-community="node-label">节点<select class="form-select" data-community="node"><option value="qna">问与答</option><option value="ideas">奇思妙想</option></select></label>
      <label class="form-label" data-community="kind-label" hidden>材料类型<select class="form-select" data-community="kind"><option value="both">Ask HN 帖子与评论</option><option value="ask">Ask HN 帖子</option><option value="comments">HN 评论</option></select></label>
      <label class="form-label community-query">关键词（可留空）<input class="form-input" data-community="query" maxlength="200" placeholder="不限定产品领域"></label>
      <label class="form-label">近几天<input class="form-input" data-community="days" type="number" min="1" max="365" value="30"></label>
      <label class="form-label">最多条数<input class="form-input" data-community="limit" type="number" min="1" max="30" value="10"></label>
    </div>
    <p class="discovery-hint" data-community="coverage"></p>
    <div class="discovery-toolbar"><button class="btn btn-primary" type="button" data-community="preview">采集预览</button><span class="discovery-hint">预览与人工选择只保留在当前页面；新预览会替换当前批。</span></div>
    <div class="discovery-error" role="alert" data-community="error"></div>
    <div aria-live="polite" data-community="summary"></div>
    <div data-community="items"></div>
    <div class="discovery-toolbar">
      <span class="discovery-hint" aria-live="polite" data-community="count"></span>
      <button class="btn btn-secondary btn-sm" type="button" data-community="all">全选</button>
      <button class="btn btn-secondary btn-sm" type="button" data-community="none">取消选择</button>
      <button class="btn btn-primary" type="button" data-community="import">导入所选材料</button>
    </div>
    <div class="discovery-hint" role="status" data-community="receipt"></div>
    <p class="discovery-hint" data-community="handoff-note" hidden>下一步会替换机会页已有的材料选择、候选结果和人工备注；请先导出需要保留的清单。然后在机会页手动点击「发现机会」。</p>
    <button class="btn btn-primary" type="button" data-community="handoff" hidden>用本批材料发现机会</button>
  `;
  const find = name => panel.querySelector(`[data-community="${name}"]`);
  const fields = ['source', 'node', 'kind', 'query', 'days', 'limit'];
  const appendText = (parent, tag, text, className = '') => {
    const element = document.createElement(tag);
    element.className = className;
    element.textContent = String(text ?? '');
    parent.appendChild(element);
    return element;
  };

  function updateControls() {
    const hn = find('source').value === 'hn';
    find('node-label').hidden = hn;
    find('kind-label').hidden = !hn;
    find('coverage').textContent = hn
      ? 'HN 使用 Algolia 搜索 API，最多 3 次请求；帖子限 Ask HN，评论来自 HN 各类讨论。样本偏英语和技术人群，不能代表全部市场。'
      : 'V2EX 读取问与答 / 奇思妙想当前公开订阅流，最多 1 次请求；关键词只过滤当前订阅流。天数仅筛选其中的发布时间，不代表覆盖该时段的全部帖子，也不含评论。';
    find('preview').disabled = previewing || importing || readingImported;
    find('preview').textContent = previewing ? '正在采集预览…' : '采集预览';
    fields.forEach(name => { find(name).disabled = importing || readingImported; });
    find('count').textContent = items.length ? `本批 ${items.length} 条，已选 ${selected.size} 条` : '';
    find('all').disabled = !items.length || previewing || importing || Boolean(imported);
    find('none').disabled = !selected.size || previewing || importing || Boolean(imported);
    find('import').disabled = !selected.size || previewing || importing || Boolean(imported);
    find('import').textContent = importing ? '正在处理所选材料…' : imported ? '本批所选材料已处理' : '导入所选材料';
    find('items').querySelectorAll('input[type="checkbox"]').forEach(input => {
      input.disabled = previewing || importing || Boolean(imported);
    });
    find('handoff').hidden = !imported;
    find('handoff-note').hidden = !imported;
    find('handoff').disabled = !imported || importing || previewing || readingImported;
    find('handoff').textContent = readingImported ? '正在读取本批材料…' : imported && !imported.materials ? '重试读取本批材料' : '用本批材料发现机会';
  }

  function clearPreview(message = '') {
    revision += 1;
    previewing = false;
    items = [];
    summary = null;
    selected = new Set();
    imported = null;
    ['summary', 'items', 'receipt', 'error'].forEach(name => { find(name).textContent = ''; });
    find('summary').textContent = message;
    updateControls();
  }

  function renderPreview() {
    const summaryEl = find('summary');
    summaryEl.textContent = '';
    const status = { empty: '未找到符合条件的材料', bounded: '已达到采集预算，仅为有界样本', collected: '采集预览完成', completed: '采集预览完成', complete: '采集预览完成' }[summary.status] || `采集状态：${summary.status || '未知'}`;
    const stopReason = { sample_limit: '已达到所选条数上限', request_limit: '已达到请求预算', sources_exhausted: '当前搜索结果已读完', single_feed_exhausted: '当前订阅流已读完', request_or_response_error: '请求或响应失败' }[summary.stop_reason] || summary.stop_reason || '未提供';
    appendText(summaryEl, 'p', status, 'community-summary-title');
    appendText(summaryEl, 'p', `请求 ${summary.requests ?? '未知'} 次 · 读取 ${summary.fetched ?? '未知'} 条 · 返回 ${items.length} 条 · 跳过 ${summary.skipped ?? '未知'} 条`, 'discovery-hint');
    appendText(summaryEl, 'p', `来源 ${summary.source ?? '未知'} · 关键词 ${summary.query || '未限定'} · 最近 ${summary.days ?? '未知'} 天 · 最多 ${summary.limit ?? '未知'} 条 · 类型 ${(summary.kinds || []).join(' / ')} · 终止原因 ${stopReason}`, 'discovery-hint');
    if (summary.coverage_note) appendText(summaryEl, 'p', summary.coverage_note, 'discovery-hint');
    if (summary.published_from || summary.published_to) appendText(summaryEl, 'p', `发布时间筛选范围：${summary.published_from || '未知'} 至 ${summary.published_to || '未知'}`, 'discovery-hint');
    const skipLabels = { outside_time_window: '发布时间不在范围内', missing_published_at: '缺少发布时间', invalid_published_at: '发布时间无效', invalid_timestamp: '时间无效', query_mismatch: '关键词未匹配', duplicate_id: '重复来源 ID', invalid_source_url: '来源链接无效', empty_text: '正文为空', beyond_sample_limit: '超出所选条数', invalid_hit: '记录格式无效', invalid_id: '来源 ID 无效', deleted_or_dead: '记录已删除或失效' };
    const skipped = Object.entries(summary.skip_reasons || {}).map(([reason, count]) => `${skipLabels[reason] || reason}：${count}`);
    if (skipped.length) appendText(summaryEl, 'p', `跳过原因：${skipped.join('；')}`, 'discovery-hint');
    (summary.errors || []).forEach(error => appendText(summaryEl, 'p', `采集提示：${error}`, 'discovery-error'));
    if (!items.length) appendText(summaryEl, 'p', '可调整关键词、节点或时间范围后重新预览。V2EX 无法补齐订阅流以外的历史内容。', 'discovery-hint');
    const list = find('items');
    list.textContent = '';
    items.forEach((item, index) => {
      const row = document.createElement('article');
      row.className = 'community-material';
      const label = document.createElement('label');
      label.className = 'community-material-select';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = selected.has(index);
      checkbox.onchange = () => {
        if (!isActive() || importing || imported) return;
        if (checkbox.checked) selected.add(index);
        else selected.delete(index);
        updateControls();
      };
      label.appendChild(checkbox);
      appendText(label, 'strong', item.subject || '无标题材料');
      row.appendChild(label);
      const details = document.createElement('details');
      appendText(details, 'summary', item.content_nature === 'api_excerpt' ? '展开 API 摘要（线索）' : item.content_nature === 'curated_comment' ? '展开精选评论（线索）' : '展开留存正文');
      appendText(details, 'p', item.text, 'community-original');
      row.appendChild(details);
      appendText(row, 'p', `发布时间：${item.raw_payload?.published_at || '未提供'} · 采集时间：${item.source_captured_at || '未提供'}`, 'discovery-hint');
      appendText(row, 'p', `${CONTENT_NATURE_LABELS[item.content_nature] || CONTENT_NATURE_LABELS.unknown} · ${LOCATOR_LABELS[item.locator_level] || LOCATOR_LABELS.unknown}`, 'discovery-hint');
      const source = discoverySourceUrl(item.external_url);
      row.appendChild(source ? createSourceLink(source, sourceEvidenceLinkLabel(item)) : createSourceUnavailable('来源链接不可打开'));
      list.appendChild(row);
    });
    updateControls();
  }

  fields.forEach(name => {
    const invalidate = () => {
      if (!isActive() || importing || readingImported) return;
      clearPreview('采集条件已改变，请重新采集预览。旧批次已清除。');
    };
    find(name).oninput = invalidate;
    find(name).onchange = invalidate;
  });
  find('all').onclick = () => {
    if (!isActive() || importing || previewing || imported) return;
    selected = new Set(items.map((_, index) => index));
    renderPreview();
  };
  find('none').onclick = () => {
    if (!isActive() || importing || previewing || imported) return;
    selected.clear();
    renderPreview();
  };
  find('preview').onclick = async () => {
    if (!isActive() || previewing || importing || readingImported) return;
    const request = {
      source: find('source').value,
      query: find('query').value.trim(),
      days: Number(find('days').value),
      limit: Number(find('limit').value),
      v2ex_node: find('node').value,
      kind: find('kind').value,
    };
    if (!Number.isInteger(request.days) || request.days < 1 || request.days > 365 || !Number.isInteger(request.limit) || request.limit < 1 || request.limit > 30 || request.query.length > 200) {
      find('error').textContent = '请填写 1–365 天、1–30 条，关键词最多 200 字。';
      return;
    }
    clearPreview();
    const token = revision;
    previewing = true;
    updateControls();
    try {
      const response = await apiPost('/connectors/community/preview', request);
      if (!isActive() || token !== revision) return;
      if (!Array.isArray(response.items) || response.items.length > 30 || !response.summary || typeof response.summary !== 'object') throw new Error('预览返回格式异常，请重试');
      items = response.items;
      summary = response.summary;
      renderPreview();
    } catch (error) {
      if (!isActive() || token !== revision) return;
      find('error').textContent = `采集预览失败：${error.message}。本次没有导入材料，可重试。`;
    } finally {
      if (isActive() && token === revision) {
        previewing = false;
        updateControls();
      }
    }
  };
  find('import').onclick = async () => {
    if (!isActive() || !selected.size || previewing || importing || imported) return;
    const token = revision;
    // Preserve every original field, including raw_payload and source metadata.
    const chosen = items.filter((_, index) => selected.has(index));
    importing = true;
    find('error').textContent = '';
    find('receipt').textContent = '';
    updateControls();
    try {
      const response = await apiPost('/feedback/batch', chosen);
      if (!isActive() || token !== revision) return;
      if (!Array.isArray(response.feedback_ids) || response.feedback_ids.length !== chosen.length || response.feedback_ids.some(id => typeof id !== 'string' || !id.trim())) throw new Error('导入回执与所选材料不对应，无法建立本批选择');
      imported = { ids: [...new Set(response.feedback_ids)], processed: response.feedback_ids.length, materials: null };
      updateControls();
      await readImportedMaterials(token);
    } catch (error) {
      if (!isActive() || token !== revision) return;
      find('error').textContent = `导入未确认完成：${error.message}。部分材料可能已处理；可重试，重复材料可能复用已有 ID。`;
    } finally {
      if (isActive() && token === revision) {
        importing = false;
        updateControls();
      }
    }
  };
  async function readImportedMaterials(token) {
    readingImported = true;
    find('error').textContent = '';
    find('receipt').textContent = `导入已确认处理 ${imported.processed} 条材料；正在回读 ${imported.ids.length} 个实际反馈 ID，核对已存内容与来源…`;
    updateControls();
    try {
      const actual = new Map();
      for (const id of imported.ids) {
        const detail = await apiGet(`/feedback/${encodeURIComponent(id)}`);
        if (!isActive() || token !== revision) return;
        if (detail.id !== id || detail.pipeline_profile !== 'product_feedback' || typeof detail.content?.text !== 'string') throw new Error('已存材料的 ID、模式或正文不匹配');
        actual.set(id, {
          ...detail, subject: detail.content.subject, text_preview: detail.content.text,
          source_url: discoverySourceUrl(detail.external_url),
        });
      }
      imported.materials = actual;
      find('receipt').textContent = `已处理 ${imported.processed} 条所选材料；本批可用 ${actual.size} 条（按实际返回 ID 合并并回读）。可能复用已存在材料，以已存原文和来源为准，不代表全部新增；尚未调用模型。`;
    } catch (error) {
      if (!isActive() || token !== revision) return;
      find('error').textContent = `导入已完成，但本批材料回读失败：${error.message}。点击「重试读取本批材料」只重试回读，不会再次导入。`;
    } finally {
      if (isActive() && token === revision) {
        readingImported = false;
        updateControls();
      }
    }
  }
  find('handoff').onclick = async () => {
    if (!isActive() || !imported || importing || previewing || readingImported) return;
    if (!imported.materials) {
      await readImportedMaterials(revision);
      return;
    }
    opportunityDiscoverySession.selected = new Map(imported.materials);
    opportunityDiscoverySession.result = null;
    opportunityDiscoverySession.materials = [];
    opportunityDiscoverySession.decisions = [];
    location.hash = 'opportunities';
  };
  updateControls();
}

function renderZhihuSearchPanel(panel) {
  let configured = false;
  let loadingStatus = false;
  let searching = false;
  let revision = 0;
  const active = () => panel.isConnected && getSelectedProfile() === 'product_feedback' && getRoute() === 'connectors';
  panel.innerHTML = `
    <h2 class="section-title">知乎官方搜索（检索线索）</h2>
    <p class="discovery-hint">官方接口返回 API 摘要与精选评论，不能直接作为原文依据送入机会分析。先打开来源取得原文，再补充导入；不在本页填写密钥。</p>
    <div data-zhihu="status" role="status"></div>
    <button class="btn btn-secondary btn-sm" type="button" data-zhihu="status-retry">重新读取配置状态</button>
    <div class="community-controls">
      <label class="form-label community-query">检索词（必填）<input class="form-input" data-zhihu="query" maxlength="200" placeholder="描述要研究的问题"></label>
      <label class="form-label">近几天（按源创建时间）<input class="form-input" data-zhihu="days" type="number" min="1" max="365" value="30"></label>
      <label class="form-label">最多线索<input class="form-input" data-zhihu="count" type="number" min="1" max="10" value="5"></label>
    </div>
    <div class="discovery-toolbar"><button class="btn btn-primary" type="button" data-zhihu="search" disabled>检索线索</button><span class="discovery-hint">单次至多 10 条、一个上游请求，不分页；检索不入库、不调用模型。</span></div>
    <div class="discovery-error" role="alert" data-zhihu="error"></div>
    <div data-zhihu="summary" class="discovery-hint" aria-live="polite"></div>
    <div data-zhihu="leads"></div>`;
  const find = name => panel.querySelector(`[data-zhihu="${name}"]`);
  const text = (parent, tag, value, className = 'discovery-hint') => {
    const element = document.createElement(tag);
    element.className = className;
    element.textContent = String(value ?? '');
    parent.appendChild(element);
    return element;
  };
  const update = () => {
    find('search').disabled = !configured || loadingStatus || searching;
    find('search').textContent = searching ? '正在检索线索…' : '检索线索';
    find('status-retry').disabled = loadingStatus || searching;
  };
  async function loadStatus() {
    if (!active() || loadingStatus || searching) return;
    const token = ++revision;
    loadingStatus = true;
    configured = false;
    find('status').textContent = '正在读取本机配置状态…';
    find('leads').textContent = '';
    find('summary').textContent = '';
    update();
    try {
      const status = await apiGet('/connectors/zhihu/status');
      if (!active() || token !== revision) return;
      configured = status.configured === true;
      find('status').textContent = '';
      text(find('status'), 'p', configured ? '已配置：可以检索线索，仍须另行补充原文。' : '未配置：当前尚不能检索，不会向知乎发送请求。');
      if (!configured) {
        const setup = discoverySourceUrl(status.setup_url) || 'https://developer.zhihu.com/';
        find('status').appendChild(createSourceLink(setup, '打开知乎开放平台申请入口'));
        const hint = typeof status.configuration_hint === 'string' && status.configuration_hint.trim()
          ? status.configuration_hint
          : '取得访问凭据后，在服务端环境设置 ZHIHU_ACCESS_SECRET 并重启服务，再重新读取配置状态。请勿把密钥填入网页或导入文件。';
        text(find('status'), 'p', `本机配置：${hint}`);
      }
      const showPublic = (label, value) => {
        const entries = (Array.isArray(value) ? value : [value]).filter(item => typeof item === 'string' && item.trim());
        if (!entries.length) return;
        text(find('status'), 'p', label);
        const list = document.createElement('ul');
        list.className = 'discovery-hint';
        entries.forEach(item => text(list, 'li', item));
        find('status').appendChild(list);
      };
      showPublic('检索能力', status.capabilities);
      showPublic('使用限制', status.limitations);
    } catch (error) {
      if (active() && token === revision) find('status').textContent = `配置状态读取失败：${error.message}。请重试；当前不会发起检索。`;
    } finally {
      if (active() && token === revision) {
        loadingStatus = false;
        update();
      }
    }
  }
  ['query', 'days', 'count'].forEach(name => {
    const invalidate = () => {
      if (!active() || loadingStatus) return;
      revision += 1;
      searching = false;
      find('leads').textContent = '';
      find('summary').textContent = '检索条件已改变，请重新检索；旧线索已清除。';
      find('error').textContent = '';
      update();
    };
    find(name).oninput = invalidate;
    find(name).onchange = invalidate;
  });
  find('status-retry').onclick = loadStatus;
  find('search').onclick = async () => {
    if (!active() || !configured || loadingStatus || searching) return;
    const request = { query: find('query').value.trim(), count: Number(find('count').value), days: Number(find('days').value) };
    if (!request.query || request.query.length > 200 || !Number.isInteger(request.count) || request.count < 1 || request.count > 10 || !Number.isInteger(request.days) || request.days < 1 || request.days > 365) {
      find('error').textContent = '请填写检索词（1–200 字）、1–10 条线索及 1–365 天。';
      return;
    }
    const token = ++revision;
    searching = true;
    find('error').textContent = '';
    find('leads').textContent = '';
    find('summary').textContent = '';
    update();
    try {
      const response = await apiPost('/connectors/zhihu/preview', request);
      if (!active() || token !== revision) return;
      if (!Array.isArray(response.leads) || response.leads.length > 10 || !response.summary || typeof response.summary !== 'object') throw new Error('线索返回格式异常');
      find('summary').textContent = response.leads.length ? `取得 ${response.leads.length} 条检索线索，尚未导入。${JSON.stringify(response.summary)}` : `未找到线索。${JSON.stringify(response.summary)}`;
      response.leads.forEach((lead, index) => {
        const row = document.createElement('article');
        row.className = 'community-material zhihu-lead';
        text(row, 'h3', lead.title || '未提供标题', '');
        text(row, 'p', 'API 摘要（检索线索，非原始正文）');
        text(row, 'p', lead.excerpt || '未提供摘要', 'community-original');
        const comments = Array.isArray(lead.curated_comments) ? lead.curated_comments : [];
        if (comments.length) text(row, 'p', '精选评论（检索线索，缺少独立评论定位；不能作为完整用户证据）');
        comments.forEach(comment => text(row, 'blockquote', comment, 'community-original'));
        text(row, 'p', `实体：${lead.entity_type || '未知'} · 平台 ID：${lead.external_id || '未知'} · 源创建时间：${lead.source_created_at || '未知'} · 源更新时间：${lead.source_updated_at || '未知'} · 采集时间：${lead.source_captured_at || '未知'}`);
        const source = discoverySourceUrl(lead.source_url);
        row.appendChild(source ? createSourceLink(source, '打开来源页面，取得原文') : createSourceUnavailable('来源页面不可打开'));
        const toolbar = document.createElement('div');
        toolbar.className = 'discovery-toolbar';
        const download = document.createElement('button');
        download.type = 'button';
        download.className = 'btn btn-secondary btn-sm';
        download.textContent = '下载线索来源 JSON';
        download.onclick = () => { if (active() && token === revision) downloadSourceJson({ lead, summary: response.summary }, `mining-zhihu-lead-${index + 1}.json`); };
        const manual = document.createElement('button');
        manual.type = 'button';
        manual.className = 'btn btn-primary btn-sm';
        manual.disabled = !source;
        manual.textContent = '去导入页补充原文';
        manual.onclick = () => {
          if (!active() || token !== revision || !source) return;
          pendingSourceLead = { ...lead, source_url: source };
          location.hash = 'import';
        };
        toolbar.append(download, manual);
        row.appendChild(toolbar);
        find('leads').appendChild(row);
      });
    } catch (error) {
      if (active() && token === revision) find('error').textContent = `知乎检索失败：${error.message}。本次没有导入材料；可重试。`;
    } finally {
      if (active() && token === revision) {
        searching = false;
        update();
      }
    }
  };
  update();
  return loadStatus();
}

// Client-side guard mirrors the collector's narrow target surface. The server
// remains authoritative and rechecks the selected tab before every read.
function existingChromePlatform(value) {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:') return null;
    const host = url.hostname.toLowerCase();
    if (host === 'xiaohongshu.com' || host === 'www.xiaohongshu.com') return 'xiaohongshu';
    if (host === 'bilibili.com' || host === 'www.bilibili.com' || host === 'search.bilibili.com') return 'bilibili';
    if (host === 'weibo.com' || host === 'www.weibo.com' || host === 's.weibo.com') return 'weibo';
    if (host === 'zhihu.com' || host === 'www.zhihu.com' || host === 'zhuanlan.zhihu.com') return 'zhihu';
    if (host === 'douyin.com' || host === 'www.douyin.com') return 'douyin';
    return null;
  } catch { return null; }
}

function existingChromeTargetUrl(value, noteOnly = false) {
  if (typeof value !== 'string' || /[\u0000-\u0020\u007f,#]/.test(value)) return null;
  if (!/^https:\/\/[^/:?#]+(?:\/|\?|$)/i.test(value)) return null;
  const platform = existingChromePlatform(value);
  if (!platform) return null;
  try {
    const url = new URL(value);
    if (url.username || url.password || url.port || url.hash) return null;
    if (platform === 'xiaohongshu') {
      const note = /^\/(?:explore|discovery\/item)\/[a-f0-9]{24}\/?$/i.test(url.pathname);
      const entry = /^\/(?:explore\/?|search_result(?:_ai)?\/?)?$/.test(url.pathname);
      return (note || (!noteOnly && entry)) ? url.href : null;
    }
    if (platform === 'bilibili') {
      const note = /^\/video\/(?:BV[A-Za-z0-9]+|av[0-9]+)\/?$/.test(url.pathname);
      const entry = /^\/(?:all\/?)?$/.test(url.pathname);
      return (note || (!noteOnly && entry)) ? url.href : null;
    }
    if (platform === 'weibo') {
      const note = /^\/(?:[0-9]+\/[A-Za-z0-9]+|detail\/[0-9]+)\/?$/.test(url.pathname);
      const entry = /^\/(?:weibo\/?|hot(?:\/.*)?|newlogin\/?|mygroups\/?|top\/summary\/?|realtime\/?|u\/[0-9]+\/?)?$/.test(url.pathname);
      return (note || (!noteOnly && entry)) ? url.href : null;
    }
    if (platform === 'zhihu') {
      const note = /^\/(?:question\/[0-9]+(?:\/answer\/[0-9]+)?|p\/[0-9]+)\/?$/.test(url.pathname);
      const entry = /^\/(?:search\/?|hot\/?|follow\/?|explore\/?|waiting\/?|knowledge-plan\/?|topic\/.*|column\/.*|people\/.*)?$/.test(url.pathname);
      return (note || (!noteOnly && entry)) ? url.href : null;
    }
    if (platform === 'douyin') {
      const note = /^\/(?:video|note)\/[0-9]{10,25}\/?$/.test(url.pathname);
      const entry = /^\/(?:discover\/?|jingxuan(?:\/.*)?|follow\/?|friend\/?|hot\/?|channel(?:\/.*)?|search\/.*|user\/.*)?$/.test(url.pathname);
      return (note || (!noteOnly && entry)) ? url.href : null;
    }
    return null;
  } catch { return null; }
}

function existingChromeSourceIdentity(value) {
  const safe = existingChromeTargetUrl(value, true);
  if (!safe) return null;
  const url = new URL(safe);
  // Access signatures may rotate between two captures of the same XHS note.
  for (const key of [...url.searchParams.keys()]) {
    if (['xsec_token', 'xsec_source'].includes(key.toLowerCase()) || key.toLowerCase().startsWith('utm_')) url.searchParams.delete(key);
  }
  return url.href;
}

function renderExistingChromePanel(panel) {
  let revision = 0, busy = false, connection = 'disconnected', task = null, batch = null;
  let tabs = [], items = [], selected = new Set(), imported = null, loadedTaskId = null, resultSummary = null;
  let checkedTabIds = new Set(), platformFilter = 'all';
  let pollTimer = null, pollsRemaining = 0, pollListening = false;
  const panelProfile = getSelectedProfile();
  const active = () => panel.isConnected && getSelectedProfile() === panelProfile && getRoute() === 'connectors';
  const running = () => task?.status === 'running' || batch?.status === 'running';
  const platformLabelMap = { xiaohongshu: '小红书', bilibili: 'B站', weibo: '微博', zhihu: '知乎', douyin: '抖音' };
  const labels = { disconnected: '未连接', connecting: '正在请求 Chrome 连接授权', connected: '已连接当前 Chrome 会话', authorization_required: '需要 Chrome 连接授权', unavailable: 'Chrome 连接暂不可用' };
  panel.innerHTML = `
    <h2 class="section-title">使用已登录 Chrome</h2>
    <p class="discovery-hint">读取你已经打开的普通 Chrome 会话。页面不会自动连接；点击「连接当前 Chrome」后，Chrome 会要求你允许本次连接。</p>
    <details class="source-import-fields"><summary>首次连接准备（Chrome 144 及以上）</summary><p class="discovery-hint">在已有 Chrome 打开 <code>chrome://inspect/#remote-debugging</code>，开启远程调试；返回这里点击连接，并在 Chrome 弹窗中允许本次连接。你已登录的平台会话可以继续使用，连接授权与平台登录是两件事。</p><p class="discovery-hint">支持国内小红书、B站、微博、知乎和抖音首页、搜索与详情标签。选中标签后，关键词搜索和指定链接会在该标签中导航；断开只取消本工具任务并断开连接，保留 Chrome 和页面。</p></details>
    <p class="discovery-hint" data-chrome="connection" aria-live="polite">正在读取本地连接状态…</p>
    <div class="discovery-toolbar"><button class="btn btn-primary" data-chrome="connect" type="button">连接当前 Chrome</button><button class="btn btn-secondary" data-chrome="disconnect" type="button">断开连接</button><button class="btn btn-secondary" data-chrome="refresh" type="button">刷新连接 / 任务</button></div>
    <div class="community-controls">
      <label class="form-label community-query">目标平台标签（单平台采集）<select class="form-select" data-chrome="tab"><option value="">请先连接，再选择标签</option></select></label>
      <label class="form-label">采集方式<select class="form-select" data-chrome="mode"><option value="current">当前笔记</option><option value="search">关键词搜索</option><option value="detail">指定笔记链接</option></select></label>
      <label class="form-label community-query" data-chrome="input-label">关键词或单个笔记链接<input class="form-input" data-chrome="input" maxlength="2000"></label>
      <label class="form-label" data-chrome="posts-label">采集篇数<input class="form-input" data-chrome="posts" type="number" min="1" max="20" value="5"></label>
      <label class="form-label">每篇评论数<input class="form-input" data-chrome="comments" type="number" min="0" max="50" value="10"></label>
    </div>
    <div class="multi-platform-box" data-chrome="multi-tabs-wrap" hidden>
      <div class="discovery-toolbar" style="margin:0 0 8px">
        <strong style="font-size:13px">🔀 多平台同时采集（勾选多个已打开标签，受控并发执行）</strong>
        <button class="btn btn-secondary btn-sm" data-chrome="select-all-platforms" type="button">全选各平台首个标签</button>
        <button class="btn btn-secondary btn-sm" data-chrome="clear-multi-tabs" type="button">清空多选</button>
      </div>
      <div class="multi-tab-grid" data-chrome="multi-tabs"></div>
    </div>
    <p class="discovery-hint" data-chrome="coverage"></p>
    <div class="discovery-toolbar">
      <button class="btn btn-primary" data-chrome="start" type="button">开始本次采集</button>
      <button class="btn btn-primary" data-chrome="batch-start" type="button" hidden>🚀 多平台同时采集</button>
      <button class="btn btn-secondary" data-chrome="stop" type="button">停止本任务</button>
    </div>
    <p class="discovery-hint" data-chrome="status" aria-live="polite">尚未启动采集。</p>
    <div data-chrome="progress-wrap" hidden>
      <div class="progress-bar-container"><div class="progress-bar-fill" data-chrome="progress-fill" style="width:0%"><span class="progress-text" data-chrome="progress-text">0%</span></div></div>
      <p class="discovery-hint" data-chrome="progress-label"></p>
    </div>
    <div class="batch-subtasks-grid" data-chrome="batch-subtasks" hidden></div>
    <p class="discovery-error" data-chrome="error" role="alert"></p>
    <p class="discovery-hint">关键词搜索每次最多 20 篇正文，每篇 0–50 条当前已加载评论，总时限 300 秒。只读取可见正文区域，不含图片文字或媒体（B站自动读取字幕）；完整性以每条采集范围为准。预览不入库、不调用模型。连接请求和任务开始后会自动刷新，也可手动刷新；离开页面停止自动刷新，后台任务须点击停止或断开取消。</p>
    <div class="platform-filter-bar" data-chrome="platform-filters" hidden></div>
    <details class="source-import-fields" data-chrome="items-details" hidden><summary data-chrome="items-summary">展开查看已采集材料</summary><div data-chrome="items"></div></details>
    <div class="discovery-toolbar">
      <span class="discovery-hint" data-chrome="count"></span>
      <label class="form-label" style="display:inline-flex;align-items:center;gap:6px;margin:0">
        <span>导入到版本</span>
        <select class="form-select" data-chrome="target-version" style="width:auto;min-width:160px;padding:6px 10px;font-size:13px"></select>
      </label>
      <button class="btn btn-secondary btn-sm" data-chrome="new-version" type="button">+ 新建版本</button>
      <button class="btn btn-secondary" data-chrome="all" type="button">全选</button>
      <button class="btn btn-secondary" data-chrome="none" type="button">取消全选</button>
      <button class="btn btn-primary" data-chrome="import" type="button">导入所选材料</button>
    </div>
    <p class="discovery-hint" data-chrome="receipt"></p><div data-chrome="snapshots"></div>
    <p class="discovery-hint" data-chrome="handoff-note" hidden>继续将替换机会页已有选择与结果；请先导出需要保留的清单。在机会页手动点击「发现机会」。来源快照核对不代表市场需求成立。</p>
    <button class="btn btn-primary" data-chrome="handoff" type="button" hidden>用本批材料发现机会</button>`;
  const find = name => panel.querySelector(`[data-chrome="${name}"]`);
  const text = (parent, tag, value, cls = '') => { const el = document.createElement(tag); el.textContent = String(value ?? ''); el.className = cls; parent.appendChild(el); return el; };
  const fields = ['tab', 'mode', 'input', 'posts', 'comments'];
  populateVersionSelect(find('target-version'), getEffectiveWriteVersion(), false);
  if (find('new-version')) {
    find('new-version').onclick = async () => {
      const name = typeof prompt === 'function' ? prompt('请输入新版本名称（如：v2-多平台调研）：') : '';
      if (!name || !name.trim()) return;
      try {
        const created = await apiPost('/versions', { name: name.trim(), description: '' });
        setSelectedVersion(created.id);
        await refreshVersionsCache();
        populateVersionSelect(find('target-version'), created.id, false);
        showToast(`已新建版本「${created.name}」并设为导入目标`, 'success');
      } catch (e) { showToast(`新建版本失败：${e.message}`, 'danger'); }
    };
  }
  function clearPolling() {
    if (pollTimer != null && typeof clearTimeout === 'function') clearTimeout(pollTimer);
    pollTimer = null;
    if (pollListening) { window.removeEventListener?.('hashchange', checkPollingPage); pollListening = false; }
  }
  function checkPollingPage() { if (!active()) clearPolling(); }
  function schedulePolling() {
    if (!active() || (connection !== 'connecting' && !running())) { clearPolling(); return; }
    if (busy || pollTimer != null || pollsRemaining <= 0 || typeof setTimeout !== 'function') return;
    if (!pollListening && typeof window.addEventListener === 'function') { window.addEventListener('hashchange', checkPollingPage); pollListening = true; }
    pollTimer = setTimeout(async () => {
      pollTimer = null;
      if (!active()) { clearPolling(); return; }
      if (busy) { schedulePolling(); return; }
      pollsRemaining -= 1;
      await refresh();
      if (active() && !pollsRemaining && (connection === 'connecting' || running())) {
        clearPolling(); text(find('status'), 'span', ' 自动刷新已达到本次上限；可手动刷新查看状态。');
      }
    }, 1500);
  }
  function update() {
    const connected = connection === 'connected';
    const chosen = tabs.find(tab => tab.id === find('tab').value);
    fields.forEach(name => { find(name).disabled = busy || running() || !connected; });
    const mode = find('mode').value;
    find('input-label').hidden = mode === 'current';
    find('input').placeholder = mode === 'search' ? '请填写搜索关键词，例如：记账软件 求推荐' : '请粘贴笔记链接：https://www.xiaohongshu.com/explore/...';
    find('posts-label').hidden = mode !== 'search';
    find('posts').disabled = busy || running() || !connected || mode !== 'search';
    find('coverage').textContent = mode === 'current' ? '仅读取当前这一篇已打开的笔记（1 篇）；如需批量采集多篇，请将「采集方式」切换为「关键词搜索」。' : mode === 'search' ? '在所选标签搜索一个关键词，打开实际结果，最多采集 1–20 篇笔记。' : '在所选标签打开一个国内小红书笔记链接，最多采集 1 篇。';
    find('connect').disabled = busy || connected || connection === 'connecting';
    find('disconnect').disabled = busy || connection === 'disconnected';
    find('refresh').disabled = busy;
    find('start').disabled = busy || !connected || running() || !chosen || (mode === 'current' && !existingChromeTargetUrl(chosen.url, true));
    const batchStartBtn = find('batch-start');
    if (batchStartBtn) {
      const canMulti = connected && tabs.length >= 2 && mode !== 'detail';
      batchStartBtn.hidden = !canMulti;
      batchStartBtn.disabled = busy || !canMulti || running() || checkedTabIds.size === 0;
      batchStartBtn.textContent = checkedTabIds.size ? `🚀 多平台同时采集 (${checkedTabIds.size} 个标签)` : '🚀 多平台同时采集';
    }
    const multiWrap = find('multi-tabs-wrap');
    if (multiWrap) multiWrap.hidden = !connected || tabs.length < 2 || mode === 'detail';
    find('stop').disabled = busy || !running();
    find('all').disabled = busy || !items.length || Boolean(imported);
    find('none').disabled = busy || !selected.size || Boolean(imported);
    find('import').disabled = busy || !selected.size || Boolean(imported);
    find('items').querySelectorAll('input[type="checkbox"]').forEach(el => { el.disabled = busy || Boolean(imported); });
    find('count').textContent = `本批 ${items.length} 条，已选 ${selected.size} 条`;
    find('handoff').hidden = !imported; find('handoff-note').hidden = !imported;
    find('handoff').disabled = busy;
    find('handoff').textContent = imported && !imported.materials ? '重试读取本批材料' : '用本批材料发现机会';
    schedulePolling();
  }
  function clearBatch() {
    items = []; selected = new Set(); imported = null; loadedTaskId = null; resultSummary = null; platformFilter = 'all';
    ['items', 'receipt', 'snapshots', 'error'].forEach(name => { find(name).textContent = ''; });
    find('items-details').hidden = true; find('items-details').open = false;
    if (find('platform-filters')) { find('platform-filters').textContent = ''; find('platform-filters').hidden = true; }
    if (!task && !batch) {
      find('progress-wrap').hidden = true;
      if (find('batch-subtasks')) { find('batch-subtasks').textContent = ''; find('batch-subtasks').hidden = true; }
    }
  }
  function setConnection(response) {
    if (!response || !Object.hasOwn(labels, response.status)) throw new Error('Chrome 连接状态格式异常');
    if (response.status === 'connecting' && connection !== 'connecting') pollsRemaining = 40;
    connection = response.status;
    const instruction = ['authorization_required', 'unavailable'].includes(connection) ? ' 请检查 Chrome 远程调试和本次连接授权；这不表示平台账号未登录。' : '';
    find('connection').textContent = `${labels[connection]}。${response.message || ''}${instruction}`;
    if (connection !== 'connected') { tabs = []; drawTabs(); }
  }
  function drawTabs() {
    const previous = find('tab').value;
    find('tab').textContent = '';
    const placeholder = text(find('tab'), 'option', tabs.length ? '请选择要读取的平台标签' : '没有可用的小红书/B站/微博/知乎/抖音标签；打开页面后刷新'); placeholder.value = '';
    tabs.forEach(tab => {
      const pLabel = platformLabelMap[tab.platform || existingChromePlatform(tab.url)] || '平台';
      const option = text(find('tab'), 'option', `[${pLabel}] ${tab.title || '页面'} · ${tab.url}`);
      option.value = tab.id;
    });
    const hasPrevious = tabs.some(tab => tab.id === previous);
    const preferred = find('mode').value === 'current'
      ? (tabs.find(tab => existingChromeTargetUrl(tab.url, true)) || tabs[0])
      : tabs[0];
    find('tab').value = hasPrevious ? previous : (preferred?.id || '');
    if (!hasPrevious && preferred && find('mode').value === 'current' && !existingChromeTargetUrl(preferred.url, true)) {
      find('mode').value = 'search';
    }
    const validIds = new Set(tabs.map(t => t.id));
    checkedTabIds = new Set([...checkedTabIds].filter(id => validIds.has(id)));
    drawMultiTabs();
  }
  function drawMultiTabs() {
    const box = find('multi-tabs');
    if (!box) return;
    box.textContent = '';
    tabs.forEach(tab => {
      const pKey = tab.platform || existingChromePlatform(tab.url) || 'xiaohongshu';
      const pLabel = platformLabelMap[pKey] || pKey;
      const chip = document.createElement('label');
      chip.className = 'multi-tab-chip' + (checkedTabIds.has(tab.id) ? ' checked' : '');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = checkedTabIds.has(tab.id);
      cb.disabled = busy || running();
      cb.onchange = () => {
        if (!active() || busy || running()) return;
        if (cb.checked) checkedTabIds.add(tab.id); else checkedTabIds.delete(tab.id);
        chip.classList.toggle('checked', cb.checked);
        update();
      };
      chip.appendChild(cb);
      text(chip, 'span', `[${pLabel}]`, 'badge badge-info');
      text(chip, 'span', (tab.title || tab.url).slice(0, 42), 'multi-tab-title');
      box.appendChild(chip);
    });
  }
  if (find('select-all-platforms')) {
    find('select-all-platforms').onclick = () => {
      if (!active() || busy || running()) return;
      const seenPlatform = new Set();
      checkedTabIds = new Set();
      tabs.forEach(t => {
        const p = t.platform || existingChromePlatform(t.url) || t.id;
        if (!seenPlatform.has(p)) { seenPlatform.add(p); checkedTabIds.add(t.id); }
      });
      drawMultiTabs(); update();
    };
  }
  if (find('clear-multi-tabs')) {
    find('clear-multi-tabs').onclick = () => {
      if (!active() || busy || running()) return;
      checkedTabIds = new Set(); drawMultiTabs(); update();
    };
  }
  function drawBatchSubtasks(currentBatch) {
    const grid = find('batch-subtasks');
    if (!grid) return;
    if (!currentBatch || !Array.isArray(currentBatch.subtasks) || !currentBatch.subtasks.length) {
      grid.textContent = ''; grid.hidden = true; return;
    }
    grid.hidden = false;
    grid.textContent = '';
    currentBatch.subtasks.forEach(st => {
      const card = document.createElement('div');
      card.className = `batch-subtask-card status-${st.status}`;
      const head = document.createElement('div');
      head.className = 'batch-subtask-head';
      const icon = st.status === 'completed' ? '✅' : st.status === 'failed' ? '❌' : st.status === 'running' ? '⏳' : st.status === 'cancelled' ? '⏹' : '○';
      text(head, 'strong', `${icon} ${st.platform_label || st.platform}`);
      text(head, 'span', `${st.progress?.percent ?? 0}%`, 'badge badge-default');
      card.appendChild(head);
      const bar = document.createElement('div');
      bar.className = 'batch-subtask-bar';
      const fill = document.createElement('div');
      fill.className = 'batch-subtask-fill' + (st.status === 'completed' ? ' done' : st.status === 'failed' ? ' fail' : '');
      fill.style.width = `${st.status === 'completed' ? 100 : (st.progress?.percent ?? 0)}%`;
      bar.appendChild(fill);
      card.appendChild(bar);
      text(card, 'p', st.message || st.progress?.label || '', 'discovery-hint');
      if (st.status === 'failed' && currentBatch.terminal) {
        const retryBtn = document.createElement('button');
        retryBtn.type = 'button';
        retryBtn.className = 'btn btn-secondary btn-sm';
        retryBtn.textContent = `🔄 重试 ${st.platform_label || st.platform}`;
        retryBtn.disabled = busy || running();
        retryBtn.onclick = async () => {
          if (!active() || busy || running()) return;
          const token = ++revision; busy = true; imported = null; loadedTaskId = null; find('error').textContent = ''; update();
          try {
            const resp = await apiPost(`/existing-chrome/batch-tasks/${encodeURIComponent(currentBatch.id)}/retry/${encodeURIComponent(st.tab_id)}`, {});
            if (!active() || token !== revision) return;
            setBatch(resp); await loadBatchResult(token);
          } catch (error) { if (active() && token === revision) find('error').textContent = `重试失败：${error.message}`; }
          finally { if (active() && token === revision) { busy = false; update(); } }
        };
        card.appendChild(retryBtn);
      }
      grid.appendChild(card);
    });
  }
  function setBatch(response) {
    if (!response || typeof response.id !== 'string' || !response.id) throw new Error('多平台批次状态格式异常');
    if (response.status === 'running' && batch?.id !== response.id) pollsRemaining = 120;
    task = null;
    batch = response;
    updateProgress(batch);
    drawBatchSubtasks(batch);
    const state = { running: '多平台采集中', completed: '多平台采集完成', failed: '多平台采集失败', cancelled: '已停止' }[batch.status] || batch.status;
    find('status').textContent = `${state}。${batch.message || ''}`;
    if (batch.status === 'failed') find('error').textContent = batch.message || '所选平台均未采集成功。';
    if (batch.status === 'completed' && loadedTaskId === batch.id) drawResultSummary();
  }
  async function loadTabs(token) {
    let response;
    try { response = await apiGet('/existing-chrome/tabs'); }
    catch (error) { if (active() && token === revision) { tabs = []; drawTabs(); } throw error; }
    if (!active() || token !== revision) return;
    if (!Array.isArray(response.tabs)) { tabs = []; drawTabs(); throw new Error('Chrome 标签列表格式异常'); }
    const ids = new Set();
    tabs = response.tabs.filter(tab => {
      if (!tab || typeof tab.id !== 'string' || !tab.id || ids.has(tab.id) || !existingChromeTargetUrl(tab.url)) return false;
      ids.add(tab.id); return true;
    });
    drawTabs();
  }
  function updateProgress(currentTask) {
    if (!currentTask) { find('progress-wrap').hidden = true; return; }
    const phasePct = { queued: 5, validate_source: 8, navigate_search: 15, read_search_results: 25, navigate_note: 55, read_note: 80, complete: 100 };
    const pct = currentTask.status === 'completed' ? 100 : (Number.isFinite(currentTask.progress?.percent) ? Math.max(0, Math.min(100, currentTask.progress.percent)) : (phasePct[currentTask.phase] ?? 10));
    find('progress-wrap').hidden = false;
    const fill = find('progress-fill');
    fill.style.width = `${pct}%`;
    fill.classList.toggle('done', currentTask.status === 'completed');
    fill.style.background = currentTask.status === 'failed' ? 'var(--danger)' : '';
    find('progress-text').textContent = `${pct}%`;
    find('progress-label').textContent = currentTask.progress?.label || (currentTask.status === 'completed' ? '采集完成' : currentTask.status === 'failed' ? '采集失败' : currentTask.status === 'cancelled' ? '采集已停止' : '正在采集中…');
  }
  function setTask(response) {
    if (!response || typeof response.id !== 'string' || !response.id || !['running', 'completed', 'failed', 'cancelled'].includes(response.status)) throw new Error('Chrome 任务状态格式异常');
    if (response.status === 'running' && task?.id !== response.id) pollsRemaining = 85;
    task = response;
    updateProgress(task);
    const state = { running: '采集中', completed: '采集完成', failed: '采集失败', cancelled: '已停止' }[task.status];
    find('status').textContent = `${state}。${task.message || ''}`;
    if (task.status === 'failed') find('error').textContent = task.error?.message || task.message || '任务失败，未提供原因。';
    if (task.status === 'completed' && loadedTaskId === task.id) drawResultSummary();
  }
  function drawPlatformFilters() {
    const bar = find('platform-filters');
    if (!bar) return;
    const counts = new Map();
    items.forEach(it => { const p = it.source_type || 'unknown'; counts.set(p, (counts.get(p) || 0) + 1); });
    if (counts.size < 2) { bar.textContent = ''; bar.hidden = true; return; }
    bar.hidden = false;
    bar.textContent = '';
    const makeChip = (key, label) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-sm ' + (platformFilter === key ? 'btn-primary' : 'btn-secondary');
      btn.textContent = label;
      btn.onclick = () => { platformFilter = key; drawItems(); };
      bar.appendChild(btn);
    };
    makeChip('all', `全部 (${items.length})`);
    for (const [p, cnt] of counts) makeChip(p, `${platformLabelMap[p] || p} (${cnt})`);
  }
  function drawItems() {
    find('items').textContent = '';
    drawPlatformFilters();
    const posts = items.filter(item => item.entity_type === 'post').length;
    find('items-details').hidden = !items.length;
    find('items-summary').textContent = items.length ? `展开查看已采集材料（共 ${items.length} 条：正文 ${posts} 篇、评论 ${items.length - posts} 条，点击折叠/展开）` : '展开查看已采集材料';
    items.forEach((item, index) => {
      if (platformFilter !== 'all' && item.source_type !== platformFilter) return;
      const row = document.createElement('article'); row.className = 'community-material';
      const label = document.createElement('label'); label.className = 'community-material-select';
      const check = document.createElement('input'); check.type = 'checkbox'; check.checked = selected.has(index);
      check.onchange = () => { if (!active() || busy || imported) return; if (check.checked) selected.add(index); else selected.delete(index); update(); };
      label.appendChild(check);
      const pTag = platformLabelMap[item.source_type];
      if (pTag) text(label, 'span', pTag, 'badge badge-info');
      text(label, 'strong', item.subject || (item.entity_type === 'comment' ? '评论原文' : '笔记正文')); row.appendChild(label);
      text(row, 'p', item.text, 'community-original');
      text(row, 'p', `实体：${item.entity_type || '未知'} · 平台 ID：${item.external_id || '未知'} · 发布时间：${item.source_created_at || '未知'} · 采集时间：${item.source_captured_at || '未知'}`, 'discovery-hint');
      text(row, 'p', `评论父级 ID：${item.parent_comment_id || '未知'} · ${item.locator_level === 'parent_page' ? '仅定位父页，不能直达评论' : item.locator_level === 'item' ? '条目页定位' : '定位范围未知'}`, 'discovery-hint');
      text(row, 'p', item.coverage_scope || '采集范围未提供', 'discovery-hint');
      text(row, 'p', `采集版本：${item.capture_version || '未知'} · 原文类型：${item.content_nature || '未知'}${item.raw_payload?.has_subtitles ? ` · ✅ 已含视频字幕（${item.raw_payload?.subtitle_language || 'CC/AI'}）` : ''}`, 'discovery-hint');
      row.appendChild(createSourceLink(item.external_url, sourceEvidenceLinkLabel(item)));
      const details = document.createElement('details'); text(details, 'summary', '查看采集记录'); text(details, 'pre', JSON.stringify(item.raw_payload || {}, null, 2), 'source-snapshot-json'); row.appendChild(details);
      find('items').appendChild(row);
    });
    update();
  }
  async function loadBatchResult(token) {
    if (batch?.status !== 'completed' || imported || loadedTaskId === batch.id) return;
    const batchId = batch.id;
    const result = await apiGet(`/existing-chrome/batch-tasks/${encodeURIComponent(batchId)}/results`);
    if (!active() || token !== revision || batch?.id !== batchId) return;
    const data = result.items;
    if (!Array.isArray(data) || data.length > 5000 || data.some(item => !item || typeof item.text !== 'string' || !item.text.trim() || !['post', 'comment'].includes(item.entity_type) || !['xiaohongshu', 'bilibili', 'weibo', 'zhihu', 'douyin'].includes(item.source_type) || item.capture_version !== 'mining-existing-chrome-dom/v1' || !existingChromeTargetUrl(item.external_url, true))) throw new Error('多平台采集结果格式或范围异常，未开放导入');
    items = data; selected = new Set(data.map((_, i) => i)); loadedTaskId = batchId; resultSummary = result.summary || {}; drawItems(); drawResultSummary();
  }
  async function loadResult(token) {
    if (task?.status !== 'completed' || imported || loadedTaskId === task.id) return;
    const taskId = task.id;
    const result = await apiGet(`/existing-chrome/tasks/${encodeURIComponent(taskId)}/results`);
    if (!active() || token !== revision || task?.id !== taskId) return;
    const data = result.items;
    if (!Array.isArray(data) || data.length > 1020 || data.some(item => !item || typeof item.text !== 'string' || !item.text.trim() || !['post', 'comment'].includes(item.entity_type) || !['xiaohongshu', 'bilibili', 'weibo', 'zhihu', 'douyin'].includes(item.source_type) || item.capture_version !== 'mining-existing-chrome-dom/v1' || !existingChromeTargetUrl(item.external_url, true)) || data.filter(item => item.entity_type === 'post').length > 20 || data.filter(item => item.entity_type === 'comment').length > 1000) throw new Error('Chrome 采集结果格式或范围异常，未开放导入');
    items = data; selected = new Set(); loadedTaskId = taskId; resultSummary = result.summary || {}; drawItems(); drawResultSummary();
  }
  function drawResultSummary() {
    const summary = resultSummary || {};
    const posts = items.filter(item => item.entity_type === 'post').length;
    find('status').textContent = `采集完成。正文 ${posts} 篇，评论 ${items.length - posts} 条，本批 ${items.length} 条。${typeof summary.coverage === 'string' ? summary.coverage : ''}`;
    if (Array.isArray(summary.incomplete_reasons) && summary.incomplete_reasons.length) text(find('status'), 'span', ` 不完整原因：${summary.incomplete_reasons.map(reason => typeof reason === 'string' ? reason : JSON.stringify(reason)).join('；')}`);
  }
  async function refresh() {
    if (!active() || busy) return;
    const token = revision; busy = true; find('error').textContent = ''; update();
    try {
      let response;
      try { response = await apiGet('/existing-chrome/status'); }
      catch (error) { if (active() && token === revision) { connection = 'unavailable'; tabs = []; drawTabs(); find('connection').textContent = '无法读取 Chrome 连接状态；请检查连接服务和授权设置。'; } throw error; }
      if (!active() || token !== revision) return;
      setConnection(response);
      if (connection === 'connected') await loadTabs(token);
      if (!active() || token !== revision) return;
      const batchId = batch?.id || response.active_batch;
      const id = task?.id || response.active_task;
      if (batchId) {
        const currentBatch = await apiGet(`/existing-chrome/batch-tasks/${encodeURIComponent(batchId)}`);
        if (!active() || token !== revision) return;
        setBatch(currentBatch); await loadBatchResult(token);
      } else if (id) {
        const current = await apiGet(`/existing-chrome/tasks/${encodeURIComponent(id)}`);
        if (!active() || token !== revision) return;
        setTask(current); await loadResult(token);
      }
    } catch (error) { if (active() && token === revision) find('error').textContent = error.message; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  }
  fields.forEach(name => { find(name).oninput = find(name).onchange = () => {
    if (!active() || busy || running()) return;
    revision += 1; task = null; batch = null; clearBatch(); find('status').textContent = '设置已更新，尚未启动本次采集。'; update();
  }; });
  find('connect').onclick = async () => {
    if (!active() || busy || ['connected', 'connecting'].includes(connection)) return;
    const token = ++revision; busy = true; find('error').textContent = ''; update();
    try {
      const response = await apiPost('/existing-chrome/connect', {});
      if (!active() || token !== revision) return;
      setConnection(response);
      if (connection === 'connected') await loadTabs(token);
    } catch (error) { if (active() && token === revision) find('error').textContent = `Chrome 连接请求失败：${error.message}。请检查本次连接授权。`; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  find('disconnect').onclick = async () => {
    if (!active() || busy || connection === 'disconnected') return;
    const token = ++revision; busy = true; find('error').textContent = ''; update();
    try {
      const response = await apiPost('/existing-chrome/disconnect', {});
      if (!active() || token !== revision) return;
      setConnection(response);
      if (running()) { task = { ...task, status: 'cancelled' }; find('status').textContent = '连接已断开，本工具任务已取消；Chrome 和页面保持打开。'; }
    } catch (error) { if (active() && token === revision) find('error').textContent = `断开未确认：${error.message}。请刷新连接状态。`; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  function validateStart(tab, mode, value, posts, comments) {
    if (!tab) return '请选择目标小红书标签。';
    if (!['current', 'search', 'detail'].includes(mode)) return '不支持的采集方式。';
    if (mode === 'current' && !existingChromeTargetUrl(tab.url, true)) return '当前选中标签不是笔记详情页（目前在首页或搜索页）；请切换为「关键词搜索」，或在 Chrome 中打开一篇笔记后刷新。';
    if (mode === 'search' && (!value || value.length > 100 || /[,，\r\n]/.test(value))) return '请在上方输入框填写要搜索的关键词（1–100 字，勿用逗号或换行）。';
    if (mode === 'detail' && !existingChromeTargetUrl(value, true)) return '请填写有效的小红书笔记链接、B站/抖音视频链接、微博详情页或知乎问答/专栏链接。';
    if (!Number.isInteger(posts) || posts < 1 || posts > 20) return '搜索采集篇数须为 1–20 的整数。';
    if (!Number.isInteger(comments) || comments < 0 || comments > 50) return '每篇评论数须为 0–50 条的整数。';
    return null;
  }
  find('start').onclick = async () => {
    if (!active() || busy || connection !== 'connected' || running()) return;
    const tab = tabs.find(item => item.id === find('tab').value), mode = find('mode').value;
    const value = find('input').value.trim(), posts = mode === 'search' ? Number(find('posts').value) : 1, comments = Number(find('comments').value);
    const validationError = validateStart(tab, mode, value, posts, comments);
    if (validationError) { find('error').textContent = validationError; return; }
    const detectedPlatform = (mode === 'detail' ? existingChromePlatform(value) : null) || tab.platform || existingChromePlatform(tab.url) || 'xiaohongshu';
    const request = { tab_id: tab.id, mode, query: mode === 'search' ? value : '', url: mode === 'detail' ? value : '', max_posts: posts, max_comments: comments };
    if (detectedPlatform !== 'xiaohongshu') request.platform = detectedPlatform;
    if (panelProfile !== 'product_feedback') request.pipeline_profile = panelProfile;
    const token = ++revision; task = null; batch = null; clearBatch(); busy = true; update();
    try {
      const response = await apiPost('/existing-chrome/tasks', request);
      if (!active() || token !== revision) return;
      setTask(response); await loadResult(token);
    } catch (error) { if (active() && token === revision) find('error').textContent = `采集请求失败：${error.message}`; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  if (find('batch-start')) {
    find('batch-start').onclick = async () => {
      if (!active() || busy || connection !== 'connected' || running()) return;
      const mode = find('mode').value;
      const value = find('input').value.trim();
      const posts = mode === 'search' ? Number(find('posts').value) : 1;
      const comments = Number(find('comments').value);
      const tabIds = [...checkedTabIds];
      if (!tabIds.length) { find('error').textContent = '请至少勾选 1 个目标平台标签。'; return; }
      if (mode === 'detail') { find('error').textContent = '多平台同时采集仅支持「关键词搜索」或「当前页面」模式。'; return; }
      if (mode === 'search' && (!value || value.length > 100 || /[,，\r\n]/.test(value))) { find('error').textContent = '请填写要搜索的关键词（1–100 字，勿用逗号或换行）。'; return; }
      if (!Number.isInteger(posts) || posts < 1 || posts > 20) { find('error').textContent = '每平台采集篇数须为 1–20 的整数。'; return; }
      if (!Number.isInteger(comments) || comments < 0 || comments > 50) { find('error').textContent = '每篇评论数须为 0–50 条的整数。'; return; }
      const request = { tab_ids: tabIds, mode, query: mode === 'search' ? value : '', max_posts: posts, max_comments: comments, concurrency: 3 };
      if (panelProfile !== 'product_feedback') request.pipeline_profile = panelProfile;
      const token = ++revision; task = null; batch = null; clearBatch(); busy = true; update();
      try {
        const response = await apiPost('/existing-chrome/batch-tasks', request);
        if (!active() || token !== revision) return;
        setBatch(response); await loadBatchResult(token);
      } catch (error) { if (active() && token === revision) find('error').textContent = `多平台采集请求失败：${error.message}`; }
      finally { if (active() && token === revision) { busy = false; update(); } }
    };
  }
  find('refresh').onclick = refresh;
  find('stop').onclick = async () => {
    if (!active() || busy || !running()) return;
    const token = revision; busy = true; find('error').textContent = ''; update();
    try {
      if (batch?.status === 'running') {
        const response = await apiPost(`/existing-chrome/batch-tasks/${encodeURIComponent(batch.id)}/stop`, {});
        if (active() && token === revision) { setBatch(response); await loadBatchResult(token); }
      } else {
        const response = await apiPost(`/existing-chrome/tasks/${encodeURIComponent(task.id)}/stop`, {});
        if (active() && token === revision) { setTask(response); await loadResult(token); }
      }
    } catch (error) { if (active() && token === revision) find('error').textContent = `停止未确认：${error.message}。请刷新任务状态。`; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  find('all').onclick = () => { if (!active() || busy || imported) return; selected = new Set(items.map((_, i) => i)); drawItems(); };
  find('none').onclick = () => { if (!active() || busy || imported) return; selected = new Set(); drawItems(); };
  async function readStored(token) {
    const actual = new Map();
    for (const id of imported.ids) {
      const detail = await apiGet(`/feedback/${encodeURIComponent(id)}`);
      if (!active() || token !== revision) return;
      if (detail.id !== id || detail.pipeline_profile !== panelProfile || typeof detail.content?.text !== 'string') throw new Error('实际已存材料与本批 ID、模式或正文不匹配');
      const expected = imported.expected.get(id) || [];
      const actualUrl = existingChromeSourceIdentity(detail.external_url);
      if (!expected.length || !actualUrl || expected.some(item => item.text !== detail.content.text || existingChromeSourceIdentity(item.external_url) !== actualUrl || item.source_type !== detail.source_type)) throw new Error('已存原文或来源与所选材料不一致，未交接到机会页');
      actual.set(id, { ...detail, subject: detail.content.subject, text_preview: detail.content.text, source_url: discoverySourceUrl(detail.external_url) });
    }
    imported.materials = actual;
    const counts = Number.isInteger(imported.ingested) && Number.isInteger(imported.duplicates) && imported.ingested >= 0 && imported.duplicates >= 0 && imported.ingested + imported.duplicates === imported.processed ? `新增 ${imported.ingested} 条、重复 ${imported.duplicates} 条；` : '新增和重复数量未确认；';
    find('receipt').textContent = `已处理 ${imported.processed} 条所选材料，${counts}本批可用 ${actual.size} 个实际唯一 ID。以回读原文和来源为准，尚未调用模型。`;
    find('snapshots').textContent = '';
    for (const [id, detail] of actual) appendSourceSnapshot(find('snapshots'), id, detail);
  }
  find('import').onclick = async () => {
    if (!active() || busy || imported || !selected.size) return;
    const token = revision, chosen = items.filter((_, index) => selected.has(index)); busy = true; find('error').textContent = ''; update();
    const targetVersion = (find('target-version')?.value || getEffectiveWriteVersion() || 'default').trim();
    const batchPath = targetVersion && targetVersion !== 'default' ? `/feedback/batch?version_id=${encodeURIComponent(targetVersion)}` : '/feedback/batch';
    try {
      const response = await apiPost(batchPath, chosen);
      if (!active() || token !== revision) return;
      if (!Array.isArray(response.feedback_ids) || response.feedback_ids.length !== chosen.length || response.feedback_ids.some(id => typeof id !== 'string' || !id.trim())) throw new Error('导入回执与所选材料不对应');
      const expected = new Map();
      response.feedback_ids.forEach((id, index) => { if (!expected.has(id)) expected.set(id, []); expected.get(id).push(chosen[index]); });
      imported = { ids: [...new Set(response.feedback_ids)], expected, processed: response.feedback_ids.length, ingested: response.ingested, duplicates: response.duplicates, materials: null };
      await readStored(token);
      refreshVersionsCache();
    } catch (error) { if (active() && token === revision) find('error').textContent = imported ? `导入已完成，回读失败：${error.message}。可重试读取，不会再次导入。` : `导入未确认：${error.message}。部分材料可能已处理，重复导入可能复用旧 ID。`; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  find('handoff').onclick = async () => {
    if (!active() || busy || !imported) return;
    if (!imported.materials) {
      const token = revision; busy = true; find('error').textContent = ''; update();
      try { await readStored(token); }
      catch (error) { if (active() && token === revision) find('error').textContent = `回读失败：${error.message}`; }
      finally { if (active() && token === revision) { busy = false; update(); } }
      return;
    }
    opportunityDiscoverySession.selected = new Map(imported.materials); opportunityDiscoverySession.result = null; opportunityDiscoverySession.materials = []; opportunityDiscoverySession.decisions = []; location.hash = 'opportunities';
  };
  update();
  return refresh();
}

function renderLocalCollectionPanel(panel) {
  let revision = 0, busy = false, ready = false, task = null, items = [], imported = null;
  let selected = new Set();
  const active = () => panel.isConnected && getSelectedProfile() === 'product_feedback' && getRoute() === 'connectors';
  panel.innerHTML = `
    <h2 class="section-title">MediaCrawler 独立浏览器采集</h2>
    <p class="discovery-hint">这是独立模式；如需读取普通 Chrome 的已登录会话，请使用上方「使用已登录 Chrome」。两种模式的连接和任务状态分别显示。</p>
    <p class="discovery-hint">仅供非商业学习研究。点击开始才打开专用浏览器，请手动登录或完成验证。普通 Chrome / App 登录不会自动共享，登录态只留本机。</p>
    <div class="community-controls">
      <label class="form-label">来源<select class="form-select" data-local="platform"><option value="xhs">小红书</option><option value="bili">B站</option><option value="wb">微博</option></select></label>
      <label class="form-label">方式<select class="form-select" data-local="mode"><option value="search">关键词</option><option value="detail">指定链接</option></select></label>
      <label class="form-label community-query">关键词或单个正文链接<input class="form-input" data-local="input" maxlength="2000"></label>
      <label class="form-label">最多篇数<input class="form-input" data-local="posts" type="number" min="1" max="3" value="3"></label>
      <label class="form-label">每篇一级评论<input class="form-input" data-local="comments" type="number" min="0" max="8" value="8"></label>
    </div>
    <p class="discovery-hint" data-local="coverage"></p><p class="discovery-hint" data-local="environment">正在检查本机环境…</p>
    <div class="discovery-toolbar"><button class="btn btn-primary" data-local="start" type="button">开始本次采集</button><button class="btn btn-secondary" data-local="refresh" type="button">刷新环境 / 任务</button><button class="btn btn-secondary" data-local="stop" type="button">停止本任务</button></div>
    <p class="discovery-hint" data-local="status" aria-live="polite"></p><p class="discovery-error" data-local="error" role="alert"></p>
    <p class="discovery-hint">最多3篇、每篇8条一级评论，总时限10分钟；不下载媒体、不采楼中楼。预览不入库、不调用模型。请手动刷新查看进度；离开页面不会自动停止任务。</p>
    <div data-local="items"></div><div class="discovery-toolbar"><span class="discovery-hint" data-local="count"></span><button class="btn btn-secondary" data-local="all" type="button">全选</button><button class="btn btn-primary" data-local="import" type="button">导入所选材料</button></div>
    <p class="discovery-hint" data-local="receipt"></p><div data-local="snapshots"></div>
    <p class="discovery-hint" data-local="handoff-note" hidden>继续将替换机会页已有选择与结果；请先导出需要保留的清单。在机会页手动点击「发现机会」。</p>
    <button class="btn btn-primary" data-local="handoff" type="button" hidden>用本批材料发现机会</button>`;
  const find = name => panel.querySelector(`[data-local="${name}"]`);
  const fields = ['platform', 'mode', 'input', 'posts', 'comments'];
  const text = (parent, tag, value, cls = '') => { const el = document.createElement(tag); el.textContent = String(value ?? ''); el.className = cls; parent.appendChild(el); return el; };
  function update() {
    const running = Boolean(task && !task.terminal);
    fields.forEach(name => { find(name).disabled = busy || running; });
    find('posts').disabled = busy || running || find('mode').value === 'detail';
    find('coverage').textContent = find('platform').value === 'bili' ? 'B站正文是上游最多500字符的视频简介片段，不是口播。作者昵称已遮蔽。' : find('platform').value === 'wb' ? '微博尝试展开长文但不保证完整，不覆盖全部评论。作者昵称已遮蔽。' : '小红书只读取笔记描述和有界一级评论，不含图片文字或媒体。作者昵称已遮蔽。';
    find('start').disabled = busy || !ready || running; find('refresh').disabled = busy; find('stop').disabled = busy || !running;
    find('all').disabled = busy || !items.length || Boolean(imported); find('import').disabled = busy || !selected.size || Boolean(imported);
    find('count').textContent = `本批 ${items.length} 条，已选 ${selected.size} 条`;
    find('items').querySelectorAll('input[type="checkbox"]').forEach(el => { el.disabled = busy || Boolean(imported); });
    find('handoff').hidden = !imported; find('handoff-note').hidden = !imported; find('handoff').disabled = busy;
    find('handoff').textContent = imported && !imported.materials ? '重试读取本批材料' : '用本批材料发现机会';
  }
  function clear() { items = []; selected = new Set(); imported = null; ['items', 'receipt', 'snapshots', 'error'].forEach(name => { find(name).textContent = ''; }); }
  function draw() {
    find('items').textContent = '';
    items.forEach((item, index) => {
      const row = document.createElement('article'); row.className = 'community-material';
      const label = document.createElement('label'); label.className = 'community-material-select';
      const check = document.createElement('input'); check.type = 'checkbox'; check.checked = selected.has(index);
      check.onchange = () => { if (!active() || busy || imported) return; if (check.checked) selected.add(index); else selected.delete(index); update(); };
      label.appendChild(check); text(label, 'strong', item.subject || (item.entity_type === 'comment' ? '一级评论' : '正文材料')); row.appendChild(label);
      text(row, 'p', item.text, 'community-original'); text(row, 'p', `发布时间：${item.source_created_at || '未知'} · 原作者未知（上游匿名化） · ${item.locator_level === 'parent_page' ? '仅定位父页' : '条目页定位'}`, 'discovery-hint'); text(row, 'p', item.coverage_scope, 'discovery-hint');
      const url = discoverySourceUrl(item.external_url); row.appendChild(url ? createSourceLink(url, sourceEvidenceLinkLabel(item)) : createSourceUnavailable('来源链接无效')); find('items').appendChild(row);
    }); update();
  }
  async function loadResult(token) {
    if (!task || !['completed', 'empty'].includes(task.status) || imported) return;
    const result = await apiGet(`/mediacrawler/tasks/${encodeURIComponent(task.id)}/results`);
    if (!active() || token !== revision) return;
    if (!Array.isArray(result.items) || result.items.length > 30) throw new Error('任务材料格式异常');
    items = result.items; selected = new Set(); draw(); const summary = result.summary || {};
    find('status').textContent = `${task.message} 正文 ${summary.posts ?? 0} 篇，评论 ${summary.comments ?? 0} 条。${summary.coverage_note || ''}`;
    if (summary.search_page_objects != null) text(find('status'), 'span', ` 搜索页返回 ${summary.search_page_objects} 个对象，其中最多 ${summary.selected_objects ?? 0} 个进入后续处理。`);
    const reasons = Object.entries(summary.skip_reasons || {}).map(([key, count]) => `${key}: ${count}`); if (reasons.length) text(find('status'), 'span', ` 排除记录：${reasons.join('；')}`);
  }
  async function refresh() {
    if (!active() || busy) return;
    const token = revision; busy = true; update();
    try {
      const env = await apiGet('/mediacrawler/status'); if (!active() || token !== revision) return;
      ready = env.ready === true; find('environment').textContent = env.message;
      const response = task ? await apiGet(`/mediacrawler/tasks/${encodeURIComponent(task.id)}`) : env.active_task;
      if (!active() || token !== revision) return; task = response;
      find('status').textContent = task?.message || '尚未启动采集；平台账号实采待验证。'; await loadResult(token);
    } catch (error) { if (active() && token === revision) find('error').textContent = error.message; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  }
  fields.forEach(name => { find(name).oninput = find(name).onchange = () => { if (!active() || busy || (task && !task.terminal)) return; revision += 1; task = null; clear(); update(); }; });
  find('start').onclick = async () => {
    if (!active() || busy || !ready || (task && !task.terminal)) return;
    const mode = find('mode').value, value = find('input').value.trim();
    const request = { platform: find('platform').value, mode, query: mode === 'search' ? value : '', url: mode === 'detail' ? value : '', max_posts: mode === 'detail' ? 1 : Number(find('posts').value), max_comments: Number(find('comments').value) };
    if (!value || (mode === 'search' && (value.length > 100 || /[,，\n\r]/.test(value))) || !Number.isInteger(request.max_posts) || request.max_posts < 1 || request.max_posts > 3 || !Number.isInteger(request.max_comments) || request.max_comments < 0 || request.max_comments > 8) { find('error').textContent = '请填写一个关键词或正文链接；最多3篇、每篇0–8条一级评论。'; return; }
    const token = ++revision; clear(); busy = true; update();
    try { const response = await apiPost('/mediacrawler/tasks', request); if (active() && token === revision) { task = response; find('status').textContent = response.message; } }
    catch (error) { if (active() && token === revision) find('error').textContent = `启动失败：${error.message}`; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  find('refresh').onclick = refresh;
  find('stop').onclick = async () => {
    if (!active() || busy || !task || task.terminal) return;
    const token = revision; busy = true; update();
    try { const response = await apiPost(`/mediacrawler/tasks/${encodeURIComponent(task.id)}/stop`, {}); if (active() && token === revision) { task = response; find('status').textContent = response.message; } }
    catch (error) { if (active() && token === revision) find('error').textContent = error.message; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  find('all').onclick = () => { if (!active() || busy || imported) return; selected = new Set(items.map((_, i) => i)); draw(); };
  async function readStored(token) {
    const actual = new Map();
    for (const id of imported.ids) {
      const detail = await apiGet(`/feedback/${encodeURIComponent(id)}`); if (!active() || token !== revision) return;
      if (detail.id !== id || detail.pipeline_profile !== 'product_feedback' || typeof detail.content?.text !== 'string') throw new Error('实际已存材料与本批ID不匹配');
      actual.set(id, { ...detail, subject: detail.content.subject, text_preview: detail.content.text, source_url: discoverySourceUrl(detail.external_url) });
    }
    imported.materials = actual; find('receipt').textContent = `已处理 ${imported.processed} 条所选材料，本批可用 ${actual.size} 个实际唯一ID；可能复用旧材料，以回读原文和来源为准，尚未调用模型。`;
    find('snapshots').textContent = ''; for (const [id, detail] of actual) appendSourceSnapshot(find('snapshots'), id, detail);
  }
  find('import').onclick = async () => {
    if (!active() || busy || imported || !selected.size) return;
    const token = revision, chosen = items.filter((_, i) => selected.has(i)); busy = true; update();
    try {
      const response = await apiPost('/feedback/batch', chosen); if (!active() || token !== revision) return;
      if (!Array.isArray(response.feedback_ids) || response.feedback_ids.length !== chosen.length || response.feedback_ids.some(id => typeof id !== 'string' || !id.trim())) throw new Error('导入回执异常');
      imported = { ids: [...new Set(response.feedback_ids)], processed: response.feedback_ids.length, materials: null }; await readStored(token);
    } catch (error) { if (active() && token === revision) find('error').textContent = imported ? `导入已完成，回读失败：${error.message}。可重试读取，不会再次导入。` : `导入未确认：${error.message}。部分材料可能已处理，重复导入可能复用旧ID。`; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  find('handoff').onclick = async () => {
    if (!active() || busy || !imported) return;
    if (!imported.materials) { const token = revision; busy = true; update(); try { await readStored(token); } catch (error) { if (active() && token === revision) find('error').textContent = `回读失败：${error.message}`; } finally { if (active() && token === revision) { busy = false; update(); } } return; }
    opportunityDiscoverySession.selected = new Map(imported.materials); opportunityDiscoverySession.result = null; opportunityDiscoverySession.materials = []; opportunityDiscoverySession.decisions = []; location.hash = 'opportunities';
  };
  update(); refresh();
}

async function renderConnectorsPage(container) {
  const profile = getSelectedProfile();
  container.innerHTML = `
    <section class="card community-panel" id="existing-chrome"></section>

    <details class="card collapsible-drawer" id="drawer-manual-import">
      <summary class="drawer-summary">✍️ 手动补录单条反馈 / 📦 批量导入 JSON（备用）</summary>
      <div class="drawer-body" id="embedded-import-slot"></div>
    </details>

    ${profile === 'product_feedback' ? `
    <details class="card collapsible-drawer" id="drawer-community-preview">
      <summary class="drawer-summary">🌐 公开社区预览（Hacker News / V2EX，免登录）</summary>
      <div class="drawer-body"><section class="community-panel" id="community-preview"></section></div>
    </details>` : ''}

    <details class="card collapsible-drawer" id="drawer-github-webhook">
      <summary class="drawer-summary">🐙 GitHub Issues 拉取 & 🔗 Webhook</summary>
      <div class="drawer-body">
        <div class="section-title" style="margin-top:4px">🐙 GitHub Issues 拉取</div>
        <div class="form-group"><label class="form-label">仓库 (owner/repo)</label><input class="form-input" id="gh-repo" placeholder="如: facebook/react"></div>
        <div class="form-row">
          <div class="form-group"><label class="form-label">标签 (逗号分隔)</label><input class="form-input" id="gh-labels" placeholder="bug,feature"></div>
          <div class="form-group"><label class="form-label">状态</label><select class="form-select" id="gh-state"><option value="all">全部</option><option value="open">Open</option><option value="closed">Closed</option></select></div>
        </div>
        <button class="btn btn-primary" id="btn-gh-fetch">🐙 拉取 Issues</button>
        <div id="gh-result" style="margin-top:12px"></div>
        <div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--border-subtle)">
          <div class="section-title">🔗 Webhook</div>
          <p style="font-size:14px;color:var(--text-muted)">Webhook 端点: <code>POST /api/v1/connectors/webhook/ingest</code></p>
        </div>
      </div>
    </details>

    <details class="card collapsible-drawer" id="drawer-legacy-tools">
      <summary class="drawer-summary">🧰 备用采集工具（知乎官方 API / MediaCrawler 专用浏览器 / 已注册连接器）</summary>
      <div class="drawer-body">
        ${profile === 'product_feedback' ? '<section class="community-panel" id="zhihu-search"></section>' : ''}
        ${profile === 'product_feedback' ? '<section class="community-panel" id="local-collection" style="margin-top:16px;padding-top:16px;border-top:1px solid var(--border-subtle)"></section>' : ''}
        <div id="connector-list" style="margin-top:16px"></div>
      </div>
    </details>
  `;
  renderExistingChromePanel(container.querySelector('#existing-chrome'));
  const manualDrawer = container.querySelector('#drawer-manual-import');
  const manualSlot = container.querySelector('#embedded-import-slot');
  let manualMounted = false;
  if (manualDrawer && manualSlot && typeof manualDrawer.addEventListener === 'function') {
    manualDrawer.addEventListener('toggle', () => {
      if (manualDrawer.open && !manualMounted) {
        manualMounted = true;
        renderImportPage(manualSlot);
      }
    });
  }
  if (profile === 'product_feedback') renderCommunitySamplesPanel(container.querySelector('#community-preview'));
  if (profile === 'product_feedback') renderZhihuSearchPanel(container.querySelector('#zhihu-search'));
  if (profile === 'product_feedback') renderLocalCollectionPanel(container.querySelector('#local-collection'));
  const listEl = container.querySelector('#connector-list');

  // List connectors
  try {
    const { connectors } = await apiGet('/connectors');
    if (!container.isConnected || getSelectedProfile() !== profile) return;
    listEl.innerHTML = `<div class="card"><div class="section-title">📋 已注册连接器 (${connectors.length})</div><div style="display:flex;gap:8px;flex-wrap:wrap">${connectors.map(c => `<span class="badge badge-info">${escapeHtml(c)}</span>`).join('')}</div></div>`;
  } catch (e) {
    if (!container.isConnected || getSelectedProfile() !== profile) return;
    showToast(`连接器列表加载失败: ${e.message}`, 'danger');
  }

  document.getElementById('btn-gh-fetch').onclick = async () => {
    const repo = document.getElementById('gh-repo').value.trim();
    if (!repo) { showToast('请输入仓库名称', 'warning'); return; }

    const btn = document.getElementById('btn-gh-fetch');
    btn.disabled = true;
    btn.textContent = '⏳ 拉取中...';

    const labelsVal = document.getElementById('gh-labels').value.trim();
    const state = document.getElementById('gh-state').value;

    try {
      const body = { repo, state };
      if (labelsVal) body.labels = labelsVal.split(',').map(s => s.trim()).filter(Boolean);
      const writeVersion = getEffectiveWriteVersion();
      if (writeVersion !== 'default') body.version_id = writeVersion;
      const result = await apiPost('/connectors/github/fetch', body);
      if (!container.isConnected || getSelectedProfile() !== profile) return;
      document.getElementById('gh-result').innerHTML = `<div style="padding:12px;background:rgba(16,185,129,0.1);border-radius:8px;color:var(--success)">✅ 拉取完成：${result.ingested_count} 条反馈已入库</div>`;
      showToast(`成功导入 ${result.ingested_count} 条 GitHub Issues`, 'success');
    } catch (e) {
      if (container.isConnected && getSelectedProfile() === profile) document.getElementById('gh-result').textContent = `❌ ${e.message}`;
    } finally {
      btn.disabled = false;
      btn.textContent = '🐙 拉取 Issues';
    }
  };
}

/* ==================================================== Page: Model Settings == */

async function renderModelSettingsPage(container) {
  container.innerHTML = '<div class="card"><p class="discovery-hint">正在读取当前模型配置…</p></div>';
  let data;
  try {
    data = await apiGet('/llm/settings');
  } catch (e) {
    if (container.isConnected) container.innerHTML = `<div class="card"><p class="discovery-error">读取模型设置失败：${escapeHtml(e.message)}</p></div>`;
    return;
  }
  if (!container.isConnected) return;

  const primaryPresets = data.presets?.primary || {};
  const embPresets = data.presets?.embedding || {};
  const primary = data.primary || {};
  const providers = primary.providers || {};
  const multimodal = data.multimodal || {};
  const embedding = data.embedding || {};

  container.innerHTML = `
    <div class="card">
      <div class="section-title">🤖 1. 主模型配置（信号提取 / 机会分析 / 需求生成）</div>
      <p class="discovery-hint" style="margin-bottom:12px">切换厂商时会自动带出默认模型名；API Key 留空表示保留当前已保存密钥，保存后即时生效并写入本地 <code>.env</code>。</p>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label" for="ms-primary-provider">主模型厂商</label>
          <select class="form-select" id="ms-primary-provider">
            ${Object.entries(primaryPresets).map(([k, v]) => `<option value="${k}" ${k === primary.provider ? 'selected' : ''}>${escapeHtml(v.label)}</option>`).join('')}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label" for="ms-primary-model">模型名称</label>
          <input class="form-input" id="ms-primary-model" maxlength="120" value="${escapeHtml(primary.model || '')}">
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label" for="ms-primary-key">API Key（<span id="ms-primary-key-status"></span>）</label>
          <input class="form-input" id="ms-primary-key" type="password" autocomplete="off" placeholder="留空保留已有密钥；填写新 Key 将覆盖保存">
        </div>
        <div class="form-group" id="ms-openai-url-group" style="display:none">
          <label class="form-label" for="ms-openai-url">OpenAI 兼容 Base URL（可选）</label>
          <input class="form-input" id="ms-openai-url" placeholder="https://api.openai.com/v1" value="${escapeHtml(primary.openai_base_url || '')}">
        </div>
        <div class="form-group" id="ms-minimax-gid-group" style="display:none">
          <label class="form-label" for="ms-minimax-gid">MiniMax Group ID</label>
          <input class="form-input" id="ms-minimax-gid" value="${escapeHtml(primary.minimax_group_id || '')}">
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="section-title">🖼️ 2. 多模态模型配置（图片 / 截图理解）</div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label" for="ms-mm-provider">多模态策略</label>
          <select class="form-select" id="ms-mm-provider">
            <option value="" ${multimodal.provider === '' ? 'selected' : ''}>自动跟随主模型（DeepSeek-Flash 推荐）</option>
            <option value="deepseek" ${multimodal.provider === 'deepseek' ? 'selected' : ''}>独立使用 DeepSeek-Flash</option>
            <option value="openai" ${multimodal.provider === 'openai' ? 'selected' : ''}>独立使用 OpenAI Vision</option>
            <option value="google" ${multimodal.provider === 'google' ? 'selected' : ''}>独立使用 Google Gemini</option>
            <option value="disabled" ${multimodal.provider === 'disabled' ? 'selected' : ''}>禁用多模态</option>
          </select>
        </div>
        <div class="form-group" id="ms-mm-model-group" style="display:none">
          <label class="form-label" for="ms-mm-model">多模态模型名称</label>
          <input class="form-input" id="ms-mm-model" maxlength="120" value="${escapeHtml(multimodal.model || '')}">
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="section-title">🧬 3. Embedding 向量模型（运行管线语义去重与主题聚类）</div>
      <p class="discovery-hint" style="margin-bottom:12px">与主模型解耦：可选本机免费开源中文模型（<code>BAAI/bge-small-zh-v1.5</code>，离线零费用），或硅基流动 / 阿里云百炼 / 智谱等国内云端向量 API。</p>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label" for="ms-emb-provider">Embedding 方案</label>
          <select class="form-select" id="ms-emb-provider">
            <option value="auto" ${embedding.provider === 'auto' ? 'selected' : ''}>自动（优先复用或本机免费中文向量）</option>
            <option value="local" ${embedding.provider === 'local' ? 'selected' : ''}>${escapeHtml(embPresets.local?.label || '本机免费中文向量')}</option>
            <option value="siliconflow" ${embedding.provider === 'siliconflow' ? 'selected' : ''}>${escapeHtml(embPresets.siliconflow?.label || '硅基流动')}</option>
            <option value="dashscope" ${embedding.provider === 'dashscope' ? 'selected' : ''}>${escapeHtml(embPresets.dashscope?.label || '阿里云百炼')}</option>
            <option value="zhipu" ${embedding.provider === 'zhipu' ? 'selected' : ''}>${escapeHtml(embPresets.zhipu?.label || '智谱 AI')}</option>
            <option value="openai" ${embedding.provider === 'openai' ? 'selected' : ''}>${escapeHtml(embPresets.openai?.label || 'OpenAI')}</option>
            <option value="custom" ${embedding.provider === 'custom' ? 'selected' : ''}>${escapeHtml(embPresets.custom?.label || '自定义兼容 API')}</option>
            <option value="disabled" ${embedding.provider === 'disabled' ? 'selected' : ''}>禁用（管线将跳过聚类）</option>
          </select>
        </div>
        <div class="form-group" id="ms-emb-model-group">
          <label class="form-label" for="ms-emb-model">Embedding 模型名</label>
          <input class="form-input" id="ms-emb-model" maxlength="160" value="${escapeHtml(embedding.model || '')}">
        </div>
      </div>
      <div class="form-row" id="ms-emb-cloud-row">
        <div class="form-group">
          <label class="form-label" for="ms-emb-url">Embedding Base URL</label>
          <input class="form-input" id="ms-emb-url" maxlength="400" value="${escapeHtml(embedding.base_url || '')}">
        </div>
        <div class="form-group">
          <label class="form-label" for="ms-emb-key">Embedding API Key（${embedding.api_key_configured ? `已配置 ${escapeHtml(embedding.api_key_masked)}` : '未单独配置'}）</label>
          <input class="form-input" id="ms-emb-key" type="password" autocomplete="off" placeholder="留空保留已有密钥；阿里云/OpenAI 亦可自动复用对应厂商 Key">
        </div>
      </div>
      <p class="discovery-hint" id="ms-emb-local-note"></p>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="discovery-toolbar">
        <button class="btn btn-primary" id="ms-save" type="button">💾 保存并立即生效</button>
        <button class="btn btn-secondary" id="ms-test-primary" type="button">⚡ 测试主模型</button>
        <button class="btn btn-secondary" id="ms-test-emb" type="button">🧬 测试 Embedding</button>
      </div>
      <p class="discovery-hint" id="ms-status" role="status" style="margin-top:10px"></p>
      <p class="discovery-error" id="ms-error" role="alert"></p>
    </div>
  `;

  const el = id => container.querySelector(`#${id}`);
  function syncPrimaryFields(resetModel = false) {
    const p = el('ms-primary-provider').value;
    const info = providers[p] || {};
    if (resetModel) el('ms-primary-model').value = info.model || primaryPresets[p]?.default_model || '';
    el('ms-primary-key-status').textContent = info.api_key_configured ? `已配置 ${info.api_key_masked}` : '未配置';
    el('ms-openai-url-group').style.display = p === 'openai' ? 'block' : 'none';
    el('ms-minimax-gid-group').style.display = p === 'minimax' ? 'block' : 'none';
  }
  function syncMultimodalFields() {
    const m = el('ms-mm-provider').value;
    el('ms-mm-model-group').style.display = ['deepseek', 'openai', 'google'].includes(m) ? 'block' : 'none';
    if (m === 'deepseek' && !el('ms-mm-model').value) el('ms-mm-model').value = 'deepseek-flash';
    if (m === 'openai' && !el('ms-mm-model').value) el('ms-mm-model').value = 'gpt-4o-mini';
    if (m === 'google' && !el('ms-mm-model').value) el('ms-mm-model').value = 'gemini-2.0-flash-lite';
  }
  function syncEmbFields(resetDefaults = false) {
    const ep = el('ms-emb-provider').value;
    const isCloud = ['siliconflow', 'dashscope', 'zhipu', 'openai', 'custom'].includes(ep);
    el('ms-emb-model-group').style.display = ep === 'disabled' ? 'none' : 'block';
    el('ms-emb-cloud-row').style.display = isCloud ? 'flex' : 'none';
    if (resetDefaults) {
      if (ep === 'local' || ep === 'auto') {
        el('ms-emb-model').value = embedding.local_model || 'BAAI/bge-small-zh-v1.5';
        el('ms-emb-url').value = '';
      } else if (embPresets[ep]) {
        el('ms-emb-model').value = embPresets[ep].default_model || '';
        el('ms-emb-url').value = embPresets[ep].base_url || '';
      }
    }
    el('ms-emb-local-note').textContent = ep === 'local' || ep === 'auto'
      ? (embedding.fastembed_available ? '✅ 本机 fastembed 已就绪，无需 API Key 即可离线生成 512 维中文向量。' : '⚠️ 当前环境未安装 fastembed，请安装后使用或切换为云端 Embedding。')
      : ep === 'disabled' ? '⚠️ 禁用后运行管线只提取文本信号，跳过语义去重与聚类。' : '提示：云端向量需要对应平台 API Key。';
  }

  el('ms-primary-provider').onchange = () => syncPrimaryFields(true);
  el('ms-mm-provider').onchange = syncMultimodalFields;
  el('ms-emb-provider').onchange = () => syncEmbFields(true);
  syncPrimaryFields(false);
  syncMultimodalFields();
  syncEmbFields(false);

  el('ms-save').onclick = async () => {
    el('ms-error').textContent = '';
    el('ms-status').textContent = '正在保存并热加载模型…';
    el('ms-save').disabled = true;
    try {
      const saved = await apiPost('/llm/settings', {
        default_llm_provider: el('ms-primary-provider').value,
        primary_model: el('ms-primary-model').value.trim(),
        primary_api_key: el('ms-primary-key').value.trim(),
        openai_base_url: el('ms-openai-url').value.trim(),
        minimax_group_id: el('ms-minimax-gid').value.trim(),
        multimodal_llm_provider: el('ms-mm-provider').value,
        multimodal_model: el('ms-mm-model').value.trim(),
        embedding_provider: el('ms-emb-provider').value,
        embedding_model: el('ms-emb-model').value.trim(),
        embedding_base_url: el('ms-emb-url').value.trim(),
        embedding_api_key: el('ms-emb-key').value.trim(),
      });
      el('ms-primary-key').value = '';
      el('ms-emb-key').value = '';
      const caps = saved.capabilities || {};
      el('ms-status').textContent = `✅ 已保存并立即生效！主模型：${caps.primary?.provider} · ${caps.primary?.model}；Embedding：${caps.embedding?.enabled ? `${caps.embedding.provider} · ${caps.embedding.model}` : '未启用'}`;
      buildSidebar();
      showToast('模型设置已保存并生效', 'success');
    } catch (e) {
      el('ms-status').textContent = '';
      el('ms-error').textContent = `保存失败：${e.message}`;
    } finally {
      el('ms-save').disabled = false;
    }
  };

  async function runTest(target, btnId) {
    const btn = el(btnId);
    btn.disabled = true;
    el('ms-error').textContent = '';
    el('ms-status').textContent = target === 'primary' ? '正在测试主模型连通性…' : '正在测试 Embedding 向量生成…';
    try {
      const res = await apiPost('/llm/test', { target });
      if (res.ok) {
        const extra = res.dimensions ? ` · 向量维度 ${res.dimensions}` : ` · 回复: ${res.preview}`;
        el('ms-status').textContent = `✅ ${res.provider} (${res.model}) 测试成功（耗时 ${res.latency_ms}ms${extra}）`;
      } else {
        el('ms-status').textContent = '';
        el('ms-error').textContent = `测试未通过：${res.error}`;
      }
    } catch (e) {
      el('ms-status').textContent = '';
      el('ms-error').textContent = `测试失败：${e.message}`;
    } finally {
      btn.disabled = false;
    }
  }

  el('ms-test-primary').onclick = () => runTest('primary', 'ms-test-primary');
  el('ms-test-emb').onclick = () => runTest('embedding', 'ms-test-emb');
}

/* ======================================================== Versions Page ===== */

async function renderVersionsPage(container) {
  container.innerHTML = `
    <div class="card">
      <div class="section-title">➕ 新建版本</div>
      <p class="discovery-hint">为不同调研课题、时间轮次或竞品建立独立版本；每个版本的原始反馈、提取信号、主题聚类、痛点、机会卡片与需求候选完全隔离。</p>
      <div class="form-row" style="margin-top:12px">
        <div class="form-group">
          <label class="form-label">版本名称 *</label>
          <input class="form-input" id="ver-new-name" maxlength="120" placeholder="例如：v2-DeepSeek插件全平台调研-11月">
        </div>
        <div class="form-group">
          <label class="form-label">版本备注 / 调研目标</label>
          <input class="form-input" id="ver-new-desc" maxlength="500" placeholder="例如：小红书+B站+微博+知乎+抖音 5 平台同步采集">
        </div>
      </div>
      <button class="btn btn-primary" id="btn-create-version" type="button">🗂️ 创建并切换到该版本</button>
    </div>
    <div id="versions-list"><div class="card"><p class="discovery-hint">正在加载版本列表…</p></div></div>
  `;

  const platformNames = {
    xiaohongshu: '小红书', bilibili: 'B站', weibo: '微博', zhihu: '知乎', douyin: '抖音',
    github: 'GitHub', manual: '手动', custom: '社区',
  };

  async function loadVersionsList() {
    const listEl = document.getElementById('versions-list');
    if (!listEl || !container.isConnected) return;
    try {
      const data = await apiGet('/versions');
      if (!container.isConnected) return;
      const versions = Array.isArray(data?.versions) ? data.versions : [];
      cachedVersions = versions.length ? versions : cachedVersions;
      const sel = document.getElementById('version-select');
      if (sel) populateVersionSelect(sel, getSelectedVersion(), true);

      if (!versions.length) {
        showEmpty(listEl, '🗂️', '暂无版本', '请先在上方创建一个新版本');
        return;
      }
      const currentVer = getSelectedVersion();
      listEl.innerHTML = '';
      versions.forEach(ver => {
        const st = ver.stats || {};
        const isCurrent = ver.id === currentVer;
        const card = document.createElement('div');
        card.className = 'card version-card' + (isCurrent ? ' version-card-active' : '');
        const sourceChips = Object.entries(st.sources || {})
          .map(([k, cnt]) => `<span class="badge badge-info">${escapeHtml(platformNames[k] || k)} ${cnt}</span>`)
          .join('');
        card.innerHTML = `
          <div class="card-header">
            <div>
              <div class="card-title">
                ${escapeHtml(ver.name)}
                ${isCurrent ? '<span class="badge badge-success" style="margin-left:8px">当前工作版本</span>' : ''}
                ${ver.status === 'archived' ? '<span class="badge badge-warning" style="margin-left:8px">已归档</span>' : ''}
                ${ver.is_default ? '<span class="badge badge-default" style="margin-left:8px">内置默认</span>' : ''}
              </div>
              <div class="card-subtitle">ID: <code>${escapeHtml(ver.id)}</code>${ver.description ? ` · ${escapeHtml(ver.description)}` : ''}</div>
            </div>
            <div class="card-header-actions">
              ${!isCurrent ? `<button class="btn btn-primary btn-sm" data-ver-act="use" type="button">切换为当前版本</button>` : ''}
              <button class="btn btn-secondary btn-sm" data-ver-act="rename" type="button">重命名</button>
              ${!ver.is_default ? `<button class="btn btn-secondary btn-sm" data-ver-act="archive" type="button">${ver.status === 'archived' ? '取消归档' : '归档'}</button>` : ''}
              ${!ver.is_default ? `<button class="btn btn-secondary btn-sm" data-ver-act="delete" style="color:var(--danger)" type="button">删除</button>` : ''}
            </div>
          </div>
          <div class="version-stats-row">
            <span class="badge badge-default">原始反馈 ${st.feedback_count ?? 0}</span>
            <span class="badge badge-default">提取信号 ${st.signal_count ?? 0}</span>
            <span class="badge badge-default">主题 ${st.theme_count ?? 0}</span>
            <span class="badge badge-default">痛点 ${st.pain_point_count ?? 0}</span>
            <span class="badge badge-default">机会 ${st.opportunity_count ?? 0}</span>
            <span class="badge badge-default">需求 ${st.requirement_count ?? 0}</span>
          </div>
          ${sourceChips ? `<div class="version-stats-row" style="margin-top:8px"><span class="discovery-hint" style="margin:0 4px 0 0">平台分布：</span>${sourceChips}</div>` : '<p class="discovery-hint" style="margin-top:8px">该版本暂未导入数据，可前往「🔌 数据源」多平台采集导入。</p>'}
        `;
        const useBtn = card.querySelector('[data-ver-act="use"]');
        if (useBtn) useBtn.onclick = () => {
          setSelectedVersion(ver.id);
          showToast(`已切换到版本「${ver.name}」`, 'success');
          navigate();
        };
        const renameBtn = card.querySelector('[data-ver-act="rename"]');
        if (renameBtn) renameBtn.onclick = async () => {
          const nextName = typeof prompt === 'function' ? prompt('修改版本名称：', ver.name) : '';
          if (!nextName || !nextName.trim()) return;
          try {
            await apiPatch(`/versions/${encodeURIComponent(ver.id)}`, { name: nextName.trim() });
            showToast('版本名称已更新', 'success');
            await loadVersionsList();
          } catch (e) { showToast(`更新失败：${e.message}`, 'danger'); }
        };
        const archBtn = card.querySelector('[data-ver-act="archive"]');
        if (archBtn) archBtn.onclick = async () => {
          const nextStatus = ver.status === 'archived' ? 'active' : 'archived';
          try {
            await apiPatch(`/versions/${encodeURIComponent(ver.id)}`, { status: nextStatus });
            showToast(nextStatus === 'archived' ? '已归档该版本' : '已恢复为活跃版本', 'info');
            await loadVersionsList();
          } catch (e) { showToast(`操作失败：${e.message}`, 'danger'); }
        };
        const delBtn = card.querySelector('[data-ver-act="delete"]');
        if (delBtn) delBtn.onclick = async () => {
          if (typeof confirm === 'function' && !confirm(`确认删除版本「${ver.name}」及其下所有反馈、信号与资产？此操作不可撤销。`)) return;
          try {
            await apiDelete(`/versions/${encodeURIComponent(ver.id)}`);
            if (getSelectedVersion() === ver.id) setSelectedVersion('default');
            showToast(`已删除版本「${ver.name}」`, 'info');
            await loadVersionsList();
            navigate();
          } catch (e) { showToast(`删除失败：${e.message}`, 'danger'); }
        };
        listEl.appendChild(card);
      });
    } catch (e) {
      if (container.isConnected) listEl.innerHTML = `<div class="card"><p class="discovery-error">加载版本失败：${escapeHtml(e.message)}</p></div>`;
    }
  }

  document.getElementById('btn-create-version').onclick = async () => {
    const nameEl = document.getElementById('ver-new-name');
    const descEl = document.getElementById('ver-new-desc');
    const name = (nameEl?.value || '').trim();
    if (!name) { showToast('请填写版本名称', 'warning'); return; }
    try {
      const created = await apiPost('/versions', { name, description: (descEl?.value || '').trim() });
      setSelectedVersion(created.id);
      if (nameEl) nameEl.value = '';
      if (descEl) descEl.value = '';
      showToast(`已创建并切换到版本「${created.name}」`, 'success');
      await loadVersionsList();
      navigate();
    } catch (e) {
      showToast(`创建版本失败：${e.message}`, 'danger');
    }
  };

  await loadVersionsList();
}

/* ============================================================ Bootstrap ===== */

window.onhashchange = navigate;

document.addEventListener('DOMContentLoaded', () => {
  navigate();
  syncActivePipelineFromServer();

  // Mobile sidebar toggle
  const sidebar = document.getElementById('sidebar');
  const btn = document.getElementById('mobileMenuBtn');
  btn.onclick = () => sidebar.classList.toggle('open');
  document.addEventListener('click', (e) => {
    if (!sidebar.contains(e.target) && e.target !== btn) {
      sidebar.classList.remove('open');
    }
  });
});
