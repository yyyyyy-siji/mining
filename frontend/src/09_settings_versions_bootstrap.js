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
