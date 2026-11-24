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

