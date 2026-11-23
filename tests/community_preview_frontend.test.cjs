// Offline interactions against the actual SPA functions. The tiny DOM below
// supports only the markup/events used here; this is not browser layout QA.
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
        text._text = token;
        stack.at(-1).appendChild(text);
      }
    }
  }
  get innerHTML() { return escape(this._text) + this.children.map(child => `<${child.tagName}>${child.innerHTML}</${child.tagName}>`).join(''); }
  get value() {
    if (this._value !== undefined) return this._value;
    if (this.tagName === 'select') return this.querySelector('option')?.value ?? '';
    return '';
  }
  set value(value) { this._value = String(value); }
  matches(selector) {
    const attr = /^([\w-]+)?\[([\w-]+)="([^"]*)"\]$/.exec(selector);
    if (attr) return (!attr[1] || this.tagName === attr[1]) && (this.attributes[attr[2]] ?? this[attr[2]]) === attr[3];
    if (selector.startsWith('#')) return this.attributes.id === selector.slice(1);
    return this.tagName === selector;
  }
  querySelectorAll(selector) {
    return this.children.flatMap(child => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] ?? null; }
}

function setup({ post = async () => { throw new Error('Unexpected POST'); }, get = async () => { throw new Error('Unexpected GET'); }, profile = 'product_feedback' } = {}) {
  const panel = new Element();
  panel.mounted = true;
  const values = new Map([['signalminer_profile', profile]]);
  const calls = [];
  const location = { hash: '#connectors' };
  const context = vm.createContext({
    URL, Blob, console, location, setTimeout: () => {}, window: {},
    localStorage: { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) },
    document: { createElement: tag => new Element(tag), addEventListener() {}, getElementById: id => panel.querySelector(`#${id}`) },
    __post: async (url, body) => { calls.push({ method: 'POST', url, body: plain(body) }); return post(url, body); },
    __get: async (url, params) => { calls.push({ method: 'GET', url, params }); return get(url, params); },
  });
  vm.runInContext(source, context);
  vm.runInContext('apiPost = __post; apiGet = __get;', context);
  context.renderCommunitySamplesPanel(panel);
  const find = name => panel.querySelector(`[data-community="${name}"]`);
  const click = name => find(name).onclick();
  const change = (name, value) => { find(name).value = value; find(name).oninput(); };
  const session = () => plain(vm.runInContext('({ selected: [...opportunityDiscoverySession.selected.entries()], result: opportunityDiscoverySession.result, materials: opportunityDiscoverySession.materials, decisions: opportunityDiscoverySession.decisions })', context));
  return { panel, context, calls, values, location, find, click, change, session };
}

const item = (n, overrides = {}) => ({
  source_type: 'custom', pipeline_profile: 'product_feedback', subject: `Title ${n}`, text: `Original ${n}`,
  external_url: `https://www.v2ex.com/t/${n}`, capture_method: 'crawler', source_captured_at: '2026-11-04T09:00:00Z',
  source_note: 'public feed', raw_payload: { published_at: '2026-11-03T01:00:00Z', updated_at: 'DO_NOT_USE_UPDATED', original: { preserved: n } }, ...overrides,
});
const preview = items => ({ items, summary: { source: 'v2ex', query: '', days: 30, limit: 10, kinds: ['qna'], requests: 1, fetched: items.length + 1, collected: items.length, skipped: 1, skip_reasons: { outside_time_window: 1 }, errors: [], status: items.length ? 'bounded' : 'empty', stop_reason: 'request_limit', coverage_note: 'Only the current public feed', published_from: '2026-10-05T09:00:00Z', published_to: '2026-11-04T09:00:00Z' } });
const detail = (id, overrides = {}) => ({ id, pipeline_profile: 'product_feedback', source_type: 'custom', content: { subject: `Stored ${id}`, text: `Stored text ${id}` }, external_url: `https://news.ycombinator.com/item?id=${id}`, ...overrides });
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };

test('defaults, bounded/empty counts, text safety, source links, and distinct time fields', async () => {
  const malicious = '<img src=x onerror="alert(1)"> & 原文';
  const h = setup({ post: async () => preview([item(1, { subject: malicious, text: malicious })]) });
  assert.equal(h.find('source').value, 'v2ex');
  assert.equal(h.find('node').value, 'qna');
  assert.equal(h.find('days').value, '30');
  assert.equal(h.find('limit').value, '10');
  assert.equal(h.find('query').value, '');
  assert.match(h.find('coverage').textContent, /关键词只过滤当前订阅流/);
  await h.click('preview');
  assert.deepEqual(h.calls[0].body, { source: 'v2ex', query: '', days: 30, limit: 10, v2ex_node: 'qna', kind: 'both' });
  assert.equal(h.calls.length, 1, 'preview must not import or analyze');
  assert.match(h.find('summary').textContent, /读取 2 条 · 返回 1 条 · 跳过 1 条/);
  assert.match(h.find('summary').textContent, /达到采集预算/);
  assert.match(h.find('summary').textContent, /发布时间筛选范围：2026-10-05T09:00:00Z 至 2026-11-04T09:00:00Z/);
  assert.match(h.find('summary').textContent, /发布时间不在范围内：1/);
  assert.equal(h.find('items').querySelector('strong').textContent, malicious);
  assert.equal(h.find('items').querySelectorAll('img').length, 0);
  assert.match(h.find('items').textContent, /发布时间：2026-11-03T01:00:00Z · 采集时间：2026-11-04T09:00:00Z/);
  assert.doesNotMatch(h.find('items').textContent, /DO_NOT_USE_UPDATED/);
  const link = h.find('items').querySelector('a');
  assert.equal(link.href, 'https://www.v2ex.com/t/1');
  assert.equal(link.rel, 'noopener noreferrer');
  assert.equal(h.find('import').disabled, true);
  const empty = setup({ post: async () => preview([]) });
  await empty.click('preview');
  assert.match(empty.find('summary').textContent, /未找到符合条件/);
  assert.equal(empty.find('handoff').hidden, true);
});

test('explicit import preserves fields and handoff uses unique actual stored IDs/URLs', async () => {
  const materials = [item(11), item(22), item(33)];
  const h = setup({
    post: async url => url.endsWith('/preview') ? preview(materials) : { ingested: 3, duplicates: 0, feedback_ids: ['old', 'old', 'new'] },
    get: async url => detail(url.split('/').at(-1)),
  });
  vm.runInContext("opportunityDiscoverySession.selected.set('previous', {id:'previous'}); opportunityDiscoverySession.result = {old: true}; opportunityDiscoverySession.materials = ['old']; opportunityDiscoverySession.decisions = ['note'];", h.context);
  await h.click('preview');
  h.click('all');
  await h.click('import');
  assert.deepEqual(h.calls.filter(call => call.url === '/feedback/batch')[0].body, materials);
  assert.deepEqual(h.calls.filter(call => call.method === 'GET').map(call => call.url), ['/feedback/old', '/feedback/new']);
  assert.match(h.find('receipt').textContent, /已处理 3 条.*本批可用 2 条/);
  assert.doesNotMatch(h.find('receipt').textContent, /新增3条|无重复/);
  assert.equal(h.session().selected[0][0], 'previous', 'do not replace session until explicit handoff');
  assert.equal(h.find('import').disabled, true);
  await h.click('import');
  assert.equal(h.calls.filter(call => call.url === '/feedback/batch').length, 1);
  await h.click('handoff');
  const session = h.session();
  assert.deepEqual(session.selected.map(([id]) => id), ['old', 'new']);
  assert.equal(session.selected[0][1].source_url, 'https://news.ycombinator.com/item?id=old');
  assert.equal(session.selected[0][1].external_url, 'https://news.ycombinator.com/item?id=old');
  assert.equal(session.selected[0][1].text_preview, 'Stored text old');
  assert.equal(session.result, null);
  assert.deepEqual(session.materials, []);
  assert.deepEqual(session.decisions, []);
  assert.equal(h.location.hash, 'opportunities');
  assert.equal(h.calls.some(call => call.url.includes('discover')), false);
});

test('changing conditions clears old batch and old replies cannot complete a newer request', async () => {
  const a = deferred();
  const b = deferred();
  let count = 0;
  const h = setup({ post: () => (++count === 1 ? a.promise : b.promise) });
  const first = h.click('preview');
  assert.equal(h.find('preview').disabled, true);
  await h.click('preview');
  assert.equal(count, 1, 'double preview is blocked');
  h.change('query', 'new query');
  assert.equal(h.find('items').children.length, 0);
  const second = h.click('preview');
  a.resolve(preview([item(1)]));
  await first;
  assert.equal(h.find('preview').disabled, true, 'stale finally must not unlock the newer request');
  assert.equal(h.find('items').children.length, 0);
  b.resolve(preview([item(2)]));
  await second;
  assert.match(h.find('items').textContent, /Title 2/);
  assert.doesNotMatch(h.find('items').textContent, /Title 1/);
  h.click('all');
  h.change('source', 'hn');
  assert.equal(h.find('items').children.length, 0);
  assert.equal(h.find('import').disabled, true);
  assert.equal(h.find('node-label').hidden, true);
  assert.equal(h.find('kind-label').hidden, false);
});

for (const leave of ['page', 'profile', 'unmount']) {
  test(`late preview/import replies cannot update after ${leave} change`, async () => {
    const pendingPreview = deferred();
    const h = setup({ post: () => pendingPreview.promise });
    const pending = h.click('preview');
    if (leave === 'page') h.location.hash = '#feedback';
    if (leave === 'profile') h.values.set('signalminer_profile', 'aigc_video');
    if (leave === 'unmount') h.panel.mounted = false;
    pendingPreview.resolve(preview([item(1)]));
    await pending;
    assert.equal(h.find('items').children.length, 0);
    assert.deepEqual(h.session().selected, []);

    const pendingImport = deferred();
    const imported = setup({ post: url => url.endsWith('/preview') ? preview([item(1)]) : pendingImport.promise });
    await imported.click('preview');
    imported.click('all');
    const importing = imported.click('import');
    if (leave === 'page') imported.location.hash = '#feedback';
    if (leave === 'profile') imported.values.set('signalminer_profile', 'aigc_video');
    if (leave === 'unmount') imported.panel.mounted = false;
    pendingImport.resolve({ feedback_ids: ['f1'] });
    await importing;
    assert.equal(imported.calls.some(call => call.method === 'GET'), false);
    assert.equal(imported.find('handoff').hidden, true);
    assert.deepEqual(imported.session().selected, []);
  });
}

test('failed readback retries only reads, validates profile, and never reimports', async () => {
  let reads = 0;
  const h = setup({
    post: async url => url.endsWith('/preview') ? preview([item(1)]) : { feedback_ids: ['f1'] },
    get: async () => (++reads === 1 ? detail('f1', { pipeline_profile: 'aigc_video' }) : detail('f1', { external_url: 'javascript:alert(1)' })),
  });
  await h.click('preview'); h.click('all'); await h.click('import');
  assert.match(h.find('error').textContent, /导入已完成.*回读失败/);
  assert.equal(h.find('import').disabled, true);
  assert.equal(h.find('handoff').textContent, '重试读取本批材料');
  await h.click('handoff');
  assert.equal(h.calls.filter(call => call.url === '/feedback/batch').length, 1);
  assert.equal(reads, 2);
  assert.deepEqual(h.session().selected, [], 'read retry must not navigate or replace selection');
  await h.click('handoff');
  assert.equal(h.session().selected[0][1].source_url, null, 'unsafe stored URL must not become clickable');
  assert.equal(h.session().selected[0][1].external_url, 'javascript:alert(1)', 'do not replace stored URL with preview URL');
});

test('preview/import errors remain failures and retain a usable retry', async () => {
  let previews = 0;
  let imports = 0;
  const h = setup({
    post: async url => {
      if (url.endsWith('/preview')) { if (++previews === 1) throw new Error('<img src=x> unavailable'); return preview([item(1)]); }
      if (++imports === 1) throw new Error('partial write may have happened');
      return { feedback_ids: [] };
    },
  });
  await h.click('preview');
  assert.match(h.find('error').textContent, /采集预览失败/);
  assert.equal(h.find('error').querySelectorAll('img').length, 0);
  assert.equal(h.find('preview').disabled, false);
  await h.click('preview'); h.click('all'); await h.click('import');
  assert.match(h.find('error').textContent, /部分材料可能已处理/);
  assert.equal(h.find('import').disabled, false);
  assert.equal(h.find('handoff').hidden, true);
  await h.click('import');
  assert.match(h.find('error').textContent, /导入回执与所选材料不对应/);
  assert.deepEqual(h.session().selected, []);
});

test('30-item bound and invalid controls stop unsupported requests', async () => {
  const h = setup({ post: async () => preview(Array.from({ length: 31 }, (_, n) => item(n + 1))) });
  h.change('limit', '31'); await h.click('preview');
  assert.equal(h.calls.length, 0);
  h.change('limit', '30'); await h.click('preview');
  assert.match(h.find('error').textContent, /返回格式异常/);
  assert.equal(h.find('import').disabled, true);
});

test('a detached O1 analysis reply cannot overwrite a new handoff session', async () => {
  const pending = deferred();
  const h = setup({ post: () => pending.promise, get: async () => [] });
  h.location.hash = '#opportunities';
  vm.runInContext("opportunityDiscoverySession.selected.set('old', {id:'old'});", h.context);
  h.context.renderOpportunityDiscovery(h.panel);
  await Promise.resolve();
  const analyzing = h.panel.querySelector('[data-role="discover"]').onclick();
  h.panel.mounted = false;
  vm.runInContext("opportunityDiscoverySession.selected = new Map([['new', {id:'new'}]]); opportunityDiscoverySession.result = null;", h.context);
  pending.resolve({ candidates: [], message: 'old analysis' });
  await analyzing;
  assert.deepEqual(h.session().selected.map(([id]) => id), ['new']);
  assert.equal(h.session().result, null);
});

test('normal collected status renders and community panel stays product-only beside legacy connectors', async () => {
  const h = setup({ post: async () => ({ ...preview([item(1)]), summary: { ...preview([item(1)]).summary, status: 'collected', stop_reason: 'sample_limit' } }) });
  await h.click('preview');
  assert.match(h.find('summary').textContent, /采集预览完成/);
  assert.match(h.find('summary').textContent, /已达到所选条数上限/);
  for (const profile of ['product_feedback', 'aigc_video']) {
    const page = setup({ profile, get: async url => { assert.equal(url, '/connectors'); return { connectors: ['github', 'webhook'] }; } });
    await page.context.renderConnectorsPage(page.panel);
    assert.equal(Boolean(page.panel.querySelector('#community-preview')), profile === 'product_feedback');
    assert.ok(page.panel.querySelector('#btn-gh-fetch'));
    assert.match(page.panel.textContent, /Webhook/);
  }
});
