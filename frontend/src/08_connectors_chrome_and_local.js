function existingChromePlatform(value) {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:') return null;
    const host = url.hostname.toLowerCase();
    if (host === 'xiaohongshu.com' || host === 'www.xiaohongshu.com') return 'xiaohongshu';
    if (host === 'bilibili.com' || host === 'www.bilibili.com' || host === 'search.bilibili.com') return 'bilibili';
    if (host === 'weibo.com' || host === 'www.weibo.com' || host === 's.weibo.com') return 'weibo';
    if (host === 'zhihu.com' || host === 'www.zhihu.com' || host === 'zhuanlan.zhihu.com') return 'zhihu';
    if (host === 'douyin.com' || host === 'www.douyin.com') return 'douyin';
    return null;
  } catch { return null; }
}

function existingChromeTargetUrl(value, noteOnly = false) {
  if (typeof value !== 'string' || /[\u0000-\u0020\u007f,#]/.test(value)) return null;
  if (!/^https:\/\/[^/:?#]+(?:\/|\?|$)/i.test(value)) return null;
  const platform = existingChromePlatform(value);
  if (!platform) return null;
  try {
    const url = new URL(value);
    if (url.username || url.password || url.port || url.hash) return null;
    if (platform === 'xiaohongshu') {
      const note = /^\/(?:explore|discovery\/item)\/[a-f0-9]{24}\/?$/i.test(url.pathname);
      const entry = /^\/(?:explore\/?|search_result(?:_ai)?\/?)?$/.test(url.pathname);
      return (note || (!noteOnly && entry)) ? url.href : null;
    }
    if (platform === 'bilibili') {
      const note = /^\/video\/(?:BV[A-Za-z0-9]+|av[0-9]+)\/?$/.test(url.pathname);
      const entry = /^\/(?:all\/?)?$/.test(url.pathname);
      return (note || (!noteOnly && entry)) ? url.href : null;
    }
    if (platform === 'weibo') {
      const note = /^\/(?:[0-9]+\/[A-Za-z0-9]+|detail\/[0-9]+)\/?$/.test(url.pathname);
      const entry = /^\/(?:weibo\/?|hot(?:\/.*)?|newlogin\/?|mygroups\/?|top\/summary\/?|realtime\/?|u\/[0-9]+\/?)?$/.test(url.pathname);
      return (note || (!noteOnly && entry)) ? url.href : null;
    }
    if (platform === 'zhihu') {
      const note = /^\/(?:question\/[0-9]+(?:\/answer\/[0-9]+)?|p\/[0-9]+)\/?$/.test(url.pathname);
      const entry = /^\/(?:search\/?|hot\/?|follow\/?|explore\/?|waiting\/?|knowledge-plan\/?|topic\/.*|column\/.*|people\/.*)?$/.test(url.pathname);
      return (note || (!noteOnly && entry)) ? url.href : null;
    }
    if (platform === 'douyin') {
      const note = /^\/(?:video|note)\/[0-9]{10,25}\/?$/.test(url.pathname);
      const entry = /^\/(?:discover\/?|jingxuan(?:\/.*)?|follow\/?|friend\/?|hot\/?|channel(?:\/.*)?|search\/.*|user\/.*)?$/.test(url.pathname);
      return (note || (!noteOnly && entry)) ? url.href : null;
    }
    return null;
  } catch { return null; }
}

function existingChromeSourceIdentity(value) {
  const safe = existingChromeTargetUrl(value, true);
  if (!safe) return null;
  const url = new URL(safe);
  // Access signatures may rotate between two captures of the same XHS note.
  for (const key of [...url.searchParams.keys()]) {
    if (['xsec_token', 'xsec_source'].includes(key.toLowerCase()) || key.toLowerCase().startsWith('utm_')) url.searchParams.delete(key);
  }
  return url.href;
}

function renderExistingChromePanel(panel) {
  let revision = 0, busy = false, connection = 'disconnected', task = null, batch = null;
  let tabs = [], items = [], selected = new Set(), imported = null, loadedTaskId = null, resultSummary = null;
  let checkedTabIds = new Set(), platformFilter = 'all';
  let pollTimer = null, pollsRemaining = 0, pollListening = false;
  const panelProfile = getSelectedProfile();
  const active = () => panel.isConnected && getSelectedProfile() === panelProfile && getRoute() === 'connectors';
  const running = () => task?.status === 'running' || batch?.status === 'running';
  const platformLabelMap = { xiaohongshu: '小红书', bilibili: 'B站', weibo: '微博', zhihu: '知乎', douyin: '抖音' };
  const labels = { disconnected: '未连接', connecting: '正在请求 Chrome 连接授权', connected: '已连接当前 Chrome 会话', authorization_required: '需要 Chrome 连接授权', unavailable: 'Chrome 连接暂不可用' };
  panel.innerHTML = `
    <h2 class="section-title">使用已登录 Chrome</h2>
    <p class="discovery-hint">读取你已经打开的普通 Chrome 会话。页面不会自动连接；点击「连接当前 Chrome」后，Chrome 会要求你允许本次连接。</p>
    <details class="source-import-fields"><summary>首次连接准备（Chrome 144 及以上）</summary><p class="discovery-hint">在已有 Chrome 打开 <code>chrome://inspect/#remote-debugging</code>，开启远程调试；返回这里点击连接，并在 Chrome 弹窗中允许本次连接。你已登录的平台会话可以继续使用，连接授权与平台登录是两件事。</p><p class="discovery-hint">支持国内小红书、B站、微博、知乎和抖音首页、搜索与详情标签。选中标签后，关键词搜索和指定链接会在该标签中导航；断开只取消本工具任务并断开连接，保留 Chrome 和页面。</p></details>
    <p class="discovery-hint" data-chrome="connection" aria-live="polite">正在读取本地连接状态…</p>
    <div class="discovery-toolbar"><button class="btn btn-primary" data-chrome="connect" type="button">连接当前 Chrome</button><button class="btn btn-secondary" data-chrome="disconnect" type="button">断开连接</button><button class="btn btn-secondary" data-chrome="refresh" type="button">刷新连接 / 任务</button></div>
    <div class="community-controls">
      <label class="form-label community-query">目标平台标签（单平台采集）<select class="form-select" data-chrome="tab"><option value="">请先连接，再选择标签</option></select></label>
      <label class="form-label">采集方式<select class="form-select" data-chrome="mode"><option value="current">当前笔记</option><option value="search">关键词搜索</option><option value="detail">指定笔记链接</option></select></label>
      <label class="form-label community-query" data-chrome="input-label">关键词或单个笔记链接<input class="form-input" data-chrome="input" maxlength="2000"></label>
      <label class="form-label" data-chrome="posts-label">采集篇数<input class="form-input" data-chrome="posts" type="number" min="1" max="20" value="5"></label>
      <label class="form-label">每篇评论数<input class="form-input" data-chrome="comments" type="number" min="0" max="50" value="10"></label>
    </div>
    <div class="multi-platform-box" data-chrome="multi-tabs-wrap" hidden>
      <div class="discovery-toolbar" style="margin:0 0 8px">
        <strong style="font-size:13px">🔀 多平台同时采集（勾选多个已打开标签，受控并发执行）</strong>
        <button class="btn btn-secondary btn-sm" data-chrome="select-all-platforms" type="button">全选各平台首个标签</button>
        <button class="btn btn-secondary btn-sm" data-chrome="clear-multi-tabs" type="button">清空多选</button>
      </div>
      <div class="multi-tab-grid" data-chrome="multi-tabs"></div>
    </div>
    <p class="discovery-hint" data-chrome="coverage"></p>
    <div class="discovery-toolbar">
      <button class="btn btn-primary" data-chrome="start" type="button">开始本次采集</button>
      <button class="btn btn-primary" data-chrome="batch-start" type="button" hidden>🚀 多平台同时采集</button>
      <button class="btn btn-secondary" data-chrome="stop" type="button">停止本任务</button>
    </div>
    <p class="discovery-hint" data-chrome="status" aria-live="polite">尚未启动采集。</p>
    <div data-chrome="progress-wrap" hidden>
      <div class="progress-bar-container"><div class="progress-bar-fill" data-chrome="progress-fill" style="width:0%"><span class="progress-text" data-chrome="progress-text">0%</span></div></div>
      <p class="discovery-hint" data-chrome="progress-label"></p>
    </div>
    <div class="batch-subtasks-grid" data-chrome="batch-subtasks" hidden></div>
    <p class="discovery-error" data-chrome="error" role="alert"></p>
    <p class="discovery-hint">关键词搜索每次最多 20 篇正文，每篇 0–50 条当前已加载评论，总时限 300 秒。只读取可见正文区域，不含图片文字或媒体（B站自动读取字幕）；完整性以每条采集范围为准。预览不入库、不调用模型。连接请求和任务开始后会自动刷新，也可手动刷新；离开页面停止自动刷新，后台任务须点击停止或断开取消。</p>
    <div class="platform-filter-bar" data-chrome="platform-filters" hidden></div>
    <details class="source-import-fields" data-chrome="items-details" hidden><summary data-chrome="items-summary">展开查看已采集材料</summary><div data-chrome="items"></div></details>
    <div class="discovery-toolbar">
      <span class="discovery-hint" data-chrome="count"></span>
      <label class="form-label" style="display:inline-flex;align-items:center;gap:6px;margin:0">
        <span>导入到版本</span>
        <select class="form-select" data-chrome="target-version" style="width:auto;min-width:160px;padding:6px 10px;font-size:13px"></select>
      </label>
      <button class="btn btn-secondary btn-sm" data-chrome="new-version" type="button">+ 新建版本</button>
      <button class="btn btn-secondary" data-chrome="all" type="button">全选</button>
      <button class="btn btn-secondary" data-chrome="none" type="button">取消全选</button>
      <button class="btn btn-primary" data-chrome="import" type="button">导入所选材料</button>
    </div>
    <p class="discovery-hint" data-chrome="receipt"></p><div data-chrome="snapshots"></div>
    <p class="discovery-hint" data-chrome="handoff-note" hidden>继续将替换机会页已有选择与结果；请先导出需要保留的清单。在机会页手动点击「发现机会」。来源快照核对不代表市场需求成立。</p>
    <button class="btn btn-primary" data-chrome="handoff" type="button" hidden>用本批材料发现机会</button>`;
  const find = name => panel.querySelector(`[data-chrome="${name}"]`);
  const text = (parent, tag, value, cls = '') => { const el = document.createElement(tag); el.textContent = String(value ?? ''); el.className = cls; parent.appendChild(el); return el; };
  const fields = ['tab', 'mode', 'input', 'posts', 'comments'];
  populateVersionSelect(find('target-version'), getEffectiveWriteVersion(), false);
  if (find('new-version')) {
    find('new-version').onclick = async () => {
      const name = typeof prompt === 'function' ? prompt('请输入新版本名称（如：v2-多平台调研）：') : '';
      if (!name || !name.trim()) return;
      try {
        const created = await apiPost('/versions', { name: name.trim(), description: '' });
        setSelectedVersion(created.id);
        await refreshVersionsCache();
        populateVersionSelect(find('target-version'), created.id, false);
        showToast(`已新建版本「${created.name}」并设为导入目标`, 'success');
      } catch (e) { showToast(`新建版本失败：${e.message}`, 'danger'); }
    };
  }
  function clearPolling() {
    if (pollTimer != null && typeof clearTimeout === 'function') clearTimeout(pollTimer);
    pollTimer = null;
    if (pollListening) { window.removeEventListener?.('hashchange', checkPollingPage); pollListening = false; }
  }
  function checkPollingPage() { if (!active()) clearPolling(); }
  function schedulePolling() {
    if (!active() || (connection !== 'connecting' && !running())) { clearPolling(); return; }
    if (busy || pollTimer != null || pollsRemaining <= 0 || typeof setTimeout !== 'function') return;
    if (!pollListening && typeof window.addEventListener === 'function') { window.addEventListener('hashchange', checkPollingPage); pollListening = true; }
    pollTimer = setTimeout(async () => {
      pollTimer = null;
      if (!active()) { clearPolling(); return; }
      if (busy) { schedulePolling(); return; }
      pollsRemaining -= 1;
      await refresh();
      if (active() && !pollsRemaining && (connection === 'connecting' || running())) {
        clearPolling(); text(find('status'), 'span', ' 自动刷新已达到本次上限；可手动刷新查看状态。');
      }
    }, 1500);
  }
  function update() {
    const connected = connection === 'connected';
    const chosen = tabs.find(tab => tab.id === find('tab').value);
    fields.forEach(name => { find(name).disabled = busy || running() || !connected; });
    const mode = find('mode').value;
    find('input-label').hidden = mode === 'current';
    find('input').placeholder = mode === 'search' ? '请填写搜索关键词，例如：记账软件 求推荐' : '请粘贴笔记链接：https://www.xiaohongshu.com/explore/...';
    find('posts-label').hidden = mode !== 'search';
    find('posts').disabled = busy || running() || !connected || mode !== 'search';
    find('coverage').textContent = mode === 'current' ? '仅读取当前这一篇已打开的笔记（1 篇）；如需批量采集多篇，请将「采集方式」切换为「关键词搜索」。' : mode === 'search' ? '在所选标签搜索一个关键词，打开实际结果，最多采集 1–20 篇笔记。' : '在所选标签打开一个国内小红书笔记链接，最多采集 1 篇。';
    find('connect').disabled = busy || connected || connection === 'connecting';
    find('disconnect').disabled = busy || connection === 'disconnected';
    find('refresh').disabled = busy;
    find('start').disabled = busy || !connected || running() || !chosen || (mode === 'current' && !existingChromeTargetUrl(chosen.url, true));
    const batchStartBtn = find('batch-start');
    if (batchStartBtn) {
      const canMulti = connected && tabs.length >= 2 && mode !== 'detail';
      batchStartBtn.hidden = !canMulti;
      batchStartBtn.disabled = busy || !canMulti || running() || checkedTabIds.size === 0;
      batchStartBtn.textContent = checkedTabIds.size ? `🚀 多平台同时采集 (${checkedTabIds.size} 个标签)` : '🚀 多平台同时采集';
    }
    const multiWrap = find('multi-tabs-wrap');
    if (multiWrap) multiWrap.hidden = !connected || tabs.length < 2 || mode === 'detail';
    find('stop').disabled = busy || !running();
    find('all').disabled = busy || !items.length || Boolean(imported);
    find('none').disabled = busy || !selected.size || Boolean(imported);
    find('import').disabled = busy || !selected.size || Boolean(imported);
    find('items').querySelectorAll('input[type="checkbox"]').forEach(el => { el.disabled = busy || Boolean(imported); });
    find('count').textContent = `本批 ${items.length} 条，已选 ${selected.size} 条`;
    find('handoff').hidden = !imported; find('handoff-note').hidden = !imported;
    find('handoff').disabled = busy;
    find('handoff').textContent = imported && !imported.materials ? '重试读取本批材料' : '用本批材料发现机会';
    schedulePolling();
  }
  function clearBatch() {
    items = []; selected = new Set(); imported = null; loadedTaskId = null; resultSummary = null; platformFilter = 'all';
    ['items', 'receipt', 'snapshots', 'error'].forEach(name => { find(name).textContent = ''; });
    find('items-details').hidden = true; find('items-details').open = false;
    if (find('platform-filters')) { find('platform-filters').textContent = ''; find('platform-filters').hidden = true; }
    if (!task && !batch) {
      find('progress-wrap').hidden = true;
      if (find('batch-subtasks')) { find('batch-subtasks').textContent = ''; find('batch-subtasks').hidden = true; }
    }
  }
  function setConnection(response) {
    if (!response || !Object.hasOwn(labels, response.status)) throw new Error('Chrome 连接状态格式异常');
    if (response.status === 'connecting' && connection !== 'connecting') pollsRemaining = 40;
    connection = response.status;
    const instruction = ['authorization_required', 'unavailable'].includes(connection) ? ' 请检查 Chrome 远程调试和本次连接授权；这不表示平台账号未登录。' : '';
    find('connection').textContent = `${labels[connection]}。${response.message || ''}${instruction}`;
    if (connection !== 'connected') { tabs = []; drawTabs(); }
  }
  function drawTabs() {
    const previous = find('tab').value;
    find('tab').textContent = '';
    const placeholder = text(find('tab'), 'option', tabs.length ? '请选择要读取的平台标签' : '没有可用的小红书/B站/微博/知乎/抖音标签；打开页面后刷新'); placeholder.value = '';
    tabs.forEach(tab => {
      const pLabel = platformLabelMap[tab.platform || existingChromePlatform(tab.url)] || '平台';
      const option = text(find('tab'), 'option', `[${pLabel}] ${tab.title || '页面'} · ${tab.url}`);
      option.value = tab.id;
    });
    const hasPrevious = tabs.some(tab => tab.id === previous);
    const preferred = find('mode').value === 'current'
      ? (tabs.find(tab => existingChromeTargetUrl(tab.url, true)) || tabs[0])
      : tabs[0];
    find('tab').value = hasPrevious ? previous : (preferred?.id || '');
    if (!hasPrevious && preferred && find('mode').value === 'current' && !existingChromeTargetUrl(preferred.url, true)) {
      find('mode').value = 'search';
    }
    const validIds = new Set(tabs.map(t => t.id));
    checkedTabIds = new Set([...checkedTabIds].filter(id => validIds.has(id)));
    drawMultiTabs();
  }
  function drawMultiTabs() {
    const box = find('multi-tabs');
    if (!box) return;
    box.textContent = '';
    tabs.forEach(tab => {
      const pKey = tab.platform || existingChromePlatform(tab.url) || 'xiaohongshu';
      const pLabel = platformLabelMap[pKey] || pKey;
      const chip = document.createElement('label');
      chip.className = 'multi-tab-chip' + (checkedTabIds.has(tab.id) ? ' checked' : '');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = checkedTabIds.has(tab.id);
      cb.disabled = busy || running();
      cb.onchange = () => {
        if (!active() || busy || running()) return;
        if (cb.checked) checkedTabIds.add(tab.id); else checkedTabIds.delete(tab.id);
        chip.classList.toggle('checked', cb.checked);
        update();
      };
      chip.appendChild(cb);
      text(chip, 'span', `[${pLabel}]`, 'badge badge-info');
      text(chip, 'span', (tab.title || tab.url).slice(0, 42), 'multi-tab-title');
      box.appendChild(chip);
    });
  }
  if (find('select-all-platforms')) {
    find('select-all-platforms').onclick = () => {
      if (!active() || busy || running()) return;
      const seenPlatform = new Set();
      checkedTabIds = new Set();
      tabs.forEach(t => {
        const p = t.platform || existingChromePlatform(t.url) || t.id;
        if (!seenPlatform.has(p)) { seenPlatform.add(p); checkedTabIds.add(t.id); }
      });
      drawMultiTabs(); update();
    };
  }
  if (find('clear-multi-tabs')) {
    find('clear-multi-tabs').onclick = () => {
      if (!active() || busy || running()) return;
      checkedTabIds = new Set(); drawMultiTabs(); update();
    };
  }
  function drawBatchSubtasks(currentBatch) {
    const grid = find('batch-subtasks');
    if (!grid) return;
    if (!currentBatch || !Array.isArray(currentBatch.subtasks) || !currentBatch.subtasks.length) {
      grid.textContent = ''; grid.hidden = true; return;
    }
    grid.hidden = false;
    grid.textContent = '';
    currentBatch.subtasks.forEach(st => {
      const card = document.createElement('div');
      card.className = `batch-subtask-card status-${st.status}`;
      const head = document.createElement('div');
      head.className = 'batch-subtask-head';
      const icon = st.status === 'completed' ? '✅' : st.status === 'failed' ? '❌' : st.status === 'running' ? '⏳' : st.status === 'cancelled' ? '⏹' : '○';
      text(head, 'strong', `${icon} ${st.platform_label || st.platform}`);
      text(head, 'span', `${st.progress?.percent ?? 0}%`, 'badge badge-default');
      card.appendChild(head);
      const bar = document.createElement('div');
      bar.className = 'batch-subtask-bar';
      const fill = document.createElement('div');
      fill.className = 'batch-subtask-fill' + (st.status === 'completed' ? ' done' : st.status === 'failed' ? ' fail' : '');
      fill.style.width = `${st.status === 'completed' ? 100 : (st.progress?.percent ?? 0)}%`;
      bar.appendChild(fill);
      card.appendChild(bar);
      text(card, 'p', st.message || st.progress?.label || '', 'discovery-hint');
      if (st.status === 'failed' && currentBatch.terminal) {
        const retryBtn = document.createElement('button');
        retryBtn.type = 'button';
        retryBtn.className = 'btn btn-secondary btn-sm';
        retryBtn.textContent = `🔄 重试 ${st.platform_label || st.platform}`;
        retryBtn.disabled = busy || running();
        retryBtn.onclick = async () => {
          if (!active() || busy || running()) return;
          const token = ++revision; busy = true; imported = null; loadedTaskId = null; find('error').textContent = ''; update();
          try {
            const resp = await apiPost(`/existing-chrome/batch-tasks/${encodeURIComponent(currentBatch.id)}/retry/${encodeURIComponent(st.tab_id)}`, {});
            if (!active() || token !== revision) return;
            setBatch(resp); await loadBatchResult(token);
          } catch (error) { if (active() && token === revision) find('error').textContent = `重试失败：${error.message}`; }
          finally { if (active() && token === revision) { busy = false; update(); } }
        };
        card.appendChild(retryBtn);
      }
      grid.appendChild(card);
    });
  }
  function setBatch(response) {
    if (!response || typeof response.id !== 'string' || !response.id) throw new Error('多平台批次状态格式异常');
    if (response.status === 'running' && batch?.id !== response.id) pollsRemaining = 120;
    task = null;
    batch = response;
    updateProgress(batch);
    drawBatchSubtasks(batch);
    const state = { running: '多平台采集中', completed: '多平台采集完成', failed: '多平台采集失败', cancelled: '已停止' }[batch.status] || batch.status;
    find('status').textContent = `${state}。${batch.message || ''}`;
    if (batch.status === 'failed') find('error').textContent = batch.message || '所选平台均未采集成功。';
    if (batch.status === 'completed' && loadedTaskId === batch.id) drawResultSummary();
  }
  async function loadTabs(token) {
    let response;
    try { response = await apiGet('/existing-chrome/tabs'); }
    catch (error) { if (active() && token === revision) { tabs = []; drawTabs(); } throw error; }
    if (!active() || token !== revision) return;
    if (!Array.isArray(response.tabs)) { tabs = []; drawTabs(); throw new Error('Chrome 标签列表格式异常'); }
    const ids = new Set();
    tabs = response.tabs.filter(tab => {
      if (!tab || typeof tab.id !== 'string' || !tab.id || ids.has(tab.id) || !existingChromeTargetUrl(tab.url)) return false;
      ids.add(tab.id); return true;
    });
    drawTabs();
  }
  function updateProgress(currentTask) {
    if (!currentTask) { find('progress-wrap').hidden = true; return; }
    const phasePct = { queued: 5, validate_source: 8, navigate_search: 15, read_search_results: 25, navigate_note: 55, read_note: 80, complete: 100 };
    const pct = currentTask.status === 'completed' ? 100 : (Number.isFinite(currentTask.progress?.percent) ? Math.max(0, Math.min(100, currentTask.progress.percent)) : (phasePct[currentTask.phase] ?? 10));
    find('progress-wrap').hidden = false;
    const fill = find('progress-fill');
    fill.style.width = `${pct}%`;
    fill.classList.toggle('done', currentTask.status === 'completed');
    fill.style.background = currentTask.status === 'failed' ? 'var(--danger)' : '';
    find('progress-text').textContent = `${pct}%`;
    find('progress-label').textContent = currentTask.progress?.label || (currentTask.status === 'completed' ? '采集完成' : currentTask.status === 'failed' ? '采集失败' : currentTask.status === 'cancelled' ? '采集已停止' : '正在采集中…');
  }
  function setTask(response) {
    if (!response || typeof response.id !== 'string' || !response.id || !['running', 'completed', 'failed', 'cancelled'].includes(response.status)) throw new Error('Chrome 任务状态格式异常');
    if (response.status === 'running' && task?.id !== response.id) pollsRemaining = 85;
    task = response;
    updateProgress(task);
    const state = { running: '采集中', completed: '采集完成', failed: '采集失败', cancelled: '已停止' }[task.status];
    find('status').textContent = `${state}。${task.message || ''}`;
    if (task.status === 'failed') find('error').textContent = task.error?.message || task.message || '任务失败，未提供原因。';
    if (task.status === 'completed' && loadedTaskId === task.id) drawResultSummary();
  }
  function drawPlatformFilters() {
    const bar = find('platform-filters');
    if (!bar) return;
    const counts = new Map();
    items.forEach(it => { const p = it.source_type || 'unknown'; counts.set(p, (counts.get(p) || 0) + 1); });
    if (counts.size < 2) { bar.textContent = ''; bar.hidden = true; return; }
    bar.hidden = false;
    bar.textContent = '';
    const makeChip = (key, label) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-sm ' + (platformFilter === key ? 'btn-primary' : 'btn-secondary');
      btn.textContent = label;
      btn.onclick = () => { platformFilter = key; drawItems(); };
      bar.appendChild(btn);
    };
    makeChip('all', `全部 (${items.length})`);
    for (const [p, cnt] of counts) makeChip(p, `${platformLabelMap[p] || p} (${cnt})`);
  }
  function drawItems() {
    find('items').textContent = '';
    drawPlatformFilters();
    const posts = items.filter(item => item.entity_type === 'post').length;
    find('items-details').hidden = !items.length;
    find('items-summary').textContent = items.length ? `展开查看已采集材料（共 ${items.length} 条：正文 ${posts} 篇、评论 ${items.length - posts} 条，点击折叠/展开）` : '展开查看已采集材料';
    items.forEach((item, index) => {
      if (platformFilter !== 'all' && item.source_type !== platformFilter) return;
      const row = document.createElement('article'); row.className = 'community-material';
      const label = document.createElement('label'); label.className = 'community-material-select';
      const check = document.createElement('input'); check.type = 'checkbox'; check.checked = selected.has(index);
      check.onchange = () => { if (!active() || busy || imported) return; if (check.checked) selected.add(index); else selected.delete(index); update(); };
      label.appendChild(check);
      const pTag = platformLabelMap[item.source_type];
      if (pTag) text(label, 'span', pTag, 'badge badge-info');
      text(label, 'strong', item.subject || (item.entity_type === 'comment' ? '评论原文' : '笔记正文')); row.appendChild(label);
      text(row, 'p', item.text, 'community-original');
      text(row, 'p', `实体：${item.entity_type || '未知'} · 平台 ID：${item.external_id || '未知'} · 发布时间：${item.source_created_at || '未知'} · 采集时间：${item.source_captured_at || '未知'}`, 'discovery-hint');
      text(row, 'p', `评论父级 ID：${item.parent_comment_id || '未知'} · ${item.locator_level === 'parent_page' ? '仅定位父页，不能直达评论' : item.locator_level === 'item' ? '条目页定位' : '定位范围未知'}`, 'discovery-hint');
      text(row, 'p', item.coverage_scope || '采集范围未提供', 'discovery-hint');
      text(row, 'p', `采集版本：${item.capture_version || '未知'} · 原文类型：${item.content_nature || '未知'}${item.raw_payload?.has_subtitles ? ` · ✅ 已含视频字幕（${item.raw_payload?.subtitle_language || 'CC/AI'}）` : ''}`, 'discovery-hint');
      row.appendChild(createSourceLink(item.external_url, sourceEvidenceLinkLabel(item)));
      const details = document.createElement('details'); text(details, 'summary', '查看采集记录'); text(details, 'pre', JSON.stringify(item.raw_payload || {}, null, 2), 'source-snapshot-json'); row.appendChild(details);
      find('items').appendChild(row);
    });
    update();
  }
  async function loadBatchResult(token) {
    if (batch?.status !== 'completed' || imported || loadedTaskId === batch.id) return;
    const batchId = batch.id;
    const result = await apiGet(`/existing-chrome/batch-tasks/${encodeURIComponent(batchId)}/results`);
    if (!active() || token !== revision || batch?.id !== batchId) return;
    const data = result.items;
    if (!Array.isArray(data) || data.length > 5000 || data.some(item => !item || typeof item.text !== 'string' || !item.text.trim() || !['post', 'comment'].includes(item.entity_type) || !['xiaohongshu', 'bilibili', 'weibo', 'zhihu', 'douyin'].includes(item.source_type) || item.capture_version !== 'mining-existing-chrome-dom/v1' || !existingChromeTargetUrl(item.external_url, true))) throw new Error('多平台采集结果格式或范围异常，未开放导入');
    items = data; selected = new Set(data.map((_, i) => i)); loadedTaskId = batchId; resultSummary = result.summary || {}; drawItems(); drawResultSummary();
  }
  async function loadResult(token) {
    if (task?.status !== 'completed' || imported || loadedTaskId === task.id) return;
    const taskId = task.id;
    const result = await apiGet(`/existing-chrome/tasks/${encodeURIComponent(taskId)}/results`);
    if (!active() || token !== revision || task?.id !== taskId) return;
    const data = result.items;
    if (!Array.isArray(data) || data.length > 1020 || data.some(item => !item || typeof item.text !== 'string' || !item.text.trim() || !['post', 'comment'].includes(item.entity_type) || !['xiaohongshu', 'bilibili', 'weibo', 'zhihu', 'douyin'].includes(item.source_type) || item.capture_version !== 'mining-existing-chrome-dom/v1' || !existingChromeTargetUrl(item.external_url, true)) || data.filter(item => item.entity_type === 'post').length > 20 || data.filter(item => item.entity_type === 'comment').length > 1000) throw new Error('Chrome 采集结果格式或范围异常，未开放导入');
    items = data; selected = new Set(); loadedTaskId = taskId; resultSummary = result.summary || {}; drawItems(); drawResultSummary();
  }
  function drawResultSummary() {
    const summary = resultSummary || {};
    const posts = items.filter(item => item.entity_type === 'post').length;
    find('status').textContent = `采集完成。正文 ${posts} 篇，评论 ${items.length - posts} 条，本批 ${items.length} 条。${typeof summary.coverage === 'string' ? summary.coverage : ''}`;
    if (Array.isArray(summary.incomplete_reasons) && summary.incomplete_reasons.length) text(find('status'), 'span', ` 不完整原因：${summary.incomplete_reasons.map(reason => typeof reason === 'string' ? reason : JSON.stringify(reason)).join('；')}`);
  }
  async function refresh() {
    if (!active() || busy) return;
    const token = revision; busy = true; find('error').textContent = ''; update();
    try {
      let response;
      try { response = await apiGet('/existing-chrome/status'); }
      catch (error) { if (active() && token === revision) { connection = 'unavailable'; tabs = []; drawTabs(); find('connection').textContent = '无法读取 Chrome 连接状态；请检查连接服务和授权设置。'; } throw error; }
      if (!active() || token !== revision) return;
      setConnection(response);
      if (connection === 'connected') await loadTabs(token);
      if (!active() || token !== revision) return;
      const batchId = batch?.id || response.active_batch;
      const id = task?.id || response.active_task;
      if (batchId) {
        const currentBatch = await apiGet(`/existing-chrome/batch-tasks/${encodeURIComponent(batchId)}`);
        if (!active() || token !== revision) return;
        setBatch(currentBatch); await loadBatchResult(token);
      } else if (id) {
        const current = await apiGet(`/existing-chrome/tasks/${encodeURIComponent(id)}`);
        if (!active() || token !== revision) return;
        setTask(current); await loadResult(token);
      }
    } catch (error) { if (active() && token === revision) find('error').textContent = error.message; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  }
  fields.forEach(name => { find(name).oninput = find(name).onchange = () => {
    if (!active() || busy || running()) return;
    revision += 1; task = null; batch = null; clearBatch(); find('status').textContent = '设置已更新，尚未启动本次采集。'; update();
  }; });
  find('connect').onclick = async () => {
    if (!active() || busy || ['connected', 'connecting'].includes(connection)) return;
    const token = ++revision; busy = true; find('error').textContent = ''; update();
    try {
      const response = await apiPost('/existing-chrome/connect', {});
      if (!active() || token !== revision) return;
      setConnection(response);
      if (connection === 'connected') await loadTabs(token);
    } catch (error) { if (active() && token === revision) find('error').textContent = `Chrome 连接请求失败：${error.message}。请检查本次连接授权。`; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  find('disconnect').onclick = async () => {
    if (!active() || busy || connection === 'disconnected') return;
    const token = ++revision; busy = true; find('error').textContent = ''; update();
    try {
      const response = await apiPost('/existing-chrome/disconnect', {});
      if (!active() || token !== revision) return;
      setConnection(response);
      if (running()) { task = { ...task, status: 'cancelled' }; find('status').textContent = '连接已断开，本工具任务已取消；Chrome 和页面保持打开。'; }
    } catch (error) { if (active() && token === revision) find('error').textContent = `断开未确认：${error.message}。请刷新连接状态。`; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  function validateStart(tab, mode, value, posts, comments) {
    if (!tab) return '请选择目标小红书标签。';
    if (!['current', 'search', 'detail'].includes(mode)) return '不支持的采集方式。';
    if (mode === 'current' && !existingChromeTargetUrl(tab.url, true)) return '当前选中标签不是笔记详情页（目前在首页或搜索页）；请切换为「关键词搜索」，或在 Chrome 中打开一篇笔记后刷新。';
    if (mode === 'search' && (!value || value.length > 100 || /[,，\r\n]/.test(value))) return '请在上方输入框填写要搜索的关键词（1–100 字，勿用逗号或换行）。';
    if (mode === 'detail' && !existingChromeTargetUrl(value, true)) return '请填写有效的小红书笔记链接、B站/抖音视频链接、微博详情页或知乎问答/专栏链接。';
    if (!Number.isInteger(posts) || posts < 1 || posts > 20) return '搜索采集篇数须为 1–20 的整数。';
    if (!Number.isInteger(comments) || comments < 0 || comments > 50) return '每篇评论数须为 0–50 条的整数。';
    return null;
  }
  find('start').onclick = async () => {
    if (!active() || busy || connection !== 'connected' || running()) return;
    const tab = tabs.find(item => item.id === find('tab').value), mode = find('mode').value;
    const value = find('input').value.trim(), posts = mode === 'search' ? Number(find('posts').value) : 1, comments = Number(find('comments').value);
    const validationError = validateStart(tab, mode, value, posts, comments);
    if (validationError) { find('error').textContent = validationError; return; }
    const detectedPlatform = (mode === 'detail' ? existingChromePlatform(value) : null) || tab.platform || existingChromePlatform(tab.url) || 'xiaohongshu';
    const request = { tab_id: tab.id, mode, query: mode === 'search' ? value : '', url: mode === 'detail' ? value : '', max_posts: posts, max_comments: comments };
    if (detectedPlatform !== 'xiaohongshu') request.platform = detectedPlatform;
    if (panelProfile !== 'product_feedback') request.pipeline_profile = panelProfile;
    const token = ++revision; task = null; batch = null; clearBatch(); busy = true; update();
    try {
      const response = await apiPost('/existing-chrome/tasks', request);
      if (!active() || token !== revision) return;
      setTask(response); await loadResult(token);
    } catch (error) { if (active() && token === revision) find('error').textContent = `采集请求失败：${error.message}`; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  if (find('batch-start')) {
    find('batch-start').onclick = async () => {
      if (!active() || busy || connection !== 'connected' || running()) return;
      const mode = find('mode').value;
      const value = find('input').value.trim();
      const posts = mode === 'search' ? Number(find('posts').value) : 1;
      const comments = Number(find('comments').value);
      const tabIds = [...checkedTabIds];
      if (!tabIds.length) { find('error').textContent = '请至少勾选 1 个目标平台标签。'; return; }
      if (mode === 'detail') { find('error').textContent = '多平台同时采集仅支持「关键词搜索」或「当前页面」模式。'; return; }
      if (mode === 'search' && (!value || value.length > 100 || /[,，\r\n]/.test(value))) { find('error').textContent = '请填写要搜索的关键词（1–100 字，勿用逗号或换行）。'; return; }
      if (!Number.isInteger(posts) || posts < 1 || posts > 20) { find('error').textContent = '每平台采集篇数须为 1–20 的整数。'; return; }
      if (!Number.isInteger(comments) || comments < 0 || comments > 50) { find('error').textContent = '每篇评论数须为 0–50 条的整数。'; return; }
      const request = { tab_ids: tabIds, mode, query: mode === 'search' ? value : '', max_posts: posts, max_comments: comments, concurrency: 3 };
      if (panelProfile !== 'product_feedback') request.pipeline_profile = panelProfile;
      const token = ++revision; task = null; batch = null; clearBatch(); busy = true; update();
      try {
        const response = await apiPost('/existing-chrome/batch-tasks', request);
        if (!active() || token !== revision) return;
        setBatch(response); await loadBatchResult(token);
      } catch (error) { if (active() && token === revision) find('error').textContent = `多平台采集请求失败：${error.message}`; }
      finally { if (active() && token === revision) { busy = false; update(); } }
    };
  }
  find('refresh').onclick = refresh;
  find('stop').onclick = async () => {
    if (!active() || busy || !running()) return;
    const token = revision; busy = true; find('error').textContent = ''; update();
    try {
      if (batch?.status === 'running') {
        const response = await apiPost(`/existing-chrome/batch-tasks/${encodeURIComponent(batch.id)}/stop`, {});
        if (active() && token === revision) { setBatch(response); await loadBatchResult(token); }
      } else {
        const response = await apiPost(`/existing-chrome/tasks/${encodeURIComponent(task.id)}/stop`, {});
        if (active() && token === revision) { setTask(response); await loadResult(token); }
      }
    } catch (error) { if (active() && token === revision) find('error').textContent = `停止未确认：${error.message}。请刷新任务状态。`; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  find('all').onclick = () => { if (!active() || busy || imported) return; selected = new Set(items.map((_, i) => i)); drawItems(); };
  find('none').onclick = () => { if (!active() || busy || imported) return; selected = new Set(); drawItems(); };
  async function readStored(token) {
    const actual = new Map();
    for (const id of imported.ids) {
      const detail = await apiGet(`/feedback/${encodeURIComponent(id)}`);
      if (!active() || token !== revision) return;
      if (detail.id !== id || detail.pipeline_profile !== panelProfile || typeof detail.content?.text !== 'string') throw new Error('实际已存材料与本批 ID、模式或正文不匹配');
      const expected = imported.expected.get(id) || [];
      const actualUrl = existingChromeSourceIdentity(detail.external_url);
      if (!expected.length || !actualUrl || expected.some(item => item.text !== detail.content.text || existingChromeSourceIdentity(item.external_url) !== actualUrl || item.source_type !== detail.source_type)) throw new Error('已存原文或来源与所选材料不一致，未交接到机会页');
      actual.set(id, { ...detail, subject: detail.content.subject, text_preview: detail.content.text, source_url: discoverySourceUrl(detail.external_url) });
    }
    imported.materials = actual;
    const counts = Number.isInteger(imported.ingested) && Number.isInteger(imported.duplicates) && imported.ingested >= 0 && imported.duplicates >= 0 && imported.ingested + imported.duplicates === imported.processed ? `新增 ${imported.ingested} 条、重复 ${imported.duplicates} 条；` : '新增和重复数量未确认；';
    find('receipt').textContent = `已处理 ${imported.processed} 条所选材料，${counts}本批可用 ${actual.size} 个实际唯一 ID。以回读原文和来源为准，尚未调用模型。`;
    find('snapshots').textContent = '';
    for (const [id, detail] of actual) appendSourceSnapshot(find('snapshots'), id, detail);
  }
  find('import').onclick = async () => {
    if (!active() || busy || imported || !selected.size) return;
    const token = revision, chosen = items.filter((_, index) => selected.has(index)); busy = true; find('error').textContent = ''; update();
    const targetVersion = (find('target-version')?.value || getEffectiveWriteVersion() || 'default').trim();
    const batchPath = targetVersion && targetVersion !== 'default' ? `/feedback/batch?version_id=${encodeURIComponent(targetVersion)}` : '/feedback/batch';
    try {
      const response = await apiPost(batchPath, chosen);
      if (!active() || token !== revision) return;
      if (!Array.isArray(response.feedback_ids) || response.feedback_ids.length !== chosen.length || response.feedback_ids.some(id => typeof id !== 'string' || !id.trim())) throw new Error('导入回执与所选材料不对应');
      const expected = new Map();
      response.feedback_ids.forEach((id, index) => { if (!expected.has(id)) expected.set(id, []); expected.get(id).push(chosen[index]); });
      imported = { ids: [...new Set(response.feedback_ids)], expected, processed: response.feedback_ids.length, ingested: response.ingested, duplicates: response.duplicates, materials: null };
      await readStored(token);
      refreshVersionsCache();
    } catch (error) { if (active() && token === revision) find('error').textContent = imported ? `导入已完成，回读失败：${error.message}。可重试读取，不会再次导入。` : `导入未确认：${error.message}。部分材料可能已处理，重复导入可能复用旧 ID。`; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  find('handoff').onclick = async () => {
    if (!active() || busy || !imported) return;
    if (!imported.materials) {
      const token = revision; busy = true; find('error').textContent = ''; update();
      try { await readStored(token); }
      catch (error) { if (active() && token === revision) find('error').textContent = `回读失败：${error.message}`; }
      finally { if (active() && token === revision) { busy = false; update(); } }
      return;
    }
    opportunityDiscoverySession.selected = new Map(imported.materials); opportunityDiscoverySession.result = null; opportunityDiscoverySession.materials = []; opportunityDiscoverySession.decisions = []; location.hash = 'opportunities';
  };
  update();
  return refresh();
}

function renderLocalCollectionPanel(panel) {
  let revision = 0, busy = false, ready = false, task = null, items = [], imported = null;
  let selected = new Set();
  const active = () => panel.isConnected && getSelectedProfile() === 'product_feedback' && getRoute() === 'connectors';
  panel.innerHTML = `
    <h2 class="section-title">MediaCrawler 独立浏览器采集</h2>
    <p class="discovery-hint">这是独立模式；如需读取普通 Chrome 的已登录会话，请使用上方「使用已登录 Chrome」。两种模式的连接和任务状态分别显示。</p>
    <p class="discovery-hint">仅供非商业学习研究。点击开始才打开专用浏览器，请手动登录或完成验证。普通 Chrome / App 登录不会自动共享，登录态只留本机。</p>
    <div class="community-controls">
      <label class="form-label">来源<select class="form-select" data-local="platform"><option value="xhs">小红书</option><option value="bili">B站</option><option value="wb">微博</option></select></label>
      <label class="form-label">方式<select class="form-select" data-local="mode"><option value="search">关键词</option><option value="detail">指定链接</option></select></label>
      <label class="form-label community-query">关键词或单个正文链接<input class="form-input" data-local="input" maxlength="2000"></label>
      <label class="form-label">最多篇数<input class="form-input" data-local="posts" type="number" min="1" max="3" value="3"></label>
      <label class="form-label">每篇一级评论<input class="form-input" data-local="comments" type="number" min="0" max="8" value="8"></label>
    </div>
    <p class="discovery-hint" data-local="coverage"></p><p class="discovery-hint" data-local="environment">正在检查本机环境…</p>
    <div class="discovery-toolbar"><button class="btn btn-primary" data-local="start" type="button">开始本次采集</button><button class="btn btn-secondary" data-local="refresh" type="button">刷新环境 / 任务</button><button class="btn btn-secondary" data-local="stop" type="button">停止本任务</button></div>
    <p class="discovery-hint" data-local="status" aria-live="polite"></p><p class="discovery-error" data-local="error" role="alert"></p>
    <p class="discovery-hint">最多3篇、每篇8条一级评论，总时限10分钟；不下载媒体、不采楼中楼。预览不入库、不调用模型。请手动刷新查看进度；离开页面不会自动停止任务。</p>
    <div data-local="items"></div><div class="discovery-toolbar"><span class="discovery-hint" data-local="count"></span><button class="btn btn-secondary" data-local="all" type="button">全选</button><button class="btn btn-primary" data-local="import" type="button">导入所选材料</button></div>
    <p class="discovery-hint" data-local="receipt"></p><div data-local="snapshots"></div>
    <p class="discovery-hint" data-local="handoff-note" hidden>继续将替换机会页已有选择与结果；请先导出需要保留的清单。在机会页手动点击「发现机会」。</p>
    <button class="btn btn-primary" data-local="handoff" type="button" hidden>用本批材料发现机会</button>`;
  const find = name => panel.querySelector(`[data-local="${name}"]`);
  const fields = ['platform', 'mode', 'input', 'posts', 'comments'];
  const text = (parent, tag, value, cls = '') => { const el = document.createElement(tag); el.textContent = String(value ?? ''); el.className = cls; parent.appendChild(el); return el; };
  function update() {
    const running = Boolean(task && !task.terminal);
    fields.forEach(name => { find(name).disabled = busy || running; });
    find('posts').disabled = busy || running || find('mode').value === 'detail';
    find('coverage').textContent = find('platform').value === 'bili' ? 'B站正文是上游最多500字符的视频简介片段，不是口播。作者昵称已遮蔽。' : find('platform').value === 'wb' ? '微博尝试展开长文但不保证完整，不覆盖全部评论。作者昵称已遮蔽。' : '小红书只读取笔记描述和有界一级评论，不含图片文字或媒体。作者昵称已遮蔽。';
    find('start').disabled = busy || !ready || running; find('refresh').disabled = busy; find('stop').disabled = busy || !running;
    find('all').disabled = busy || !items.length || Boolean(imported); find('import').disabled = busy || !selected.size || Boolean(imported);
    find('count').textContent = `本批 ${items.length} 条，已选 ${selected.size} 条`;
    find('items').querySelectorAll('input[type="checkbox"]').forEach(el => { el.disabled = busy || Boolean(imported); });
    find('handoff').hidden = !imported; find('handoff-note').hidden = !imported; find('handoff').disabled = busy;
    find('handoff').textContent = imported && !imported.materials ? '重试读取本批材料' : '用本批材料发现机会';
  }
  function clear() { items = []; selected = new Set(); imported = null; ['items', 'receipt', 'snapshots', 'error'].forEach(name => { find(name).textContent = ''; }); }
  function draw() {
    find('items').textContent = '';
    items.forEach((item, index) => {
      const row = document.createElement('article'); row.className = 'community-material';
      const label = document.createElement('label'); label.className = 'community-material-select';
      const check = document.createElement('input'); check.type = 'checkbox'; check.checked = selected.has(index);
      check.onchange = () => { if (!active() || busy || imported) return; if (check.checked) selected.add(index); else selected.delete(index); update(); };
      label.appendChild(check); text(label, 'strong', item.subject || (item.entity_type === 'comment' ? '一级评论' : '正文材料')); row.appendChild(label);
      text(row, 'p', item.text, 'community-original'); text(row, 'p', `发布时间：${item.source_created_at || '未知'} · 原作者未知（上游匿名化） · ${item.locator_level === 'parent_page' ? '仅定位父页' : '条目页定位'}`, 'discovery-hint'); text(row, 'p', item.coverage_scope, 'discovery-hint');
      const url = discoverySourceUrl(item.external_url); row.appendChild(url ? createSourceLink(url, sourceEvidenceLinkLabel(item)) : createSourceUnavailable('来源链接无效')); find('items').appendChild(row);
    }); update();
  }
  async function loadResult(token) {
    if (!task || !['completed', 'empty'].includes(task.status) || imported) return;
    const result = await apiGet(`/mediacrawler/tasks/${encodeURIComponent(task.id)}/results`);
    if (!active() || token !== revision) return;
    if (!Array.isArray(result.items) || result.items.length > 30) throw new Error('任务材料格式异常');
    items = result.items; selected = new Set(); draw(); const summary = result.summary || {};
    find('status').textContent = `${task.message} 正文 ${summary.posts ?? 0} 篇，评论 ${summary.comments ?? 0} 条。${summary.coverage_note || ''}`;
    if (summary.search_page_objects != null) text(find('status'), 'span', ` 搜索页返回 ${summary.search_page_objects} 个对象，其中最多 ${summary.selected_objects ?? 0} 个进入后续处理。`);
    const reasons = Object.entries(summary.skip_reasons || {}).map(([key, count]) => `${key}: ${count}`); if (reasons.length) text(find('status'), 'span', ` 排除记录：${reasons.join('；')}`);
  }
  async function refresh() {
    if (!active() || busy) return;
    const token = revision; busy = true; update();
    try {
      const env = await apiGet('/mediacrawler/status'); if (!active() || token !== revision) return;
      ready = env.ready === true; find('environment').textContent = env.message;
      const response = task ? await apiGet(`/mediacrawler/tasks/${encodeURIComponent(task.id)}`) : env.active_task;
      if (!active() || token !== revision) return; task = response;
      find('status').textContent = task?.message || '尚未启动采集；平台账号实采待验证。'; await loadResult(token);
    } catch (error) { if (active() && token === revision) find('error').textContent = error.message; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  }
  fields.forEach(name => { find(name).oninput = find(name).onchange = () => { if (!active() || busy || (task && !task.terminal)) return; revision += 1; task = null; clear(); update(); }; });
  find('start').onclick = async () => {
    if (!active() || busy || !ready || (task && !task.terminal)) return;
    const mode = find('mode').value, value = find('input').value.trim();
    const request = { platform: find('platform').value, mode, query: mode === 'search' ? value : '', url: mode === 'detail' ? value : '', max_posts: mode === 'detail' ? 1 : Number(find('posts').value), max_comments: Number(find('comments').value) };
    if (!value || (mode === 'search' && (value.length > 100 || /[,，\n\r]/.test(value))) || !Number.isInteger(request.max_posts) || request.max_posts < 1 || request.max_posts > 3 || !Number.isInteger(request.max_comments) || request.max_comments < 0 || request.max_comments > 8) { find('error').textContent = '请填写一个关键词或正文链接；最多3篇、每篇0–8条一级评论。'; return; }
    const token = ++revision; clear(); busy = true; update();
    try { const response = await apiPost('/mediacrawler/tasks', request); if (active() && token === revision) { task = response; find('status').textContent = response.message; } }
    catch (error) { if (active() && token === revision) find('error').textContent = `启动失败：${error.message}`; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  find('refresh').onclick = refresh;
  find('stop').onclick = async () => {
    if (!active() || busy || !task || task.terminal) return;
    const token = revision; busy = true; update();
    try { const response = await apiPost(`/mediacrawler/tasks/${encodeURIComponent(task.id)}/stop`, {}); if (active() && token === revision) { task = response; find('status').textContent = response.message; } }
    catch (error) { if (active() && token === revision) find('error').textContent = error.message; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  find('all').onclick = () => { if (!active() || busy || imported) return; selected = new Set(items.map((_, i) => i)); draw(); };
  async function readStored(token) {
    const actual = new Map();
    for (const id of imported.ids) {
      const detail = await apiGet(`/feedback/${encodeURIComponent(id)}`); if (!active() || token !== revision) return;
      if (detail.id !== id || detail.pipeline_profile !== 'product_feedback' || typeof detail.content?.text !== 'string') throw new Error('实际已存材料与本批ID不匹配');
      actual.set(id, { ...detail, subject: detail.content.subject, text_preview: detail.content.text, source_url: discoverySourceUrl(detail.external_url) });
    }
    imported.materials = actual; find('receipt').textContent = `已处理 ${imported.processed} 条所选材料，本批可用 ${actual.size} 个实际唯一ID；可能复用旧材料，以回读原文和来源为准，尚未调用模型。`;
    find('snapshots').textContent = ''; for (const [id, detail] of actual) appendSourceSnapshot(find('snapshots'), id, detail);
  }
  find('import').onclick = async () => {
    if (!active() || busy || imported || !selected.size) return;
    const token = revision, chosen = items.filter((_, i) => selected.has(i)); busy = true; update();
    try {
      const response = await apiPost('/feedback/batch', chosen); if (!active() || token !== revision) return;
      if (!Array.isArray(response.feedback_ids) || response.feedback_ids.length !== chosen.length || response.feedback_ids.some(id => typeof id !== 'string' || !id.trim())) throw new Error('导入回执异常');
      imported = { ids: [...new Set(response.feedback_ids)], processed: response.feedback_ids.length, materials: null }; await readStored(token);
    } catch (error) { if (active() && token === revision) find('error').textContent = imported ? `导入已完成，回读失败：${error.message}。可重试读取，不会再次导入。` : `导入未确认：${error.message}。部分材料可能已处理，重复导入可能复用旧ID。`; }
    finally { if (active() && token === revision) { busy = false; update(); } }
  };
  find('handoff').onclick = async () => {
    if (!active() || busy || !imported) return;
    if (!imported.materials) { const token = revision; busy = true; update(); try { await readStored(token); } catch (error) { if (active() && token === revision) find('error').textContent = `回读失败：${error.message}`; } finally { if (active() && token === revision) { busy = false; update(); } } return; }
    opportunityDiscoverySession.selected = new Map(imported.materials); opportunityDiscoverySession.result = null; opportunityDiscoverySession.materials = []; opportunityDiscoverySession.decisions = []; location.hash = 'opportunities';
  };
  update(); refresh();
}

async function renderConnectorsPage(container) {
  const profile = getSelectedProfile();
  container.innerHTML = `
    <section class="card community-panel" id="existing-chrome"></section>

    <details class="card collapsible-drawer" id="drawer-manual-import">
      <summary class="drawer-summary">✍️ 手动补录单条反馈 / 📦 批量导入 JSON（备用）</summary>
      <div class="drawer-body" id="embedded-import-slot"></div>
    </details>

    ${profile === 'product_feedback' ? `
    <details class="card collapsible-drawer" id="drawer-community-preview">
      <summary class="drawer-summary">🌐 公开社区预览（Hacker News / V2EX，免登录）</summary>
      <div class="drawer-body"><section class="community-panel" id="community-preview"></section></div>
    </details>` : ''}

    <details class="card collapsible-drawer" id="drawer-github-webhook">
      <summary class="drawer-summary">🐙 GitHub Issues 拉取 & 🔗 Webhook</summary>
      <div class="drawer-body">
        <div class="section-title" style="margin-top:4px">🐙 GitHub Issues 拉取</div>
        <div class="form-group"><label class="form-label">仓库 (owner/repo)</label><input class="form-input" id="gh-repo" placeholder="如: facebook/react"></div>
        <div class="form-row">
          <div class="form-group"><label class="form-label">标签 (逗号分隔)</label><input class="form-input" id="gh-labels" placeholder="bug,feature"></div>
          <div class="form-group"><label class="form-label">状态</label><select class="form-select" id="gh-state"><option value="all">全部</option><option value="open">Open</option><option value="closed">Closed</option></select></div>
        </div>
        <button class="btn btn-primary" id="btn-gh-fetch">🐙 拉取 Issues</button>
        <div id="gh-result" style="margin-top:12px"></div>
        <div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--border-subtle)">
          <div class="section-title">🔗 Webhook</div>
          <p style="font-size:14px;color:var(--text-muted)">Webhook 端点: <code>POST /api/v1/connectors/webhook/ingest</code></p>
        </div>
      </div>
    </details>

    <details class="card collapsible-drawer" id="drawer-legacy-tools">
      <summary class="drawer-summary">🧰 备用采集工具（知乎官方 API / MediaCrawler 专用浏览器 / 已注册连接器）</summary>
      <div class="drawer-body">
        ${profile === 'product_feedback' ? '<section class="community-panel" id="zhihu-search"></section>' : ''}
        ${profile === 'product_feedback' ? '<section class="community-panel" id="local-collection" style="margin-top:16px;padding-top:16px;border-top:1px solid var(--border-subtle)"></section>' : ''}
        <div id="connector-list" style="margin-top:16px"></div>
      </div>
    </details>
  `;
  renderExistingChromePanel(container.querySelector('#existing-chrome'));
  const manualDrawer = container.querySelector('#drawer-manual-import');
  const manualSlot = container.querySelector('#embedded-import-slot');
  let manualMounted = false;
  if (manualDrawer && manualSlot && typeof manualDrawer.addEventListener === 'function') {
    manualDrawer.addEventListener('toggle', () => {
      if (manualDrawer.open && !manualMounted) {
        manualMounted = true;
        renderImportPage(manualSlot);
      }
    });
  }
  if (profile === 'product_feedback') renderCommunitySamplesPanel(container.querySelector('#community-preview'));
  if (profile === 'product_feedback') renderZhihuSearchPanel(container.querySelector('#zhihu-search'));
  if (profile === 'product_feedback') renderLocalCollectionPanel(container.querySelector('#local-collection'));
  const listEl = container.querySelector('#connector-list');

  // List connectors
  try {
    const { connectors } = await apiGet('/connectors');
    if (!container.isConnected || getSelectedProfile() !== profile) return;
    listEl.innerHTML = `<div class="card"><div class="section-title">📋 已注册连接器 (${connectors.length})</div><div style="display:flex;gap:8px;flex-wrap:wrap">${connectors.map(c => `<span class="badge badge-info">${escapeHtml(c)}</span>`).join('')}</div></div>`;
  } catch (e) {
    if (!container.isConnected || getSelectedProfile() !== profile) return;
    showToast(`连接器列表加载失败: ${e.message}`, 'danger');
  }

  document.getElementById('btn-gh-fetch').onclick = async () => {
    const repo = document.getElementById('gh-repo').value.trim();
    if (!repo) { showToast('请输入仓库名称', 'warning'); return; }

    const btn = document.getElementById('btn-gh-fetch');
    btn.disabled = true;
    btn.textContent = '⏳ 拉取中...';

    const labelsVal = document.getElementById('gh-labels').value.trim();
    const state = document.getElementById('gh-state').value;

    try {
      const body = { repo, state };
      if (labelsVal) body.labels = labelsVal.split(',').map(s => s.trim()).filter(Boolean);
      const writeVersion = getEffectiveWriteVersion();
      if (writeVersion !== 'default') body.version_id = writeVersion;
      const result = await apiPost('/connectors/github/fetch', body);
      if (!container.isConnected || getSelectedProfile() !== profile) return;
      document.getElementById('gh-result').innerHTML = `<div style="padding:12px;background:rgba(16,185,129,0.1);border-radius:8px;color:var(--success)">✅ 拉取完成：${result.ingested_count} 条反馈已入库</div>`;
      showToast(`成功导入 ${result.ingested_count} 条 GitHub Issues`, 'success');
    } catch (e) {
      if (container.isConnected && getSelectedProfile() === profile) document.getElementById('gh-result').textContent = `❌ ${e.message}`;
    } finally {
      btn.disabled = false;
      btn.textContent = '🐙 拉取 Issues';
    }
  };
}

