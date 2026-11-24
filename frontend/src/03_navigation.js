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

