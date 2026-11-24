/* ==================================================== Page: Connectors ====== */

function renderCommunitySamplesPanel(panel) {
  // This preview and its import receipt belong to this mounted page only.
  let revision = 0;
  let previewing = false;
  let importing = false;
  let readingImported = false;
  let items = [];
  let summary = null;
  let selected = new Set();
  let imported = null;
  const isActive = () => panel.isConnected && getSelectedProfile() === 'product_feedback' && getRoute() === 'connectors';
  panel.innerHTML = `
    <h2 class="section-title">从公开社区取得第一批材料</h2>
    <p class="discovery-hint">先预览原始帖子或评论，再勾选导入。采集预览不入库、不调用模型；导入后也不会自动分析。</p>
    <div class="community-controls">
      <label class="form-label">来源<select class="form-select" data-community="source"><option value="v2ex">V2EX 公开订阅</option><option value="hn">Hacker News</option></select></label>
      <label class="form-label" data-community="node-label">节点<select class="form-select" data-community="node"><option value="qna">问与答</option><option value="ideas">奇思妙想</option></select></label>
      <label class="form-label" data-community="kind-label" hidden>材料类型<select class="form-select" data-community="kind"><option value="both">Ask HN 帖子与评论</option><option value="ask">Ask HN 帖子</option><option value="comments">HN 评论</option></select></label>
      <label class="form-label community-query">关键词（可留空）<input class="form-input" data-community="query" maxlength="200" placeholder="不限定产品领域"></label>
      <label class="form-label">近几天<input class="form-input" data-community="days" type="number" min="1" max="365" value="30"></label>
      <label class="form-label">最多条数<input class="form-input" data-community="limit" type="number" min="1" max="30" value="10"></label>
    </div>
    <p class="discovery-hint" data-community="coverage"></p>
    <div class="discovery-toolbar"><button class="btn btn-primary" type="button" data-community="preview">采集预览</button><span class="discovery-hint">预览与人工选择只保留在当前页面；新预览会替换当前批。</span></div>
    <div class="discovery-error" role="alert" data-community="error"></div>
    <div aria-live="polite" data-community="summary"></div>
    <div data-community="items"></div>
    <div class="discovery-toolbar">
      <span class="discovery-hint" aria-live="polite" data-community="count"></span>
      <button class="btn btn-secondary btn-sm" type="button" data-community="all">全选</button>
      <button class="btn btn-secondary btn-sm" type="button" data-community="none">取消选择</button>
      <button class="btn btn-primary" type="button" data-community="import">导入所选材料</button>
    </div>
    <div class="discovery-hint" role="status" data-community="receipt"></div>
    <p class="discovery-hint" data-community="handoff-note" hidden>下一步会替换机会页已有的材料选择、候选结果和人工备注；请先导出需要保留的清单。然后在机会页手动点击「发现机会」。</p>
    <button class="btn btn-primary" type="button" data-community="handoff" hidden>用本批材料发现机会</button>
  `;
  const find = name => panel.querySelector(`[data-community="${name}"]`);
  const fields = ['source', 'node', 'kind', 'query', 'days', 'limit'];
  const appendText = (parent, tag, text, className = '') => {
    const element = document.createElement(tag);
    element.className = className;
    element.textContent = String(text ?? '');
    parent.appendChild(element);
    return element;
  };

  function updateControls() {
    const hn = find('source').value === 'hn';
    find('node-label').hidden = hn;
    find('kind-label').hidden = !hn;
    find('coverage').textContent = hn
      ? 'HN 使用 Algolia 搜索 API，最多 3 次请求；帖子限 Ask HN，评论来自 HN 各类讨论。样本偏英语和技术人群，不能代表全部市场。'
      : 'V2EX 读取问与答 / 奇思妙想当前公开订阅流，最多 1 次请求；关键词只过滤当前订阅流。天数仅筛选其中的发布时间，不代表覆盖该时段的全部帖子，也不含评论。';
    find('preview').disabled = previewing || importing || readingImported;
    find('preview').textContent = previewing ? '正在采集预览…' : '采集预览';
    fields.forEach(name => { find(name).disabled = importing || readingImported; });
    find('count').textContent = items.length ? `本批 ${items.length} 条，已选 ${selected.size} 条` : '';
    find('all').disabled = !items.length || previewing || importing || Boolean(imported);
    find('none').disabled = !selected.size || previewing || importing || Boolean(imported);
    find('import').disabled = !selected.size || previewing || importing || Boolean(imported);
    find('import').textContent = importing ? '正在处理所选材料…' : imported ? '本批所选材料已处理' : '导入所选材料';
    find('items').querySelectorAll('input[type="checkbox"]').forEach(input => {
      input.disabled = previewing || importing || Boolean(imported);
    });
    find('handoff').hidden = !imported;
    find('handoff-note').hidden = !imported;
    find('handoff').disabled = !imported || importing || previewing || readingImported;
    find('handoff').textContent = readingImported ? '正在读取本批材料…' : imported && !imported.materials ? '重试读取本批材料' : '用本批材料发现机会';
  }

  function clearPreview(message = '') {
    revision += 1;
    previewing = false;
    items = [];
    summary = null;
    selected = new Set();
    imported = null;
    ['summary', 'items', 'receipt', 'error'].forEach(name => { find(name).textContent = ''; });
    find('summary').textContent = message;
    updateControls();
  }

  function renderPreview() {
    const summaryEl = find('summary');
    summaryEl.textContent = '';
    const status = { empty: '未找到符合条件的材料', bounded: '已达到采集预算，仅为有界样本', collected: '采集预览完成', completed: '采集预览完成', complete: '采集预览完成' }[summary.status] || `采集状态：${summary.status || '未知'}`;
    const stopReason = { sample_limit: '已达到所选条数上限', request_limit: '已达到请求预算', sources_exhausted: '当前搜索结果已读完', single_feed_exhausted: '当前订阅流已读完', request_or_response_error: '请求或响应失败' }[summary.stop_reason] || summary.stop_reason || '未提供';
    appendText(summaryEl, 'p', status, 'community-summary-title');
    appendText(summaryEl, 'p', `请求 ${summary.requests ?? '未知'} 次 · 读取 ${summary.fetched ?? '未知'} 条 · 返回 ${items.length} 条 · 跳过 ${summary.skipped ?? '未知'} 条`, 'discovery-hint');
    appendText(summaryEl, 'p', `来源 ${summary.source ?? '未知'} · 关键词 ${summary.query || '未限定'} · 最近 ${summary.days ?? '未知'} 天 · 最多 ${summary.limit ?? '未知'} 条 · 类型 ${(summary.kinds || []).join(' / ')} · 终止原因 ${stopReason}`, 'discovery-hint');
    if (summary.coverage_note) appendText(summaryEl, 'p', summary.coverage_note, 'discovery-hint');
    if (summary.published_from || summary.published_to) appendText(summaryEl, 'p', `发布时间筛选范围：${summary.published_from || '未知'} 至 ${summary.published_to || '未知'}`, 'discovery-hint');
    const skipLabels = { outside_time_window: '发布时间不在范围内', missing_published_at: '缺少发布时间', invalid_published_at: '发布时间无效', invalid_timestamp: '时间无效', query_mismatch: '关键词未匹配', duplicate_id: '重复来源 ID', invalid_source_url: '来源链接无效', empty_text: '正文为空', beyond_sample_limit: '超出所选条数', invalid_hit: '记录格式无效', invalid_id: '来源 ID 无效', deleted_or_dead: '记录已删除或失效' };
    const skipped = Object.entries(summary.skip_reasons || {}).map(([reason, count]) => `${skipLabels[reason] || reason}：${count}`);
    if (skipped.length) appendText(summaryEl, 'p', `跳过原因：${skipped.join('；')}`, 'discovery-hint');
    (summary.errors || []).forEach(error => appendText(summaryEl, 'p', `采集提示：${error}`, 'discovery-error'));
    if (!items.length) appendText(summaryEl, 'p', '可调整关键词、节点或时间范围后重新预览。V2EX 无法补齐订阅流以外的历史内容。', 'discovery-hint');
    const list = find('items');
    list.textContent = '';
    items.forEach((item, index) => {
      const row = document.createElement('article');
      row.className = 'community-material';
      const label = document.createElement('label');
      label.className = 'community-material-select';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = selected.has(index);
      checkbox.onchange = () => {
        if (!isActive() || importing || imported) return;
        if (checkbox.checked) selected.add(index);
        else selected.delete(index);
        updateControls();
      };
      label.appendChild(checkbox);
      appendText(label, 'strong', item.subject || '无标题材料');
      row.appendChild(label);
      const details = document.createElement('details');
      appendText(details, 'summary', item.content_nature === 'api_excerpt' ? '展开 API 摘要（线索）' : item.content_nature === 'curated_comment' ? '展开精选评论（线索）' : '展开留存正文');
      appendText(details, 'p', item.text, 'community-original');
      row.appendChild(details);
      appendText(row, 'p', `发布时间：${item.raw_payload?.published_at || '未提供'} · 采集时间：${item.source_captured_at || '未提供'}`, 'discovery-hint');
      appendText(row, 'p', `${CONTENT_NATURE_LABELS[item.content_nature] || CONTENT_NATURE_LABELS.unknown} · ${LOCATOR_LABELS[item.locator_level] || LOCATOR_LABELS.unknown}`, 'discovery-hint');
      const source = discoverySourceUrl(item.external_url);
      row.appendChild(source ? createSourceLink(source, sourceEvidenceLinkLabel(item)) : createSourceUnavailable('来源链接不可打开'));
      list.appendChild(row);
    });
    updateControls();
  }

  fields.forEach(name => {
    const invalidate = () => {
      if (!isActive() || importing || readingImported) return;
      clearPreview('采集条件已改变，请重新采集预览。旧批次已清除。');
    };
    find(name).oninput = invalidate;
    find(name).onchange = invalidate;
  });
  find('all').onclick = () => {
    if (!isActive() || importing || previewing || imported) return;
    selected = new Set(items.map((_, index) => index));
    renderPreview();
  };
  find('none').onclick = () => {
    if (!isActive() || importing || previewing || imported) return;
    selected.clear();
    renderPreview();
  };
  find('preview').onclick = async () => {
    if (!isActive() || previewing || importing || readingImported) return;
    const request = {
      source: find('source').value,
      query: find('query').value.trim(),
      days: Number(find('days').value),
      limit: Number(find('limit').value),
      v2ex_node: find('node').value,
      kind: find('kind').value,
    };
    if (!Number.isInteger(request.days) || request.days < 1 || request.days > 365 || !Number.isInteger(request.limit) || request.limit < 1 || request.limit > 30 || request.query.length > 200) {
      find('error').textContent = '请填写 1–365 天、1–30 条，关键词最多 200 字。';
      return;
    }
    clearPreview();
    const token = revision;
    previewing = true;
    updateControls();
    try {
      const response = await apiPost('/connectors/community/preview', request);
      if (!isActive() || token !== revision) return;
      if (!Array.isArray(response.items) || response.items.length > 30 || !response.summary || typeof response.summary !== 'object') throw new Error('预览返回格式异常，请重试');
      items = response.items;
      summary = response.summary;
      renderPreview();
    } catch (error) {
      if (!isActive() || token !== revision) return;
      find('error').textContent = `采集预览失败：${error.message}。本次没有导入材料，可重试。`;
    } finally {
      if (isActive() && token === revision) {
        previewing = false;
        updateControls();
      }
    }
  };
  find('import').onclick = async () => {
    if (!isActive() || !selected.size || previewing || importing || imported) return;
    const token = revision;
    // Preserve every original field, including raw_payload and source metadata.
    const chosen = items.filter((_, index) => selected.has(index));
    importing = true;
    find('error').textContent = '';
    find('receipt').textContent = '';
    updateControls();
    try {
      const response = await apiPost('/feedback/batch', chosen);
      if (!isActive() || token !== revision) return;
      if (!Array.isArray(response.feedback_ids) || response.feedback_ids.length !== chosen.length || response.feedback_ids.some(id => typeof id !== 'string' || !id.trim())) throw new Error('导入回执与所选材料不对应，无法建立本批选择');
      imported = { ids: [...new Set(response.feedback_ids)], processed: response.feedback_ids.length, materials: null };
      updateControls();
      await readImportedMaterials(token);
    } catch (error) {
      if (!isActive() || token !== revision) return;
      find('error').textContent = `导入未确认完成：${error.message}。部分材料可能已处理；可重试，重复材料可能复用已有 ID。`;
    } finally {
      if (isActive() && token === revision) {
        importing = false;
        updateControls();
      }
    }
  };
  async function readImportedMaterials(token) {
    readingImported = true;
    find('error').textContent = '';
    find('receipt').textContent = `导入已确认处理 ${imported.processed} 条材料；正在回读 ${imported.ids.length} 个实际反馈 ID，核对已存内容与来源…`;
    updateControls();
    try {
      const actual = new Map();
      for (const id of imported.ids) {
        const detail = await apiGet(`/feedback/${encodeURIComponent(id)}`);
        if (!isActive() || token !== revision) return;
        if (detail.id !== id || detail.pipeline_profile !== 'product_feedback' || typeof detail.content?.text !== 'string') throw new Error('已存材料的 ID、模式或正文不匹配');
        actual.set(id, {
          ...detail, subject: detail.content.subject, text_preview: detail.content.text,
          source_url: discoverySourceUrl(detail.external_url),
        });
      }
      imported.materials = actual;
      find('receipt').textContent = `已处理 ${imported.processed} 条所选材料；本批可用 ${actual.size} 条（按实际返回 ID 合并并回读）。可能复用已存在材料，以已存原文和来源为准，不代表全部新增；尚未调用模型。`;
    } catch (error) {
      if (!isActive() || token !== revision) return;
      find('error').textContent = `导入已完成，但本批材料回读失败：${error.message}。点击「重试读取本批材料」只重试回读，不会再次导入。`;
    } finally {
      if (isActive() && token === revision) {
        readingImported = false;
        updateControls();
      }
    }
  }
  find('handoff').onclick = async () => {
    if (!isActive() || !imported || importing || previewing || readingImported) return;
    if (!imported.materials) {
      await readImportedMaterials(revision);
      return;
    }
    opportunityDiscoverySession.selected = new Map(imported.materials);
    opportunityDiscoverySession.result = null;
    opportunityDiscoverySession.materials = [];
    opportunityDiscoverySession.decisions = [];
    location.hash = 'opportunities';
  };
  updateControls();
}

function renderZhihuSearchPanel(panel) {
  let configured = false;
  let loadingStatus = false;
  let searching = false;
  let revision = 0;
  const active = () => panel.isConnected && getSelectedProfile() === 'product_feedback' && getRoute() === 'connectors';
  panel.innerHTML = `
    <h2 class="section-title">知乎官方搜索（检索线索）</h2>
    <p class="discovery-hint">官方接口返回 API 摘要与精选评论，不能直接作为原文依据送入机会分析。先打开来源取得原文，再补充导入；不在本页填写密钥。</p>
    <div data-zhihu="status" role="status"></div>
    <button class="btn btn-secondary btn-sm" type="button" data-zhihu="status-retry">重新读取配置状态</button>
    <div class="community-controls">
      <label class="form-label community-query">检索词（必填）<input class="form-input" data-zhihu="query" maxlength="200" placeholder="描述要研究的问题"></label>
      <label class="form-label">近几天（按源创建时间）<input class="form-input" data-zhihu="days" type="number" min="1" max="365" value="30"></label>
      <label class="form-label">最多线索<input class="form-input" data-zhihu="count" type="number" min="1" max="10" value="5"></label>
    </div>
    <div class="discovery-toolbar"><button class="btn btn-primary" type="button" data-zhihu="search" disabled>检索线索</button><span class="discovery-hint">单次至多 10 条、一个上游请求，不分页；检索不入库、不调用模型。</span></div>
    <div class="discovery-error" role="alert" data-zhihu="error"></div>
    <div data-zhihu="summary" class="discovery-hint" aria-live="polite"></div>
    <div data-zhihu="leads"></div>`;
  const find = name => panel.querySelector(`[data-zhihu="${name}"]`);
  const text = (parent, tag, value, className = 'discovery-hint') => {
    const element = document.createElement(tag);
    element.className = className;
    element.textContent = String(value ?? '');
    parent.appendChild(element);
    return element;
  };
  const update = () => {
    find('search').disabled = !configured || loadingStatus || searching;
    find('search').textContent = searching ? '正在检索线索…' : '检索线索';
    find('status-retry').disabled = loadingStatus || searching;
  };
  async function loadStatus() {
    if (!active() || loadingStatus || searching) return;
    const token = ++revision;
    loadingStatus = true;
    configured = false;
    find('status').textContent = '正在读取本机配置状态…';
    find('leads').textContent = '';
    find('summary').textContent = '';
    update();
    try {
      const status = await apiGet('/connectors/zhihu/status');
      if (!active() || token !== revision) return;
      configured = status.configured === true;
      find('status').textContent = '';
      text(find('status'), 'p', configured ? '已配置：可以检索线索，仍须另行补充原文。' : '未配置：当前尚不能检索，不会向知乎发送请求。');
      if (!configured) {
        const setup = discoverySourceUrl(status.setup_url) || 'https://developer.zhihu.com/';
        find('status').appendChild(createSourceLink(setup, '打开知乎开放平台申请入口'));
        const hint = typeof status.configuration_hint === 'string' && status.configuration_hint.trim()
          ? status.configuration_hint
          : '取得访问凭据后，在服务端环境设置 ZHIHU_ACCESS_SECRET 并重启服务，再重新读取配置状态。请勿把密钥填入网页或导入文件。';
        text(find('status'), 'p', `本机配置：${hint}`);
      }
      const showPublic = (label, value) => {
        const entries = (Array.isArray(value) ? value : [value]).filter(item => typeof item === 'string' && item.trim());
        if (!entries.length) return;
        text(find('status'), 'p', label);
        const list = document.createElement('ul');
        list.className = 'discovery-hint';
        entries.forEach(item => text(list, 'li', item));
        find('status').appendChild(list);
      };
      showPublic('检索能力', status.capabilities);
      showPublic('使用限制', status.limitations);
    } catch (error) {
      if (active() && token === revision) find('status').textContent = `配置状态读取失败：${error.message}。请重试；当前不会发起检索。`;
    } finally {
      if (active() && token === revision) {
        loadingStatus = false;
        update();
      }
    }
  }
  ['query', 'days', 'count'].forEach(name => {
    const invalidate = () => {
      if (!active() || loadingStatus) return;
      revision += 1;
      searching = false;
      find('leads').textContent = '';
      find('summary').textContent = '检索条件已改变，请重新检索；旧线索已清除。';
      find('error').textContent = '';
      update();
    };
    find(name).oninput = invalidate;
    find(name).onchange = invalidate;
  });
  find('status-retry').onclick = loadStatus;
  find('search').onclick = async () => {
    if (!active() || !configured || loadingStatus || searching) return;
    const request = { query: find('query').value.trim(), count: Number(find('count').value), days: Number(find('days').value) };
    if (!request.query || request.query.length > 200 || !Number.isInteger(request.count) || request.count < 1 || request.count > 10 || !Number.isInteger(request.days) || request.days < 1 || request.days > 365) {
      find('error').textContent = '请填写检索词（1–200 字）、1–10 条线索及 1–365 天。';
      return;
    }
    const token = ++revision;
    searching = true;
    find('error').textContent = '';
    find('leads').textContent = '';
    find('summary').textContent = '';
    update();
    try {
      const response = await apiPost('/connectors/zhihu/preview', request);
      if (!active() || token !== revision) return;
      if (!Array.isArray(response.leads) || response.leads.length > 10 || !response.summary || typeof response.summary !== 'object') throw new Error('线索返回格式异常');
      find('summary').textContent = response.leads.length ? `取得 ${response.leads.length} 条检索线索，尚未导入。${JSON.stringify(response.summary)}` : `未找到线索。${JSON.stringify(response.summary)}`;
      response.leads.forEach((lead, index) => {
        const row = document.createElement('article');
        row.className = 'community-material zhihu-lead';
        text(row, 'h3', lead.title || '未提供标题', '');
        text(row, 'p', 'API 摘要（检索线索，非原始正文）');
        text(row, 'p', lead.excerpt || '未提供摘要', 'community-original');
        const comments = Array.isArray(lead.curated_comments) ? lead.curated_comments : [];
        if (comments.length) text(row, 'p', '精选评论（检索线索，缺少独立评论定位；不能作为完整用户证据）');
        comments.forEach(comment => text(row, 'blockquote', comment, 'community-original'));
        text(row, 'p', `实体：${lead.entity_type || '未知'} · 平台 ID：${lead.external_id || '未知'} · 源创建时间：${lead.source_created_at || '未知'} · 源更新时间：${lead.source_updated_at || '未知'} · 采集时间：${lead.source_captured_at || '未知'}`);
        const source = discoverySourceUrl(lead.source_url);
        row.appendChild(source ? createSourceLink(source, '打开来源页面，取得原文') : createSourceUnavailable('来源页面不可打开'));
        const toolbar = document.createElement('div');
        toolbar.className = 'discovery-toolbar';
        const download = document.createElement('button');
        download.type = 'button';
        download.className = 'btn btn-secondary btn-sm';
        download.textContent = '下载线索来源 JSON';
        download.onclick = () => { if (active() && token === revision) downloadSourceJson({ lead, summary: response.summary }, `mining-zhihu-lead-${index + 1}.json`); };
        const manual = document.createElement('button');
        manual.type = 'button';
        manual.className = 'btn btn-primary btn-sm';
        manual.disabled = !source;
        manual.textContent = '去导入页补充原文';
        manual.onclick = () => {
          if (!active() || token !== revision || !source) return;
          pendingSourceLead = { ...lead, source_url: source };
          location.hash = 'import';
        };
        toolbar.append(download, manual);
        row.appendChild(toolbar);
        find('leads').appendChild(row);
      });
    } catch (error) {
      if (active() && token === revision) find('error').textContent = `知乎检索失败：${error.message}。本次没有导入材料；可重试。`;
    } finally {
      if (active() && token === revision) {
        searching = false;
        update();
      }
    }
  };
  update();
  return loadStatus();
}

// Client-side guard mirrors the collector's narrow target surface. The server
// remains authoritative and rechecks the selected tab before every read.
