// Offline tests verifying pipeline status persists when navigating across modules.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../frontend/static/app.js'), 'utf8');

class DOMNode {
  constructor(tag = 'div', id = '') {
    this.tagName = tag.toUpperCase();
    this.id = id;
    this.children = [];
    this.attributes = id ? { id } : {};
    this._text = '';
    this.dataset = {};
    this.style = {};
    this.hidden = false;
    this.className = '';
    this.classList = {
      add: (...cls) => { this.className = [...new Set([...this.className.split(/\s+/).filter(Boolean), ...cls])].join(' '); },
      remove: (...cls) => { this.className = this.className.split(/\s+/).filter(Boolean).filter(c => !cls.includes(c)).join(' '); },
      toggle: (cls, force) => { if (force) this.classList.add(cls); else this.classList.remove(cls); },
    };
  }
  get isConnected() { return true; }
  appendChild(child) { child.parent = this; this.children.push(child); return child; }
  append(...children) { children.forEach(c => { if (typeof c === 'string') { const t = new DOMNode('#text'); t._text = c; this.appendChild(t); } else this.appendChild(c); }); }
  set textContent(v) { this._text = String(v ?? ''); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  set innerHTML(html) {
    this._text = ''; this.children = [];
    const stack = [this];
    for (const token of String(html).match(/<[^>]+>|[^<]+/g) || []) {
      if (token.startsWith('</')) { stack.pop(); continue; }
      if (token.startsWith('<')) {
        const tag = /^<([a-z0-9-]+)/i.exec(token)?.[1];
        if (!tag) continue;
        const child = new DOMNode(tag);
        const attrs = token.slice(tag.length + 1, -1);
        for (const match of attrs.matchAll(/([\w-]+)(?:="([^"]*)")?/g)) child.attributes[match[1]] = match[2] ?? '';
        child.id = child.attributes.id || '';
        child.className = child.attributes.class || '';
        child.hidden = Object.hasOwn(child.attributes, 'hidden');
        stack.at(-1).appendChild(child);
        if (!['input', 'br', 'hr'].includes(tag.toLowerCase())) stack.push(child);
      } else {
        const text = new DOMNode('#text'); text._text = token; stack.at(-1).appendChild(text);
      }
    }
  }
  get innerHTML() { return this.textContent; }
  _byId(id) {
    if (this.id === id) return this;
    for (const c of this.children) { const hit = c._byId(id); if (hit) return hit; }
    return null;
  }
  querySelector(selector) {
    if (selector.startsWith('#')) return this._byId(selector.slice(1));
    if (selector.startsWith('.')) {
      const cls = selector.slice(1);
      if (this.className.split(/\s+/).includes(cls)) return this;
    }
    for (const c of this.children) { const hit = c.querySelector(selector); if (hit) return hit; }
    return null;
  }
}

test('pipeline run progress persists across route switches and restores on return', async () => {
  const root = new DOMNode('body', 'root');
  const nav = new DOMNode('nav', 'sidebar-nav');
  const content = new DOMNode('main', 'content-area');
  const toasts = new DOMNode('div', 'toast-container');
  root.append(nav, content, toasts);
  const location = { hash: '#pipeline' };
  const store = new Map([['signalminer_profile', 'product_feedback']]);
  const eventSources = [];

  class FakeEventSource {
    constructor(url) { this.url = url; eventSources.push(this); }
    close() { this.closed = true; }
  }

  const context = vm.createContext({
    URL, URLSearchParams, Blob, console, location, setTimeout: () => {},
    EventSource: FakeEventSource,
    window: { addEventListener() {}, removeEventListener() {} },
    document: {
      title: '',
      createElement: tag => new DOMNode(tag),
      createTextNode: text => { const n = new DOMNode('#text'); n._text = text; return n; },
      getElementById: id => root._byId(id),
      addEventListener() {},
    },
    localStorage: { getItem: k => store.get(k), setItem: (k, v) => store.set(k, v) },
    fetch: async (url, opts) => {
      if (url.includes('/pipeline/run') && opts?.method === 'POST') {
        return { ok: true, status: 202, json: async () => ({ run_id: 'run_persist_1', feedback_count: 2, profile: 'product_feedback' }) };
      }
      if (url.includes('/pipeline/runs')) {
        return { ok: true, status: 200, json: async () => ({ runs: [] }) };
      }
      if (url.includes('/llm/capabilities')) {
        return {
          ok: true, status: 200,
          json: async () => ({
            primary: { provider: 'deepseek', model: 'deepseek-flash', input_modalities: ['text', 'image'], supports_embedding: false, supports_multimodal: true },
            multimodal: { enabled: true, provider: 'deepseek', model: 'deepseek-flash', input_modalities: ['text', 'image'], supports_embedding: false, supports_multimodal: true },
          }),
        };
      }
      if (url.includes('/feedback')) {
        return { ok: true, status: 200, json: async () => ([]) };
      }
      return { ok: true, status: 200, json: async () => ({ feedback_ids: [], items: [], connectors: [] }) };
    },
  });
  vm.runInContext(source, context);
  context.renderPipelinePage(content);
  context.buildSidebar();
  await new Promise(r => setImmediate(r));

  // Start pipeline
  await root._byId('btn-run-pipeline').onclick();
  assert.equal(eventSources.length, 1);
  assert.equal(root._byId('pipeline-progress-card').style.display, 'block');

  // Switch away to feedback page mid-run
  location.hash = '#feedback';
  context.navigate();
  await new Promise(r => setImmediate(r));
  eventSources[0].onmessage({ data: JSON.stringify({ step: 'extraction', status: 'completed', progress: 0.35, message: '提取 5 条信号' }) });

  // Persistent banner and sidebar badge must stay visible on the other route!
  const banner = root._byId('global-pipeline-banner');
  assert.equal(banner.hidden, false);
  assert.match(banner.textContent, /35%/);
  assert.match(banner.textContent, /提取 5 条信号/);
  const badge = root._byId('sidebar-pipeline-badge');
  assert.equal(badge.hidden, false);
  assert.match(badge.textContent, /35%/);

  // Also check sidebar LLM capabilities render DeepSeek multimodal!
  assert.match(nav.textContent, /deepseek-flash/);
  assert.match(nav.textContent, /多模态 ✓/);

  // Switch back to pipeline page -> progress bar, steps, and stop button must be restored!
  location.hash = '#pipeline';
  context.navigate();
  assert.equal(root._byId('global-pipeline-banner').hidden, true);
  assert.equal(root._byId('pipeline-progress-card').style.display, 'block');
  assert.equal(root._byId('progress-pct').textContent, '35%');
  assert.equal(root._byId('step-extraction').querySelector('.step-icon').textContent, '✅');
  assert.equal(root._byId('btn-stop-pipeline').style.display, 'inline-flex');

  // Terminal 'completed' event marks all remaining un-emitted steps (quality_gate, opportunity, requirement) as completed
  context.applyPipelineEvent('run_test_1', {
    run_id: 'run_test_1',
    profile: 'product_feedback',
    step: 'complete',
    status: 'completed',
    progress: 1,
    message: 'Done',
  });
  assert.equal(root._byId('step-quality_gate').querySelector('.step-icon').textContent, '✅');
  assert.equal(root._byId('step-opportunity').querySelector('.step-icon').textContent, '✅');
  assert.equal(root._byId('step-requirement').querySelector('.step-icon').textContent, '✅');
});
