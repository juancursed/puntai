function toggleTheme(){
  var root=document.documentElement;
  var next=root.getAttribute('data-theme')==='dark'?'light':'dark';
  root.setAttribute('data-theme',next);
  try{localStorage.setItem('uniteval-theme',next);}catch(e){}
}
// ── Estado global ──────────────────────────────────────────────
const MODEL_LABELS = {claude: 'Claude Sonnet 4', openai: 'GPT-4o', laguna: 'Laguna'};

const state = {
  projectPath: '',
  model: 'claude',
  readOnly: false,    // Demo en línea (Vercel): la configuración no se puede guardar
  scannedTests: [],   // [{file, abs_path, tests:[{name,lineno,code,docstring}]}]
  runResults: [],     // [{name,file,function,outcome,duration,message}]
  analyses: {},       // {testName: {quality,score,...}}
  selectedTest: null,
  reportId: null,     // Evaluación guardada en curso o abierta
  reports: [],        // Historial de evaluaciones guardadas
};

// ── Analítica (Microsoft Clarity) ─────────────────────────────
// La app es de una sola página: se etiqueta la sección visible para poder
// filtrar grabaciones y heatmaps por sección en el panel de Clarity.
function track(kind, ...args) {
  try { if (typeof window.clarity === 'function') window.clarity(kind, ...args); } catch (e) {}
}
track('set', 'dispositivo', window.matchMedia('(max-width: 760px)').matches ? 'movil' : 'escritorio');

// ── Navegación ─────────────────────────────────────────────────
const MOBILE_QUERY = window.matchMedia('(max-width: 760px)');

function setSidebarOpen(open) {
  document.body.classList.toggle('sidebar-open', open);
  document.getElementById('menu-toggle')?.setAttribute('aria-expanded', String(open));
}

function toggleSidebar() {
  if (!document.body.classList.contains('sidebar-open')) track('event', 'abrir_menu');
  setSidebarOpen(!document.body.classList.contains('sidebar-open'));
}

function closeSidebar() {
  setSidebarOpen(false);
}

MOBILE_QUERY.addEventListener?.('change', e => { if (!e.matches) closeSidebar(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSidebar(); });

function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  document.getElementById('nav-' + name).classList.add('active');
  const titles = {summary:'Resumen', tests:'Pruebas detectadas', analysis:'Análisis IA', config:'Configuración'};
  document.getElementById('panel-title').textContent = titles[name] || name;
  closeSidebar();
  document.getElementById('page-' + name).scrollTop = 0;
  track('set', 'seccion', name);
  track('event', 'ver_' + name);
}

// ── Toast ──────────────────────────────────────────────────────
function toast(msg, duration=2800) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), duration);
}

// ── Config ─────────────────────────────────────────────────────
async function loadConfig() {
  try {
    const cfg = await api('/api/config');
    state.projectPath = cfg.project_path || '';
    state.model = cfg.model || 'claude';
    document.getElementById('model-select').value = state.model;
    document.getElementById('cfg-project-path').value = state.projectPath;
    showKeyStatus(cfg.configured_keys || {});
    document.getElementById('cfg-openrouter-model').value = cfg.openrouter_model || 'poolside/laguna-s-2.1';
    state.readOnly = Boolean(cfg.read_only);
    if (state.readOnly) applyReadOnlyMode();
    updateProjectDisplay();
  } catch(e) { console.error('Error cargando config:', e); }
}

// Las claves nunca llegan al navegador: solo se indica si ya están definidas.
function showKeyStatus(configured) {
  const fields = {
    anthropic_api_key: 'cfg-anthropic-key',
    openai_api_key: 'cfg-openai-key',
    openrouter_api_key: 'cfg-openrouter-key',
  };
  Object.entries(fields).forEach(([field, id]) => {
    const input = document.getElementById(id);
    input.dataset.placeholder ??= input.placeholder;
    input.value = '';
    input.placeholder = configured[field]
      ? 'Configurada (déjala vacía para conservarla)'
      : input.dataset.placeholder;
  });
}

// En la demo en línea solo se elige el modelo; ruta y claves las fija el servidor.
function applyReadOnlyMode() {
  document.getElementById('cfg-readonly-notice').hidden = false;
  document.getElementById('btn-change-project').hidden = true;
  document.querySelectorAll('#page-config input, #page-config button').forEach(el => { el.disabled = true; });
}

async function saveConfig() {
  const model = document.getElementById('model-select').value;
  if (state.readOnly) { state.model = model; return; }
  const projectPath = document.getElementById('cfg-project-path').value || state.projectPath;
  const anthropicKey = document.getElementById('cfg-anthropic-key').value;
  const openaiKey = document.getElementById('cfg-openai-key').value;
  const openrouterKey = document.getElementById('cfg-openrouter-key').value;
  const openrouterModel = document.getElementById('cfg-openrouter-model').value.trim() || 'poolside/laguna-s-2.1';
  state.model = model;
  try {
    await api('/api/config', 'POST', {
      project_path: projectPath,
      model,
      anthropic_api_key: anthropicKey,
      openai_api_key: openaiKey,
      openrouter_api_key: openrouterKey,
      openrouter_model: openrouterModel,
    });
    showKeyStatus((await api('/api/config')).configured_keys || {});
    toast('Configuración guardada');
  } catch(e) {
    console.error('Error guardando config:', e);
    toast('Error guardando config');
  }
}

function applyProjectPath() {
  const path = document.getElementById('cfg-project-path').value.trim();
  if (!path) return toast('Ingresa una ruta válida');
  state.projectPath = path;
  updateProjectDisplay();
  saveConfig();
  toast('Proyecto actualizado');
}

// ── Modal proyecto ─────────────────────────────────────────────
function openProjectModal() {
  closeSidebar();
  document.getElementById('modal-project-path').value = state.projectPath;
  document.getElementById('project-modal').classList.add('open');
}
function closeProjectModal() {
  document.getElementById('project-modal').classList.remove('open');
}
function applyProjectModal() {
  const path = document.getElementById('modal-project-path').value.trim();
  if (!path) return toast('Ingresa una ruta válida');
  state.projectPath = path;
  document.getElementById('cfg-project-path').value = path;
  updateProjectDisplay();
  saveConfig();
  closeProjectModal();
}

function updateProjectDisplay() {
  const hasProject = !!state.projectPath;
  const parts = state.projectPath ? state.projectPath.split(/[/\\]/) : [];
  const name = parts.findLast(Boolean) || 'Sin proyecto';
  document.getElementById('project-name-display').textContent = name;
  document.getElementById('project-path-display').textContent = state.projectPath || '—';
  document.getElementById('project-dot').style.background = hasProject ? 'var(--brand)' : 'var(--text3)';
}

// ── Escanear proyecto ──────────────────────────────────────────
async function runScan() {
  track('event', 'escanear');
  if (!state.projectPath) { openProjectModal(); return; }
  setLoading('btn-scan', true, 'Escaneando...');
  try {
    const result = await api('/api/scan', 'POST', { path: state.projectPath });
    state.scannedTests = result.test_files || [];
    state.runResults = [];
    state.analyses = {};
    state.selectedTest = null;
    state.reportId = null;
    refreshViews();
    enableActions();
    toast(`✓ ${result.total_tests} pruebas detectadas en ${state.scannedTests.length} archivo(s)`);
  } catch(e) {
    toast('Error: ' + (e.message || 'No se pudo escanear'));
  } finally { setLoading('btn-scan', false, 'Escanear proyecto'); }
}

// ── Ejecutar pytest ────────────────────────────────────────────
async function runTests() {
  track('event', 'ejecutar_pruebas');
  if (!state.projectPath) return toast('Selecciona un proyecto primero');
  setLoading('btn-run', true, 'Ejecutando...');
  try {
    const result = await api('/api/run', 'POST', { path: state.projectPath });
    state.runResults = result.tests || [];
    refreshViews();
    const sum = result.summary || {};
    const firstProblem = state.runResults.find(t => t.outcome === 'error' && t.message);
    if (sum.error && !sum.passed && !sum.failed && firstProblem) {
      console.error('pytest:', firstProblem.name, firstProblem.message);
      toast(`pytest: ${sum.error} prueba(s) con error al prepararse. ${firstProblem.message.trim().split(/\r?\n/).pop()}`, 10000);
    } else {
      toast(`✓ pytest completado: ${sum.passed || 0} passed, ${sum.failed || 0} failed, `
        + `${sum.error || 0} error, ${sum.skipped || 0} skipped (de ${sum.total || 0})`
        + (result.runner ? ` · ${result.runner}` : ''));
    }
  } catch(e) {
    console.error('Error ejecutando pytest:', e);
    toast('Error ejecutando pytest: ' + (e.message || ''), 10000);
  } finally { setLoading('btn-run', false, 'Ejecutar pruebas'); }
}

// ── Analizar con IA ────────────────────────────────────────────
async function analyzeAll() {
  track('event', 'evaluar_ia');
  if (!state.scannedTests.length) return toast('Escanea el proyecto primero');
  setLoading('btn-analyze', true, 'Analizando...');

  const allTests = [];
  state.scannedTests.forEach(f => {
    f.tests.forEach(t => {
      const runResult = getRunResult(f.file, t.name);
      allTests.push({ file: f.file, test: t, outcome: runResult?.outcome || 'unknown' });
    });
  });

  let done = 0;
  let lastError = '';
  await Promise.all(allTests.map(async (item) => {
    if (state.analyses[item.test.name]) { done++; return; }
    try {
      const analysis = await api('/api/analyze', 'POST', {
        project_path: state.projectPath,
        test_file: item.file,
        test_name: item.test.name,
        test_code: item.test.code,
        test_result: item.outcome,
        model: state.model,
      });
      state.analyses[item.test.name] = analysis;
      done++;
      document.getElementById('btn-analyze-label').textContent = `Analizando (${done}/${allTests.length})...`;
      refreshViews();
    } catch(e) {
      console.error('Error analizando prueba:', e);
      lastError = e.message || 'Error al analizar con IA';
      done++;
    }
  }));

  refreshViews();
  await saveReport();
  setLoading('btn-analyze', false, 'Evaluar con IA');
  if (lastError && !Object.keys(state.analyses).length) {
    toast(`Error: ${lastError}`, 5000);
  } else {
    toast(`✓ Análisis completado para ${Object.keys(state.analyses).length} prueba(s)`);
  }
}

async function analyzeOne(testName, testFile) {
  const outcome = getRunResult(testFile, testName)?.outcome || 'unknown';
  try {
    const analysis = await api('/api/analyze', 'POST', {
      project_path: state.projectPath,
      test_file: testFile,
      test_name: testName,
      test_code: findTest(testName)?.code || '',
      test_result: outcome,
      model: state.model,
    });
    state.analyses[testName] = analysis;
    refreshViews();
    await saveReport();
    toast('✓ Análisis completado');
  } catch(e) { toast('Error en análisis: ' + e.message); }
}

// ── Render: lista de pruebas ───────────────────────────────────
function allTests() {
  return state.scannedTests.flatMap(f => f.tests.map(test => ({
    file: f.file,
    test,
    outcome: getRunResult(f.file, test.name)?.outcome || 'pending',
  })));
}

function testRowHtml(item, note = '') {
  const name = escHtml(item.test.name);
  return `
    <div class="test-row ${state.selectedTest === item.test.name ? 'selected' : ''}"
         onclick="selectTest(${jsArg(item.test.name)}, ${jsArg(item.file)})">
      ${badgeHtml(item.outcome)}
      ${note
        ? `<span class="test-main"><span class="test-fn">${name}</span><span class="test-note">${escHtml(note)}</span></span>`
        : `<span class="test-fn">${name}</span>`}
      <span class="test-file-tag">${escHtml(item.file)}</span>
      ${scoreTagHtml(state.analyses[item.test.name])}
    </div>
  `;
}

function scoreTagHtml(analysis) {
  if (!analysis) return '';
  const score = analysis.quality_score;
  if (score === null || score === undefined) return '<span class="score-tag">Sin nota</span>';
  return `<span class="score-tag ${escHtml(analysis.quality)}">${escHtml(String(score))}/${analysis.max_score || 10}</span>`;
}

function renderTestsList() {
  const container = document.getElementById('tests-list');
  const tests = allTests();

  document.getElementById('tests-count-label').textContent =
    tests.length ? `${tests.length} prueba(s)` : '—';

  if (!tests.length) {
    container.innerHTML = '<div class="empty"><h3>Sin pruebas</h3><p>Escanea el proyecto para ver las pruebas.</p></div>';
    return;
  }

  container.innerHTML = tests.map(item => testRowHtml(item)).join('');
}

function renderSummaryList() {
  const container = document.getElementById('summary-test-list');
  const tests = allTests();

  const files = [...new Set(tests.map(i => i.file))];
  document.getElementById('summary-files-label').textContent = files.length ? files.join(' · ') : '—';

  if (!tests.length) {
    container.innerHTML = '<div class="empty"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg><h3>Sin datos aún</h3><p>Selecciona un proyecto y escanéalo para comenzar.</p></div>';
    return;
  }

  container.innerHTML = tests.slice(0, 10).map(item => testRowHtml(item)).join('');
}

// ── Reportes guardados ─────────────────────────────────────────
function computeSummary() {
  const tests = allTests();
  const analyses = tests.map(i => state.analyses[i.test.name]).filter(Boolean);
  const scored = analyses.filter(a => a.quality_score !== null && a.quality_score !== undefined);
  const count = quality => analyses.filter(a => a.quality === quality).length;
  const sum = scored.reduce((total, a) => total + (a.quality_score / (a.max_score || 10)) * 5, 0);
  return {
    total: tests.length,
    passed: tests.filter(i => i.outcome === 'passed').length,
    failed: tests.filter(i => i.outcome === 'failed' || i.outcome === 'error').length,
    cases: state.runResults.length,
    analyzed: analyses.length,
    average: scored.length ? Math.round((sum / scored.length) * 10) / 10 : null,
    alta: count('alta'),
    media: count('media'),
    baja: count('baja'),
  };
}

async function saveReport() {
  if (!Object.keys(state.analyses).length) return;
  try {
    const saved = await api('/api/reports', 'POST', {
      id: state.reportId,
      project_path: state.projectPath,
      model: state.model,
      summary: computeSummary(),
      scanned_tests: state.scannedTests,
      run_results: state.runResults,
      analyses: state.analyses,
    });
    state.reportId = saved.id;
    await loadReports();
  } catch(e) {
    console.error('Error guardando reporte:', e);
    toast('El análisis terminó, pero no se pudo guardar el reporte', 5000);
  }
}

async function loadReports() {
  try {
    state.reports = await api('/api/reports');
  } catch(e) {
    console.error('Error cargando reportes:', e);
  }
  renderHistory();
}

function formatDate(isoDate) {
  return isoDate ? new Date(isoDate).toLocaleString('es', {dateStyle:'short', timeStyle:'short'}) : '—';
}

function projectName(path) {
  return String(path || '').split(/[/\\]/).findLast(Boolean) || 'Sin proyecto';
}

function renderHistory() {
  const count = state.reports.length;
  document.getElementById('history-count-label').textContent = count ? `${count} guardada(s)` : '—';

  if (!count) {
    document.getElementById('history-list').innerHTML =
      '<div class="empty"><h3>Sin evaluaciones guardadas</h3><p>Cada evaluación con IA se guarda aquí para que puedas revisarla después.</p></div>';
    return;
  }

  document.getElementById('history-list').innerHTML = state.reports.map(report => {
    const summary = report.summary || {};
    const average = summary.average ?? '—';
    return `
      <button type="button" class="history-row ${state.reportId === report.id ? 'selected' : ''}"
              onclick="openReport(${jsArg(report.id)})">
        <span class="history-date">${escHtml(formatDate(report.created_at))}</span>
        <span class="history-project">${escHtml(projectName(report.project_path))}</span>
        <span>${escHtml(MODEL_LABELS[report.model] || report.model)}</span>
        <span>${summary.analyzed ?? 0}/${summary.total ?? 0} evaluadas</span>
        <span class="score-tag">${escHtml(String(average))}/5</span>
      </button>
    `;
  }).join('');
}

async function openReport(reportId) {
  try {
    const report = await api('/api/reports/' + encodeURIComponent(reportId));
    state.reportId = report.id;
    state.projectPath = report.project_path || '';
    state.scannedTests = report.scanned_tests || [];
    state.runResults = report.run_results || [];
    state.analyses = report.analyses || {};
    updateProjectDisplay();
    enableActions();
    document.getElementById('history-banner-text').textContent =
      `Viendo la evaluación guardada del ${formatDate(report.created_at)} (${projectName(report.project_path)}).`;
    document.getElementById('history-banner').style.display = 'flex';
    showAnalysisOverview();
    renderHistory();
  } catch(e) {
    toast('No se pudo abrir la evaluación: ' + e.message);
  }
}

async function leaveReport() {
  state.projectPath = document.getElementById('cfg-project-path').value;
  state.scannedTests = [];
  state.runResults = [];
  state.analyses = {};
  state.selectedTest = null;
  state.reportId = null;
  updateProjectDisplay();
  refreshViews();
  showPage('summary');
  if (state.projectPath) await runScan();
}

// ── Render: análisis IA ────────────────────────────────────────
const BACK_BUTTON = '<button class="link-btn back-btn" onclick="showAnalysisOverview()">← Panel general</button>';

function showAnalysisOverview() {
  state.selectedTest = null;
  refreshViews();
  showPage('analysis');
}

function renderAnalysisOverview() {
  const content = document.getElementById('analysis-content');
  const summary = computeSummary();

  if (!summary.analyzed) {
    content.innerHTML = `
      <div class="empty" style="padding:60px 24px">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
        <h3>Sin análisis aún</h3>
        <p>Escanea el proyecto y haz clic en "Evaluar con IA". Aquí verás el resultado general y podrás abrir el análisis de cada prueba.</p>
      </div>
    `;
    return;
  }

  const statCard = (label, value, color, sub) => `
    <div class="stat-card">
      <div class="stat-lbl">${label}</div>
      <div class="stat-val ${color}">${value}</div>
      <div class="stat-sub">${sub}</div>
    </div>
  `;
  const rank = item => {
    const analysis = state.analyses[item.test.name];
    if (!analysis) return Infinity;
    const score = analysis.quality_score;
    return score === null || score === undefined ? Number.MAX_VALUE : score / (analysis.max_score || 10);
  };
  const rows = allTests().sort((a, b) => rank(a) - rank(b)).map(item => {
    const analysis = state.analyses[item.test.name];
    return testRowHtml(item, analysis ? plainText(analysis.summary) : 'Sin evaluar');
  }).join('');

  content.innerHTML = `
    <div class="overview">
      <div class="overview-stats">
        ${statCard('Evaluadas', `${summary.analyzed}/${summary.total}`, '', 'pruebas')}
        ${statCard('Calificación promedio', summary.average === null ? '—' : `${summary.average}/5`, 'green', 'de las evaluadas')}
        ${statCard('Calidad alta', summary.alta, 'green', '4 a 5')}
        ${statCard('Calidad media', summary.media, 'amber', '3 a 3.9')}
        ${statCard('Calidad baja', summary.baja, 'red', 'menos de 3')}
      </div>
      <div class="card">
        <div class="card-head">
          Resultado por prueba
          <small>de menor a mayor calificación · selecciona una para ver su informe</small>
        </div>
        <div class="test-list">${rows}</div>
      </div>
    </div>
  `;
}

// Texto de una línea para las filas del panel, sin marcas de Markdown.
function plainText(markdown) {
  return String(markdown || '').replace(/[*`#]/g, '').replace(/\s+/g, ' ').trim();
}

function refreshViews() {
  if (state.reportId === null) document.getElementById('history-banner').style.display = 'none';
  renderTestsList();
  renderSummaryList();
  updateStats();
  if (state.selectedTest && state.analyses[state.selectedTest]) {
    renderAnalysisPane(state.selectedTest);
  } else if (!state.selectedTest) {
    renderAnalysisOverview();
  }
}

function enableActions() {
  document.getElementById('btn-run').disabled = false;
  document.getElementById('btn-analyze').disabled = false;
}

function selectTest(testName, testFile) {
  state.selectedTest = testName;
  renderTestsList();
  renderSummaryList();
  showPage('analysis');

  if (state.analyses[testName]) {
    renderAnalysisPane(testName);
  } else {
    document.getElementById('analysis-content').innerHTML = `
      ${BACK_BUTTON}
      <div class="empty" style="padding:60px 24px">
        <h3>Prueba seleccionada: ${escHtml(testName)}</h3>
        <p>Esta prueba no ha sido analizada todavía.</p>
        <button class="btn btn-primary" style="margin-top:12px"
          onclick="analyzeOne(${jsArg(testName)}, ${jsArg(testFile)})">
          Analizar con IA
        </button>
      </div>
    `;
  }
}

function renderAnalysisPane(testName) {
  if (!testName) return;
  const analysis = state.analyses[testName];
  if (!analysis) return;

  const file = findTestFile(testName);
  const outcome = getRunResult(file, testName)?.outcome;
  const sourceFiles = analysis.source_files || [];

  document.getElementById('analysis-content').innerHTML = `
    ${BACK_BUTTON}
    <div class="analysis-grid">
      <article class="report">
        <div class="report-kicker">Informe de calidad de la prueba</div>
        <h2 class="report-title">${escHtml(testName)}</h2>
        <div class="report-meta">
          ${outcome ? badgeHtml(outcome) : ''}
          <span>${escHtml(file)}</span>
        </div>
        ${renderScore(analysis)}
        ${analysis.source_code ? '' : '<div class="report-notice">No se localizó el código fuente de la función evaluada: el análisis se basa solo en la prueba.</div>'}
        ${analysis.source_truncated ? '<div class="report-notice">El código fuente superó el límite de envío: se omitieron las dependencias más lejanas.</div>' : ''}
        ${analysis.steps?.length ? renderSteps(analysis) : renderLegacySections(analysis)}
      </article>

      <div class="code-stack">
        <div class="ai-card">
          <div class="ai-head">Prueba unitaria</div>
          <div class="code-block">${escHtml(findTest(testName)?.code)}</div>
        </div>
        ${analysis.source_code ? `
          <div class="ai-card">
            <div class="ai-head">Código fuente evaluado</div>
            <div class="code-files">${sourceFiles.map(escHtml).join(' · ')}</div>
            <div class="code-block">${escHtml(analysis.source_code)}</div>
          </div>` : ''}
      </div>
    </div>
  `;
}

function renderScore(analysis) {
  const score = analysis.quality_score;
  if (score === null || score === undefined) {
    return '<div class="report-score"><h3>Calificación: sin determinar</h3></div>';
  }
  const maxScore = analysis.max_score || 10;
  const color = {alta:'green', media:'amber', baja:'red'}[analysis.quality] || 'text3';
  const quality = analysis.quality ? `<span style="color:var(--${color})">Calidad ${escHtml(analysis.quality)}</span>` : '';
  const width = Math.min(100, Math.round((score / maxScore) * 100));
  return `
    <div class="report-score">
      <h3>Calificación: ${escHtml(String(score))}/${maxScore}${quality}</h3>
      <div class="report-bar"><div style="width:${width}%;background:var(--${color})"></div></div>
    </div>
  `;
}

function renderSteps(analysis) {
  return analysis.steps.map(step => {
    const recommendations = step.number === 4 && analysis.recommendations
      ? `<h5>Recomendaciones</h5><div class="report-text">${renderMarkdown(analysis.recommendations)}</div>`
      : '';
    return `
      <section class="report-section">
        <h4><span class="report-step">Paso ${step.number}.</span>${escHtml(step.title)}</h4>
        <div class="report-text">${renderMarkdown(step.content)}</div>
        ${recommendations}
      </section>
    `;
  }).join('');
}

// Respuestas en JSON, sin los cuatro pasos.
function renderLegacySections(analysis) {
  const section = (title, items) => {
    if (!items?.length) return '';
    const list = items.map(i => `<li>${renderInlineMarkdown(i)}</li>`).join('');
    return `<section class="report-section"><h4>${title}</h4><div class="report-text"><ul>${list}</ul></div></section>`;
  };
  const summary = analysis.summary
    ? `<section class="report-section"><h4>Resumen</h4><div class="report-text">${renderMarkdown(analysis.summary)}</div></section>`
    : '';
  return summary
    + section('Problemas encontrados', analysis.issues)
    + section('Sugerencias', analysis.suggestions)
    + section('Casos no cubiertos', analysis.missing_cases)
    + section('Buenas prácticas', analysis.good_practices);
}

// Markdown básico de las respuestas de la IA. Todo el texto pasa por escHtml.
function renderInlineMarkdown(text) {
  // El código se aparta primero porque una negrita puede contener `código`.
  const codeSpans = [];
  const withoutCode = String(text || '').replace(/`([^`]+)`/g, (_, code) => {
    codeSpans.push(code);
    return `\u0000${codeSpans.length - 1}\u0000`;
  });
  return escHtml(withoutCode)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>')
    .replace(/\u0000(\d+)\u0000/g, (_, index) => `<code>${escHtml(codeSpans[index])}</code>`);
}

function renderMarkdown(text) {
  const html = [];
  let paragraph = [];
  const lists = [];  // Pila de listas abiertas: [{tag, indent}]
  let code = null;

  const flushParagraph = () => {
    if (paragraph.length) html.push(`<p>${renderInlineMarkdown(paragraph.join(' '))}</p>`);
    paragraph = [];
  };
  const closeLevel = () => html.push(`</li></${lists.pop().tag}>`);
  const closeList = () => {
    while (lists.length) closeLevel();
  };

  for (const rawLine of String(text || '').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (code !== null) {
      if (line.startsWith('```')) {
        html.push(`<div class="code-block">${escHtml(code.join('\n'))}</div>`);
        code = null;
      } else {
        code.push(rawLine);
      }
      continue;
    }
    if (line.startsWith('```')) {
      flushParagraph();
      closeList();
      code = [];
      continue;
    }
    const item = rawLine.match(/^(\s*)(?:([-*•])|(\d+)[.)])\s+(.*)$/);
    if (item) {
      flushParagraph();
      const indent = item[1].length;
      const tag = item[2] ? 'ul' : 'ol';
      while (lists.length && indent < lists.at(-1).indent) closeLevel();
      const current = lists.at(-1);
      if (!current || indent > current.indent) {
        html.push(`<${tag}>`);
        lists.push({tag, indent});
      } else {
        html.push('</li>');
        if (current.tag !== tag) {
          html.push(`</${current.tag}><${tag}>`);
          current.tag = tag;
        }
      }
      html.push(`<li>${renderInlineMarkdown(item[4])}`);
      continue;
    }
    // Una línea en blanco no cierra la lista: así no se reinicia la numeración.
    if (!line) {
      flushParagraph();
      continue;
    }
    closeList();
    if (/^-{3,}$/.test(line)) {
      flushParagraph();
      continue;
    }
    const heading = line.match(/^#{1,6}\s+(.*)$/);
    if (heading) {
      flushParagraph();
      html.push(`<p><strong>${renderInlineMarkdown(heading[1])}</strong></p>`);
      continue;
    }
    paragraph.push(line);
  }
  flushParagraph();
  closeList();
  if (code !== null) html.push(`<div class="code-block">${escHtml(code.join('\n'))}</div>`);
  return html.join('');
}

// ── Estadísticas ───────────────────────────────────────────────
function updateStats() {
  const summary = computeSummary();
  const executed = state.runResults.length > 0;

  document.getElementById('stat-total').textContent = summary.total || '—';
  document.getElementById('stat-total-sub').textContent =
    executed ? `pruebas · ${summary.cases} casos ejecutados` : 'pruebas';
  document.getElementById('stat-passed').textContent = executed ? summary.passed : '—';
  document.getElementById('stat-failed').textContent = executed ? summary.failed : '—';
  document.getElementById('stat-analyzed').textContent = summary.analyzed;
  document.getElementById('stat-analyzed-total').textContent = summary.total;
  document.getElementById('stat-passed-pct').textContent =
    executed && summary.total ? Math.round((summary.passed / summary.total) * 100) + '%' : '—';
}

// ── Helpers ────────────────────────────────────────────────────
function findTest(testName) {
  return state.scannedTests.flatMap(f => f.tests).find(t => t.name === testName);
}

function findTestFile(testName) {
  return state.scannedTests.find(f => f.tests.some(t => t.name === testName))?.file || '';
}

function sameFile(a, b) {
  const [left, right] = [a, b].map(path => String(path || '').replaceAll('\\', '/'));
  return left === right || left.endsWith('/' + right) || right.endsWith('/' + left);
}

// Una función con parametrize produce varios casos (test_x[1], test_x[2]...):
// la prueba solo cuenta como aprobada si ninguno de sus casos falló.
function getRunResult(file, fnName) {
  const cases = state.runResults.filter(r => sameFile(r.file, file) && r.function.split('[')[0] === fnName);
  if (!cases.length) return undefined;
  const severity = ['error', 'failed', 'passed', 'skipped'];
  const outcome = severity.find(o => cases.some(c => c.outcome === o)) || cases[0].outcome;
  return { outcome };
}

function badgeHtml(outcome) {
  const map = {passed:'badge-pass', failed:'badge-fail', error:'badge-err', skipped:'badge-skip', pending:'badge-pending', unknown:'badge-pending'};
  const cls = map[outcome] || 'badge-pending';
  const label = {passed:'PASS', failed:'FAIL', error:'ERR', skipped:'SKIP', pending:'—', unknown:'—'}[outcome] || outcome.toUpperCase();
  return `<span class="badge ${cls}">${label}</span>`;
}

function escHtml(str) {
  return String(str || '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
}

// Argumento seguro para un onclick en línea; conserva las barras de las rutas de Windows.
function jsArg(value) {
  return escHtml(JSON.stringify(value));
}

function setLoading(btnId, loading, label) {
  const btn = document.getElementById(btnId);
  const lbl = document.getElementById(btnId + '-label');
  btn.disabled = loading;
  if (loading) {
    lbl.innerHTML = `<span class="spinner"></span> ${label}`;
  } else {
    lbl.textContent = label;
  }
}

async function api(path, method='GET', body=null) {
  const opts = { method, headers: {'Content-Type': 'application/json'} };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
  return data;
}

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('server-status').textContent = 'Servidor activo · ' + location.host;
  document.getElementById('server-footer').textContent = 'FastAPI · ' + location.host;
  loadConfig();
  loadReports();
  renderAnalysisOverview();
});
