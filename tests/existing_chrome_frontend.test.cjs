// D4 offline interactions against the actual SPA, using synthetic records.
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
const noteUrl = 'https://www.xiaohongshu.com/explore/64abcdef0123456789abcdef?xsec_token=OFFLINE';
const noteTab = { id: 'note-tab', title: '<script>OFFLINE title</script>', url: noteUrl };
const homeTab = { id: 'home-tab', title: 'OFFLINE 首页', url: 'https://www.xiaohongshu.com/explore' };
const status = (state = 'connected', activeTask = null) => ({ status: state, message: `OFFLINE ${state}`, active_task: activeTask, capabilities: { platform: 'xiaohongshu', max_posts: 1, max_comments: 3 } });
const task = (state = 'running', overrides = {}) => ({ id: 'task-one', status: state, terminal: state !== 'running', mode: 'current', tab_id: 'note-tab', message: `OFFLINE task ${state}`, ...overrides });
const item = (entity = 'post', n = 1) => ({ source_type: 'xiaohongshu', platform: 'xiaohongshu', pipeline_profile: 'product_feedback', external_id: entity === 'post' ? '64abcdef0123456789abcdef' : null, external_url: noteUrl, entity_type: entity, capture_method: 'crawler', capture_version: 'mining-existing-chrome-dom/v1', content_nature: 'original_text', text_origin: 'body', subject: '<script>OFFLINE title</script>', text: `${'<img src=x onerror=alert(1)>OFFLINE 原文'.repeat(30)} ${n}`, source_created_at: null, source_captured_at: '2026-11-12T10:00:00+08:00', locator_level: entity === 'post' ? 'item' : 'parent_page', parent_comment_id: null, coverage_scope: 'OFFLINE 已加载片段，不能据此声称完整采集', raw_payload: { method: 'OFFLINE DOM fixture', preserved: n } });
const stored = id => ({ id, pipeline_profile: 'product_feedback', source_type: 'xiaohongshu', external_url: noteUrl, content: { subject: `OFFLINE stored ${id}`, text: item().text }, context: { capture_method: 'crawler' } });

async function setup({ get, post, initial = 'connected', tabList = [noteTab, homeTab], timers = null } = {}) {
  const panel = new Element(); panel.mounted = true;
  const location = { hash: '#connectors' }, calls = [], values = new Map([['signalminer_profile', 'product_feedback']]);
  const listeners = new Map();
  const context = vm.createContext({ URL, Blob, console, location,
    window: { addEventListener: (name, handler) => listeners.set(name, handler), removeEventListener: name => listeners.delete(name) },
    setTimeout: timers ? timers.setTimeout : () => {}, clearTimeout: timers?.clearTimeout,
    localStorage: { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) },
    document: { createElement: tag => new Element(tag), addEventListener() {} },
    __get: async url => { calls.push({ method: 'GET', url }); if (get) return get(url); if (url === '/existing-chrome/status') return status(initial); if (url === '/existing-chrome/tabs') return { tabs: tabList }; throw new Error(`Unexpected GET ${url}`); },
    __post: async (url, body) => { calls.push({ method: 'POST', url, body: plain(body) }); if (post) return post(url, body); throw new Error(`Unexpected POST ${url}`); },
  });
  vm.runInContext(source, context); vm.runInContext('apiGet=__get; apiPost=__post', context);
  await context.renderExistingChromePanel(panel); await flush();
  const find = name => panel.querySelector(`[data-chrome="${name}"]`);
  const click = name => find(name).onclick();
  const change = (name, value) => { find(name).value = value; find(name).oninput(); };
  const session = () => plain(vm.runInContext('({selected:[...opportunityDiscoverySession.selected],result:opportunityDiscoverySession.result})', context));
  return { panel, location, values, calls, context, find, click, change, session, listeners };
}

async function previewSetup({ get, post, result = { items: [item(), item('comment', 2)], summary: { coverage: 'OFFLINE bounded', incomplete_reasons: ['仅已加载'] } } } = {}) {
  const h = await setup({
    get: async url => {
      if (url === '/existing-chrome/status') return status();
      if (url === '/existing-chrome/tabs') return { tabs: [noteTab, homeTab] };
      if (url === '/existing-chrome/tasks/task-one') return task('completed');
      if (url.endsWith('/results')) return result;
      return get ? get(url) : stored(url.split('/').at(-1));
    },
    post: async (url, body) => url === '/existing-chrome/tasks' ? task() : post(url, body),
  });
  h.change('tab', 'note-tab'); await h.click('start'); await h.click('refresh');
  return h;
}

test('mount is read-only and Chrome connection is an explicit, separate authorization step', async () => {
  let state = 'disconnected';
  const h = await setup({ get: async url => url.endsWith('/tabs') ? { tabs: [noteTab] } : status(state), post: async url => { assert.equal(url, '/existing-chrome/connect'); state = 'connecting'; return status(state); } });
  assert.deepEqual(h.calls.map(call => call.url), ['/existing-chrome/status']);
  assert.equal(h.find('start').disabled, true); assert.equal(h.find('connect').disabled, false);
  assert.match(h.panel.textContent, /chrome:\/\/inspect\/#remote-debugging/); assert.match(h.panel.textContent, /允许本次连接/);
  await h.click('connect'); assert.equal(h.find('connect').disabled, true); assert.equal(h.find('disconnect').disabled, false);
  assert.equal(h.calls.some(call => call.url.endsWith('/tabs')), false);
  state = 'connected'; await h.click('refresh');
  assert.equal(h.find('tab').querySelectorAll('option').length, 2);
  assert.equal(h.find('tab').value, 'note-tab', 'first eligible tab is auto-selected on connect/refresh');
  assert.equal(h.find('start').disabled, false);
  assert.equal(h.calls.filter(call => call.method === 'POST').length, 1);
});

test('authorization_required and unavailable describe connection authorization, never missing platform login', async () => {
  for (const initial of ['authorization_required', 'unavailable']) {
    const h = await setup({ initial });
    assert.match(h.find('connection').textContent, /连接授权/);
    assert.match(h.find('connection').textContent, /不表示平台账号未登录/);
    assert.equal(h.find('start').disabled, true); assert.equal(h.calls.length, 1);
  }
});

test('only domestic HTTPS XHS entry and note targets appear, and unsafe titles stay text', async () => {
  const badUrls = ['http://www.xiaohongshu.com/explore', 'https://www.xiaohongshu.com:443/explore', 'https://www.xiaohongshu.com.evil.invalid/explore', 'https://user@www.xiaohongshu.com/explore', 'https://www.xiaohongshu.com/user/profile/123', 'https://www.xiaohongshu.com/explore#fragment', 'https://www.rednote.com/explore', 'https://www.xiaohongshu.com/explore?q=a,b', 'https://www.xiaohongshu.com/explore\n'];
  const aiSearchTab = { id: 'ai-search', title: 'OFFLINE 小红书搜索', url: 'https://xiaohongshu.com/search_result_ai?keyword=OFFLINE' };
  const h = await setup({ tabList: [noteTab, homeTab, aiSearchTab, noteTab, ...badUrls.map((url, n) => ({ id: `bad${n}`, title: 'forbidden', url }))] });
  assert.equal(h.find('tab').querySelectorAll('option').length, 4);
  assert.equal(h.find('tab').querySelectorAll('script').length, 0);
  assert.match(h.find('tab').textContent, /<script>OFFLINE title<\/script>/);
  for (const url of badUrls) assert.equal(h.context.existingChromeTargetUrl(url), null, url);
  h.change('tab', 'home-tab'); assert.equal(h.find('start').disabled, true);
  h.change('tab', 'ai-search'); assert.equal(h.find('start').disabled, true, 'AI search is only a navigation target, never a current note');
  h.change('mode', 'search'); assert.equal(h.find('start').disabled, false);
});

test('current uses one selected note with 0 comments; search and detail send their own exact bounded requests', async () => {
  const h = await setup({ post: async () => task('failed', { error: { message: 'OFFLINE end' } }) });
  h.change('tab', 'note-tab'); h.change('comments', '0'); await h.click('start');
  assert.deepEqual(h.calls.find(call => call.method === 'POST').body, { tab_id: 'note-tab', mode: 'current', query: '', url: '', max_posts: 1, max_comments: 0 });
  h.change('mode', 'search'); h.change('posts', '8'); h.change('input', '工作流'); await h.click('start');
  assert.deepEqual(h.calls.filter(call => call.method === 'POST').at(-1).body, { tab_id: 'note-tab', mode: 'search', query: '工作流', url: '', max_posts: 8, max_comments: 0 });
  h.change('mode', 'detail'); h.change('input', noteUrl); h.change('comments', '15'); await h.click('start');
  assert.deepEqual(h.calls.filter(call => call.method === 'POST').at(-1).body, { tab_id: 'note-tab', mode: 'detail', query: '', url: noteUrl, max_posts: 1, max_comments: 15 });
  assert.equal(h.calls.some(call => call.url.endsWith('/results')), false);
});

test('invalid links, modes, keywords, comment bounds and missing tabs never start a task', async () => {
  const h = await setup();
  h.change('tab', ''); await h.click('start'); assert.match(h.find('error').textContent, /目标小红书标签/);
  h.change('tab', 'note-tab');
  for (const [mode, input, posts, comments, pattern] of [
    ['detail', 'https://www.xiaohongshu.com/explore', '1', '3', /笔记链接/],
    ['detail', 'https://www.rednote.com/explore/64abcdef0123456789abcdef', '1', '3', /笔记链接/],
    ['search', 'a,b', '5', '3', /关键词/],
    ['search', 'a\nb', '5', '3', /关键词/],
    ['search', '', '5', '3', /关键词/],
    ['search', '工作流', '21', '3', /1–20/],
    ['search', '工作流', '0', '3', /1–20/],
    ['current', '', '1', '51', /0–50/],
    ['current', '', '1', '-1', /0–50/],
    ['current', '', '1', '1.5', /0–50/],
    ['unknown', '', '1', '3', /采集方式/],
  ]) {
    h.change('mode', mode); h.change('input', input); h.change('posts', posts); h.change('comments', comments); await h.click('start');
    assert.match(h.find('error').textContent, pattern);
  }
  assert.equal(h.calls.some(call => call.method === 'POST'), false);
});

test('terminal preview preserves full original text, unknown identity, metadata and batch selection across refresh', async () => {
  const h = await previewSetup();
  assert.equal(h.calls.filter(call => call.method === 'POST').length, 1, 'no ingest or model call for preview');
  assert.equal(h.find('items').querySelectorAll('script').length, 0); assert.equal(h.find('items').querySelectorAll('img').length, 0);
  assert.equal(h.find('items-details').hidden, false); assert.notEqual(h.find('items-details').open, true);
  assert.equal(h.find('progress-wrap').hidden, false); assert.equal(h.find('progress-text').textContent, '100%');
  assert.ok(h.find('items').textContent.includes(item().text)); assert.ok(item().text.length > 512);
  assert.match(h.find('items').textContent, /平台 ID：未知/); assert.match(h.find('items').textContent, /不能直达评论/); assert.match(h.find('items').textContent, /发布时间：未知/);
  assert.match(h.find('status').textContent, /正文 1 篇，评论 1 条/); assert.match(h.find('status').textContent, /仅已加载/);
  h.click('all'); await h.click('refresh');
  assert.match(h.find('count').textContent, /已选 2 条/); assert.equal(h.calls.filter(call => call.url.endsWith('/results')).length, 1);
  h.click('none'); assert.equal(h.find('import').disabled, true);
  h.change('comments', '2'); assert.equal(h.find('items').textContent, ''); assert.equal(h.find('handoff').hidden, true);
});

test('selected import preserves provenance; duplicate IDs use actual readback, snapshots and a deliberate opportunity handoff', async () => {
  const duplicatedBody = [item(), { ...item('comment', 2), text: item().text }];
  const h = await previewSetup({
    result: { items: duplicatedBody },
    post: async url => { assert.equal(url, '/feedback/batch'); return { feedback_ids: ['existing', 'existing'], ingested: 0, duplicates: 2 }; },
    get: async url => url.endsWith('/source-snapshot') ? { feedback_id: 'existing', snapshot_verification: { status: 'verified' }, original: '<img>OFFLINE' } : stored('existing'),
  });
  h.click('all'); await h.click('import');
  assert.deepEqual(h.calls.find(call => call.url === '/feedback/batch').body, duplicatedBody);
  assert.equal(h.calls.filter(call => call.url === '/feedback/existing').length, 1);
  assert.match(h.find('receipt').textContent, /新增 0 条、重复 2 条/); assert.match(h.find('receipt').textContent, /1 个实际唯一 ID/);
  assert.equal(h.find('import').disabled, true); assert.equal(h.find('snapshots').querySelectorAll('button').length, 1);
  assert.deepEqual(h.session().selected, []);
  await h.find('snapshots').querySelector('button').onclick();
  assert.match(h.find('snapshots').textContent, /OFFLINE/); assert.equal(h.find('snapshots').querySelectorAll('img').length, 0);
  assert.equal(h.calls.filter(call => call.url.endsWith('/source-snapshot')).length, 1);
  vm.runInContext("opportunityDiscoverySession.selected = new Map([['old',{id:'old'}]]); opportunityDiscoverySession.result = {old:true};", h.context);
  await h.click('handoff');
  assert.equal(h.location.hash, 'opportunities'); assert.deepEqual(h.session().selected.map(([id]) => id), ['existing']);
  assert.equal(h.session().result, null); assert.equal(h.session().selected[0][1].text_preview, stored('existing').content.text);
});

test('readback failure retry performs reads only and refuses mismatched stored records', async () => {
  let fail = true;
  const h = await previewSetup({ post: async () => ({ feedback_ids: ['one'] }), get: async () => { if (fail) return stored('wrong'); return stored('one'); } });
  const check = h.find('items').querySelector('input'); check.checked = true; check.onchange();
  await h.click('import'); assert.match(h.find('error').textContent, /导入已完成，回读失败/);
  assert.equal(h.find('import').disabled, true); assert.equal(h.find('handoff').textContent, '重试读取本批材料');
  fail = false; await h.click('handoff'); assert.equal(h.location.hash, '#connectors');
  assert.equal(h.calls.filter(call => call.url === '/feedback/batch').length, 1);
  assert.match(h.find('receipt').textContent, /新增和重复数量未确认/);
  await h.click('handoff'); assert.deepEqual(h.session().selected.map(([id]) => id), ['one']);
});

test('running task is stoppable; failed and cancelled states never expose partial results', async () => {
  for (const terminal of ['failed', 'cancelled']) {
    const h = await setup({ post: async url => url.endsWith('/stop') ? task(terminal, { error: terminal === 'failed' ? { message: 'OFFLINE page closed' } : null }) : task() });
    h.change('tab', 'note-tab'); await h.click('start');
    assert.equal(h.find('mode').disabled, true); assert.equal(h.find('stop').disabled, false);
    await h.click('stop'); assert.equal(h.find('stop').disabled, true);
    assert.equal(h.find('items').textContent, ''); assert.equal(h.calls.some(call => call.url.endsWith('/results')), false);
    if (terminal === 'failed') assert.match(h.find('error').textContent, /page closed/);
  }
});

test('disconnect cancels only the tool task and clears target tabs without importing or reconnecting', async () => {
  const h = await setup({ post: async url => url.endsWith('/disconnect') ? status('disconnected') : task() });
  h.change('tab', 'note-tab'); await h.click('start'); await h.click('disconnect');
  assert.equal(h.find('start').disabled, true); assert.equal(h.find('stop').disabled, true);
  assert.match(h.find('status').textContent, /Chrome 和页面保持打开/);
  assert.deepEqual(h.calls.filter(call => call.method === 'POST').map(call => call.url), ['/existing-chrome/tasks', '/existing-chrome/disconnect']);
});

test('malformed and over-bound completed batches remain non-importable', async () => {
  for (const items of [Array.from({ length: 21 }, () => item()), Array.from({ length: 1001 }, (_, n) => item('comment', n)), [item('comment'), { ...item(), external_url: 'https://www.rednote.com/explore/64abcdef0123456789abcdef' }], [{ ...item(), capture_version: 'untrusted' }]]) {
    const h = await previewSetup({ result: { items } });
    assert.match(h.find('error').textContent, /结果格式或范围异常/); assert.equal(h.find('import').disabled, true);
    assert.equal(h.find('items').textContent, '');
  }
});

test('late start, preview and import replies cannot mutate a changed route, profile or detached panel', async () => {
  for (const boundary of ['route', 'profile', 'unmount']) {
    const later = deferred();
    const h = await setup({ post: () => later.promise }); h.change('tab', 'note-tab');
    const pending = h.click('start');
    if (boundary === 'route') h.location.hash = '#opportunities';
    if (boundary === 'profile') h.values.set('signalminer_profile', 'aigc_video');
    if (boundary === 'unmount') h.panel.mounted = false;
    later.resolve(task('completed')); await pending;
    assert.equal(h.calls.some(call => call.url.endsWith('/results')), false);
    assert.doesNotMatch(h.find('status').textContent, /采集完成/);
  }
  const later = deferred();
  const h = await previewSetup({ post: () => later.promise }); h.click('all');
  const importing = h.click('import'); h.location.hash = '#opportunities';
  vm.runInContext("opportunityDiscoverySession.selected = new Map([['new',{id:'new'}]]);", h.context);
  later.resolve({ feedback_ids: ['old', 'old'] }); await importing;
  assert.equal(h.find('snapshots').textContent, ''); assert.deepEqual(h.session().selected.map(([id]) => id), ['new']);
  assert.equal(h.calls.some(call => call.url === '/feedback/old'), false);
});

test('connection status errors fail closed and error objects display useful server messages', async () => {
  let broken = false;
  const h = await setup({ get: async url => { if (broken) throw new Error('OFFLINE transport failed'); return url.endsWith('/tabs') ? { tabs: [noteTab] } : status(); } });
  h.change('tab', 'note-tab'); assert.equal(h.find('start').disabled, false);
  broken = true; await h.click('refresh'); assert.equal(h.find('start').disabled, true); assert.match(h.find('error').textContent, /transport failed/);
  const context = vm.createContext({ URL, URLSearchParams, Blob, console, window: {}, document: { addEventListener() {} }, localStorage: { getItem() {} }, fetch: async () => ({ ok: false, status: 409, json: async () => ({ detail: { code: 'authorization_required', message: 'OFFLINE allow this Chrome connection' } }) }) });
  vm.runInContext(source, context);
  await assert.rejects(context.apiPost('/existing-chrome/connect', {}), /allow this Chrome connection/);
  await assert.rejects(context.apiGet('/existing-chrome/tabs'), /allow this Chrome connection/);
});

function controlledTimers() {
  let next = 0; const pending = new Map();
  return {
    pending,
    setTimeout: (callback, delay) => { assert.equal(delay, 1500); const id = ++next; pending.set(id, callback); return id; },
    clearTimeout: id => pending.delete(id),
    tick: async () => { const [id, callback] = pending.entries().next().value; pending.delete(id); await callback(); },
  };
}

test('explicit connect automatically refreshes connecting status without silently connecting on mount', async () => {
  const timers = controlledTimers(); let state = 'disconnected';
  const h = await setup({ timers, get: async url => url.endsWith('/tabs') ? { tabs: [noteTab] } : status(state), post: async () => { state = 'connecting'; return status(state); } });
  assert.equal(timers.pending.size, 0);
  await h.click('connect'); assert.equal(timers.pending.size, 1);
  state = 'connected'; await timers.tick();
  assert.match(h.find('connection').textContent, /已连接当前 Chrome/); assert.equal(timers.pending.size, 0);
  assert.equal(h.calls.filter(call => call.url === '/existing-chrome/connect').length, 1);
});

test('started task automatically reaches original preview and stops polling at terminal state', async () => {
  const timers = controlledTimers();
  const h = await setup({ timers, post: async () => task(), get: async url => {
    if (url.endsWith('/status')) return status();
    if (url.endsWith('/tabs')) return { tabs: [noteTab] };
    if (url.endsWith('/results')) return { items: [item()], summary: { coverage: 'OFFLINE automatic preview' } };
    return task('completed');
  } });
  h.change('tab', 'note-tab'); await h.click('start'); assert.equal(timers.pending.size, 1);
  await timers.tick(); assert.equal(timers.pending.size, 0);
  assert.ok(h.find('items').textContent.includes(item().text)); assert.match(h.find('status').textContent, /automatic preview/);
  assert.equal(h.calls.some(call => call.url === '/feedback/batch'), false);
});

test('route exit, disconnect and failed tasks cancel automatic refresh timers', async () => {
  for (const ending of ['route', 'disconnect', 'failed']) {
    const timers = controlledTimers();
    const h = await setup({ timers, post: async url => url.endsWith('/disconnect') ? status('disconnected') : task(), get: async url => url.endsWith('/status') ? status() : url.endsWith('/tabs') ? { tabs: [noteTab] } : task('failed') });
    h.change('tab', 'note-tab'); await h.click('start'); assert.equal(timers.pending.size, 1);
    if (ending === 'route') { h.location.hash = '#opportunities'; h.listeners.get('hashchange')(); }
    if (ending === 'disconnect') await h.click('disconnect');
    if (ending === 'failed') await timers.tick();
    assert.equal(timers.pending.size, 0, ending);
  }
});

test('automatic polling is bounded for both pending authorization and running tasks', async () => {
  for (const [kind, budget] of [['connect', 40], ['task', 85]]) {
    const timers = controlledTimers(); let state = kind === 'connect' ? 'disconnected' : 'connected';
    const h = await setup({ timers, post: async () => { if (kind === 'connect') { state = 'connecting'; return status(state); } return task(); }, get: async url => url.endsWith('/status') ? status(state) : url.endsWith('/tabs') ? { tabs: [noteTab] } : task() });
    if (kind === 'connect') await h.click('connect');
    else { h.change('tab', 'note-tab'); await h.click('start'); }
    for (let n = 0; n < budget; n += 1) { assert.equal(timers.pending.size, 1); await timers.tick(); }
    assert.equal(timers.pending.size, 0); assert.match(h.find('status').textContent, /自动刷新已达到本次上限/);
    assert.equal(h.find('refresh').disabled, false);
  }
});

test('stored original and source must correspond to every returned batch ID; access-token rotation remains compatible', async () => {
  for (const mismatch of ['text', 'source', 'duplicate-id']) {
    const h = await previewSetup({
      post: async () => ({ feedback_ids: mismatch === 'duplicate-id' ? ['one', 'one'] : ['one'] }),
      get: async () => ({ ...stored('one'), ...(mismatch === 'text' ? { content: { text: 'WRONG original' } } : {}), ...(mismatch === 'source' ? { external_url: 'https://www.xiaohongshu.com/explore/74abcdef0123456789abcdef' } : {}) }),
    });
    if (mismatch === 'duplicate-id') h.click('all');
    else { const check = h.find('items').querySelector('input'); check.checked = true; check.onchange(); }
    await h.click('import'); assert.match(h.find('error').textContent, /已存原文或来源与所选材料不一致/);
    assert.equal(h.find('snapshots').textContent, ''); assert.deepEqual(h.session().selected, []);
  }
  const h = await previewSetup({ post: async () => ({ feedback_ids: ['one'], ingested: 0, duplicates: 1 }), get: async () => ({ ...stored('one'), external_url: noteUrl.replace('OFFLINE', 'ROTATED') }) });
  const check = h.find('items').querySelector('input'); check.checked = true; check.onchange(); await h.click('import');
  assert.equal(h.find('error').textContent, ''); assert.match(h.find('receipt').textContent, /重复 1 条/);
});
