/* ==================================================== Page: Import ========== */

async function renderImportPage(container) {
  const profile = getSelectedProfile();
  const profileCfg = getProfileConfig();
  const isVideoProfile = profile === 'aigc_video';
  let sourceLead = !isVideoProfile ? pendingSourceLead : null;
  if (sourceLead) pendingSourceLead = null;

  container.innerHTML = `
    <div class="card">
      <div class="section-title">${profileCfg.importTitle}</div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">${isVideoProfile ? '视频平台 / 网站' : '来源网站'}</label>
          <select class="form-select" id="import-source">
            ${renderSourceOptionGroups(profile)}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">数据获得方法</label>
          <select class="form-select" id="import-capture-method"></select>
        </div>
      </div>
      <div class="source-method-guide" id="source-method-guide"></div>
      <div id="browser-screenshot-hint" style="display:none;margin-top:4px;padding:6px 10px;background:#fff3cd;border:1px solid #ffc107;border-radius:4px;font-size:13px;color:#856404;">
        ⚠️ 截图/OCR 方法必须填写「截图路径」或在「来源备注」中说明截图内容，否则无法提交。
      </div>
      <div class="form-group">
        <label class="form-label">来源备注（可选）</label>
        <input class="form-input" id="import-source-note" placeholder="如：开放平台拉取 / 页面截图 OCR / 人工浏览时间">
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">${isVideoProfile ? '创作者名' : '用户名'}</label>
          <input class="form-input" id="import-author" placeholder="${isVideoProfile ? '如：账号名' : '如：张三'}">
        </div>
        <div class="form-group" ${isVideoProfile ? 'style="display:none"' : ''}>
          <label class="form-label">邮箱（可选）</label>
          <input class="form-input" id="import-email" placeholder="zhangsan@example.com">
        </div>
      </div>
      ${isVideoProfile ? `
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">播放量</label>
          <input class="form-input" id="import-views" type="number" min="0" step="1" value="0">
        </div>
        <div class="form-group">
          <label class="form-label">点赞量</label>
          <input class="form-input" id="import-likes" type="number" min="0" step="1" value="0">
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">视频链接（必填，真实可打开）</label>
        <input class="form-input" id="import-video-url" placeholder="https://...">
      </div>
      ` : ''}
      <div class="form-group">
        <label class="form-label">${isVideoProfile ? '视频标题' : '标题'}</label>
        <input class="form-input" id="import-subject" placeholder="${isVideoProfile ? '视频标题...' : '反馈标题...'}">
      </div>
      <div class="form-group">
        <label class="form-label">${isVideoProfile ? '视频文案 / 简介 / 评论摘要' : '正文'}</label>
        <textarea class="form-textarea" id="import-text" placeholder="${isVideoProfile ? '粘贴视频标题、描述、字幕、评论或爆款观察...' : '请输入反馈内容...'}"></textarea>
      </div>
      <div class="form-group" ${isVideoProfile ? 'style="display:none"' : ''}>
        <label class="form-label">真实来源 URL（必填，可点击）</label>
        <input class="form-input" id="import-external-url" placeholder="https://...">
      </div>
      <details class="source-import-fields">
        <summary>来源信息与内容性质（未知可留空）</summary>
        <p class="discovery-hint">默认是「人工提供文本，未联网核验」。摘要、精选评论不能直接作为机会分析的原文依据；来源时间请填写含时区的 ISO 时间。</p>
        <div class="form-row">
          <label class="form-label">内容性质<select class="form-select" id="import-content-nature"><option value="manual_text">人工提供文本，未联网核验</option><option value="original_text">原始正文</option><option value="ocr_text">截图 OCR 文本</option><option value="api_excerpt">API 摘要（线索）</option><option value="curated_comment">精选评论（线索）</option><option value="unknown">未知</option></select></label>
          <label class="form-label">正文来源字段<select class="form-select" id="import-text-origin"><option value="user_provided">用户提供，未联网核验</option><option value="body">对象正文</option><option value="title">对象自身标题（无正文）</option><option value="ocr">截图 OCR</option><option value="unknown">未知</option></select></label>
          <label class="form-label">定位等级<select class="form-select" id="import-locator-level"><option value="unknown">未知</option><option value="item">条目</option><option value="parent_page">仅父页面（不能直达评论）</option></select></label>
        </div>
        <div class="form-row">
          <label class="form-label">实体类型<select class="form-select" id="import-entity-type"><option value="unknown">未知</option><option value="post">帖子</option><option value="comment">评论</option><option value="answer">回答</option><option value="article">文章</option><option value="video">视频</option></select></label>
          <label class="form-label">平台对象 / 评论 ID<input class="form-input" id="import-external-id" placeholder="没有独立 ID 就留空"></label>
          <label class="form-label">覆盖范围<input class="form-input" id="import-coverage-scope" placeholder="如：完整正文 / 部分摘录"></label>
        </div>
        <div class="form-row">
          <label class="form-label">父页面对象 ID<input class="form-input" id="import-parent-id"></label>
          <label class="form-label">父页面 URL<input class="form-input" id="import-parent-url" placeholder="https://..."></label>
        </div>
        <div class="form-row">
          <label class="form-label">父评论 ID<input class="form-input" id="import-parent-comment-id"></label>
          <label class="form-label">父评论 URL<input class="form-input" id="import-parent-comment-url" placeholder="https://..."></label>
        </div>
        <div class="form-row">
          <label class="form-label">源创建时间<input class="form-input" id="import-source-created-at" placeholder="2026-11-05T09:00:00+08:00"></label>
          <label class="form-label">源更新时间<input class="form-input" id="import-source-updated-at" placeholder="未知留空，不替代创建时间"></label>
          <label class="form-label">采集时间<input class="form-input" id="import-source-captured-at" placeholder="含时区 ISO 时间；未知留空"></label>
        </div>
        <div class="form-row">
          <label class="form-label">采集版本<input class="form-input" id="import-capture-version"></label>
          <label class="form-label">截图路径（可选）<input class="form-input" id="import-screenshot-path"></label>
        </div>
      </details>
      <button class="btn btn-primary" id="btn-import-single">${isVideoProfile ? '🎬 提交视频样本' : '📨 提交反馈'}</button>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="section-title">📦 批量导入 JSON</div>
      <div class="file-drop-zone" id="file-drop-zone">
        <div class="file-drop-zone-icon">📂</div>
        <p>拖拽 JSON 文件到此处，或点击上传</p>
        <input type="file" id="file-input" accept=".json" style="display:none">
      </div>
      <details style="margin-top:8px;font-size:13px;color:var(--text-muted, #666);">
        <summary style="cursor:pointer;font-weight:600;">📋 证据包字段说明（每项必须包含）</summary>
        <div style="padding:8px 0;line-height:1.7;">
          <strong>必填：</strong><code>source_type</code>, <code>external_url</code>, <code>capture_method</code>, <code>text</code><br>
          <strong>可选：</strong><code>subject</code>, <code>author_name</code>, <code>source_note</code>, <code>screenshot_path</code>, <code>ocr_text</code>, <code>source_captured_at</code>, <code>raw_payload</code>；来源字段包括 <code>external_id</code>、<code>entity_type</code>、<code>parent_id</code> / <code>parent_url</code>、<code>parent_comment_id</code> / <code>parent_comment_url</code>、<code>source_created_at</code> / <code>source_updated_at</code>、<code>locator_level</code>、<code>content_nature</code>、<code>coverage_scope</code>、<code>capture_version</code>、<code>text_origin</code>。默认人工提供，未联网核验。<br>
          <span style="color:#b91c1c;">⚠ browser_screenshot 方法必须填写 screenshot_path 或 source_note</span>
        </div>
      </details>
      <div id="batch-result"></div>
    </div>
  `;

  updateSourceAcquisitionControls();
  document.getElementById('import-source').onchange = updateSourceAcquisitionControls;
  if (sourceLead) {
    const fill = (id, value) => { if (value != null) document.getElementById(id).value = String(value); };
    fill('import-source', 'zhihu');
    fill('import-capture-method', 'manual_browser');
    fill('import-subject', sourceLead.title);
    fill('import-external-url', sourceLead.source_url);
    fill('import-external-id', sourceLead.external_id);
    const entity = sourceLead.entity_type === 'question' ? 'post' : sourceLead.entity_type;
    fill('import-entity-type', ['post', 'comment', 'answer', 'article', 'video'].includes(entity) ? entity : 'unknown');
    fill('import-source-created-at', sourceLead.source_created_at);
    fill('import-source-updated-at', sourceLead.source_updated_at);
    fill('import-source-note', '来自知乎官方搜索线索；正文由用户另行提供，未联网核验；摘要和精选评论仅供参考。');
    updateSourceAcquisitionControls();
  }

  document.getElementById('btn-import-single').onclick = async () => {
    const sourceType = document.getElementById('import-source').value;
    const captureMethod = document.getElementById('import-capture-method').value;
    const author = document.getElementById('import-author').value.trim() || undefined;
    const email = document.getElementById('import-email')?.value || undefined;
    const subject = document.getElementById('import-subject').value || undefined;
    const sourceNote = document.getElementById('import-source-note').value.trim() || undefined;
    const text = document.getElementById('import-text').value.trim();

    if (!text) { showToast('请输入反馈内容', 'warning'); return; }

    const externalUrl = document.getElementById('import-external-url')?.value.trim() || undefined;
    const videoUrl = document.getElementById('import-video-url')?.value.trim() || undefined;
    const views = parseInt(document.getElementById('import-views')?.value || '0', 10) || 0;
    const likes = parseInt(document.getElementById('import-likes')?.value || '0', 10) || 0;
    const sourceUrl = isVideoProfile ? videoUrl : externalUrl;
    if (!sourceUrl) {
      showToast('必须提供真实可点击来源 URL', 'warning');
      return;
    }
    if (!/^https?:\/\//i.test(sourceUrl)) {
      showToast('来源 URL 必须以 http(s) 开头', 'warning');
      return;
    }
    const payload = {
      source_type: sourceType,
      text,
      subject,
      author_name: author,
      author_email: email,
      pipeline_profile: profile,
      external_url: sourceUrl,
      capture_method: captureMethod,
      source_note: sourceNote,
      content_nature: document.getElementById('import-content-nature').value,
      text_origin: document.getElementById('import-text-origin').value,
      locator_level: document.getElementById('import-locator-level').value,
      entity_type: document.getElementById('import-entity-type').value,
    };
    const sourceInputs = {
      external_id: 'external-id', parent_id: 'parent-id', parent_url: 'parent-url',
      parent_comment_id: 'parent-comment-id', parent_comment_url: 'parent-comment-url',
      source_created_at: 'source-created-at', source_updated_at: 'source-updated-at',
      source_captured_at: 'source-captured-at', coverage_scope: 'coverage-scope',
      capture_version: 'capture-version', screenshot_path: 'screenshot-path',
    };
    for (const [field, suffix] of Object.entries(sourceInputs)) {
      const value = document.getElementById(`import-${suffix}`).value.trim();
      if (!value) continue;
      if (field.endsWith('_at') && (!/(Z|[+-]\d{2}:\d{2})$/i.test(value) || Number.isNaN(Date.parse(value)))) {
        showToast('来源时间必须是含时区的 ISO 时间，例如 2026-11-05T09:00:00+08:00', 'warning');
        return;
      }
      if (field.endsWith('_url') && !discoverySourceUrl(value)) {
        showToast('父页面 / 父评论 URL 必须是有效的 http(s) 链接', 'warning');
        return;
      }
      payload[field] = value;
    }
    if (sourceLead) payload.raw_payload = { zhihu_search_lead: sourceLead };

    if (isVideoProfile) {
      payload.video_url = videoUrl;
      payload.views = views;
      payload.likes = likes;
      payload.platform = sourceType.startsWith('video_') ? sourceType.replace('video_', '') : sourceType;
    }

    try {
      const writeVersion = getEffectiveWriteVersion();
      if (writeVersion !== 'default') payload.version_id = writeVersion;
      const result = await apiPost('/feedback/ingest', payload);
      if (!container.isConnected || getSelectedProfile() !== profile) return;
      sourceLead = null;
      showToast(`✅ 已提交 (ID: ${result.feedback_id || result.id})`, 'success');
      document.getElementById('import-text').value = '';
      document.getElementById('import-subject').value = '';
      document.getElementById('import-source-note').value = '';
      Object.values(sourceInputs).forEach(suffix => { document.getElementById(`import-${suffix}`).value = ''; });
      document.getElementById('import-content-nature').value = 'manual_text';
      document.getElementById('import-text-origin').value = 'user_provided';
      document.getElementById('import-locator-level').value = 'unknown';
      document.getElementById('import-entity-type').value = 'unknown';
      if (isVideoProfile) {
        document.getElementById('import-video-url').value = '';
      } else {
        document.getElementById('import-external-url').value = '';
      }
    } catch (e) {
      if (container.isConnected && getSelectedProfile() === profile) showToast(`❌ ${e.message}`, 'danger');
    }
  };

  const dropZone = document.getElementById('file-drop-zone');
  const fileInput = document.getElementById('file-input');

  dropZone.onclick = () => fileInput.click();
  dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('dragover'); };
  dropZone.ondragleave = () => dropZone.classList.remove('dragover');
  dropZone.ondrop = async (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (!file) return;
    await uploadBatchFile(file);
  };
  fileInput.onchange = async () => {
    if (fileInput.files[0]) await uploadBatchFile(fileInput.files[0]);
  };

  async function uploadBatchFile(file) {
    const text = await file.text();
    if (!container.isConnected || getSelectedProfile() !== profile) return;
    let items;
    try { items = JSON.parse(text); } catch {
      showToast('文件不是有效的 JSON', 'danger');
      return;
    }
    if (!Array.isArray(items)) items = [items];
    // Normalize URL fields: map common field names to external_url
    items = items.map(item => {
      if (!item.source_type && item.source) item.source_type = item.source;
      if (!item.text) item.text = item.content || item.body || item.feedback || item.caption || item.description || '';
      if (!item.external_url) {
        item.external_url = item.source_url || item.url || item.video_url || item.link || undefined;
      }
      item.capture_method = item.capture_method || item.collection_method || item.acquisition_method || 'manual_browser';
      item.source_note = item.source_note || item.note || item.provenance_note || undefined;
      item.content_nature = item.content_nature || 'manual_text';
      item.text_origin = item.text_origin || 'user_provided';
      item.locator_level = item.locator_level || 'unknown';
      item.pipeline_profile = item.pipeline_profile || profile;
      if (isVideoProfile) {
        item.source_type = item.source_type || (item.platform ? `video_${item.platform}` : 'video_manual');
        item.video_url = item.video_url || item.external_url;
        item.views = Number(item.views || 0);
        item.likes = Number(item.likes || 0);
        item.platform = item.platform || (item.source_type.startsWith('video_') ? item.source_type.replace('video_', '') : item.source_type);
      }
      return item;
    });
    const missingUrlIndex = items.findIndex(item => !item.external_url);
    if (missingUrlIndex !== -1) {
      showToast(`第 ${missingUrlIndex + 1} 条缺少真实来源 URL`, 'danger');
      return;
    }
    try {
      const result = await apiPost('/feedback/batch', items);
      if (!container.isConnected || getSelectedProfile() !== profile) return;
      document.getElementById('batch-result').innerHTML = `
        <div style="margin-top:16px;padding:12px;background:rgba(16,185,129,0.1);border-radius:8px;color:var(--success)">
          ✅ 批量导入完成：${result.ingested} 条
        </div>
      `;
    } catch (e) {
      if (container.isConnected && getSelectedProfile() === profile) showToast(`❌ 批量导入失败: ${e.message}`, 'danger');
    }
  }
}

/* ==================================================== Page: Feedback ======== */

async function renderFeedbackPage(container) {
  const profile = getSelectedProfile();
  let revision = 0;
  container.innerHTML = '<div class="filters-bar"><button class="btn btn-secondary" id="btn-refresh-fb">🔄 刷新</button></div><div id="fb-list"></div>';

  async function load() {
    const token = ++revision;
    const listEl = container.querySelector('#fb-list');
    listEl.innerHTML = '';
    showSkeleton(listEl, 5);
    try {
      const data = await apiGet('/feedback', { limit: 100, profile: getSelectedProfile(), version_id: getSelectedVersion() });
      if (!container.isConnected || token !== revision || getSelectedProfile() !== profile) return;
      listEl.innerHTML = '';
      if (!data.length) return showEmpty(listEl, '📭', '暂无原始反馈', '导入数据后这里会显示所有原始反馈');

      data.forEach(fb => {
        const text = (fb.text_preview || fb.content?.text || '').slice(0, 200);
        const signalCount = fb.signal_count || 0;
        const stateIcon = { pending: '⏳', completed: '✅', failed: '❌', dismissed: '🗑️' }[fb.processing_state] || '📌';
        const stateBadge = createBadge(`${stateIcon} ${fb.processing_state}`, fb.processing_state === 'completed' ? 'success' : fb.processing_state === 'failed' ? 'danger' : 'default');

        const fbSourceButtonHtml = sourceButtonHtml(fb.source_url, fb.external_url, '数据来源');

        const card = createExpandableCard(
          `<div><div style="font-weight:600;margin-bottom:4px">${escapeHtml(text.slice(0, 80))}${text.length > 80 ? '…' : ''}</div>
           <div style="font-size:12px;color:var(--text-muted)">${escapeHtml(String(fb.source_type || '未知'))} · ${escapeHtml(fb.author?.name || '未知作者')} · ${signalCount} 个信号</div></div>
           <div class="card-header-actions">${fbSourceButtonHtml}${stateBadge.outerHTML}</div>`,
          `<p style="white-space:pre-wrap">${escapeHtml(text)}</p>
           <div style="margin-top:8px;font-size:12px;color:var(--text-muted)">ID: ${escapeHtml(String(fb.id))} · created: ${escapeHtml(fb.created_at || '—')}</div>`
        );
        appendSourceSnapshot(card.children[1], fb.id);
        listEl.appendChild(card);
      });
    } catch (e) {
      if (container.isConnected && token === revision && getSelectedProfile() === profile) showToast(`加载失败: ${e.message}`, 'danger');
    }
  }

  document.getElementById('btn-refresh-fb').onclick = load;
  load();
}

/* ==================================================== Page: Signals ========= */

async function renderSignalsPage(container) {
  const signalTypes = getProfileConfig().signalTypes;
  container.innerHTML = `
    <div class="filters-bar">
      <div class="form-group"><label class="form-label">信号类型</label><select class="form-select" id="sig-type"><option value="">全部</option>${signalTypes.map(t => `<option value="${t}">${t}</option>`).join('')}</select></div>
      <div class="form-group"><label class="form-label">最低模型自评分（未校准，仅查看筛选）: <span id="sig-conf-val">0.00</span></label><input type="range" class="form-input" id="sig-conf" min="0" max="1" step="0.05" value="0" style="padding:0"></div>
      <button class="btn btn-secondary btn-sm" id="btn-filter-sig">🔍 筛选</button>
    </div>
    <div id="sig-list"></div>
  `;

  const confSlider = document.getElementById('sig-conf');
  confSlider.oninput = () => document.getElementById('sig-conf-val').textContent = parseFloat(confSlider.value).toFixed(2);

  async function load() {
    const listEl = document.getElementById('sig-list');
    listEl.innerHTML = '';
    showSkeleton(listEl, 5);
    try {
      const params = { limit: 200, profile: getSelectedProfile() };
      const typeVal = document.getElementById('sig-type').value;
      if (typeVal) params.signal_type = typeVal;
      const confVal = parseFloat(document.getElementById('sig-conf').value);
      if (confVal > 0) params.min_model_self_score = confVal;
      params.version_id = getSelectedVersion();
      const data = await apiGet('/signals', params);
      listEl.innerHTML = '';
      if (!data.length) return showEmpty(listEl, '🔍', '暂无匹配信号', '尝试调整筛选条件');

      data.forEach(sig => {
        const conf = sig.confidence || 0;
        const confColor = confidenceColor(conf);
        const evidence = (sig.evidence || []).join(' · ');
        // P13-1: honest confidence display — model self-report, not calibrated
        const evidenceStatus = sig.evidence_validation_status || 'not_checked';
        const evidenceBadge = {
          verified: '<span class="badge badge-success" style="font-size:11px">证据已验证</span>',
          partial: '<span class="badge badge-warning" style="font-size:11px">证据部分匹配</span>',
          invalid: '<span class="badge badge-danger" style="font-size:11px">证据未匹配</span>',
          not_checked: '',
        }[evidenceStatus] || '';
        const confLabel = sig.calibrated_confidence != null
          ? `校准 ${(sig.calibrated_confidence * 100).toFixed(0)}%`
          : `模型自评 ${conf.toFixed(2)}（未校准）`;
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
          <div class="card-header">
            <div>
              <div class="card-title">${escapeHtml(sig.summary || '')}</div>
              <div class="card-subtitle">${escapeHtml(sig.signal_type || '')} · ${escapeHtml(sig.source_type || '—')}</div>
            </div>
            <span class="badge" style="color:${confColor};background:${confColor}15">${escapeHtml(confLabel)}</span>
          </div>
          <div class="card-body">
            ${evidence ? `<div style="margin-bottom:8px"><strong>证据:</strong> «${escapeHtml(evidence)}» ${evidenceBadge}</div>` : ''}
            ${sig.implicit_need ? `<div style="color:var(--accent-secondary)"><strong>隐含需求:</strong> ${escapeHtml(sig.implicit_need)}</div>` : ''}
            ${sourceStatusHtml(sig.source_url, sig.external_url, '查看原始来源')}
            ${!sig.source_url && !sig.external_url && sig.source_type ? `<div style="margin-top:4px;font-size:12px;color:var(--text-muted)">📎 来源平台: ${escapeHtml(sig.source_type)}</div>` : ''}
          </div>
        `;
        listEl.appendChild(card);
      });
    } catch (e) {
      showToast(`加载失败: ${e.message}`, 'danger');
    }
  }

  document.getElementById('btn-filter-sig').onclick = load;
  load();
}

/* ==================================================== Page: Themes =========== */

async function renderThemesPage(container) {
  container.innerHTML = '<div class="card-grid-2" id="theme-grid"></div>';
  const grid = document.getElementById('theme-grid');
  showSkeleton(grid, 4);
  try {
    const data = await apiGet('/themes', { limit: 50, profile: getSelectedProfile(), version_id: getSelectedVersion() });
    grid.innerHTML = '';
    if (!data.length) return showEmpty(grid, '🏷️', '暂无主题', '运行管线以生成主题聚类');

    data.forEach(theme => {
      const card = document.createElement('div');
      card.className = 'card card-expandable';
      card.innerHTML = `
        <div class="card-header">
          <div style="flex:1">
            <div class="card-title">${escapeHtml(theme.name || '')}</div>
            <div class="card-subtitle">${Number(theme.signal_count) || 0} 个信号 · ${escapeHtml(theme.status || '')}</div>
          </div>
          <button class="expand-toggle">▼</button>
        </div>
        <div class="card-body">
          <p>${escapeHtml(theme.description || '')}</p>
          ${(theme.representative_quotes || []).map(q => `<div class="evidence-quote">«${escapeHtml(q)}»</div>`).join('')}
        </div>
      `;
      const toggle = card.querySelector('.expand-toggle');
      toggle.onclick = () => { card.classList.toggle('expanded'); toggle.classList.toggle('open'); };
      grid.appendChild(card);
    });
  } catch (e) { showToast(`加载失败: ${e.message}`, 'danger'); }
}

/* ==================================================== Page: Pain Points ===== */

async function renderPainPointsPage(container) {
  container.innerHTML = '<div class="filters-bar"><div class="form-group"><label class="form-label">严重度</label><select class="form-select" id="pp-sev"><option value="">全部</option><option>critical</option><option>high</option><option>medium</option><option>low</option></select></div><button class="btn btn-secondary btn-sm" id="btn-pp-filter">🔍</button></div><div id="pp-list"></div>';

  async function load() {
    const listEl = document.getElementById('pp-list');
    listEl.innerHTML = '';
    showSkeleton(listEl, 4);
    try {
      const data = await apiGet('/pain-points', { limit: 50, profile: getSelectedProfile(), version_id: getSelectedVersion() });
      listEl.innerHTML = '';
      if (!data.length) return showEmpty(listEl, '😌', '暂无痛点', '运行管线以识别用户痛点');

      const sevIcon = { critical: '🔴', high: '🟠', medium: '🟡', low: '🟢' };
      const sevFilter = document.getElementById('pp-sev').value;

      data.filter(pp => !sevFilter || pp.severity === sevFilter).forEach(pp => {
        const badge = createBadge(`${sevIcon[pp.severity] || ''} ${pp.severity}`, pp.severity === 'critical' ? 'danger' : pp.severity === 'high' ? 'warning' : 'info');
        const card = createExpandableCard(
          `<div><div class="card-title">${escapeHtml(pp.description || '')}</div><div class="card-subtitle">${escapeHtml(pp.user_segment || '')} · ${escapeHtml(pp.frequency || '')}</div></div>${badge.outerHTML}`,
          `<p><strong>业务影响:</strong> ${escapeHtml(pp.business_impact || '')}</p>${(pp.evidence_quotes || []).map(q => `<div class="evidence-quote">«${escapeHtml(q)}»</div>`).join('')}`
        );
        listEl.appendChild(card);
      });
    } catch (e) { showToast(`加载失败: ${e.message}`, 'danger'); }
  }

  document.getElementById('btn-pp-filter').onclick = load;
  load();
}

