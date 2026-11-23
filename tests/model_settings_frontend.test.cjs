// Offline SPA test for the Model Settings (#settings) page.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../frontend/static/app.js'), 'utf8');

class Node {
  constructor(tag = 'div', id = '') {
    this.tagName = tag.toUpperCase();
    this.id = id;
    this.children = [];
    this.attributes = id ? { id } : {};
    this._text = '';
    this._value = undefined;
    this.disabled = false;
    this.style = {};
    this.classList = { add() {}, remove() {}, toggle() {} };
  }
  get isConnected() { return true; }
  appendChild(c) { c.parent = this; this.children.push(c); return c; }
  append(...cs) { cs.forEach(c => this.appendChild(c)); }
  set textContent(v) { this._text = String(v ?? ''); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  set value(v) { this._value = String(v); }
  get value() {
    if (this._value !== undefined) return this._value;
    if (this.tagName === 'SELECT') return this.children.find(c => c.attributes?.selected !== undefined)?.attributes.value ?? this.children[0]?.attributes?.value ?? '';
    return '';
  }
  set innerHTML(html) {
    this._text = ''; this.children = [];
    const stack = [this];
    for (const token of String(html).match(/<[^>]+>|[^<]+/g) || []) {
      if (token.startsWith('</')) { stack.pop(); continue; }
      if (token.startsWith('<')) {
        const tag = /^<([a-z0-9-]+)/i.exec(token)?.[1];
        if (!tag) continue;
        const child = new Node(tag);
        const attrs = token.slice(tag.length + 1, -1);
        for (const match of attrs.matchAll(/([\w-]+)(?:="([^"]*)")?/g)) child.attributes[match[1]] = match[2] ?? '';
        child.id = child.attributes.id || '';
        if (Object.hasOwn(child.attributes, 'value')) child._value = child.attributes.value;
        stack.at(-1).appendChild(child);
        if (!['input', 'br', 'hr'].includes(tag.toLowerCase())) stack.push(child);
      } else {
        const t = new Node('#text'); t._text = token; stack.at(-1).appendChild(t);
      }
    }
  }
  querySelector(sel) {
    if (sel.startsWith('#')) {
      const target = sel.slice(1);
      if (this.id === target) return this;
      for (const c of this.children) { const hit = c.querySelector(sel); if (hit) return hit; }
    }
    return null;
  }
}

test('model settings page loads masked state, switches embedding preset, saves and tests', async () => {
  const container = new Node('div', 'page-body');
  const calls = [];
  const context = vm.createContext({
    URL, URLSearchParams, Blob, console, location: { hash: '#settings' }, setTimeout: () => {},
    window: {}, localStorage: { getItem: () => 'product_feedback', setItem() {} },
    document: { createElement: tag => new Node(tag), getElementById: id => container.querySelector(`#${id}`), addEventListener() {} },
    fetch: async (url, opts) => {
      const method = opts?.method || 'GET';
      calls.push({ method, url, body: opts?.body ? JSON.parse(opts.body) : null });
      if (url.endsWith('/llm/settings') && method === 'GET') {
        return {
          ok: true, status: 200,
          json: async () => ({
            primary: { provider: 'deepseek', model: 'deepseek-flash', openai_base_url: '', minimax_group_id: '', providers: { deepseek: { model: 'deepseek-flash', api_key_configured: true, api_key_masked: 'sk-4****c407' }, qwen: { model: 'qwen-max', api_key_configured: false, api_key_masked: '' } } },
            multimodal: { provider: '', model: '' },
            embedding: { provider: 'auto', model: 'BAAI/bge-small-zh-v1.5', local_model: 'BAAI/bge-small-zh-v1.5', base_url: '', api_key_configured: false, api_key_masked: '', fastembed_available: true },
            presets: {
              primary: { deepseek: { label: 'DeepSeek', default_model: 'deepseek-flash' }, qwen: { label: '通义千问', default_model: 'qwen-max' } },
              embedding: { local: { label: '本机免费', default_model: 'BAAI/bge-small-zh-v1.5', base_url: '' }, siliconflow: { label: '硅基流动', default_model: 'BAAI/bge-m3', base_url: 'https://api.siliconflow.cn/v1' } },
            },
          }),
        };
      }
      if (url.endsWith('/llm/settings') && method === 'POST') {
        return { ok: true, status: 200, json: async () => ({ capabilities: { primary: { provider: 'deepseek', model: 'deepseek-flash' }, embedding: { enabled: true, provider: 'siliconflow', model: 'BAAI/bge-m3' } } }) };
      }
      if (url.endsWith('/llm/test')) {
        return { ok: true, status: 200, json: async () => ({ ok: true, provider: 'siliconflow', model: 'BAAI/bge-m3', dimensions: 1024, latency_ms: 42 }) };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    },
  });
  vm.runInContext(source, context);
  context.buildSidebar = () => {};
  context.showToast = () => {};
  await context.renderModelSettingsPage(container);

  assert.match(container.querySelector('#ms-primary-key-status').textContent, /sk-4\*\*\*\*c407/);
  container.querySelector('#ms-emb-provider').value = 'siliconflow';
  container.querySelector('#ms-emb-provider').onchange();
  assert.equal(container.querySelector('#ms-emb-model').value, 'BAAI/bge-m3');
  assert.equal(container.querySelector('#ms-emb-url').value, 'https://api.siliconflow.cn/v1');

  container.querySelector('#ms-emb-key').value = 'sf-test-key';
  await container.querySelector('#ms-save').onclick();
  const postCall = calls.find(c => c.url.endsWith('/llm/settings') && c.method === 'POST');
  assert.equal(postCall.body.embedding_provider, 'siliconflow');
  assert.equal(postCall.body.embedding_api_key, 'sf-test-key');
  assert.match(container.querySelector('#ms-status').textContent, /已保存并立即生效/);

  await container.querySelector('#ms-test-emb').onclick();
  assert.match(container.querySelector('#ms-status').textContent, /向量维度 1024/);
});
