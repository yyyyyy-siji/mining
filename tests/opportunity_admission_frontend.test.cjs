// D5 offline interactions against the actual SPA, using synthetic records.
// These tests do not connect Chrome or prove real platform collection.
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

const flush = () => new Promise(resolve => setImmediate(resolve));
const plainValue = value => JSON.parse(JSON.stringify(value));
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { resolve, promise }; };
Element.prototype.click = function () { return this.onclick?.(); };
Element.prototype.remove = function () { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); };
const evidence = (quote, id = 'feedback-one') => ({ feedback_id: id, quote, quote_field: 'text', source_type: 'xiaohongshu', source_url: 'https://www.xiaohongshu.com/explore/64abcdef0123456789abcdef', external_url: 'https://www.xiaohongshu.com/explore/64abcdef0123456789abcdef', source_captured_at: '2026-11-12T10:00:00+08:00', locator_level: 'parent_page', content_nature: 'original_text', snapshot_verification: { status: 'verified' }, capture_version: 'mining-existing-chrome-dom/v1' });
const assessment = () => ({
  current_difficulty: { statement: '<script>OFFLINE 当前仍需逐条核对</script>', evidence: [evidence('<img>OFFLINE 现在仍需逐条核对')] },
  current_solution: { status: 'mentioned', description: 'OFFLINE 已有周报', evidence: [evidence('OFFLINE 已有周报')] },
  remaining_gap: { status: 'explicit', description: 'OFFLINE 周报不能附回原始改动依据', evidence: [evidence('OFFLINE 但不能附回原始改动依据')] },
  basis: 'current_complaint',
});
const candidate = () => ({ title: '<script>OFFLINE 缺口</script>', user_segment: 'OFFLINE 维护者', scenario: 'OFFLINE 对账', pain_point: 'OFFLINE 手工核对', minimum_idea: 'OFFLINE 附原文', reasoning: 'OFFLINE 仅为推断', evidence: [evidence('OFFLINE 通用引文')], validation_questions: ['OFFLINE 是否当前仍困难'], need_assessment: assessment() });
const result = (strict = true, candidates = [candidate()]) => ({ require_unmet_evidence: strict, selected_count: 1, analyzed_count: 1, duplicate_count: 0, message: 'OFFLINE 预览', candidates, limitations: ['OFFLINE 不证明市场需求'], excluded: [], semantic_status: 'model_assessment_pending_review', market_validation: 'not_performed' });
const material = () => ({ id: 'feedback-one', pipeline_profile: 'product_feedback', subject: 'OFFLINE 已存材料', text_preview: 'OFFLINE 现在仍需逐条核对；已有周报，但不能附回原始改动依据', source_type: 'xiaohongshu', source_url: evidence('').source_url });

async function setup({ post, legacyFixture = false, seededResult = null } = {}) {
  const panel = new Element(); panel.mounted = true;
  if (legacyFixture) {
    const query = panel.querySelector.bind(panel);
    panel.querySelector = selector => ['[data-role="require-unmet"]', '[data-role="quality-note"]'].includes(selector) ? null : query(selector);
  }
  const body = new Element('body'); body.mounted = true;
  const calls = [], blobs = [], downloads = [], values = new Map([['signalminer_profile', 'product_feedback']]);
  const location = { hash: '#opportunities' };
  class CaptureURL extends URL {}
  CaptureURL.createObjectURL = blob => { blobs.push(blob); return 'blob:OFFLINE'; };
  CaptureURL.revokeObjectURL = () => {};
  const context = vm.createContext({ URL: CaptureURL, Blob, console, window: {}, location, setTimeout: () => {},
    localStorage: { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) },
    document: { addEventListener() {}, body, createElement: tag => { const el = new Element(tag); if (tag === 'a') el.click = () => downloads.push({ href: el.href, download: el.download }); return el; } },
    __get: async url => { calls.push({ method: 'GET', url }); if (url === '/feedback') return [material()]; if (url.endsWith('/source-snapshot')) return { feedback_id: 'feedback-one', snapshot_verification: { status: 'verified' }, content: { text: 'OFFLINE original' } }; return { ...material(), content: { text: material().text_preview } }; },
    __post: async (url, payload) => { calls.push({ method: 'POST', url, payload: plain(payload) }); return post ? post(url, payload) : result(); },
  });
  vm.runInContext(source, context); vm.runInContext('apiGet=__get; apiPost=__post', context);
  context.__material = material(); context.__result = seededResult;
  vm.runInContext('opportunityDiscoverySession.selected.set(__material.id,__material); opportunityDiscoverySession.result=__result;', context);
  context.renderOpportunityDiscovery(panel); await flush();
  const find = role => panel.querySelector(`[data-role="${role}"]`);
  const click = role => find(role).onclick();
  const session = () => plain(vm.runInContext('({result:opportunityDiscoverySession.result,decisions:opportunityDiscoverySession.decisions,selected:[...opportunityDiscoverySession.selected]})', context));
  return { panel, body, context, calls, blobs, downloads, values, location, find, click, session };
}

test('real opportunity UI defaults strict and calls discover only on explicit analysis', async () => {
  const h = await setup();
  assert.equal(h.find('require-unmet').checked, true); assert.match(h.find('quality-note').textContent, /严格候选预览/);
  assert.equal(h.calls.some(call => call.method === 'POST'), false);
  await h.click('discover');
  assert.deepEqual(h.calls.find(call => call.method === 'POST').payload, { feedback_ids: ['feedback-one'], require_unmet_evidence: true });
  assert.match(h.find('results').textContent, /严格候选预览/); assert.match(h.find('results').textContent, /语义待核实，市场未验证/);
  assert.equal(h.session().decisions[0].action, ''); assert.match(h.find('results').textContent, /尚未判断/);
});

test('disabling strict is a labeled loose preview; changing quality does not reanalyze or relabel existing results', async () => {
  const h = await setup({ post: async (_url, payload) => result(payload.require_unmet_evidence) });
  await h.click('discover');
  h.find('require-unmet').checked = false; h.find('require-unmet').onchange();
  assert.match(h.find('quality-note').textContent, /宽松线索预览/); assert.match(h.find('results').textContent, /本次质量模式：严格候选预览/);
  assert.equal(h.calls.filter(call => call.method === 'POST').length, 1);
  await h.click('discover');
  assert.equal(h.calls.filter(call => call.method === 'POST').at(-1).payload.require_unmet_evidence, false);
  assert.match(h.find('results').textContent, /本次质量模式：宽松 \/ 兼容线索预览/);
});

test('strict roles show safe original quotes, unknown solution stays unknown, and every role exposes its stored snapshot', async () => {
  const h = await setup(); await h.click('discover');
  const output = h.find('results');
  for (const label of ['当前困难', '已有办法', '尚存缺口']) assert.match(output.textContent, new RegExp(label));
  for (const part of Object.values(assessment()).filter(value => value?.evidence)) assert.ok(output.textContent.includes(part.evidence[0].quote));
  assert.equal(output.querySelectorAll('script').length, 0); assert.equal(output.querySelectorAll('img').length, 0);
  const snapshotButtons = output.querySelectorAll('button').filter(button => button.textContent === '查看来源详情 / 快照');
  assert.equal(snapshotButtons.length, 4, 'generic and three role evidence groups use the same provenance reader');
  await snapshotButtons[2].onclick(); assert.equal(h.calls.filter(call => call.url.endsWith('/source-snapshot')).length, 1);
  const unknown = candidate(); unknown.need_assessment.current_solution = { status: 'unknown', description: '', evidence: [] };
  const second = await setup({ post: async () => result(true, [unknown]) }); await second.click('discover');
  assert.match(second.find('results').textContent, /已有办法：未知 \/ 未提供（未知）/);
  assert.match(second.find('results').textContent, /该角色未提供本批原话/);
});

test('download includes analysis mode, all three complete role evidence payloads and undecided human review', async () => {
  const h = await setup(); await h.click('discover');
  const download = h.find('results').querySelectorAll('button').find(button => button.textContent === '下载候选与人工判断清单'); download.onclick();
  assert.equal(h.downloads[0].download, 'mining-opportunity-candidates.txt');
  const exported = await h.blobs[0].text();
  assert.match(exported, /质量模式：严格候选预览/); assert.match(exported, /语义待核实；市场未验证/);
  assert.match(exported, /当前困难原话/); assert.match(exported, /已有办法原话/); assert.match(exported, /尚存缺口原话/);
  for (const part of Object.values(assessment()).filter(value => value?.evidence)) assert.ok(exported.includes(JSON.stringify(part.evidence[0])));
  assert.match(exported, /我的判断：尚未判断/); assert.match(exported, /market|市场/);
});

test('missing new control keeps old request compatibility and legacy assessments remain explicitly unverified', async () => {
  const oldCandidate = candidate(); delete oldCandidate.need_assessment;
  const h = await setup({ legacyFixture: true, post: async () => result(false, [oldCandidate]) });
  await h.click('discover');
  assert.deepEqual(h.calls.find(call => call.method === 'POST').payload, { feedback_ids: ['feedback-one'] });
  assert.match(h.find('results').textContent, /未提供结构化角色依据/);
  assert.match(h.find('results').textContent, /未启用缺口门禁/);
});

test('strict mode refuses server fallback and missing assessments, and 0 candidates stays a valid honest result', async () => {
  const missing = candidate(); delete missing.need_assessment;
  for (const response of [result(false), result(true, [missing])]) {
    const h = await setup({ post: async () => response }); await h.click('discover');
    assert.match(h.find('error').textContent, /机会发现失败/); assert.equal(h.session().result, null);
    assert.equal(h.find('results').textContent, '');
  }
  const empty = await setup({ post: async () => ({ ...result(true, []), message: 'OFFLINE 原文仅提已有能力，缺口证据不足', excluded: [{ candidate_index: 0, reason: 'OFFLINE 缺少尚存缺口' }] }) });
  await empty.click('discover'); assert.match(empty.find('results').textContent, /本批暂无值得跟进的机会/);
  assert.match(empty.find('results').textContent, /缺少尚存缺口/); assert.match(empty.find('results').textContent, /严格候选预览/);
});

test('quality is frozen during an analysis and late strict responses cannot replace a newer material batch', async () => {
  const later = deferred(); const h = await setup({ post: () => later.promise });
  const pending = h.click('discover'); assert.equal(h.find('require-unmet').disabled, true);
  vm.runInContext("opportunityDiscoverySession.selected=new Map([['new',{id:'new'}]]); opportunityDiscoverySession.result={newer:true};", h.context);
  later.resolve(result()); await pending;
  assert.equal(h.session().result.newer, true); assert.equal(h.find('results').textContent, '');
});
