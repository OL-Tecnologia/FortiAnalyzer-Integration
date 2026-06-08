const API = "http://127.0.0.1:8765";

const el = (id) => document.getElementById(id);

const panelWelcome = el("panelWelcome");
const panelInstall = el("panelInstall");
const panelDone = el("panelDone");
const btnStart = el("btnStart");
const btnRecheck = el("btnRecheck");
const btnLaunch = el("btnLaunch");
const btnReinstall = el("btnReinstall");
const chkPackage = el("chkPackage");
const chkPython = el("chkPython");
const chkInstalled = el("chkInstalled");
const packageHint = el("packageHint");
const pythonHint = el("pythonHint");
const installBar = el("installBar");
const installPct = el("installPct");
const installMessage = el("installMessage");
const installLog = el("installLog");
const errorBox = el("errorBox");

let pollTimer = null;

function showPanel(step) {
  [panelWelcome, panelInstall, panelDone].forEach((p) => p.classList.add("hidden"));
  document.querySelectorAll(".step-dot").forEach((d) => {
    const n = Number(d.dataset.step);
    d.classList.toggle("is-active", n === step);
    d.classList.toggle("is-done", n < step);
  });
  if (step === 1) panelWelcome.classList.remove("hidden");
  if (step === 2) panelInstall.classList.remove("hidden");
  if (step === 3) panelDone.classList.remove("hidden");
}

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.classList.remove("hidden");
}

function clearError() {
  errorBox.classList.add("hidden");
}

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || data.detail || res.statusText);
  return data;
}

function updatePreflight(data) {
  clearError();
  let canInstall = true;

  if (data.project_ok) {
    chkPackage.textContent = `Pacote completo (${data.project_path || "OK"})`;
    chkPackage.className = "ok";
    packageHint.classList.add("hidden");
  } else {
    chkPackage.textContent = "Pacote incompleto — extraia o ZIP inteiro";
    chkPackage.className = "fail";
    packageHint.classList.remove("hidden");
    canInstall = false;
    if (data.project_error) showError(data.project_error);
  }

  if (data.python_version) {
    chkPython.textContent = `Python ${data.python_version} encontrado`;
    chkPython.className = "ok";
    pythonHint.classList.add("hidden");
  } else {
    chkPython.textContent = "Python 3.11+ nao encontrado";
    chkPython.className = "fail";
    pythonHint.classList.remove("hidden");
    canInstall = false;
  }

  btnStart.disabled = !canInstall;

  if (data.installed) {
    chkInstalled.textContent = `Ja instalado (ADOM ${data.adom || "—"})`;
    chkInstalled.className = "ok";
    btnStart.textContent = "Reinstalar";
  } else {
    chkInstalled.textContent = "Sistema ainda nao instalado";
    chkInstalled.className = "";
    btnStart.textContent = "Instalar";
  }
}

async function loadPreflight() {
  try {
    const data = await api("/api/install/preflight");
    updatePreflight(data);
    if (data.status === "completed" && data.installed) {
      showPanel(3);
    }
  } catch (err) {
    showError("Nao foi possivel conectar ao instalador. Execute Instalar.bat.");
  }
}

function renderLog(logs) {
  installLog.innerHTML = (logs || [])
    .map((line) => `<li>${escapeHtml(line)}</li>`)
    .join("");
  installLog.scrollTop = installLog.scrollHeight;
}

function escapeHtml(text) {
  const d = document.createElement("div");
  d.textContent = text;
  return d.innerHTML;
}

function updateInstallProgress(data) {
  const pct = data.percent ?? 0;
  installBar.style.width = `${pct}%`;
  installPct.textContent = `${pct}%`;
  installMessage.textContent = data.message || "Instalando...";
  renderLog(data.logs);
}

async function pollStatus() {
  try {
    const data = await api("/api/install/status");
    updateInstallProgress(data);
    if (data.status === "completed") {
      stopPoll();
      showPanel(3);
      el("doneMessage").textContent = data.message || "Instalacao concluida.";
      return;
    }
    if (data.status === "failed") {
      stopPoll();
      showPanel(1);
      showError(data.error || data.message || "Falha na instalacao");
    }
  } catch (err) {
    stopPoll();
    showError(err.message);
    showPanel(1);
  }
}

function startPoll() {
  stopPoll();
  pollTimer = setInterval(pollStatus, 600);
  pollStatus();
}

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function startInstall() {
  clearError();
  showPanel(2);
  installBar.style.width = "0%";
  installLog.innerHTML = "";
  try {
    await api("/api/install/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ shortcut: true, force_env: false }),
    });
    startPoll();
  } catch (err) {
    showError(err.message);
    showPanel(1);
  }
}

async function launchPortal() {
  try {
    const data = await api("/api/install/launch-portal", { method: "POST" });
    if (data.url) window.open(data.url, "_blank");
  } catch (err) {
    showError(err.message);
  }
}

btnStart.addEventListener("click", startInstall);
btnRecheck.addEventListener("click", loadPreflight);
btnLaunch.addEventListener("click", launchPortal);
btnReinstall.addEventListener("click", startInstall);

loadPreflight();
