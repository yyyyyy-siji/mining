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

const flush = () => new Promise(resolve => setImmediate(resolve));
const plainValue = value => JSON.parse(JSON.stringify(value));
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { resolve, promise }; };
const sample = n => ({ source_type: 'xiaohongshu', platform: 'xiaohongshu', pipeline_profile: 'product_feedback', capture_method: 'crawler', content_nature: 'original_text', text_origin: 'body', entity_type: n === 1 ? 'post' : 'comment', locator_level: n === 1 ? 'item' : 'parent_page', external_id: String(n), external_url: `https://www.xiaohongshu.com/explore/64abcdef0123456789abcdef?xsec_token=access${n}`, subject: `<script>Title${n}</script>`, text: `<img src=x onerror=alert(1)>Original${n}`, raw_payload: { record: { preserved: n } }, coverage_scope: 'OFFLINE只测试映射' });
const stored = id => ({ id, pipeline_profile: 'product_feedback', external_url: `https://m.weibo.cn/detail/${id}`, content: { text: `已存正文${id}`, subject: `已存${id}` }, context: { capture_method: 'crawler' } });
const currentTask = (status = 'running') => ({ id: 'task1', platform: 'xhs', status, terminal: ['completed', 'empty', 'failed', 'cancelled'].includes(status), message: `任务${status}` });

async function setup({ get, post, ready = true } = {}) {
  const panel = new Element(); panel.mounted = true;
  const location = { hash: '#connectors' }; const calls = []; const values = new Map([['signalminer_profile', 'product_feedback']]);
  const context = vm.createContext({ URL, Blob, console, location, window: {}, setTimeout: () => {},
    localStorage: { getItem: k => values.get(k), setItem: (k, v) => values.set(k, v) },
    document: { createElement: tag => new Element(tag), addEventListener() {} },
    __get: async url => { calls.push({ method: 'GET', url }); if (url === '/mediacrawler/status') return get ? get(url) : { ready, message: ready ? '就绪，未验证平台' : '未安装', active_task: null }; return get(url); },
    __post: async (url, body) => { calls.push({ method: 'POST', url, body: plainValue(body) }); return post(url, body); },
  });
  vm.runInContext(source, context); vm.runInContext('apiGet=__get; apiPost=__post', context);
  context.renderLocalCollectionPanel(panel); await flush();
  const find = name => panel.querySelector(`[data-local="${name}"]`);
  const change = (name, value) => { find(name).value = value; find(name).oninput(); };
  const click = name => find(name).onclick();
  const session = () => plainValue(vm.runInContext('[...opportunityDiscoverySession.selected.entries()]', context));
  return { panel, location, calls, context, find, change, click, session };
}

test('initial status only; never opens platform or imports on mount, and missing install is honest', async () => {
  const h = await setup({ ready: false });
  assert.equal(h.calls.length, 1); assert.equal(h.calls[0].url, '/mediacrawler/status');
  assert.equal(h.find('start').disabled, true); assert.match(h.find('environment').textContent, /未安装/);
  assert.match(h.panel.textContent, /普通 Chrome.*不会自动共享/); assert.match(h.panel.textContent, /离开页面不会自动停止/);
  assert.equal(h.find('platform').value, 'xhs'); assert.equal(h.find('posts').value, '3');
  assert.equal(h.find('handoff').hidden, true);
});

test('explicit start, terminal read-only preview, selected import, unique actual IDs, snapshots and handoff', async () => {
  const h = await setup({
    get: async url => url === '/mediacrawler/status' ? { ready: true, message: '就绪', active_task: null } : url.endsWith('/results') ? { items: [sample(1), sample(2), sample(3)], summary: { posts: 1, comments: 2, search_page_objects: 20, selected_objects: 3 } } : url.startsWith('/mediacrawler/tasks/') ? currentTask('completed') : stored(url.split('/').at(-1)),
    post: async url => url === '/mediacrawler/tasks' ? currentTask() : { feedback_ids: ['old', 'old', 'new'] },
  });
  h.change('input', '工作流'); await h.click('start');
  assert.deepEqual(h.calls.find(c => c.method === 'POST').body, { platform: 'xhs', mode: 'search', query: '工作流', url: '', max_posts: 3, max_comments: 8 });
  assert.equal(h.find('platform').disabled, true); assert.equal(h.find('stop').disabled, false);
  await h.click('refresh');
  assert.equal(h.calls.filter(c => c.method === 'POST').length, 1, 'preview does not import/model');
  assert.match(h.find('status').textContent, /搜索页返回 20.*3 个进入/);
  assert.equal(h.find('items').querySelectorAll('script').length, 0); assert.equal(h.find('items').querySelectorAll('img').length, 0);
  assert.match(h.find('items').textContent, /仅定位父页/); assert.match(h.find('items').textContent, /发布时间：未知/);
  h.click('all'); await h.click('import');
  assert.deepEqual(h.calls.find(c => c.url === '/feedback/batch').body, [sample(1), sample(2), sample(3)]);
  assert.deepEqual(h.calls.filter(c => c.url.startsWith('/feedback/')).map(c => c.url), ['/feedback/batch', '/feedback/old', '/feedback/new']);
  assert.match(h.find('receipt').textContent, /已处理 3 条.*2 个实际唯一ID/); assert.doesNotMatch(h.find('receipt').textContent, /全部新增/);
  assert.equal(h.find('snapshots').querySelectorAll('button').length, 2);
  assert.deepEqual(h.session(), []); await h.click('handoff');
  assert.equal(h.location.hash, 'opportunities'); assert.deepEqual(h.session().map(pair => pair[0]), ['old', 'new']);
  assert.equal(h.session()[0][1].source_url, 'https://m.weibo.cn/detail/old');
});

test('readback failure retries read only; stop and failures do not expose partial results', async () => {
  let failRead = true;
  const h = await setup({ get: async url => {
    if (url === '/mediacrawler/status') return { ready: true, active_task: null };
    if (url.endsWith('/results')) return { items: [sample(1)] };
    if (url.startsWith('/mediacrawler/tasks/')) return currentTask('completed');
    if (failRead) throw new Error('temporary'); return stored('one');
  }, post: async url => url === '/mediacrawler/tasks' ? currentTask() : { feedback_ids: ['one'] } });
  h.change('input', '需求'); await h.click('start'); await h.click('refresh'); h.click('all'); await h.click('import');
  assert.match(h.find('error').textContent, /回读失败/); assert.equal(h.find('import').disabled, true);
  failRead = false; await h.click('handoff');
  assert.equal(h.calls.filter(c => c.url === '/feedback/batch').length, 1); assert.equal(h.location.hash, '#connectors');
  await h.click('handoff'); assert.equal(h.session().length, 1);
  const stopped = await setup({ post: async url => url.endsWith('/stop') ? currentTask('cancelled') : currentTask() });
  stopped.change('input', '需求'); await stopped.click('start'); await stopped.click('stop');
  assert.match(stopped.find('status').textContent, /cancelled/); assert.equal(stopped.find('items').textContent, '');
});

test('mode bounds and route changes suppress late results; failed tasks are not completed', async () => {
  const later = deferred();
  const h = await setup({ post: async () => later.promise });
  h.change('mode', 'detail'); h.change('input', 'https://www.bilibili.com/video/av123'); h.change('platform', 'bili');
  assert.match(h.find('coverage').textContent, /不是口播/); assert.equal(h.find('posts').disabled, true);
  const pending = h.click('start'); h.location.hash = '#opportunities'; later.resolve(currentTask()); await pending;
  assert.doesNotMatch(h.find('status').textContent, /任务running/, 'detached route cannot receive task status');
  assert.equal(h.calls.find(c => c.method === 'POST').body.max_posts, 1);
  const failed = await setup({ get: async url => url === '/mediacrawler/status' ? { ready: true, active_task: currentTask('failed') } : currentTask('failed') });
  assert.match(failed.find('status').textContent, /failed/); assert.equal(failed.calls.some(c => c.url.endsWith('/results')), false);
});

