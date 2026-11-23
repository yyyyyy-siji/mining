// D1 offline UI semantics against the actual SPA. This is not browser layout QA.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../frontend/static/app.js'), 'utf8');
const escape = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const plain = value => JSON.parse(JSON.stringify(value));
class Element {
  constructor(tag = 'div') {
    this.tagName = tag.toLowerCase();
    this.children = [];
    this.attributes = {};
    this._text = '';
    this._value = undefined;
    this.disabled = false;
    this.checked = false;
    this.hidden = false;
    this.dataset = {};
    this.style = {};
    this.classList = { add() {}, remove() {}, toggle() {} };
  }
  get isConnected() { return Boolean(this.mounted || this.parent?.isConnected); }
  appendChild(child) { child.parent = this; this.children.push(child); return child; }
  append(...children) { children.forEach(child => this.appendChild(child)); }
  set textContent(value) { this._text = String(value ?? ''); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  set innerHTML(html) {
    this._text = '';
    this.children = [];
    // Replacing a real select's options re-evaluates its selected value.
    if (this.tagName === 'select') this._value = undefined;
    const stack = [this];
    for (const token of String(html).match(/<[^>]+>|[^<]+/g) || []) {
      if (token.startsWith('</')) { stack.pop(); continue; }
      if (token.startsWith('<')) {
        const tag = /^<([a-z0-9-]+)/i.exec(token)?.[1];
        if (!tag) continue;
        const child = new Element(tag);
        const attrs = token.slice(tag.length + 1, -1);
        for (const match of attrs.matchAll(/([\w-]+)(?:="([^"]*)")?/g)) {
          child.attributes[match[1]] = match[2] ?? '';
        }
        child.hidden = Object.hasOwn(child.attributes, 'hidden');
        child.type = child.attributes.type;
        if (Object.hasOwn(child.attributes, 'value')) child._value = child.attributes.value;
        stack.at(-1).appendChild(child);
        if (!['input', 'br', 'hr'].includes(child.tagName)) stack.push(child);
      } else {
        const text = new Element('#text');
        text._text = token.replaceAll('&lt;', '<').replaceAll('&gt;', '>').replaceAll('&quot;', '"').replaceAll('&amp;', '&');
        stack.at(-1).appendChild(text);
      }
    }
  }
  click() { if (this.onclick) return this.onclick(); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); }
  get outerHTML() { return `<${this.tagName}>${this.innerHTML}</${this.tagName}>`; }
  get innerHTML() { return escape(this._text) + this.children.map(child => `<${child.tagName}>${child.innerHTML}</${child.tagName}>`).join(''); }
  get value() {
    if (this._value !== undefined) return this._value;
    if (this.tagName === 'select') return this.querySelectorAll('option').find(option => Object.hasOwn(option.attributes, 'selected'))?.value ?? this.querySelector('option')?.value ?? '';
    return '';
  }
  set value(value) { this._value = String(value); }
  matches(selector) {
    const attr = /^([\w-]+)?\[([\w-]+)="([^"]*)"\]$/.exec(selector);
    if (attr) return (!attr[1] || this.tagName === attr[1]) && (this.attributes[attr[2]] ?? this[attr[2]]) === attr[3];
    if (selector.startsWith('.')) return String(this.className || '').split(' ').includes(selector.slice(1));
    if (selector.startsWith('#')) return this.attributes.id === selector.slice(1);
    return this.tagName === selector;
  }
  querySelectorAll(selector) {
    return this.children.flatMap(child => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] ?? null; }
}


function setup({ get = async () => { throw new Error('Unexpected GET'); }, post = async () => { throw new Error('Unexpected POST'); }, route = 'connectors' } = {}) {
  const panel = new Element();
  panel.mounted = true;
  const body = new Element('body');
  body.mounted = true;
  const values = new Map([['signalminer_profile', 'product_feedback']]);
  const calls = [];
  const blobs = [];
  const downloads = [];
  const location = { hash: `#${route}` };
  class TestURL extends URL {
    static createObjectURL(blob) { blobs.push(blob); return `blob:test-${blobs.length}`; }
    static revokeObjectURL() {}
  }
  const document = {
    body, addEventListener() {}, getElementById: id => panel.querySelector(`#${id}`),
    createElement(tag) {
      const element = new Element(tag);
      if (tag === 'a') element.click = () => { downloads.push({ href: element.href, filename: element.download }); };
      return element;
    },
  };
  const context = vm.createContext({
    URL: TestURL, Blob, console, location, setTimeout: () => {}, window: {}, document,
    localStorage: { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) },
    __get: async (url, params) => { calls.push({ method: 'GET', url, params }); return get(url, params); },
    __post: async (url, payload) => { calls.push({ method: 'POST', url, payload: plain(payload) }); return post(url, payload); },
  });
  vm.runInContext(source, context);
  vm.runInContext('apiGet = __get; apiPost = __post; showToast = () => {};', context);
  return { panel, context, location, values, calls, blobs, downloads,
    find: name => panel.querySelector(`[data-zhihu="${name}"]`),
    start: () => context.renderZhihuSearchPanel(panel),
  };
}
const status = configured => ({ configured, capabilities: ['official search'], limitations: ['API excerpts only'], setup_url: 'https://developer.zhihu.com/', configuration_hint: '在本机服务端设置 ZHIHU_ACCESS_SECRET 并重启服务；请勿在网页填写密钥。' });
const lead = overrides => ({
  title: '<img src=x onerror=bad()> title', excerpt: '<script>bad()</script> 摘要',
  curated_comments: ['<img src=x> 精选评论'], source_url: 'https://www.zhihu.com/question/123/answer/456',
  external_id: '456', entity_type: 'answer', content_nature: 'api_excerpt',
  source_created_at: '2026-10-30T09:00:00+08:00', source_updated_at: '2026-11-03T09:00:00+08:00',
  source_captured_at: '2026-11-05T01:00:00Z', provenance: { SearchHashId: 'search-1', raw_item: { ContentID: '456' } }, ...overrides,
});
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };
const buttons = element => element.querySelectorAll('button');
const findButton = (element, label) => buttons(element).find(button => button.textContent.includes(label));

test('unconfigured Zhihu stays server-only, exposes setup, and performs no preview or model call', async () => {
  const h = setup({ get: async () => status(false) });
  await h.start();
  assert.match(h.panel.textContent, /知乎官方搜索（检索线索）/);
  assert.match(h.find('status').textContent, /未配置/);
  assert.match(h.find('status').textContent, /ZHIHU_ACCESS_SECRET/);
  assert.equal(h.find('status').textContent.match(/ZHIHU_ACCESS_SECRET/g).length, 1, 'configuration guidance appears once');
  assert.equal(h.find('status').querySelectorAll('li').length, 2);
  assert.doesNotMatch(h.find('status').textContent, /\["official search"\]|\["API excerpts only"\]/);
  assert.equal(h.find('search').disabled, true);
  h.find('query').value = '效率工具';
  await h.find('search').onclick();
  assert.deepEqual(h.calls.map(call => call.url), ['/connectors/zhihu/status']);
  assert.equal(h.panel.querySelectorAll('input').length, 3, 'no credential input');
  assert.deepEqual([...h.values.keys()], ['signalminer_profile'], 'no credential persistence');
  const link = h.find('status').querySelector('a');
  assert.equal(link.href, 'https://developer.zhihu.com/');
  assert.equal(link.rel, 'noopener noreferrer');
});

test('leads are safe, clearly non-original, downloadable, and handed to empty manual text without auto-import', async () => {
  const rawLead = lead();
  const h = setup({ get: async () => status(true), post: async (url) => url.endsWith('/preview') ? { leads: [rawLead], summary: { requests: 1, count: 1 } } : { feedback_id: 'f1' } });
  await h.start();
  h.find('query').value = '效率';
  await h.find('search').onclick();
  assert.deepEqual(h.calls[1].payload, { query: '效率', count: 5, days: 30 });
  const list = h.find('leads');
  assert.equal(list.querySelectorAll('img').length, 0);
  assert.equal(list.querySelectorAll('script').length, 0);
  assert.match(list.textContent, /API 摘要（检索线索，非原始正文）/);
  assert.match(list.textContent, /精选评论（检索线索，缺少独立评论定位/);
  assert.doesNotMatch(list.textContent, /展开原文/);
  assert.equal(h.calls.filter(call => call.method === 'POST').length, 1);
  findButton(list, '下载线索来源 JSON').onclick();
  assert.equal(h.downloads.length, 1);
  assert.deepEqual(JSON.parse(await h.blobs[0].text()).lead, rawLead);
  findButton(list, '去导入页补充原文').onclick();
  assert.equal(h.location.hash, 'import');
  await h.context.renderImportPage(h.panel);
  const get = suffix => h.panel.querySelector(`#import-${suffix}`);
  assert.equal(get('text').value, '', 'API excerpt and comments never become the original body');
  assert.equal(get('external-id').value, '456');
  assert.equal(get('source-created-at').value, rawLead.source_created_at);
  assert.equal(get('content-nature').value, 'manual_text');
  assert.equal(get('text-origin').value, 'user_provided');
  assert.equal(get('locator-level').value, 'unknown');
  assert.equal(get('author').value, '');
  assert.equal(get('capture-method').value, 'manual_browser', 'supplemented text was provided manually');
  get('text').value = '用户另行提供的正文';
  get('entity-type').value = 'answer';
  await h.panel.querySelector('#btn-import-single').onclick();
  const payload = h.calls.at(-1).payload;
  assert.equal(payload.text, '用户另行提供的正文');
  assert.equal(payload.external_id, '456');
  assert.equal(payload.source_created_at, rawLead.source_created_at);
  assert.equal(payload.content_nature, 'manual_text');
  assert.equal(payload.text_origin, 'user_provided');
  assert.equal(payload.locator_level, 'unknown');
  assert.equal(payload.capture_method, 'manual_browser');
  assert.equal(payload.author_name, undefined, 'unknown author must not become a claimed name');
  assert.deepEqual(payload.raw_payload.zhihu_search_lead, rawLead);
});

test('invalid inputs never post; upstream errors remain errors and support retry', async () => {
  let fail = true;
  const h = setup({ get: async () => status(true), post: async () => {
    if (fail) throw new Error('503 upstream unavailable');
    return { leads: [], summary: { requests: 1 } };
  } });
  await h.start();
  await h.find('search').onclick();
  assert.equal(h.calls.length, 1);
  h.find('query').value = 'tool';
  h.find('count').value = '11';
  await h.find('search').onclick();
  assert.equal(h.calls.length, 1);
  h.find('count').value = '5';
  await h.find('search').onclick();
  assert.match(h.find('error').textContent, /503 upstream unavailable/);
  assert.doesNotMatch(h.find('summary').textContent, /未找到/);
  assert.equal(h.find('search').disabled, false);
  fail = false;
  await h.find('search').onclick();
  assert.match(h.find('summary').textContent, /未找到线索/);
});

test('late lead replies cannot populate new conditions, detached pages, or another mining profile', async () => {
  for (const mode of ['conditions', 'route', 'profile', 'detached']) {
    const wait = deferred();
    const h = setup({ get: async () => status(true), post: () => wait.promise });
    await h.start();
    h.find('query').value = 'old query';
    const pending = h.find('search').onclick();
    if (mode === 'conditions') { h.find('query').value = 'new query'; h.find('query').oninput(); }
    if (mode === 'route') h.location.hash = '#import';
    if (mode === 'profile') h.values.set('signalminer_profile', 'aigc_video');
    if (mode === 'detached') h.panel.mounted = false;
    wait.resolve({ leads: [lead()], summary: {} });
    await pending;
    assert.equal(h.find('leads').querySelectorAll('article').length, 0, mode);
    assert.equal(vm.runInContext('pendingSourceLead', h.context), null, mode);
  }
});

test('source details distinguish parent-page links and download the exact server snapshot safely', async () => {
  const record = {
    id: 'feedback-1', source_evidence: { content_nature: 'manual_text', locator_level: 'parent_page', external_id: 'comment-2', parent_id: 'post-1' },
    snapshot_verification: { status: 'verified' },
  };
  const snapshot = { source_evidence: record.source_evidence, content: { text: '<img src=x> original' }, raw_payload: { original: { preserved: true } }, snapshot_verification: { status: 'verified' }, snapshot_hash: 'abc' };
  const h = setup({ route: 'feedback', get: async url => url.endsWith('source-snapshot') ? snapshot : record });
  h.context.appendSourceSnapshot(h.panel, 'feedback-1', record);
  assert.match(h.panel.textContent, /仅定位父页面，不能直达该评论/);
  assert.match(h.panel.textContent, /人工提供文本，未联网核验/);
  assert.match(h.panel.textContent, /留存快照完整性一致/);
  assert.equal(h.context.sourceEvidenceLinkLabel(record), '打开父页面（不能直达该评论）');
  assert.equal(h.context.createSourceLink('javascript:alert(1)').tagName, 'span');
  await findButton(h.panel, '查看来源详情').onclick();
  assert.deepEqual(h.calls.map(call => call.url), ['/feedback/feedback-1', '/feedback/feedback-1/source-snapshot']);
  assert.equal(h.panel.querySelectorAll('img').length, 0);
  assert.match(h.panel.textContent, /不能证明平台真实性/);
  assert.deepEqual(JSON.parse(h.panel.querySelector('pre').textContent), snapshot);
  findButton(h.panel, '下载完整来源快照 JSON').onclick();
  assert.deepEqual(JSON.parse(await h.blobs[0].text()), snapshot);
});

test('historical and mismatched records are explicit; stale snapshot requests cannot mutate unmounted panels', async () => {
  const h = setup({ route: 'feedback' });
  assert.match(h.context.sourceEvidenceDescription({}), /历史文本，未记录快照/);
  assert.match(h.context.sourceEvidenceDescription({ snapshot_status: 'mismatch' }), /核对不一致/);
  const wait = deferred();
  const stale = setup({ route: 'feedback', get: () => wait.promise });
  stale.context.appendSourceSnapshot(stale.panel, 'old');
  const pending = findButton(stale.panel, '查看来源详情').onclick();
  const before = stale.panel.textContent;
  stale.panel.mounted = false;
  wait.resolve({ id: 'old', source_evidence: { content_nature: 'original_text' }, snapshot_verification: { status: 'verified' } });
  await pending;
  assert.equal(stale.panel.textContent, before);
  assert.equal(stale.calls.length, 1, 'no snapshot call after unmount');
});

test('manual entry defaults to browser capture and preserves explicit supported methods on source changes', async () => {
  const h = setup({ route: 'import' });
  await h.context.renderImportPage(h.panel);
  const source = h.panel.querySelector('#import-source');
  const method = h.panel.querySelector('#import-capture-method');
  assert.equal(method.value, 'manual_browser', 'initial user-provided text is not crawler output');
  method.value = 'crawler';
  method.onchange();
  source.value = 'tieba';
  source.onchange();
  assert.equal(method.value, 'crawler', 'a supported explicit choice must survive source changes');
  source.value = 'github';
  source.onchange();
  assert.equal(method.value, 'manual_browser', 'an unsupported previous choice falls back to manual');
  method.value = 'official_api';
  method.onchange();
  source.value = 'xiaohongshu';
  source.onchange();
  assert.equal(method.value, 'official_api', 'official API remains available when explicitly chosen');
  source.value = 'weibo';
  source.onchange();
  assert.equal(method.value, 'manual_browser');
});

test('manual source fields preserve identity and time; timezone-free input never posts', async () => {
  const h = setup({ route: 'import', post: async () => ({ feedback_id: 'one' }) });
  await h.context.renderImportPage(h.panel);
  const get = suffix => h.panel.querySelector(`#import-${suffix}`);
  get('text').value = 'A real manually provided comment';
  get('external-url').value = 'https://www.zhihu.com/question/123';
  get('external-id').value = 'comment-2';
  get('parent-id').value = 'post-1';
  get('parent-url').value = 'https://www.zhihu.com/question/123';
  get('parent-comment-id').value = 'comment-1';
  get('parent-comment-url').value = 'https://www.zhihu.com/question/123?comment=1';
  get('entity-type').value = 'comment';
  get('locator-level').value = 'parent_page';
  get('source-created-at').value = '2026-11-05T09:00:00';
  await h.panel.querySelector('#btn-import-single').onclick();
  assert.equal(h.calls.length, 0);
  get('source-created-at').value = '2026-11-05T09:00:00+08:00';
  get('source-updated-at').value = '2026-11-05T09:30:00+08:00';
  get('source-captured-at').value = '2026-11-05T01:40:00Z';
  get('coverage-scope').value = '完整评论';
  get('capture-version').value = 'manual-v1';
  await h.panel.querySelector('#btn-import-single').onclick();
  const payload = h.calls[0].payload;
  assert.equal(payload.external_id, 'comment-2');
  assert.equal(payload.entity_type, 'comment');
  assert.equal(payload.parent_id, 'post-1');
  assert.equal(payload.parent_comment_id, 'comment-1');
  assert.equal(payload.locator_level, 'parent_page');
  assert.equal(payload.coverage_scope, '完整评论');
  assert.equal(payload.capture_version, 'manual-v1');
  assert.equal(payload.source_created_at, '2026-11-05T09:00:00+08:00');
  assert.equal(payload.source_updated_at, '2026-11-05T09:30:00+08:00');
  assert.equal(payload.source_captured_at, '2026-11-05T01:40:00Z');
  assert.equal(payload.author_name, undefined);
});

test('candidate evidence and exported decisions keep provenance and never call a parent URL a direct comment link', async () => {
  const evidence = {
    feedback_id: 'comment-feedback', quote: '<img src=x> 用户提供的原话', quote_field: 'content.text', source_type: 'zhihu',
    source_url: 'https://www.zhihu.com/question/123', external_url: 'https://www.zhihu.com/question/123',
    content_nature: 'manual_text', locator_level: 'parent_page', external_id: 'comment-9', parent_id: '123',
    source_created_at: '2026-11-01T00:00:00Z', source_captured_at: '2026-11-05T00:00:00Z',
    snapshot_status: 'verified', snapshot_hash: 'snap-abc', text_origin: 'user_provided',
  };
  const h = setup({ route: 'opportunities', get: async () => [] });
  h.context.__result = {
    candidates: [{ title: 'Candidate', user_segment: 'user', scenario: 'scene', pain_point: 'problem', minimum_idea: 'idea', reasoning: 'reason', validation_questions: ['verify'], evidence: [evidence] }],
    selected_count: 1, analyzed_count: 1, duplicate_count: 0, message: 'preview', limitations: [], excluded: [],
  };
  vm.runInContext('opportunityDiscoverySession.result = __result;', h.context);
  h.context.renderOpportunityDiscovery(h.panel);
  assert.match(h.panel.textContent, /引文匹配字段：content.text/);
  assert.match(h.panel.textContent, /人工提供文本，未联网核验/);
  assert.match(h.panel.textContent, /仅定位父页面，不能直达该评论/);
  assert.equal(h.panel.querySelectorAll('img').length, 0);
  assert.ok(h.panel.querySelectorAll('a').some(link => link.textContent === '🔗 打开父页面（不能直达该评论）'));
  assert.ok(findButton(h.panel, '查看来源详情 / 快照'));
  findButton(h.panel, '下载候选与人工判断清单').onclick();
  const text = await h.blobs[0].text();
  assert.match(text, /"external_id":"comment-9"/);
  assert.match(text, /"snapshot_hash":"snap-abc"/);
  assert.match(text, /"quote_field":"content.text"/);
  assert.match(text, /不能直达该评论/);
});

test('snapshot verification response overrides an earlier detail integrity label', async () => {
  const h = setup({ route: 'feedback', get: async url => url.endsWith('source-snapshot') ? {
    feedback_id: 'changed', source_evidence: { content_nature: 'manual_text' }, snapshot_verification: { status: 'mismatch' },
  } : { id: 'changed', source_evidence: { content_nature: 'manual_text' }, snapshot_verification: { status: 'verified' } } });
  h.context.appendSourceSnapshot(h.panel, 'changed');
  await findButton(h.panel, '查看来源详情').onclick();
  const label = h.panel.querySelector('p').textContent;
  assert.match(label, /快照核对不一致/);
  assert.doesNotMatch(label, /留存快照完整性一致/);
});

test('Zhihu question leads map to a supported post entity while preserving the original API lead', async () => {
  const raw = lead({ entity_type: 'question', external_id: '123', source_url: 'https://www.zhihu.com/question/123', provenance: { raw_payload: { original: { ContentType: 'Question', ContentID: '123' } } } });
  const h = setup({ get: async () => status(true), post: async url => url.endsWith('/preview') ? { leads: [raw], summary: {} } : { feedback_id: 'question' } });
  await h.start();
  h.find('query').value = 'question';
  await h.find('search').onclick();
  findButton(h.find('leads'), '去导入页补充原文').onclick();
  await h.context.renderImportPage(h.panel);
  assert.equal(h.panel.querySelector('#import-entity-type').value, 'post');
  h.panel.querySelector('#import-text').value = '用户补充的问题正文';
  await h.panel.querySelector('#btn-import-single').onclick();
  const payload = h.calls.at(-1).payload;
  assert.equal(payload.entity_type, 'post');
  assert.equal(payload.raw_payload.zhihu_search_lead.entity_type, 'question');
  assert.equal(payload.raw_payload.zhihu_search_lead.provenance.raw_payload.original.ContentType, 'Question');
});
