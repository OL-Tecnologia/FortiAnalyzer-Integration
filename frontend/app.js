const API_BASE = window.location.origin;

const API = { credentials: "include" };

function apiUrl(path) {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

const PHASES = [
  { id: "faz", label: "FortiAnalyzer" },
  { id: "hierarchy", label: "Hierarquia" },
  { id: "pdf", label: "Montagem do PDF" },
  { id: "finalize", label: "Finalização" },
];

const el = (id) => document.getElementById(id);

const btnGenerate = el("btnGenerate");
const btnLogout = el("btnLogout");
const userLabel = el("userLabel");
const progressPanel = el("progressPanel");
const progressBar = el("progressBar");
const progressPercent = el("progressPercent");
const progressLabel = el("progressLabel");
const progressStep = el("progressStep");
const progressLog = el("progressLog");
const phaseList = el("phaseList");
const resultPanel = el("resultPanel");
const resultMessage = el("resultMessage");
const btnDownload = el("btnDownload");
const errorBox = el("errorBox");
const clientBadge = el("clientBadge");
const footerSchedule = el("footerSchedule");

let eventSource = null;
let currentJobId = null;
let phaseState = {};

function initPhaseState() {
  phaseState = {};
  for (const p of PHASES) {
    phaseState[p.id] = { percent: 0, message: "", status: "pending" };
  }
}

function renderPhaseBars() {
  if (!phaseList) return;
  phaseList.innerHTML = PHASES.map((p) => {
    const st = phaseState[p.id] || { percent: 0, message: "", status: "pending" };
    const cls = st.status === "done" ? "is-done" : st.status === "active" ? "is-active" : "is-pending";
    const detail = st.message
      ? `<p class="phase-detail">${escapeHtml(st.message)}</p>`
      : "";
    return `
      <div class="phase-item ${cls}" data-phase="${p.id}">
        <div class="phase-head">
          <span class="phase-name">${p.label}</span>
          <span class="phase-pct">${st.percent}%</span>
        </div>
        <div class="phase-bar">
          <div class="phase-bar-fill" style="width: ${st.percent}%"></div>
        </div>
        ${detail}
      </div>`;
  }).join("");
}

function escapeHtml(text) {
  const d = document.createElement("div");
  d.textContent = text;
  return d.innerHTML;
}

function markPhasesBeforeDone(phaseId) {
  let found = false;
  for (const p of PHASES) {
    if (p.id === phaseId) {
      found = true;
      continue;
    }
    if (!found) {
      phaseState[p.id].percent = 100;
      phaseState[p.id].status = "done";
    }
  }
}

function updatePhaseFromEvent(data) {
  const phase = data.phase || data.step || "faz";
  const phasePct = data.phase_percent ?? data.percent ?? 0;
  const message = data.message || "";

  if (!phaseState[phase]) {
    phaseState[phase] = { percent: 0, message: "", status: "pending" };
  }

  markPhasesBeforeDone(phase);

  for (const p of PHASES) {
    if (p.id !== phase && phaseState[p.id].status === "active") {
      phaseState[p.id].status = "done";
      phaseState[p.id].percent = 100;
    }
  }

  phaseState[phase].percent = Math.max(phaseState[phase].percent, phasePct);
  phaseState[phase].message = message;
  phaseState[phase].status = data.status === "completed" ? "done" : "active";
  if (data.status === "completed") {
    phaseState[phase].percent = 100;
    for (const p of PHASES) {
      phaseState[p.id].status = "done";
      phaseState[p.id].percent = 100;
    }
  }

  renderPhaseBars();
}

async function checkAuth() {
  const res = await fetch(apiUrl("/api/auth/me"), API);
  if (!res.ok) return null;
  return res.json();
}

async function requireAuth() {
  const me = await checkAuth();
  if (!me || !me.authenticated) {
    window.location.href = "/login.html";
    return null;
  }
  return me;
}

async function logout() {
  await fetch(apiUrl("/api/auth/logout"), { method: "POST", ...API });
  window.location.href = "/login.html";
}

async function loadClient() {
  try {
    const res = await fetch(apiUrl("/api/client"), API);
    if (!res.ok) throw new Error("Falha ao carregar cliente");
    const data = await res.json();
    clientBadge.textContent = `ADOM ${data.adom}`;
    footerSchedule.textContent = data.report_schedule;
    btnGenerate.disabled = false;
  } catch (err) {
    clientBadge.textContent = "Erro API";
    showError(err.message + " — inicie o servidor: python -m forti_report.api.app");
  }
}

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.classList.remove("hidden");
}

function clearError() {
  errorBox.classList.add("hidden");
  errorBox.textContent = "";
}

function resetUi() {
  clearError();
  resultPanel.classList.add("hidden");
  progressPanel.classList.remove("hidden");
  progressPanel.classList.add("is-running");
  progressBar.style.width = "0%";
  progressPercent.textContent = "0%";
  progressLabel.textContent = "Preparando…";
  progressStep.textContent = "";
  progressLog.innerHTML = "";
  initPhaseState();
  renderPhaseBars();
  btnGenerate.disabled = true;
}

function appendLog(message, percent) {
  const li = document.createElement("li");
  li.textContent = `[${percent}%] ${message}`;
  progressLog.appendChild(li);
  progressLog.scrollTop = progressLog.scrollHeight;
}

function onProgressEvent(data) {
  if (data.status === "closed") return;

  const pct = data.percent ?? 0;
  progressBar.style.width = `${pct}%`;
  progressPercent.textContent = `${pct}%`;
  progressLabel.textContent =
    data.status === "completed"
      ? "Concluído"
      : data.status === "failed"
        ? "Falhou"
        : "Em andamento…";
  progressStep.textContent = data.message || "";

  updatePhaseFromEvent(data);

  if (data.message) {
    const items = progressLog.querySelectorAll("li");
    const last = items[items.length - 1];
    if (!last || last.textContent !== `[${pct}%] ${data.message}`) {
      appendLog(data.message, pct);
    }
  }

  if (data.status === "completed" && data.download_url) {
    finishSuccess(data);
  } else if (data.status === "failed") {
    finishError(data.error || data.message || "Erro desconhecido");
  }
}

function stopRunningAnimation() {
  progressPanel?.classList.remove("is-running");
}

function finishSuccess(data) {
  stopRunningAnimation();
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  btnGenerate.disabled = false;
  resultPanel.classList.remove("hidden");
  resultMessage.textContent = data.message || "PDF pronto.";
  const url = data.download_url || `/api/reports/mensal/jobs/${currentJobId}/download`;
  btnDownload.href = url;
  btnDownload.download = data.pdf_filename || "relatorio.pdf";
}

function finishError(msg) {
  stopRunningAnimation();
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  btnGenerate.disabled = false;
  showError(msg);
}

async function startGeneration() {
  resetUi();
  currentJobId = null;

  const body = {
    days: 60,
    download: true,
    force_download: el("optForce").checked,
    charts: el("optCharts").checked,
  };

  try {
    const res = await fetch(apiUrl("/api/reports/mensal/generate"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
    });
    if (res.status === 401) {
      window.location.href = "/login.html";
      return;
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }
    const job = await res.json();
    currentJobId = job.job_id;
    connectStream(job.stream_url);
  } catch (err) {
    finishError(err.message);
  }
}

function connectStream(streamUrl) {
  if (eventSource) eventSource.close();
  eventSource = new EventSource(apiUrl(streamUrl.startsWith("/") ? streamUrl : `/${streamUrl}`));

  eventSource.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      onProgressEvent(data);
    } catch {
      /* ignore parse errors */
    }
  };

  eventSource.onerror = () => {
    if (currentJobId) {
      pollFallback(currentJobId);
    }
  };
}

async function pollFallback(jobId) {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  try {
    const res = await fetch(apiUrl(`/api/reports/mensal/jobs/${jobId}`), API);
    if (res.status === 401) {
      window.location.href = "/login.html";
      return;
    }
    const data = await res.json();
    if (data.last_event) onProgressEvent(data.last_event);
    if (data.status === "completed") {
      finishSuccess({
        status: "completed",
        message: "Relatório gerado.",
        download_url: `/api/reports/mensal/jobs/${jobId}/download`,
        pdf_filename: data.pdf_filename,
      });
    } else if (data.status === "failed") {
      finishError(data.error || "Falha na geração");
    } else {
      setTimeout(() => pollFallback(jobId), 2000);
    }
  } catch (err) {
    finishError(err.message);
  }
}

btnGenerate.addEventListener("click", startGeneration);
btnLogout.addEventListener("click", logout);

(async () => {
  const me = await requireAuth();
  if (!me) return;
  if (userLabel) userLabel.textContent = me.user || "";
  await loadClient();
})();
