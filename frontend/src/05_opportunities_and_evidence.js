/* ==================================================== Page: Opportunities == */

// Kept only for this browser session; these previews never alter stored assets.
const opportunityDiscoverySession = { selected: new Map(), result: null, materials: [], decisions: [], requireUnmetEvidence: true };

function discoverySourceUrl(value) {
  try {
    const url = new URL(String(value || ''));
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
  } catch (_error) {
    return null;
  }
}

function renderOpportunityDiscovery(panel) {
  const session = opportunityDiscoverySession;
  const selected = session.selected;
  const pageSize = 20;
  let offset = 0;
  let rows = [];
  let loading = false;
  let generating = false;
  let hasNext = false;
  panel.innerHTML = `
    <h2 class="section-title">从真实材料发现产品机会</h2>
    <p class="discovery-hint">选择已导入的产品反馈，每批最多 30 条。结果是至多 3 个待验证的候选，也可能没有值得跟进的机会。</p>
    <p class="discovery-hint">还没有材料？先去<a href="#connectors">数据源</a>连接已登录 Chrome，预览国内社区原文并选择导入，也可在「导入反馈」录入原文或 JSON。这里只分析你勾选的材料。</p>
    <label class="community-material-select"><input data-role="require-unmet" type="checkbox" checked><span>只推荐有当前困难与尚存缺口依据的候选</span></label>
    <p class="discovery-hint" data-role="quality-note"></p>
    <div class="discovery-toolbar">
      <span data-role="count" aria-live="polite"></span>
      <button class="btn btn-secondary btn-sm" data-role="clear" type="button">清空选择</button>
      <button class="btn btn-secondary btn-sm" data-role="refresh" type="button">刷新材料 / 重试</button>
      <button class="btn btn-primary btn-sm" data-role="discover" type="button">发现机会</button>
    </div>
    <div data-role="error" class="discovery-error" role="alert"></div>
    <div data-role="materials" aria-live="polite"></div>
    <div class="discovery-toolbar">
      <button class="btn btn-secondary btn-sm" data-role="previous" type="button">上一页</button>
      <span data-role="page" class="discovery-hint"></span>
      <button class="btn btn-secondary btn-sm" data-role="next" type="button">下一页</button>
    </div>
    <div data-role="results" aria-live="polite"></div>
  `;
  const find = role => panel.querySelector(`[data-role="${role}"]`);
  const errorEl = find('error');
  const materialsEl = find('materials');
  const resultsEl = find('results');
  const escaped = value => escapeHtml(String(value ?? ''));
  const qualityControl = find('require-unmet');
  if (qualityControl) qualityControl.checked = session.requireUnmetEvidence !== false;

  function updateQualityNote() {
    const note = find('quality-note');
    if (note) note.textContent = qualityControl?.checked ? '严格候选预览：当前困难、明确剩余缺口都须有本批原文支持；已有办法若被提及也须有依据。角色归类仍为模型判断，语义待核实、市场未验证。切换后需重新点击「发现机会」。' : '宽松线索预览：未启用当前困难与尚存缺口门禁，可能包含已解决问题或产品能力复述；不代表值得开发。切换后需重新点击「发现机会」。';
  }

  function updateControls() {
    find('count').textContent = `已选 ${selected.size} / 30 条（跨页保留）`;
    find('clear').disabled = generating || selected.size === 0;
    find('refresh').disabled = loading || generating;
    find('discover').disabled = generating || loading || selected.size === 0;
    find('discover').textContent = generating ? '正在分析所选材料…' : '发现机会';
    find('previous').disabled = loading || generating || offset === 0;
    find('next').disabled = loading || generating || !hasNext;
    if (qualityControl) qualityControl.disabled = generating;
    materialsEl.querySelectorAll('input[type="checkbox"]').forEach(input => {
      input.disabled = generating || loading || (!input.checked && selected.size >= 30);
    });
  }

  function renderMaterials() {
    materialsEl.innerHTML = '';
    find('page').textContent = `第 ${Math.floor(offset / pageSize) + 1} 页 · 本页 ${rows.length} 条`;
    if (!rows.length) {
      materialsEl.innerHTML = '<p class="discovery-hint">本页暂无产品反馈。可返回上一页，或先在「数据导入」导入真实材料后刷新。</p>';
    }
    rows.forEach(fb => {
      const row = document.createElement('div');
      row.className = 'discovery-material';
      const label = document.createElement('label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = selected.has(fb.id);
      checkbox.onchange = () => {
        if (checkbox.checked && selected.size < 30) selected.set(fb.id, fb);
        else {
          selected.delete(fb.id);
          checkbox.checked = false;
        }
        updateControls();
      };
      const description = document.createElement('div');
      description.className = 'discovery-material-text';
      description.innerHTML = `<strong>${escaped(fb.subject || fb.text_preview || '无标题材料')}</strong>
        <p>${escaped(fb.text_preview || '')}</p>
        <span class="discovery-hint">${escaped(fb.source_type)} · 导入时间 ${escaped(fb.created_at || '未知')}</span>`;
      label.append(checkbox, description);
      row.appendChild(label);
      const source = document.createElement('div');
      source.innerHTML = sourceButtonHtml(discoverySourceUrl(fb.source_url), fb.external_url);
      row.appendChild(source);
      materialsEl.appendChild(row);
    });
    updateControls();
  }

  async function loadMaterials(nextOffset = offset) {
    loading = true;
    errorEl.textContent = '';
    updateControls();
    materialsEl.innerHTML = '<p class="discovery-hint">正在读取已导入的产品反馈…</p>';
    try {
      const data = await apiGet('/feedback', { profile: 'product_feedback', version_id: getSelectedVersion(), limit: pageSize + 1, offset: nextOffset });
      if (!panel.isConnected) return;
      if (!Array.isArray(data)) throw new Error('材料列表格式异常，请重试');
      offset = nextOffset;
      rows = data.slice(0, pageSize);
      hasNext = data.length > pageSize;
      renderMaterials();
    } catch (error) {
      if (!panel.isConnected) return;
      errorEl.textContent = `材料加载失败：${error.message}。点击「刷新材料 / 重试」可重试。`;
      renderMaterials();
    } finally {
      loading = false;
      if (panel.isConnected) updateControls();
    }
  }

  function exportResult() {
    const result = session.result;
    const lines = ['MINING 产品机会候选清单', '候选预览，未保存为机会资产；模型归纳与方案均待人工核实。',
      `质量模式：${result.require_unmet_evidence === true ? '严格候选预览（当前困难与尚存缺口门禁）' : '宽松 / 兼容线索预览（未启用缺口门禁）'}`,
      '语义待核实；市场未验证。结构与逐字匹配不能证明需求普遍、语义正确或付费意愿。',
      `选择 ${result.selected_count} 条；分析 ${result.analyzed_count} 条；完全相同原文重复 ${result.duplicate_count} 条。`,
      String(result.message || ''), '', '本批所选材料：'];
    session.materials.forEach((fb, index) => lines.push(`${index + 1}. ${fb.subject || fb.text_preview || fb.id}`, `来源：${discoverySourceUrl(fb.source_url) || fb.external_url || '未记录来源'}；ID：${fb.id}`));
    (result.candidates || []).slice(0, 3).forEach((candidate, index) => {
      const decision = session.decisions[index] || {};
      lines.push('', `候选 ${index + 1}：${candidate.title}`, '系统归纳与建议（推断）：',
        `人群：${candidate.user_segment}`, `场景：${candidate.scenario}`, `痛点：${candidate.pain_point}`,
        `最小设想：${candidate.minimum_idea}`, `提出理由：${candidate.reasoning}`, '原文依据：');
      (candidate.evidence || []).forEach(evidence => lines.push(`「${evidence.quote}」`,
        `来源：${discoverySourceUrl(evidence.source_url) || '来源不可打开'}；反馈 ID：${evidence.feedback_id}`,
        sourceEvidenceDescription(evidence), `证据元信息：${JSON.stringify(evidence)}`));
      const assessment = candidate.need_assessment;
      if (assessment) {
        lines.push(`缺口判断依据：${assessmentBasisLabel(assessment.basis)}（模型判断，语义待核实）`);
        for (const [role, label] of assessmentRoles()) {
          const part = assessment[role] || {};
          lines.push(`${label}：${part.statement || part.description || '未知 / 未提供'}${part.status ? `；状态：${assessmentStatusLabel(part.status)}` : ''}`);
          (part.evidence || []).forEach(evidence => lines.push(`${label}原话：「${evidence.quote}」`, `来源：${discoverySourceUrl(evidence.source_url) || '来源不可打开'}；反馈 ID：${evidence.feedback_id}`, sourceEvidenceDescription(evidence), `角色证据元信息：${JSON.stringify(evidence)}`));
        }
      } else lines.push('缺口评估：未提供结构化角色依据，不代表已核实当前需求。');
      lines.push('待验证问题：', ...(candidate.validation_questions || []).map(question => `- ${question}`),
        `我的判断：${decision.action || '尚未判断'}`, `原因 / 下一步：${decision.note || '未填写'}`);
    });
    lines.push('', '限制：', ...(result.limitations || []));
    (result.excluded || []).forEach(item => lines.push(`排除：${item.feedback_id || (item.candidate_index == null ? '材料 / 候选' : `候选 ${item.candidate_index}`)}；${item.reason}`));
    const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'mining-opportunity-candidates.txt';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function renderResults() {
    const result = session.result;
    resultsEl.innerHTML = '';
    if (!result) return;
    const summary = document.createElement('div');
    summary.className = 'discovery-summary';
    summary.innerHTML = `<h3>本次候选预览 · 未保存为机会资产</h3>
      <p>${escaped(result.message || '')}</p>
      <p class="discovery-hint">本次质量模式：${result.require_unmet_evidence === true ? '严格候选预览（当前困难与尚存缺口门禁）' : '宽松 / 兼容线索预览（未启用缺口门禁）'}。语义待核实，市场未验证。</p>
      <p class="discovery-hint">选择 ${escaped(result.selected_count)} 条；分析 ${escaped(result.analyzed_count)} 条；完全相同原文重复 ${escaped(result.duplicate_count)} 条。调整材料后需重新点击「发现机会」。</p>
      <p class="discovery-hint">本结果仅做文本归纳，未进行语义去重或市场验证。人群、场景与痛点也是模型归纳，请核对原话；不能据此认定需求普遍或用户愿意付费。</p>
      <p class="discovery-hint">人工判断仅保留在当前浏览器页面中，刷新或关闭页面会丢失，请先导出清单。</p>`;
    const exportButton = document.createElement('button');
    exportButton.type = 'button';
    exportButton.className = 'btn btn-secondary btn-sm';
    exportButton.textContent = '下载候选与人工判断清单';
    exportButton.onclick = exportResult;
    summary.appendChild(exportButton);
    resultsEl.appendChild(summary);
    const candidates = (result.candidates || []).slice(0, 3);
    if (!candidates.length) {
      const empty = document.createElement('p');
      empty.className = 'discovery-hint';
      empty.textContent = '本批暂无值得跟进的机会。可补充更具体的困难、现有替代做法及原文来源后重新分析。';
      resultsEl.appendChild(empty);
    }
    candidates.forEach((candidate, index) => {
      const card = document.createElement('article');
      card.className = 'card discovery-candidate';
      card.innerHTML = `<h3>${index + 1}. ${escaped(candidate.title)}</h3>
        <div data-need-assessment="panel"></div>
        <section><h4>原文依据</h4>${(candidate.evidence || []).map((evidence, evidenceIndex) => `
          <div data-source-evidence="${evidenceIndex}">
          <blockquote class="evidence-quote">${escaped(evidence.quote)}</blockquote>
          <div class="discovery-hint">${escaped(evidence.source_type)} · ${escaped(evidence.feedback_id)} · 引文匹配字段：${escaped(evidence.quote_field || '未记录')}${evidence.source_created_at ? ` · 源创建时间 ${escaped(evidence.source_created_at)}` : ''}${evidence.source_captured_at ? ` · 采集时间 ${escaped(evidence.source_captured_at)}` : ''}</div>
          ${sourceButtonHtml(discoverySourceUrl(evidence.source_url), evidence.external_url, sourceEvidenceLinkLabel(evidence))}</div>`).join('')}</section>
        <section><h4>系统归纳与建议（推断，待确认）</h4>
          <p><strong>目标人群：</strong>${escaped(candidate.user_segment)}</p>
          <p><strong>使用场景：</strong>${escaped(candidate.scenario)}</p>
          <p><strong>具体痛点：</strong>${escaped(candidate.pain_point)}</p>
          <p><strong>最小产品 / 功能设想：</strong>${escaped(candidate.minimum_idea)}</p>
          <p><strong>提出理由：</strong>${escaped(candidate.reasoning)}</p></section>
        <section><h4>待验证问题</h4><ul>${(candidate.validation_questions || []).map(question => `<li>${escaped(question)}</li>`).join('')}</ul></section>`;
      (candidate.evidence || []).forEach((evidence, evidenceIndex) => {
        appendSourceSnapshot(card.querySelector(`[data-source-evidence="${evidenceIndex}"]`), evidence.feedback_id, evidence);
      });
      renderNeedAssessment(card, candidate.need_assessment);
      const review = document.createElement('section');
      review.className = 'discovery-review';
      review.innerHTML = '<h4>我的判断（仅本次会话）</h4>';
      const decision = session.decisions[index] || { action: '', note: '' };
      session.decisions[index] = decision;
      const actionLabel = document.createElement('label');
      actionLabel.className = 'form-label';
      actionLabel.textContent = '后续行动';
      const select = document.createElement('select');
      select.className = 'form-select';
      ['', '继续找用户了解', '做一个小原型', '放弃'].forEach(action => {
        const option = document.createElement('option');
        option.value = action;
        option.textContent = action || '尚未判断';
        select.appendChild(option);
      });
      select.value = decision.action;
      select.onchange = () => { decision.action = select.value; };
      actionLabel.appendChild(select);
      const noteLabel = document.createElement('label');
      noteLabel.className = 'form-label';
      noteLabel.textContent = '判断原因 / 下一步要验证什么';
      const note = document.createElement('textarea');
      note.className = 'form-textarea';
      note.rows = 2;
      note.value = decision.note;
      note.oninput = () => { decision.note = note.value; };
      noteLabel.appendChild(note);
      review.append(actionLabel, noteLabel);
      card.appendChild(review);
      resultsEl.appendChild(card);
    });
    const notices = document.createElement('div');
    notices.className = 'discovery-hint';
    notices.innerHTML = (result.limitations || []).map(item => `<p>限制：${escaped(item)}</p>`).join('') +
      (result.excluded || []).map(item => `<p>已排除 ${escaped(item.feedback_id || (item.candidate_index == null ? '材料 / 候选' : `候选 ${item.candidate_index}`))}：${escaped(item.reason)}</p>`).join('');
    resultsEl.appendChild(notices);
  }

  function assessmentRoles() { return [['current_difficulty', '当前困难'], ['current_solution', '已有办法'], ['remaining_gap', '尚存缺口']]; }
  function assessmentStatusLabel(value) { return { mentioned: '原文已提及', unknown: '未知', explicit: '原文明确不足', already_addressed: '原文显示已解决' }[value] || '未知'; }
  function assessmentBasisLabel(value) { return { current_complaint: '当前困难 / 抱怨', feature_request: '直接功能请求', historical_resolved: '历史困难已解决', solution_praise: '现有方案赞美', unknown: '未知' }[value] || '未知'; }
  function renderNeedAssessment(card, assessment) {
    const target = card.querySelector('[data-need-assessment="panel"]') || card;
    const section = document.createElement('section');
    const title = document.createElement('h4'); title.textContent = '当前困难与尚存缺口（模型判断，语义待核实）'; section.appendChild(title);
    if (!assessment) {
      const note = document.createElement('p'); note.className = 'discovery-hint'; note.textContent = '未提供结构化角色依据；这是宽松 / 兼容线索，不代表当前仍有未满足需求。'; section.appendChild(note); target.appendChild(section); return;
    }
    const basis = document.createElement('p'); basis.className = 'discovery-hint'; basis.textContent = `判断依据：${assessmentBasisLabel(assessment.basis)}。市场未验证。`; section.appendChild(basis);
    for (const [role, label] of assessmentRoles()) {
      const part = assessment[role] || {}, block = document.createElement('div');
      const heading = document.createElement('p'); const strong = document.createElement('strong'); strong.textContent = `${label}：`; heading.appendChild(strong);
      const description = document.createElement('span'); description.textContent = `${part.statement || part.description || '未知 / 未提供'}${part.status ? `（${assessmentStatusLabel(part.status)}）` : ''}`; heading.appendChild(description); block.appendChild(heading);
      const evidenceList = Array.isArray(part.evidence) ? part.evidence : [];
      if (!evidenceList.length) { const note = document.createElement('p'); note.className = 'discovery-hint'; note.textContent = '该角色未提供本批原话；未知内容不能据此补全。'; block.appendChild(note); }
      evidenceList.forEach(evidence => {
        const quote = document.createElement('blockquote'); quote.className = 'evidence-quote'; quote.textContent = evidence.quote; block.appendChild(quote);
        const meta = document.createElement('p'); meta.className = 'discovery-hint'; meta.textContent = `${evidence.source_type || '未知来源'} · ${evidence.feedback_id || '未知反馈 ID'} · 引文匹配字段：${evidence.quote_field || '未记录'}`; block.appendChild(meta);
        block.appendChild(createSourceLink(evidence.source_url, sourceEvidenceLinkLabel(evidence)));
        appendSourceSnapshot(block, evidence.feedback_id, evidence);
      });
      section.appendChild(block);
    }
    target.appendChild(section);
  }

  find('clear').onclick = () => { selected.clear(); renderMaterials(); };
  find('refresh').onclick = () => loadMaterials();
  find('previous').onclick = () => loadMaterials(Math.max(0, offset - pageSize));
  find('next').onclick = () => loadMaterials(offset + pageSize);
  if (qualityControl) qualityControl.onchange = () => { if (generating) return; session.requireUnmetEvidence = qualityControl.checked; updateQualityNote(); };
  find('discover').onclick = async () => {
    if (!selected.size || selected.size > 30 || generating) return;
    generating = true;
    errorEl.textContent = '';
    updateControls();
    const materials = [...selected.values()];
    const requireUnmet = qualityControl?.checked === true;
    try {
      const request = { feedback_ids: materials.map(fb => fb.id) };
      if (qualityControl) request.require_unmet_evidence = requireUnmet;
      const result = await apiPost('/opportunities/discover', request);
      if (!panel.isConnected || getSelectedProfile() !== 'product_feedback' || session.selected !== selected) return;
      if (requireUnmet && result.require_unmet_evidence !== true) throw new Error('服务未确认当前困难与尚存缺口门禁已启用，请检查版本后重试');
      if (requireUnmet && (!Array.isArray(result.candidates) || result.candidates.some(candidate => !candidate.need_assessment))) throw new Error('严格候选缺少结构化角色依据，未展示为推荐结果');
      session.result = result;
      session.materials = materials;
      session.decisions = [];
      if (panel.isConnected) renderResults();
    } catch (error) {
      if (panel.isConnected) errorEl.textContent = `机会发现失败：${error.message}。选择已保留，可再次点击「发现机会」重试；下方已有结果属于上一次分析。`;
    } finally {
      generating = false;
      if (panel.isConnected) updateControls();
    }
  };
  updateQualityNote();
  renderResults();
  loadMaterials();
}

async function renderOpportunitiesPage(container) {
  const profile = getSelectedProfile();
  container.innerHTML = `${profile === 'product_feedback' ? '<section class="card discovery-panel" id="opp-discovery"></section><h2 class="section-title">历史机会资产</h2><p class="discovery-hint">以下为既有管线生成的历史资产，机器处理状态不代表人工已审核。</p>' : ''}<div id="opp-list"></div>`;
  if (profile === 'product_feedback') renderOpportunityDiscovery(container.querySelector('#opp-discovery'));
  const listEl = container.querySelector('#opp-list');
  showSkeleton(listEl, 4);
  try {
    const data = await apiGet('/opportunities', { limit: 50, profile: getSelectedProfile(), version_id: getSelectedVersion() });
    listEl.innerHTML = '';
    if (!data.length) return showEmpty(listEl, '💡', '暂无历史机会资产', profile === 'product_feedback' ? '可先在上方选择真实材料，预览本批候选机会' : '运行管线以识别产品机会');

    data.forEach(opp => {
      // Build card manually to hook into expand for lazy-load
      const card = document.createElement('div');
      card.className = 'card card-expandable';

      const header = document.createElement('div');
      header.className = 'card-header';
      header.innerHTML = `<div class="card-title">${escapeHtml(opp.jtbd_statement)}</div>`;

      const toggle = document.createElement('button');
      toggle.className = 'expand-toggle';
      toggle.innerHTML = '▼';

      const body = document.createElement('div');
      body.className = 'card-body';
      body.innerHTML = `<p>${escapeHtml(opp.description)}</p>
         ${(opp.assumptions || []).map(a => `<div style="margin:4px 0;color:var(--warning)">⚠ 假设: ${escapeHtml(a)}</div>`).join('')}
         <div style="margin-top:8px;font-size:12px;color:var(--text-muted)">优先级: ${escapeHtml(JSON.stringify(opp.priority))}</div>
         <div class="opp-evidence-placeholder" id="opp-ev-${opp.id}" style="margin-top:12px"></div>`;

      let evidenceLoaded = false;
      toggle.onclick = async () => {
        card.classList.toggle('expanded');
        toggle.classList.toggle('open');

        // Lazy-load supporting evidence on first expand
        if (!evidenceLoaded && card.classList.contains('expanded')) {
          evidenceLoaded = true;
          const placeholder = document.getElementById(`opp-ev-${opp.id}`);
          if (placeholder) {
            placeholder.innerHTML = '<div class="skeleton skeleton-row" style="height:40px"></div>';
            try {
              const detail = await apiGet(`/opportunities/${opp.id}`);
              const evidence = detail.supporting_evidence || [];
              if (evidence.length) {
                let evHtml = '<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border)"><strong>📎 支撑证据链:</strong></div>';
                evidence.forEach(ev => {
                  const quote = ev.quote || ev.signal_summary || '';
                  const srcType = ev.source_type || '';
                  const sigId = ev.signal_id || '';
                  evHtml += `<div style="margin:6px 0;font-size:13px">💬 <em>${escapeHtml(quote)}</em></div>
                    <div style="font-size:11px;color:var(--text-muted);margin-bottom:2px">Signal: ${escapeHtml(sigId)} [${escapeHtml(srcType)}]${ev.author_segment ? ' · ' + escapeHtml(ev.author_segment) : ''}</div>`;
                  evHtml += sourceStatusHtml(ev.source_url, ev.external_url, '查看原始来源');
                });
                placeholder.innerHTML = evHtml;
              } else {
                placeholder.innerHTML = '<div style="font-size:12px;color:var(--text-muted);margin-top:8px">暂无支撑证据</div>';
              }
            } catch (e) {
              placeholder.innerHTML = `<div style="color:var(--danger);font-size:12px">加载失败: ${escapeHtml(e.message)}</div>`;
            }
          }
        }
      };

      header.appendChild(toggle);
      card.appendChild(header);
      card.appendChild(body);
      listEl.appendChild(card);
    });
  } catch (e) { showToast(`加载失败: ${e.message}`, 'danger'); }
}

/* ==================================================== Page: Requirements ==== */

async function renderRequirementsPage(container) {
  container.innerHTML = '<div id="req-list"></div>';
  const listEl = document.getElementById('req-list');
  showSkeleton(listEl, 3);
  try {
    const data = await apiGet('/requirements', { limit: 50, profile: getSelectedProfile(), version_id: getSelectedVersion() });
    listEl.innerHTML = '';
    if (!data.length) return showEmpty(listEl, '📝', '暂无需求候选', '运行管线以生成需求资产');

    data.forEach(req => {
      const stories = (req.user_stories || []).map(s =>
        `<tr><td>${escapeHtml(s.role || '')}</td><td>${escapeHtml(s.action || '')}</td><td>${escapeHtml(s.benefit || '')}</td></tr>`
      ).join('');

      // Build evidence chain preview
      const evidenceCount = (req.evidence_trail || []).length;
      const evPreview = evidenceCount > 0
        ? `<span class="badge badge-info">📎 ${evidenceCount} 条证据</span>`
        : '<span class="badge badge-default">无证据</span>';
      const safeReqId = escapeHtml(String(req.id || ''));

      const card = createExpandableCard(
        `<div style="flex:1">
          <div class="card-title">${escapeHtml(req.title || '')}</div>
          <div class="card-subtitle">${(req.acceptance_criteria || []).length} 条验收标准 · ${stories ? '含用户故事' : '无用户故事'}</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px">${evPreview}<button class="btn btn-sm btn-secondary btn-evidence-trace" type="button" title="查看证据链">🔗 追溯</button></div>`,
        `<div class="section-title" style="font-size:14px">📋 用户故事</div>
         <div class="table-container"><table class="table"><thead><tr><th>角色</th><th>行为</th><th>价值</th></tr></thead><tbody>${stories || '<tr><td colspan="3">—</td></tr>'}</tbody></table></div>
         <div class="section-title" style="font-size:14px;margin-top:16px">✅ 验收标准</div>
         <ul style="padding-left:20px">${(req.acceptance_criteria || []).map(a => `<li style="margin-bottom:4px">${escapeHtml(a)}</li>`).join('') || '<li>—</li>'}</ul>
         ${req.decision_reasoning ? `<div class="section-title" style="font-size:14px;margin-top:16px">🧠 决策理由</div><p>${escapeHtml(req.decision_reasoning)}</p>` : ''}
         <div id="evidence-chain-${safeReqId}" style="margin-top:16px"></div>`
      );
      const traceBtn = card.querySelector('.btn-evidence-trace');
      if (traceBtn) {
        traceBtn.onclick = (e) => { e.stopPropagation(); window.loadEvidenceChain(String(req.id || ''), traceBtn); };
      }
      listEl.appendChild(card);
    });
  } catch (e) { showToast(`加载失败: ${e.message}`, 'danger'); }
}

/* ==================================================== Evidence Chain ======== */

function revealEvidenceChainContainer(container) {
  const card = container.closest('.card-expandable');
  if (!card) return;
  card.classList.add('expanded');
  const toggle = card.querySelector('.expand-toggle');
  if (toggle) toggle.classList.add('open');
}

window.loadEvidenceChain = async function (reqId, trigger) {
  const container = document.getElementById(`evidence-chain-${reqId}`);
  if (!container) return;
  revealEvidenceChainContainer(container);
  if (container.dataset.loaded === 'true') {
    container.scrollIntoView({ block: 'nearest' });
    return;
  }
  if (container.dataset.loading === 'true') return;

  container.dataset.loading = 'true';
  const originalTriggerText = trigger?.textContent;
  if (trigger) {
    trigger.disabled = true;
    trigger.textContent = '⏳ 加载中';
  }
  container.innerHTML = '<div class="skeleton skeleton-row" style="height:60px"></div><div class="skeleton skeleton-row" style="height:60px"></div>';
  try {
    const data = await apiGet(`/requirements/${reqId}/evidence-trail`);
    container.innerHTML = '';

    const links = data.evidence_links || [];
    if (!links.length) {
      container.innerHTML = '<p style="color:var(--text-muted);padding:12px">暂无证据链数据</p>';
      container.dataset.loaded = 'true';
      return;
    }

    const chain = document.createElement('div');
    chain.className = 'evidence-chain';

    // Requirement header
    const reqNode = document.createElement('div');
    reqNode.className = 'evidence-node level-requirement';
    reqNode.innerHTML = `<div class="evidence-node-header">📝 需求: ${escapeHtml(data.title || '')}</div>`;
    chain.appendChild(reqNode);

    links.forEach(link => {
      const node = document.createElement('div');
      node.className = `evidence-node level-signal`;
      const conf = Number(link.confidence) || 0;
      const confColor = confidenceColor(conf);
      node.innerHTML = `
        <div class="evidence-node-header">
          🔬 <span style="flex:1">${escapeHtml(link.signal_summary || '信号')}</span>
          <span class="badge" style="color:${confColor};background:${confColor}15">模型自评 ${conf.toFixed(2)}</span>
        </div>
        <div class="evidence-node-body">
          <div><strong>类型:</strong> ${escapeHtml(link.signal_type || '—')} · <strong>来源:</strong> ${escapeHtml(link.source_type || '—')}</div>
          ${link.author_segment ? `<div><strong>用户:</strong> ${escapeHtml(link.author_segment)}</div>` : ''}
          ${link.quote ? `<div class="evidence-quote">«${escapeHtml(link.quote)}»</div>` : ''}
          <div style="margin-top:4px;font-size:11px;color:var(--text-muted)">
            ${link.raw_feedback_preview ? `原文预览: ${escapeHtml(link.raw_feedback_preview.slice(0, 100))}…` : ''}
          </div>
        </div>
      `;

      // Append source state if available.
      const bodyEl = node.querySelector('.evidence-node-body');
      if (bodyEl) {
        appendSourceStatus(bodyEl, link.source_url, link.external_url, '查看原始来源');
      }

      chain.appendChild(node);
    });

    // Validation summary
    const validation = data.validation || {};
    const validBadge = validation.is_valid
      ? '<span class="badge badge-success">✅ 证据链完整</span>'
      : `<span class="badge badge-warning">⚠ ${validation.broken_links?.length || 0} 个断裂链接</span>`;

    const valNode = document.createElement('div');
    valNode.style.cssText = 'padding:12px;margin-top:8px;font-size:13px;';
    valNode.innerHTML = `${validBadge} ${validation.total_links || 0} 条证据，${validation.valid_links || 0} 条有效`;
    chain.appendChild(valNode);

    container.appendChild(chain);
    container.dataset.loaded = 'true';
  } catch (e) {
    container.innerHTML = `<p style="color:var(--danger)">证据链加载失败: ${escapeHtml(e.message || String(e))}</p>`;
  } finally {
    delete container.dataset.loading;
    if (trigger) {
      trigger.disabled = false;
      trigger.textContent = originalTriggerText || '🔗 追溯';
    }
  }
};

