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
let currentPendingNote = "";
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

function paintClientBadge(displayName, adom) {
  if (!clientBadge) return;
  const name = displayName || "Cliente";
  const adomText = adom || "não configurado";
  clientBadge.textContent = `${name} · ADOM ${adomText}`;
  try {
    sessionStorage.setItem(
      "fazPortalClient",
      JSON.stringify({ display_name: name, adom: adom || "" })
    );
  } catch {
    /* armazenamento da aba indisponível */
  }
}

function restoreClientBadge() {
  try {
    const raw = sessionStorage.getItem("fazPortalClient");
    if (!raw) return;
    const saved = JSON.parse(raw);
    if (saved?.display_name || saved?.adom) {
      paintClientBadge(saved.display_name, saved.adom);
    }
  } catch {
    /* ignora valor antigo inválido */
  }
}

async function loadClient() {
  try {
    const res = await fetch(apiUrl("/api/client"), { cache: "no-store", ...API });
    if (!res.ok) throw new Error("Falha ao carregar cliente");
    const data = await res.json();
    paintClientBadge(data.display_name, data.adom);
    footerSchedule.textContent = data.report_schedule;
    btnGenerate.disabled = false;
  } catch (err) {
    if (!clientBadge.textContent || clientBadge.textContent.startsWith("Carregando")) {
      restoreClientBadge();
    }
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
    finishSuccess({ ...data, pending_note: currentPendingNote });
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
  const pending = data.pending_note ? ` ${data.pending_note}` : "";
  resultMessage.textContent = `${data.message || "PDF mensal pronto."}${pending}`;
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

const REPORT_PICKS = [
  { id: "pickDiario", kind: "diario", label: "Diário" },
  { id: "pickSemanal", kind: "semanal", label: "Semanal" },
  { id: "pickMensal", kind: "mensal", label: "Mensal" },
];

function selectedReports() {
  return REPORT_PICKS.filter((item) => el(item.id)?.checked).map((item) => item.kind);
}

function syncPickAll() {
  const all = el("pickAll");
  if (!all) return;
  all.checked = REPORT_PICKS.every((item) => el(item.id)?.checked);
  updateReportSummary();
}

function updateReportSummary() {
  const summary = el("reportSummary");
  if (!summary) return;
  const chosen = REPORT_PICKS.filter((item) => el(item.id)?.checked);
  if (!chosen.length) {
    summary.textContent = "Nenhum selecionado";
    return;
  }
  if (chosen.length === REPORT_PICKS.length) {
    summary.textContent = "Todos";
    return;
  }
  summary.textContent = chosen.map((item) => item.label).join(", ");
}

function setReportListOpen(open) {
  const panel = el("reportChoices");
  const button = el("btnToggleReports");
  if (!panel || !button) return;
  panel.classList.toggle("hidden", !open);
  button.setAttribute("aria-expanded", open ? "true" : "false");
  button.textContent = open ? "Recolher" : "Expandir";
}

function pendingPeriodMessage(kinds) {
  const labels = [];
  if (kinds.includes("diario")) labels.push("diário");
  if (kinds.includes("semanal")) labels.push("semanal");
  if (!labels.length) return "";
  const plural = labels.length > 1;
  const subject = plural ? `Os relatórios ${labels.join(" e ")}` : `O relatório ${labels[0]}`;
  return `${subject} ainda não ${plural ? "geram" : "gera"} PDF nesta versão.`;
}

async function startGeneration(kinds) {
  const chosen = kinds?.length ? kinds : selectedReports();
  if (!chosen.length) {
    setReportListOpen(true);
    const box = el("reportPickMsg");
    if (box) {
      box.textContent = "Marque ao menos um relatório.";
      box.classList.remove("hidden");
    }
    return;
  }

  const pending = pendingPeriodMessage(chosen);
  if (!chosen.includes("mensal")) {
    resultPanel.classList.add("hidden");
    progressPanel.classList.add("hidden");
    showError(pending);
    return;
  }

  resetUi();
  currentJobId = null;

  const body = {
    days: 60,
    download: true,
    force_download: el("optForce").checked,
    charts: el("optCharts").checked,
    reports: chosen,
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
    currentPendingNote = pending;
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
        message: "Relatório mensal gerado.",
        pending_note: currentPendingNote,
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

btnGenerate.addEventListener("click", () => startGeneration());
el("pickAll")?.addEventListener("change", () => {
  const on = el("pickAll").checked;
  for (const item of REPORT_PICKS) {
    const box = el(item.id);
    if (box) box.checked = on;
  }
  updateReportSummary();
});
for (const item of REPORT_PICKS) {
  el(item.id)?.addEventListener("change", syncPickAll);
}
el("btnToggleReports")?.addEventListener("click", () => {
  const open = el("btnToggleReports").getAttribute("aria-expanded") !== "true";
  setReportListOpen(open);
});
btnLogout.addEventListener("click", logout);

function syncRetryOptions() {
  const enabled = !!el("cfgRetryEnabled")?.checked;
  const row = el("cfgRetryOptions");
  if (row) {
    row.classList.toggle("hidden", !enabled);
  }
}

function fillConfigForm(data) {
  el("cfgScheduleEnabled").checked = !!data.mensal_schedule_enabled;
  el("cfgDay").value = data.mensal_schedule_day;
  el("cfgHour").value = data.mensal_schedule_hour;
  el("cfgMinute").value = data.mensal_schedule_minute;
  el("cfgRetryEnabled").checked = data.mensal_schedule_retry_enabled !== false;
  el("cfgRetryHours").value = data.mensal_schedule_retry_hours || 2;
  el("cfgRetryMax").value = data.mensal_schedule_max_retries || 3;
  syncRetryOptions();
  el("cfgNextRun").textContent = data.next_run_at
    ? `Próxima execução: ${data.next_run_at} (America/Sao_Paulo)`
    : "Fuso: America/Sao_Paulo";
  el("cfgSmtpFrom").value = data.smtp_from || "";
  el("cfgSmtpTo").value = data.smtp_to || "";
  el("cfgSmtpCc").value = data.smtp_cc || "";
  el("cfgSmtpAlert").value = data.smtp_alert_to || "";
}

function showConfigMsg(text, ok) {
  const box = el("configMsg");
  if (!box) return;
  box.textContent = text;
  box.classList.remove("hidden", "is-ok", "is-error");
  box.classList.add(ok ? "is-ok" : "is-error");
}

function hideConfigMsg() {
  const box = el("configMsg");
  if (!box) return;
  box.textContent = "";
  box.classList.add("hidden");
  box.classList.remove("is-ok", "is-error");
}

async function loadAutomationConfig() {
  const res = await fetch(apiUrl("/api/settings/automation"), API);
  if (res.status === 401) {
    window.location.href = "/login.html";
    return false;
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = typeof err.detail === "string" ? err.detail : null;
    throw new Error(detail || `Erro ao carregar configuração (${res.status})`);
  }
  fillConfigForm(await res.json());
  hideConfigMsg();
  return true;
}

async function saveAutomationConfig(ev) {
  ev.preventDefault();
  const btn = el("btnSaveConfig");
  btn.disabled = true;
  showConfigMsg("Salvando…", true);

  const retryEnabled = el("cfgRetryEnabled").checked;
  const retryHours = Number(el("cfgRetryHours").value);
  const retryMax = Number(el("cfgRetryMax").value);

  if (retryEnabled) {
    if (!Number.isFinite(retryHours) || retryHours < 1 || retryHours > 168) {
      showConfigMsg("Informe o intervalo em horas (1 a 168).", false);
      btn.disabled = false;
      return;
    }
    if (!Number.isFinite(retryMax) || retryMax < 2 || retryMax > 20) {
      showConfigMsg("Informe o máximo de tentativas (2 a 20).", false);
      btn.disabled = false;
      return;
    }
  }

  const body = {
    mensal_schedule_enabled: el("cfgScheduleEnabled").checked,
    mensal_schedule_day: Number(el("cfgDay").value),
    mensal_schedule_hour: Number(el("cfgHour").value),
    mensal_schedule_minute: Number(el("cfgMinute").value),
    mensal_schedule_timezone: "America/Sao_Paulo",
    mensal_schedule_retry_enabled: retryEnabled,
    mensal_schedule_retry_hours: retryEnabled ? retryHours : undefined,
    mensal_schedule_max_retries: retryEnabled ? retryMax : undefined,
    smtp_from: el("cfgSmtpFrom").value.trim(),
    smtp_to: el("cfgSmtpTo").value.trim(),
    smtp_cc: el("cfgSmtpCc").value.trim(),
    smtp_alert_to: el("cfgSmtpAlert").value.trim(),
  };

  try {
    const res = await fetch(apiUrl("/api/settings/automation"), {
      method: "PUT",
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
      throw new Error(typeof err.detail === "string" ? err.detail : "Falha ao salvar");
    }
    fillConfigForm(await res.json());
    showConfigMsg("Configuração salva.", true);
  } catch (err) {
    showConfigMsg(err.message || "Erro ao salvar", false);
  } finally {
    btn.disabled = false;
  }
}

async function openConfigModal() {
  const modal = el("configModal");
  if (!modal) return;
  hideConfigMsg();
  modal.classList.remove("hidden");
  document.body.classList.add("modal-open");
  try {
    await loadAutomationConfig();
  } catch (err) {
    // Só alerta se a API/rede realmente falhou
    if (err && err.message) {
      showConfigMsg(err.message, false);
    }
  }
}

function closeConfigModal() {
  const modal = el("configModal");
  if (!modal) return;
  modal.classList.add("hidden");
  document.body.classList.remove("modal-open");
}

const configForm = el("configForm");
if (configForm) {
  configForm.addEventListener("submit", saveAutomationConfig);
}
el("cfgRetryEnabled")?.addEventListener("change", syncRetryOptions);
el("btnOpenConfig")?.addEventListener("click", openConfigModal);
el("btnCloseConfig")?.addEventListener("click", closeConfigModal);
el("configModalBackdrop")?.addEventListener("click", closeConfigModal);
document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape" && el("configModal") && !el("configModal").classList.contains("hidden")) {
    closeConfigModal();
  }
});

(async () => {
  const me = await requireAuth();
  if (!me) return;
  if (userLabel) userLabel.textContent = me.user || "";
  paintClientBadge(me.display_name, me.adom);
  await loadClient();
})();
