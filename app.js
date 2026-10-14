const state = {
  sources: [],
  allResults: [],
  visibleResults: [],
  sourceStatuses: [],
  query: null,
  loading: false,
  deepseek: { configured: false, max_items: 20, model: "deepseek-chat" },
  deepseekSearchEnabled: false,
  deepseekToggleTouched: false,
  abortController: null,
  cancelled: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
const elements = {
  form: $("#searchForm"), keywords: $("#keywords"), fromYear: $("#fromYear"),
  toYear: $("#toYear"), maxResults: $("#maxResults"), sourceGrid: $("#sourceGrid"),
  sourceCount: $("#sourceCount"), searchBtn: $("#searchBtn"), resetBtn: $("#resetBtn"),
  formHint: $("#formHint"), selectAllSources: $("#selectAllSources"),
  clearSources: $("#clearSources"), searchPanel: $("#searchPanel"),
  translationHint: $("#translationHint"),
  queryExpansionList: $("#queryExpansionList"), summarySection: $("#summarySection"),
  summaryTotal: $("#summaryTotal"), summaryRaw: $("#summaryRaw"),
  summaryAbstract: $("#summaryAbstract"), summaryOpen: $("#summaryOpen"),
  sourceStatusList: $("#sourceStatusList"), elapsedText: $("#elapsedText"),
  resultsSection: $("#resultsSection"), resultCount: $("#resultCount"),
  resultsBody: $("#resultsBody"), tableEmpty: $("#tableEmpty"),
  filterInput: $("#filterInput"), sourceFilter: $("#sourceFilter"),
  sortSelect: $("#sortSelect"), exportBtn: $("#exportBtn"),
  summarizeBtn: $("#summarizeBtn"), deepseekKeyPanel: $("#deepseekKeyPanel"),
  deepseekKeyStatus: $("#deepseekKeyStatus"), deepseekApiKey: $("#deepseekApiKey"),
  toggleDeepseekKey: $("#toggleDeepseekKey"), deepseekModel: $("#deepseekModel"),
  saveDeepseekKey: $("#saveDeepseekKey"), deepseekSearchToggle: $("#deepseekSearchToggle"),
  deepseekConnectedInfo: $("#deepseekConnectedInfo"), changeDeepseekKey: $("#changeDeepseekKey"),
  cancelBtn: $("#cancelBtn"),
  selectedSourceCount: $("#selectedSourceCount"), searchProgress: $("#searchProgress"),
  matchScope: $("#matchScope"), excludeKeywords: $("#excludeKeywords"),
  onlyAbstract: $("#onlyAbstract"), onlyOpenAccess: $("#onlyOpenAccess"), onlyDoi: $("#onlyDoi"),
  toast: $("#toast"),
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}

function escapeRegex(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function queryVariants() {
  const groups = state.query?.query_terms || [];
  const variants = [];
  groups.forEach((group) => (group.variants || []).forEach((value) => {
    const text = String(value || "").trim();
    if (text && !variants.includes(text)) variants.push(text);
  }));
  return variants.sort((a, b) => b.length - a.length);
}

function regexForVariant(value) {
  const escaped = escapeRegex(value);
  if (/^[A-Za-z0-9][A-Za-z0-9 ._-]*$/.test(value)) {
    return `(?<![A-Za-z0-9])${escaped}(?![A-Za-z0-9])`;
  }
  return escaped;
}

function highlightTitle(value) {
  const text = String(value ?? "");
  const variants = queryVariants();
  if (!text || !variants.length) return escapeHtml(text);
  const pattern = new RegExp(`(${variants.map(regexForVariant).join("|")})`, "giu");
  let result = "";
  let position = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    result += escapeHtml(text.slice(position, start));
    result += `<mark class="title-hit">${escapeHtml(match[0])}</mark>`;
    position = start + match[0].length;
  }
  if (!result) return escapeHtml(text);
  result += escapeHtml(text.slice(position));
  return result;
}

function safeUrl(value) {
  const text = String(value ?? "").trim();
  return /^https?:\/\//i.test(text) ? text : "";
}

function formatNumber(value, digits = 0) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return number.toLocaleString("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function formatMetric(value, digits = 0) {
  if (value === null || value === undefined || value === "") return '<span class="metric-muted">—</span>';
  return `<span class="metric-value">${formatNumber(value, digits)}</span>`;
}

function sourceNames(item) {
  if (Array.isArray(item.sources) && item.sources.length) return item.sources;
  return item.source ? [item.source] : [];
}

function updateDeepSeekToggle() {
  const configured = Boolean(state.deepseek.configured);
  elements.deepseekSearchToggle.disabled = !configured;
  elements.deepseekSearchToggle.classList.toggle("active", configured && state.deepseekSearchEnabled);
  elements.searchPanel.classList.toggle("ai-search-active", configured && state.deepseekSearchEnabled);
  if (!configured) {
    elements.deepseekSearchToggle.textContent = "DeepSeek 选词：未配置";
    elements.deepseekSearchToggle.title = "请先在页面顶部配置 DeepSeek API Key";
  } else {
    elements.deepseekSearchToggle.textContent = `DeepSeek 选词：${state.deepseekSearchEnabled ? "已开启" : "已关闭"}`;
    elements.deepseekSearchToggle.title = state.deepseekSearchEnabled
      ? "本次检索会使用 DeepSeek 选择的扩展词"
      : "本次检索不会使用 DeepSeek 选词";
  }
}

function updateDeepSeekUI(status) {
  state.deepseek = { ...state.deepseek, ...(status || {}) };
  const configured = Boolean(state.deepseek.configured);
  elements.deepseekKeyPanel.classList.toggle("deepseek-configured", configured);
  $("#aiConnectionLabel").textContent = configured ? "已连接 · AI 选词与摘要概括可用" : "可选配置 · 启用选词与摘要概括";
  if (!configured) elements.deepseekKeyPanel.classList.remove("editing");
  elements.deepseekKeyStatus.textContent = configured
    ? `已连接：${state.deepseek.key_hint || "Key 已保存"} · 模型：${state.deepseek.model}`
    : "未配置，输入 Key 后即可使用 AI 选词与摘要概括";
  elements.deepseekConnectedInfo.textContent = configured
    ? `${state.deepseek.key_hint || "Key 已保存"} · ${state.deepseek.model} · AI 能力已启用`
    : "";
  elements.deepseekApiKey.placeholder = configured ? "已配置，输入新 Key 可替换" : "输入 sk-...";
  elements.saveDeepseekKey.textContent = configured ? "更新 Key" : "保存 Key";
  if (state.deepseek.model) {
    const exists = Array.from(elements.deepseekModel.options).some((option) => option.value === state.deepseek.model);
    if (!exists) {
      const option = document.createElement("option");
      option.value = state.deepseek.model;
      option.textContent = state.deepseek.model;
      elements.deepseekModel.appendChild(option);
    }
    elements.deepseekModel.value = state.deepseek.model;
  }
  if (configured && !state.deepseekToggleTouched) {
    state.deepseekSearchEnabled = true;
  }
  if (!configured) {
    state.deepseekSearchEnabled = false;
  }
  updateDeepSeekToggle();
  elements.summarizeBtn.disabled = !configured || !state.visibleResults.length;
  elements.summarizeBtn.title = configured
    ? `使用 ${state.deepseek.model} 概括当前最多 ${state.deepseek.max_items} 条摘要`
    : "请先在页面顶部配置 DEEPSEEK_API_KEY";
}

async function saveDeepSeekConfig() {
  const apiKey = elements.deepseekApiKey.value.trim();
  if (!apiKey) {
    showToast("请输入 DeepSeek API Key。", true);
    elements.deepseekApiKey.focus();
    return;
  }
  const originalText = elements.saveDeepseekKey.textContent;
  elements.saveDeepseekKey.disabled = true;
  elements.saveDeepseekKey.textContent = "保存中…";
  try {
    const status = await requestJson("/api/deepseek/config", {
      method: "POST",
      body: JSON.stringify({
        api_key: apiKey,
        model: elements.deepseekModel.value,
      }),
    });
    updateDeepSeekUI(status);
    elements.deepseekKeyPanel.classList.remove("editing");
    elements.deepseekApiKey.value = "";
    showToast("DeepSeek API Key 已保存并启用。");
  } catch (error) {
    showToast(error.message || "保存 DeepSeek API Key 失败", true);
  } finally {
    elements.saveDeepseekKey.disabled = false;
    elements.saveDeepseekKey.textContent = state.deepseek.configured ? "更新 Key" : originalText;
  }
}

function showToast(message, isError = false) {
  elements.toast.textContent = message;
  elements.toast.className = `toast show${isError ? " error" : ""}`;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => { elements.toast.className = "toast"; }, 3600);
}

function setLoading(loading) {
  state.loading = loading;
  elements.searchProgress.hidden = !loading;
  elements.form.setAttribute("aria-busy", String(loading));
  elements.resetBtn.disabled = loading;
  elements.searchBtn.disabled = loading;
  elements.searchBtn.classList.toggle("loading", loading);
  elements.searchBtn.querySelector(".btn-text").textContent = loading ? "检索中…" : "开始检索";
  elements.cancelBtn.disabled = !loading;
  elements.cancelBtn.title = loading ? "点击终止本次检索" : "检索进行中可点击终止";
  if (loading) {
    elements.formHint.textContent = "";
    state.cancelled = false;
  }
}

function selectedSources() {
  return $$('input[name="source_id"]:checked').map((input) => input.value);
}

const sourcePresets = {
  general: ["openalex", "crossref"],
  computing: ["openalex", "arxiv", "semantic_scholar"],
  medical: ["pubmed", "europe_pmc", "crossref"],
};

function updateSourceSelection() {
  const selected = selectedSources();
  elements.selectedSourceCount.textContent = `已选 ${selected.length} 个`;
  $$("[data-preset]").forEach((button) => {
    const preset = button.dataset.preset === "all" ? state.sources.map((source) => source.id) : sourcePresets[button.dataset.preset];
    button.setAttribute("aria-pressed", String(Boolean(preset?.length) && preset.length === selected.length && preset.every((id) => selected.includes(id))));
  });
}

function renderSources(sources) {
  state.sources = sources;
  elements.sourceCount.textContent = sources.length;
  const defaults = new Set(["openalex", "crossref"]);
  elements.sourceGrid.innerHTML = sources.map((source) => `
    <label class="source-card">
      <input type="checkbox" name="source_id" value="${escapeHtml(source.id)}" ${defaults.has(source.id) ? "checked" : ""}>
      <span class="source-card-content">
        <span class="source-name">${escapeHtml(source.name)}</span>
        <span class="source-desc">${escapeHtml(source.description)}</span>
        <span class="source-tags">${(source.capabilities || []).map((tag) => `<span class="source-tag">${escapeHtml(tag)}</span>`).join("")}</span>
      </span>
    </label>
  `).join("");
  updateSourceSelection();
}

function renderStatuses(statuses, elapsedMs) {
  state.sourceStatuses = statuses || [];
  const success = state.sourceStatuses.filter((item) => item.status === "ok").length;
  elements.elapsedText.textContent = `${success}/${state.sourceStatuses.length} 个数据源成功 · ${elapsedMs || 0} ms`;
  elements.sourceStatusList.innerHTML = state.sourceStatuses.map((item) => `
    <div class="status-item ${item.status === "ok" ? "ok" : "error"}">
      <span class="status-dot"></span>
      <span>
        <span class="status-name">${escapeHtml(item.name || item.id)}</span>
        <span class="status-detail">${escapeHtml(item.message || "")}${item.elapsed_ms !== undefined ? ` · ${item.elapsed_ms} ms` : ""}</span>
      </span>
    </div>
  `).join("");
}

function renderQueryExpansion(query) {
  const groups = query.query_terms || [];
  const translationSources = [];
  groups.forEach((group) => (group.translation_sources || []).forEach((source) => {
    if (!translationSources.includes(source)) translationSources.push(source);
  }));
  const validation = query.deepseek_term_selection?.validation;
  const validationLabel = validation === "semantic_complete" ? " · 已完成语义完整性校验" : "";
  elements.translationHint.textContent = translationSources.length
    ? `扩展来源：${translationSources.join(" + ")}${validationLabel}`
    : "未检测到需要扩展的关键词";
  const deepseekWarnings = query.deepseek_term_warnings || [];
  elements.queryExpansionList.innerHTML = groups.map((group) => {
    const variants = group.variants || [];
    const variantSources = group.variant_sources || {};
    const warnings = group.translation_warnings || [];
    return `
      <div class="query-term-group">
        <div>
          <span class="query-term-source">${escapeHtml(group.keyword || "")}</span>
          <span class="query-term-meta">${variants.length} 个检索变体</span>
        </div>
        <div>
          <div class="query-term-variants">
            ${variants.map((value) => {
              const sources = variantSources[value] || [];
              const isDeepSeek = sources.includes("DeepSeek");
              const label = sources.length ? ` title="${escapeHtml(sources.join(" + "))}"` : "";
              return `<span class="query-variant ${value === group.keyword ? "original" : ""} ${isDeepSeek ? "deepseek-term" : ""}"${label}>${escapeHtml(value)}${isDeepSeek ? '<span class="term-source">DeepSeek</span>' : ""}</span>`;
            }).join("")}
          </div>
          ${warnings.length ? `<div class="translation-warning">${warnings.map(escapeHtml).join("；")}</div>` : ""}
        </div>
      </div>
    `;
  }).join("") + (deepseekWarnings.length
    ? `<div class="translation-warning">DeepSeek 选词失败，已改用本地词库继续检索：${deepseekWarnings.map(escapeHtml).join("；")}</div>`
    : "");
}

function renderSummary(data) {
  const results = data.results || [];
  const abstractCount = results.filter((item) => item.abstract).length;
  const openCount = results.filter((item) => item.open_access === true).length;
  elements.summaryTotal.textContent = formatNumber(results.length);
  elements.summaryRaw.textContent = formatNumber(data.raw_total || 0);
  elements.summaryAbstract.textContent = formatNumber(abstractCount);
  elements.summaryOpen.textContent = formatNumber(openCount);
  elements.summarySection.hidden = false;
  renderStatuses(data.sources || [], data.elapsed_ms);
}

function renderSourceFilter(results) {
  const names = [];
  results.forEach((item) => sourceNames(item).forEach((name) => {
    if (!names.includes(name)) names.push(name);
  }));
  const current = elements.sourceFilter.value;
  elements.sourceFilter.innerHTML = '<option value="">全部来源</option>' +
    names.sort().map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
  if (names.includes(current)) elements.sourceFilter.value = current;
}

function ensureResultUids(results) {
  results.forEach((item, index) => {
    if (!item._uid) {
      item._uid = `paper-${Date.now()}-${index}-${Math.random().toString(36).slice(2, 8)}`;
    }
  });
}

function aiSummaryMarkup(item) {
  if (item.summary_zh) {
    return `<div class="ai-summary"><span class="ai-badge">DeepSeek</span><span>${escapeHtml(item.summary_zh)}</span></div>`;
  }
  if (item.summary_status === "error") {
    return `<div class="ai-summary error"><span class="ai-badge">DeepSeek</span><span>概括失败：${escapeHtml(item.summary_error || "未知错误")}</span></div>`;
  }
  return "";
}

function abstractMarkup(item, id) {
  const text = String(item.abstract || "").trim();
  if (!text) return '<p class="paper-abstract metric-muted">暂无摘要</p>';
  const long = text.length > 210;
  if (!long) return `<p class="paper-abstract">${escapeHtml(text)}</p>`;
  return `<p class="paper-abstract collapsed" data-abstract-wrapper="${id}"><span class="abstract-preview">${escapeHtml(text.slice(0, 210))}…</span><span class="abstract-full" hidden>${escapeHtml(text)}</span></p><button type="button" class="abstract-toggle" data-abstract="${id}">展开摘要</button>`;
}

function rowsMarkup(results) {
  return results.map((item, index) => {
    const itemId = `paper-${index}-${Math.random().toString(36).slice(2, 8)}`;
    const url = safeUrl(item.url);
    const title = highlightTitle(item.title || "无标题");
    const aiSummary = aiSummaryMarkup(item);
    const authors = item.authors ? escapeHtml(item.authors) : "作者信息暂缺";
    const venue = item.venue ? escapeHtml(item.venue) : "—";
    const types = item.publication_type ? `<span class="paper-type">${escapeHtml(item.publication_type)}</span>` : "";
    const sourceTags = sourceNames(item).map((name) => `<span class="source-pill">${escapeHtml(name)}</span>`).join(" ");
    const evidence = (item.match_evidence || []).map((hit) => `<span class="evidence-pill" title="命中词：${escapeHtml((hit.terms || []).join(' / '))}">${escapeHtml(hit.keyword)} · ${escapeHtml(hit.field)}</span>`).join("");
    const link = url ? `<a class="link-button" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">打开 ↗</a>` : '<span class="metric-muted">—</span>';
    const meanCited = formatMetric(item.journal_2yr_mean_citedness, 3);
    const citations = formatMetric(item.citations, 0);
    const year = item.year ? String(item.year) : "—";
    return `
      <tr>
        <td class="index-cell">${index + 1}</td>
        <td class="col-paper">
          ${url ? `<a class="paper-title" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${title}</a>` : `<span class="paper-title">${title}</span>`}
          ${aiSummary}
          <span class="paper-authors">${authors}</span>
          ${types}
          ${abstractMarkup(item, itemId)}
          <div class="match-evidence">${evidence}${item.open_access === true ? '<span class="evidence-pill evidence-oa">开放获取</span>' : ""}</div>
          ${item.doi ? `<span class="paper-doi">DOI: ${escapeHtml(item.doi)}</span>` : ""}
          <div>${sourceTags || "—"}</div>
        </td>
        <td class="col-year">${escapeHtml(year)}</td>
        <td class="col-venue"><span class="venue-text">${venue}</span></td>
        <td class="col-metric">${meanCited}</td>
        <td class="col-metric">${citations}</td>
        <td class="col-link">${link}</td>
      </tr>
    `;
  }).join("");
}

function applyFilters() {
  const text = elements.filterInput.value.trim().toLocaleLowerCase();
  const source = elements.sourceFilter.value;
  const sort = elements.sortSelect.value;
  let results = state.allResults.filter((item) => {
    const haystack = [item.title, item.authors, item.venue, item.abstract].join(" ").toLocaleLowerCase();
    const matchesText = !text || haystack.includes(text);
    const matchesSource = !source || sourceNames(item).includes(source);
    const matchesQuality = (!elements.onlyAbstract.checked || Boolean(item.abstract?.trim())) &&
      (!elements.onlyOpenAccess.checked || item.open_access === true) &&
      (!elements.onlyDoi.checked || Boolean(item.doi));
    return matchesText && matchesSource && matchesQuality;
  });
  if (sort === "relevance") results = [...results].sort((a, b) => (b.relevance_score || 0) - (a.relevance_score || 0));
  if (sort === "year_desc") results = [...results].sort((a, b) => (b.year || 0) - (a.year || 0));
  if (sort === "year_asc") results = [...results].sort((a, b) => (a.year || 9999) - (b.year || 9999));
  if (sort === "citations_desc") results = [...results].sort((a, b) => (b.citations || 0) - (a.citations || 0));
  state.visibleResults = results;
  elements.resultsBody.innerHTML = rowsMarkup(results);
  elements.resultCount.textContent = `显示 ${results.length} / 共 ${state.allResults.length} 条结果`;
  elements.tableEmpty.hidden = results.length > 0;
  const allFailed = state.sourceStatuses.length > 0 && state.sourceStatuses.every((item) => item.status !== "ok");
  elements.tableEmpty.querySelector("p").textContent = allFailed
    ? "数据源连接失败，请查看上方数据源状态后重试。"
    : "没有符合条件的论文，可减少关键词、切换「任一包含」或清除结果筛选。";
  elements.exportBtn.disabled = results.length === 0;
  elements.summarizeBtn.disabled = !state.deepseek.configured || results.length === 0;
}

function renderResults(data) {
  state.allResults = data.results || [];
  ensureResultUids(state.allResults);
  state.query = data.query || null;
  renderQueryExpansion(state.query || {});
  renderSummary(data);
  renderSourceFilter(state.allResults);
  elements.resultsSection.hidden = false;
  elements.filterInput.value = "";
  elements.sortSelect.value = "relevance";
  elements.sourceFilter.value = "";
  [elements.onlyAbstract, elements.onlyOpenAccess, elements.onlyDoi].forEach((input) => { input.checked = false; });
  applyFilters();
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `请求失败（HTTP ${response.status}）`);
  return data;
}

async function runSearch(event) {
  event.preventDefault();
  const keywords = elements.keywords.value.trim();
  if (!keywords) {
    elements.formHint.textContent = "请先输入至少一个关键词。";
    elements.keywords.focus();
    return;
  }
  const sources = selectedSources();
  if (!sources.length) {
    elements.formHint.textContent = "请至少选择一个数据源。";
    return;
  }
  if (!elements.form.reportValidity()) return;
  if (elements.fromYear.value && elements.toYear.value && Number(elements.fromYear.value) > Number(elements.toYear.value)) {
    elements.formHint.textContent = "起始年份不能晚于结束年份。";
    elements.fromYear.focus();
    return;
  }
  const payload = {
    keywords,
    sources,
    match_mode: document.querySelector('input[name="match_mode"]:checked')?.value || "all",
    from_year: elements.fromYear.value || null,
    to_year: elements.toYear.value || null,
    max_results: Number(elements.maxResults.value || 10),
    use_deepseek_terms: state.deepseekSearchEnabled,
    match_scope: elements.matchScope.value,
    exclude_keywords: elements.excludeKeywords.value,
  };
  state.abortController = new AbortController();
  setLoading(true);
  try {
    const data = await requestJson("/api/search", {
      method: "POST",
      body: JSON.stringify(payload),
      signal: state.abortController.signal,
    });
    renderResults(data);
    elements.resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    const failedSources = (data.sources || []).filter((source) => source.status !== "ok");
    if (failedSources.length === data.sources?.length && failedSources.length > 0) {
      showToast("数据源连接失败，请查看数据源状态后重试。", true);
    } else if (!data.total) {
      showToast("没有找到匹配结果，可尝试减少关键词或扩大年份范围。");
    } else {
      showToast(`检索完成：去重后 ${data.total} 篇${failedSources.length ? `，${failedSources.length} 个数据源失败，覆盖可能不完整` : `，原始 ${data.raw_total} 条`}。`);
    }
  } catch (error) {
    if (state.cancelled || error?.name === "AbortError") {
      elements.formHint.textContent = "检索已终止，可重新填写关键词后再次检索。";
      showToast("检索已终止。");
    } else {
      elements.formHint.textContent = error.message || "检索失败，请稍后重试。";
      showToast(error.message || "检索失败", true);
    }
  } finally {
    state.abortController = null;
    setLoading(false);
    elements.keywords.focus();
  }
}

function cancelSearch() {
  if (!state.loading || !state.abortController) return;
  state.cancelled = true;
  state.abortController.abort();
}

async function summarizeResults() {
  if (!state.deepseek.configured) {
    showToast("请先配置 DEEPSEEK_API_KEY 并重启服务。", true);
    return;
  }
  const maxItems = Number(state.deepseek.max_items || 20);
  const candidates = state.visibleResults.filter((item) => item.abstract).slice(0, maxItems);
  if (!candidates.length) {
    showToast("当前结果中没有可概括的摘要。", true);
    return;
  }
  const originalHtml = elements.summarizeBtn.innerHTML;
  elements.summarizeBtn.disabled = true;
  elements.summarizeBtn.textContent = `概括中…（最多 ${maxItems} 篇）`;
  try {
    const data = await requestJson("/api/summarize", {
      method: "POST",
      body: JSON.stringify({ results: candidates }),
    });
    const itemMap = new Map(state.allResults.map((item) => [item._uid, item]));
    (data.summaries || []).forEach((summary) => {
      const item = itemMap.get(summary.uid);
      if (!item) return;
      item.summary_status = summary.status;
      item.summary_zh = summary.summary || "";
      item.summary_error = summary.error || "";
    });
    applyFilters();
    elements.summarizeBtn.disabled = true;
    const succeeded = (data.summaries || []).filter((item) => item.status === "ok").length;
    showToast(`DeepSeek 已完成 ${succeeded} 篇摘要概括${data.limited ? `，本次最多处理 ${maxItems} 篇` : ""}。`);
  } catch (error) {
    showToast(error.message || "DeepSeek 摘要概括失败", true);
  } finally {
    elements.summarizeBtn.innerHTML = originalHtml;
    elements.summarizeBtn.disabled = !state.deepseek.configured || !state.visibleResults.length;
  }
}

async function exportResults() {
  const results = state.visibleResults.length ? state.visibleResults : state.allResults;
  if (!results.length) {
    showToast("没有可导出的结果。", true);
    return;
  }
  elements.exportBtn.disabled = true;
  const originalText = elements.exportBtn.innerHTML;
  elements.exportBtn.textContent = "正在生成…";
  try {
    const response = await fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ results, query: state.query || {}, sources: state.sourceStatuses }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || `导出失败（HTTP ${response.status}）`);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    const filename = encoded ? decodeURIComponent(encoded) : `paper_search_${Date.now()}.xlsx`;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    showToast(`已导出 ${results.length} 条结果。`);
  } catch (error) {
    showToast(error.message || "导出失败", true);
  } finally {
    elements.exportBtn.innerHTML = originalText;
    elements.exportBtn.disabled = state.visibleResults.length === 0;
  }
}

function resetView() {
  elements.form.reset();
  elements.keywords.value = "";
  elements.fromYear.value = "";
  elements.toYear.value = "";
  elements.maxResults.value = "10";
  document.querySelector('input[name="match_mode"][value="all"]').checked = true;
  state.allResults = [];
  state.visibleResults = [];
  state.sourceStatuses = [];
  state.query = null;
  elements.summarySection.hidden = true;
  elements.resultsSection.hidden = true;
  elements.summarizeBtn.disabled = true;
  elements.formHint.textContent = "";
  elements.filterInput.value = "";
  elements.sourceFilter.value = "";
  elements.sortSelect.value = "relevance";
  [elements.onlyAbstract, elements.onlyOpenAccess, elements.onlyDoi].forEach((input) => { input.checked = false; });
  renderSources(state.sources);
}

function bindEvents() {
  elements.form.addEventListener("submit", runSearch);
  elements.resetBtn.addEventListener("click", resetView);
  elements.cancelBtn.addEventListener("click", cancelSearch);
  elements.exportBtn.addEventListener("click", exportResults);
  elements.summarizeBtn.addEventListener("click", summarizeResults);
  elements.saveDeepseekKey.addEventListener("click", saveDeepSeekConfig);
  elements.changeDeepseekKey.addEventListener("click", () => {
    elements.deepseekKeyPanel.classList.add("editing");
    elements.deepseekApiKey.focus();
  });
  elements.deepseekSearchToggle.addEventListener("click", () => {
    if (!state.deepseek.configured) return;
    state.deepseekToggleTouched = true;
    state.deepseekSearchEnabled = !state.deepseekSearchEnabled;
    updateDeepSeekToggle();
  });
  elements.toggleDeepseekKey.addEventListener("click", () => {
    const show = elements.deepseekApiKey.type === "password";
    elements.deepseekApiKey.type = show ? "text" : "password";
    elements.toggleDeepseekKey.textContent = show ? "隐藏" : "显示";
  });
  elements.selectAllSources.addEventListener("click", () => { $$('input[name="source_id"]').forEach((input) => { input.checked = true; }); updateSourceSelection(); });
  elements.clearSources.addEventListener("click", () => { $$('input[name="source_id"]').forEach((input) => { input.checked = false; }); updateSourceSelection(); });
  elements.sourceGrid.addEventListener("change", updateSourceSelection);
  $$("[data-preset]").forEach((button) => button.addEventListener("click", () => {
    const preset = button.dataset.preset === "all" ? state.sources.map((source) => source.id) : sourcePresets[button.dataset.preset];
    $$('input[name="source_id"]').forEach((input) => { input.checked = preset.includes(input.value); });
    updateSourceSelection();
  }));
  $("#recentYears").addEventListener("click", () => {
    const year = Number(new Intl.DateTimeFormat("en", { timeZone: "Asia/Shanghai", year: "numeric" }).format(new Date()));
    elements.fromYear.value = year - 4;
    elements.toYear.value = year;
  });
  [elements.onlyAbstract, elements.onlyOpenAccess, elements.onlyDoi].forEach((input) => input.addEventListener("change", applyFilters));
  elements.filterInput.addEventListener("input", applyFilters);
  elements.sourceFilter.addEventListener("change", applyFilters);
  elements.sortSelect.addEventListener("change", applyFilters);
  elements.resultsBody.addEventListener("click", (event) => {
    const button = event.target.closest(".abstract-toggle");
    if (!button) return;
    const wrapper = button.previousElementSibling;
    if (!wrapper) return;
    const collapsed = wrapper.classList.toggle("collapsed");
    const preview = wrapper.querySelector(".abstract-preview");
    const full = wrapper.querySelector(".abstract-full");
    if (preview) preview.hidden = !collapsed;
    if (full) full.hidden = collapsed;
    button.textContent = collapsed ? "展开摘要" : "收起摘要";
  });
  $$(".example-chip").forEach((button) => {
    button.addEventListener("click", () => {
      elements.keywords.value = button.dataset.example || "";
      elements.keywords.focus();
    });
  });
}

async function init() {
  bindEvents();
  try {
    const [data, deepseekStatus] = await Promise.all([
      requestJson("/api/sources", { method: "GET" }),
      requestJson("/api/deepseek/status", { method: "GET" }),
    ]);
    updateDeepSeekUI(deepseekStatus || state.deepseek);
    renderSources(data.sources || []);
  } catch (error) {
    elements.sourceGrid.innerHTML = `<div class="status-item error"><span class="status-dot"></span><span class="status-detail">${escapeHtml(error.message || "无法加载数据源")}</span></div>`;
    showToast("无法加载数据源列表", true);
  }
}

init();


