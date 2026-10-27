const API_BASE = window.location.origin;
const API = { credentials: "include" };

function apiUrl(path) {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

const el = (id) => document.getElementById(id);

const RUN_LABELS = { diario: "Diário", semanal: "Semanal", mensal: "Mensal" };

function formatRun(iso) {
  if (!iso) return "desligado";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(date);
}

function paintNextRuns(box, runs, schedules, masterEnabled) {
  if (!box) return;
  box.replaceChildren();
  if (masterEnabled === false) {
    const note = document.createElement("li");
    note.textContent = "Envio automático desligado";
    box.appendChild(note);
  }
  for (const key of ["diario", "semanal", "mensal"]) {
    const li = document.createElement("li");
    const enabled = schedules?.[key]?.enabled !== false;
    li.textContent = `${RUN_LABELS[key]}: ${enabled && runs[key] ? formatRun(runs[key]) : "desligado"}`;
    box.appendChild(li);
  }
}

function readClock(prefix) {
  return {
    enabled: el(prefix + "Enabled").checked,
    hour: Number(el(prefix + "Hour").value),
    minute: Number(el(prefix + "Minute").value),
  };
}

function readScheduleFields(enabledId) {
  const diario = readClock("cfgDiario");
  const semanal = readClock("cfgSemanal");
  const mensal = readClock("cfgMensal");
  semanal.weekday = Number(el("cfgSemanalWeekday").value);
  mensal.day = Number(el("cfgMensalDay").value);
  return {
    enabled: el(enabledId).checked,
    hour: diario.hour,
    minute: diario.minute,
    day: mensal.day,
    diario,
    semanal,
    mensal,
  };
}

function fillClock(prefix, report, hour, minute) {
  const item = report || {};
  el(prefix + "Enabled").checked = item.enabled !== false;
  el(prefix + "Hour").value = item.hour ?? hour;
  el(prefix + "Minute").value = item.minute ?? minute;
}

function fillScheduleFields(enabledId, schedule, hour, minute) {
  el(enabledId).checked = !!schedule.enabled;
  fillClock("cfgDiario", schedule.diario, hour, minute);
  fillClock("cfgSemanal", schedule.semanal, hour, minute);
  el("cfgSemanalWeekday").value = String(schedule.semanal?.weekday ?? 0);
  fillClock("cfgMensal", schedule.mensal, hour, minute);
  el("cfgMensalDay").value = schedule.mensal?.day ?? 1;
}

function validateSchedule(schedule) {
  const clocks = [
    ["diário", schedule.diario],
    ["semanal", schedule.semanal],
    ["mensal", schedule.mensal],
  ];
  for (const [label, clock] of clocks) {
    if (!Number.isInteger(clock.hour) || clock.hour < 0 || clock.hour > 23) {
      return `Hora do ${label} deve estar entre 0 e 23.`;
    }
    if (!Number.isInteger(clock.minute) || clock.minute < 0 || clock.minute > 59) {
      return `Minuto do ${label} deve estar entre 0 e 59.`;
    }
  }
  if (!Number.isInteger(schedule.semanal.weekday) || schedule.semanal.weekday < 0 || schedule.semanal.weekday > 6) {
    return "Escolha o dia da semana do relatório semanal.";
  }
  if (!Number.isInteger(schedule.mensal.day) || schedule.mensal.day < 1 || schedule.mensal.day > 28) {
    return "Dia do mês do relatório mensal deve estar entre 1 e 28.";
  }
  return "";
}

let editingSlug = null;
let adminSetup = false;

function showMsg(text, ok) {
  const box = el("adminMsg");
  if (!box) return;
  box.textContent = text;
  box.classList.remove("hidden", "is-ok", "is-error");
  box.classList.add(ok ? "is-ok" : "is-error");
}

function showLoginError(text) {
  const box = el("adminLoginError");
  if (!box) return;
  box.textContent = text;
  box.classList.remove("hidden");
}

function parseFazEndpoint(raw) {
  let text = (raw || "").trim();
  let useSsl = null;
  const lower = text.toLowerCase();
  if (lower.startsWith("https://")) {
    useSsl = true;
    text = text.slice(8);
  } else if (lower.startsWith("http://")) {
    useSsl = false;
    text = text.slice(7);
  }
  text = text.split("/")[0].trim();
  let host = text;
  let port = null;
  if ((text.match(/:/g) || []).length === 1) {
    const [h, p] = text.split(":");
    if (/^\d+$/.test(p)) {
      host = h;
      port = Number(p);
    }
  }
  return { host, port, useSsl };
}

function draftFromForm() {
  const endpoint = parseFazEndpoint(el("cfgFazHost").value);
  const port = endpoint.port ?? Number(el("cfgFazPort").value || 8090);
  const useSsl = endpoint.useSsl ?? el("cfgFazSsl").checked;
  return {
    slug: el("cfgSlug").value.trim().toLowerCase(),
    display_name: el("cfgDisplayName").value.trim(),
    enabled: el("cfgEnabled").checked,
    faz: {
      host: endpoint.host,
      port,
      use_ssl: useSsl,
      verify_ssl: el("cfgFazVerifySsl").checked,
      adom: el("cfgFazAdom").value.trim(),
      report_schedule_mensal: el("cfgFazSchedule").value.trim(),
    },
    automation: {
      faz_user: el("cfgAutoUser").value.trim(),
    },
    schedule: readScheduleFields("cfgSchedEnabled"),
    email: {
      smtp_from: el("cfgSmtpFrom").value.trim(),
      smtp_to: el("cfgSmtpTo").value.trim(),
      smtp_cc: el("cfgSmtpCc").value.trim(),
      smtp_alert_to: el("cfgSmtpAlert").value.trim(),
    },
    pdf: {
      cover_logo:
        el("cfgLogo").value.trim() ||
        `assets/clients/${el("cfgSlug").value.trim().toLowerCase() || "cliente"}/logo.png`,
      cover_logo_width_cm: Number(el("cfgLogoWidth")?.value || 2.1),
      cover_logo_align: el("cfgLogoAlign")?.value || "right",
      cover_logo_offset_x_cm: Number(el("cfgLogoOffsetX")?.value || 0),
      cover_logo_offset_y_cm: Number(el("cfgLogoOffsetY")?.value || 0.35),
      // Faixas OL — padrão fixo da capa (não configuráveis por tenant)
      cover_header: "assets/img/cabecalho_capa.png",
      cover_footer: "assets/img/rodape_capa.png",
      email_subject_prefix: el("cfgEmailPrefix").value.trim(),
    },
    hierarchy: {
      device_pattern:
        el("cfgDevicePattern").value.trim() ||
        "^(?:(?P<prefix>hafw\\d+)|fw)-(?P<region>[a-z0-9]+)-(?P<site>.+)$",
    },
    output: { subdir: el("cfgSlug").value.trim().toLowerCase() },
  };
}

const OL_COVER_HEADER = "assets/img/cabecalho_capa.png";
const OL_COVER_FOOTER = "assets/img/rodape_capa.png";

function setAssetField(kind, path) {
  const map = {
    cover_logo: { path: "cfgLogo", hint: "cfgLogoPath" },
  };
  const ids = map[kind];
  if (!ids) return;
  if (el(ids.path)) el(ids.path).value = path || "";
  if (el(ids.hint)) el(ids.hint).textContent = path ? `Salvo em: ${path}` : "";
  _lastLogoSrc = "";
  refreshCoverPreview();
}

function clearAssetPreviews() {
  _lastBandHeaderSrc = "";
  _lastBandFooterSrc = "";
  _lastLogoSrc = "";
  setAssetField("cover_logo", "");
  if (el("cfgCoverHeader")) el("cfgCoverHeader").value = OL_COVER_HEADER;
  if (el("cfgCoverFooter")) el("cfgCoverFooter").value = OL_COVER_FOOTER;
  refreshCoverPreview();
}

function _monthYearLabel() {
  const months = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
  ];
  const now = new Date();
  return `${months[now.getMonth()]}/${now.getFullYear()}`;
}

function _previewSrc(kind, relPath, { bust = false } = {}) {
  if (!relPath) return "";
  const slug = (editingSlug || el("cfgSlug")?.value || "").trim().toLowerCase();
  const t = bust ? Date.now() : "1";
  if (slug && relPath.includes(`/clients/${slug}/`)) {
    return apiUrl(`/api/admin/clients/${slug}/assets/${kind}?t=${bust ? Date.now() : t}`);
  }
  // Assets OL padrão: sem cache-bust agressivo (evita spam 404/200 no console)
  return apiUrl(`/api/admin/asset-preview?path=${encodeURIComponent(relPath)}&t=${t}`);
}

function _setPreviewImage(imgId, phId, src) {
  const img = el(imgId);
  const ph = el(phId);
  if (!img) return;
  if (!src) {
    img.removeAttribute("src");
    img.classList.add("hidden");
    ph?.classList.remove("hidden");
    return;
  }
  img.onload = () => {
    img.classList.remove("hidden");
    ph?.classList.add("hidden");
  };
  img.onerror = () => {
    img.classList.add("hidden");
    ph?.classList.remove("hidden");
  };
  img.src = src;
}

function _setBandImage(imgId, src) {
  const img = el(imgId);
  if (!img) return;
  if (!src) {
    img.removeAttribute("src");
    img.classList.add("is-missing");
    return;
  }
  img.onload = () => img.classList.remove("is-missing");
  img.onerror = () => img.classList.add("is-missing");
  img.src = src;
}

let _previewTimer = null;
let _lastBandHeaderSrc = "";
let _lastBandFooterSrc = "";
let _lastLogoSrc = "";

function refreshCoverPreview() {
  // Debounce: evita tempestade de requests a cada tecla no formulário
  if (_previewTimer) clearTimeout(_previewTimer);
  _previewTimer = setTimeout(_refreshCoverPreviewNow, 180);
}

function _refreshCoverPreviewNow() {
  const adom = el("cfgFazAdom")?.value.trim() || "ADOM";
  const display = el("cfgDisplayName")?.value.trim() || "";
  if (el("previewSubtitle")) {
    const label = display || adom || "Cliente";
    el("previewSubtitle").textContent = `Relatório Unificado — ${label}`;
  }
  if (el("previewTitle")) {
    el("previewTitle").textContent = "RELATÓRIO MENSAL  GERAL";
  }
  if (el("previewUnits")) {
    el("previewUnits").textContent = "N unidades regionais · N dispositivos";
  }
  if (el("previewMonth")) {
    el("previewMonth").textContent = _monthYearLabel();
  }
  const cover = el("coverPreview");
  if (cover) cover.dataset.client = display || adom;

  const headerSrc = _previewSrc("cover_header", OL_COVER_HEADER);
  const footerSrc = _previewSrc("cover_footer", OL_COVER_FOOTER);
  const logoSrc = _previewSrc("cover_logo", el("cfgLogo")?.value.trim());
  // Faixas OL são estáveis — não recarregar a cada refresh (só cache-bust na 1ª vez)
  if (headerSrc !== _lastBandHeaderSrc) {
    _lastBandHeaderSrc = headerSrc;
    _setBandImage("previewHeader", headerSrc);
  }
  if (footerSrc !== _lastBandFooterSrc) {
    _lastBandFooterSrc = footerSrc;
    _setBandImage("previewFooter", footerSrc);
  }
  if (logoSrc !== _lastLogoSrc) {
    _lastLogoSrc = logoSrc;
    _setPreviewImage("previewLogo", "previewLogoPh", logoSrc);
  }
  _applyLogoLayoutPreview();
}

function _applyLogoLayoutPreview() {
  const row = document.querySelector(".cover-a4-logo-row");
  const logo = el("previewLogo");
  const ph = el("previewLogoPh");
  if (!row) return;

  const widthCm = Math.max(0.5, Math.min(10, Number(el("cfgLogoWidth")?.value || 2.1)));
  const align = el("cfgLogoAlign")?.value || "right";
  const oxCm = Number(el("cfgLogoOffsetX")?.value || 0);
  const oyCm = Math.max(0, Number(el("cfgLogoOffsetY")?.value || 0.35));
  // A4 = 21 cm de largura → % da prévia
  const widthPct = (widthCm / 21) * 100;
  const oxPct = (oxCm / 21) * 100;
  // Altura da prévia ~ proporção A4; Y em % da altura da capa (~29.7 cm)
  const oyPct = (oyCm / 29.7) * 100;

  row.style.justifyContent =
    align === "left" ? "flex-start" : align === "center" ? "center" : "flex-end";
  row.style.paddingBottom = `${Math.max(oyPct, 0.4)}%`;

  const applyBox = (node) => {
    if (!node) return;
    node.style.width = `${widthPct}%`;
    node.style.maxWidth = `${widthPct}%`;
    node.style.maxHeight = "none";
    node.style.height = "auto";
    node.style.transform = `translateX(${oxPct}%)`;
  };
  applyBox(logo);
  applyBox(ph);
}

async function downloadBrandingPreview() {
  const draft = draftFromForm();
  if (!draft.slug) {
    showMsg("Informe o slug antes de baixar a prévia.", false);
    return;
  }
  if (!draft.display_name) {
    showMsg("Informe o Nome de exibição antes de baixar a prévia.", false);
    return;
  }
  showMsg("Gerando PDF de prévia (capa + página com rodapé)…", true);
  try {
    const res = await fetch(apiUrl("/api/admin/branding-preview"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        ...draft,
        require_connection_ok: false,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(typeof err.detail === "string" ? err.detail : "Falha ao gerar prévia");
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `previa_branding_${draft.slug}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    showMsg("PDF de prévia baixado (página 1 = capa, página 2 = rodapé do corpo).", true);
  } catch (err) {
    showMsg(err.message || "Falha ao baixar prévia", false);
  }
}

async function uploadAsset(kind, fileInput) {
  const file = fileInput.files?.[0];
  if (!file) return;
  const slug = (editingSlug || el("cfgSlug").value || "").trim().toLowerCase();
  if (!slug) {
    showMsg("Informe o slug do cliente antes de enviar o logo.", false);
    fileInput.value = "";
    return;
  }
  const body = new FormData();
  body.append("kind", kind);
  body.append("file", file);
  showMsg(`Enviando ${kind}…`, true);
  const res = await fetch(apiUrl(`/api/admin/clients/${slug}/assets`), {
    method: "POST",
    credentials: "include",
    body,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    showMsg(typeof data.detail === "string" ? data.detail : "Falha no upload", false);
    fileInput.value = "";
    return;
  }
  if (!editingSlug) editingSlug = slug;
  setAssetField(kind, data.path || "");
  showMsg(`Upload OK: ${data.path}`, true);
  if (data.client) {
    // mantém form alinhado se o YAML já existia
    el("cfgSlug").disabled = true;
  }
}

function fillForm(client) {
  editingSlug = client.slug;
  el("cfgSlug").value = client.slug || "";
  el("cfgSlug").disabled = true;
  el("cfgDisplayName").value = client.display_name || "";
  el("cfgEnabled").checked = client.enabled !== false;
  el("cfgFazHost").value = client.faz?.host || "";
  el("cfgFazPort").value = client.faz?.port || 8090;
  el("cfgFazAdom").value = client.faz?.adom || "";
  el("cfgFazSchedule").value = client.faz?.report_schedule_mensal || "";
  el("cfgFazSsl").checked = client.faz?.use_ssl !== false;
  el("cfgFazVerifySsl").checked = !!client.faz?.verify_ssl;
  el("cfgAutoUser").value = client.automation?.faz_user || "";
  el("cfgAutoPassword").value = "";
  el("cfgAutoPasswordHint").textContent = client.automation_password_set
    ? "Senha de automação já cadastrada (deixe em branco para manter)."
    : "Nenhuma senha de automação cadastrada ainda.";
  fillScheduleFields("cfgSchedEnabled", client.schedule || {}, client.schedule?.hour ?? 6, client.schedule?.minute ?? 0);
  paintNextRuns(el("cfgNextRuns"), client.next_runs || {}, client.schedule || {}, !!client.schedule?.enabled);
  el("cfgSmtpFrom").value = client.email?.smtp_from || "";
  el("cfgSmtpTo").value = client.email?.smtp_to || "";
  el("cfgSmtpCc").value = client.email?.smtp_cc || "";
  el("cfgSmtpAlert").value = client.email?.smtp_alert_to || "";
  el("cfgEmailPrefix").value = client.pdf?.email_subject_prefix || "";
  setAssetField("cover_logo", client.pdf?.cover_logo || "");
  if (el("cfgLogoWidth")) el("cfgLogoWidth").value = client.pdf?.cover_logo_width_cm ?? 2.1;
  if (el("cfgLogoAlign")) el("cfgLogoAlign").value = client.pdf?.cover_logo_align || "right";
  if (el("cfgLogoOffsetX")) el("cfgLogoOffsetX").value = client.pdf?.cover_logo_offset_x_cm ?? 0;
  if (el("cfgLogoOffsetY")) el("cfgLogoOffsetY").value = client.pdf?.cover_logo_offset_y_cm ?? 0.35;
  if (el("cfgCoverHeader")) el("cfgCoverHeader").value = OL_COVER_HEADER;
  if (el("cfgCoverFooter")) el("cfgCoverFooter").value = OL_COVER_FOOTER;
  el("cfgDevicePattern").value = client.hierarchy?.device_pattern || "";
  el("clientFormTitle").textContent = `Editar: ${client.display_name}`;
  el("clientForm").classList.remove("hidden");
  refreshCoverPreview();
}

function resetForm() {
  editingSlug = null;
  el("clientForm").reset();
  el("cfgNextRuns")?.replaceChildren();
  el("cfgSlug").disabled = false;
  el("cfgEnabled").checked = true;
  el("cfgFazSsl").checked = true;
  el("cfgFazPort").value = 8090;
  el("cfgFazSchedule").value = "MENSAL-RELATÓRIO DE ENDPOINT";
  el("cfgAutoPasswordHint").textContent = "";
  clearAssetPreviews();
  el("clientFormTitle").textContent = "Novo cliente";
  el("clientForm").classList.remove("hidden");
  el("adminMsg")?.classList.add("hidden");
  refreshCoverPreview();
}

async function loadClients() {
  const res = await fetch(apiUrl("/api/admin/clients"), API);
  if (!res.ok) throw new Error("Falha ao listar clientes");
  const clients = await res.json();
  const list = el("clientList");
  list.innerHTML = clients
    .map(
      (c) => `
    <li class="client-list-item">
      <div>
        <strong>${c.display_name}</strong>
        <span class="muted"> — ${c.slug} / ADOM ${c.faz?.adom || "?"} @ ${c.faz?.host || "?"}</span>
      </div>
      <div class="client-list-actions">
        <button type="button" class="btn btn-ghost btn-sm" data-edit="${c.slug}">Editar</button>
        <button type="button" class="btn btn-danger btn-sm" data-remove="${c.slug}" data-name="${escapeAttr(c.display_name)}">Remover FAZ</button>
      </div>
    </li>`
    )
    .join("");
  list.querySelectorAll("[data-edit]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const found = clients.find((c) => c.slug === btn.getAttribute("data-edit"));
      if (found) fillForm(found);
    });
  });
  list.querySelectorAll("[data-remove]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const slug = btn.getAttribute("data-remove");
      const name = btn.getAttribute("data-name") || slug;
      removeClient(slug, name);
    });
  });
}

function escapeAttr(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");
}

async function removeClient(slug, displayName) {
  if (!slug) return;
  const ok = window.confirm(
    `Remover o FAZ/cliente "${displayName}" (${slug})?\n\n` +
      "Isso apaga a configuração e o logo deste tenant.\n" +
      "PDFs já gerados em output/ são mantidos."
  );
  if (!ok) return;
  try {
    const res = await fetch(apiUrl(`/api/admin/clients/${slug}`), {
      ...API,
      method: "DELETE",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Falha ao remover (${res.status})`);
    }
    if (editingSlug === slug) {
      el("clientForm").classList.add("hidden");
      editingSlug = null;
    }
    showMsg(`Cliente "${displayName}" removido.`, true);
    await loadClients();
  } catch (err) {
    showMsg(err.message || String(err), false);
  }
}

function showSetupMode(enabled) {
  adminSetup = enabled;
  const lead = el("adminLoginLead");
  if (lead) {
    lead.textContent = enabled
      ? "Crie a senha do Super Admin. Ela vale só para esta instalação."
      : "Acesso Super Admin para cadastrar clientes (FAZ, ADOM, branding, e-mail automático).";
  }
  el("adminPasswordLabel").textContent = enabled ? "Crie a senha" : "Senha Super Admin";
  el("adminPasswordConfirmRow")?.classList.toggle("hidden", !enabled);
  el("adminSetupHint")?.classList.toggle("hidden", !enabled);
  const password = el("adminPassword");
  if (password) password.autocomplete = enabled ? "new-password" : "current-password";
  const confirm = el("adminPasswordConfirm");
  if (confirm) confirm.required = enabled;
  el("btnAdminLogin").textContent = enabled ? "Criar senha e entrar" : "Entrar";
}

async function ensureAdmin() {
  const res = await fetch(apiUrl("/api/admin/me"), API);
  const me = await res.json();
  showSetupMode(!me.configured);
  if (me.authenticated) {
    el("adminLoginCard").classList.add("hidden");
    el("adminPanel").classList.remove("hidden");
    el("btnAdminLogout").classList.remove("hidden");
    await loadClients();
    return true;
  }
  el("adminLoginCard").classList.remove("hidden");
  el("adminPanel").classList.add("hidden");
  el("btnAdminLogout").classList.add("hidden");
  return false;
}

async function init() {
  el("adminLoginForm")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    el("adminLoginError")?.classList.add("hidden");
    const password = el("adminPassword").value;
    const path = adminSetup ? "/api/admin/setup" : "/api/admin/login";
    const payload = adminSetup
      ? { password, password_confirm: el("adminPasswordConfirm").value }
      : { password };
    const res = await fetch(apiUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const detail = typeof err.detail === "string" ? err.detail : null;
      if (res.status === 429) {
        showLoginError(detail || "Muitas tentativas. Aguarde alguns minutos ou reinicie o app.");
      } else {
        showLoginError(detail || "Senha inválida");
      }
      return;
    }
    const ok = await ensureAdmin();
    if (!ok) {
      showLoginError(
        "Login OK, mas a sessão não ficou salva no navegador. Use sempre http://localhost:8000 (não misture com 127.0.0.1)."
      );
    }
  });

  el("btnAdminLogout")?.addEventListener("click", async () => {
    await fetch(apiUrl("/api/admin/logout"), { method: "POST", ...API });
    window.location.reload();
  });

  el("btnNewClient")?.addEventListener("click", resetForm);
  el("btnCancelClient")?.addEventListener("click", () => {
    el("clientForm").classList.add("hidden");
  });

  el("cfgFazHost")?.addEventListener("blur", () => {
    const parsed = parseFazEndpoint(el("cfgFazHost").value);
    if (!parsed.host) return;
    el("cfgFazHost").value = parsed.host;
    if (parsed.port != null) el("cfgFazPort").value = String(parsed.port);
    if (parsed.useSsl != null) el("cfgFazSsl").checked = parsed.useSsl;
  });

  el("cfgLogoFile")?.addEventListener("change", (ev) => uploadAsset("cover_logo", ev.target));
  el("btnRefreshCoverPreview")?.addEventListener("click", () => refreshCoverPreview());
  el("btnDownloadCoverPreview")?.addEventListener("click", () => downloadBrandingPreview());
  el("cfgFazAdom")?.addEventListener("input", () => refreshCoverPreview());
  el("cfgDisplayName")?.addEventListener("input", () => refreshCoverPreview());
  ["cfgLogoWidth", "cfgLogoAlign", "cfgLogoOffsetX", "cfgLogoOffsetY"].forEach((id) => {
    el(id)?.addEventListener("input", () => refreshCoverPreview());
    el(id)?.addEventListener("change", () => refreshCoverPreview());
  });

  function showEmailTest(text, ok, fix) {
    const box = el("emailTestMsg");
    const fixBox = el("emailTestFix");
    if (box) {
      box.textContent = text || "";
      box.classList.remove("hidden", "is-ok", "is-error");
      box.classList.add(ok ? "is-ok" : "is-error");
    }
    if (!fixBox) return;
    if (fix) {
      fixBox.textContent = `Como corrigir: ${fix}`;
      fixBox.classList.remove("hidden");
    } else {
      fixBox.textContent = "";
      fixBox.classList.add("hidden");
    }
  }

  el("btnTestEmail")?.addEventListener("click", async () => {
    const btn = el("btnTestEmail");
    if (btn) btn.disabled = true;
    showEmailTest("Enviando e-mail de teste…", true, "");
    try {
      const res = await fetch(apiUrl("/api/admin/email-test"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          smtp_from: el("cfgSmtpFrom").value.trim(),
          smtp_to: el("cfgSmtpTo").value.trim(),
          smtp_cc: el("cfgSmtpCc").value.trim(),
        }),
      });
      if (res.status === 401) {
        showEmailTest("A sessão de administrador expirou.", false, "Entre de novo na Administração e teste outra vez.");
        return;
      }
      if (res.status === 404) {
        showEmailTest(
          "Este programa ainda não tem o teste de e-mail.",
          false,
          "Feche o programa e abra a versão atualizada do FortiAnalyzer Reports."
        );
        return;
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.ok === false) {
        const problem = data.problem || data.message || data.detail || "O e-mail não foi enviado.";
        showEmailTest(typeof problem === "string" ? problem : "O e-mail não foi enviado.", false, data.fix || "");
        return;
      }
      showEmailTest(data.message || "E-mail de teste enviado.", true, "");
    } catch (err) {
      showEmailTest(
        err.message || "Não foi possível falar com o programa.",
        false,
        "Confira se o FortiAnalyzer Reports está aberto e tente de novo."
      );
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  el("btnTestConn")?.addEventListener("click", async () => {
    const draft = draftFromForm();
    const slug = editingSlug || draft.slug;
    if (!slug) {
      showMsg("Informe o slug.", false);
      return;
    }
    showMsg("Testando conexão…", true);
    const res = await fetch(apiUrl(`/api/admin/clients/${slug}/test-connection`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        draft,
        faz_user: draft.automation.faz_user,
        faz_password: el("cfgAutoPassword").value || null,
      }),
    });
    const data = await res.json().catch(() => ({}));
    showMsg(data.detail || (res.ok && data.ok ? "OK" : "Falha no teste"), !!data.ok);
  });

  el("clientForm")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const draft = draftFromForm();
    if (!draft.slug) {
      showMsg("Informe o slug.", false);
      return;
    }
    const scheduleError = validateSchedule(draft.schedule);
    if (scheduleError) {
      showMsg(scheduleError, false);
      return;
    }
    const password = el("cfgAutoPassword").value;
    const payload = {
      ...draft,
      automation_faz_password: password || null,
      require_connection_ok: true,
    };
    showMsg("Testando e salvando…", true);
    // Novo cadastro = POST; edição = PUT (API faz upsert se o YAML ainda não existir)
    const isEdit = !!editingSlug && editingSlug === draft.slug;
    let res = await fetch(
      isEdit ? apiUrl(`/api/admin/clients/${editingSlug}`) : apiUrl("/api/admin/clients"),
      {
        method: isEdit ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      }
    );
    // Se o form ficou em "editar" mas o tenant sumiu, cria via POST
    if (!res.ok && res.status === 404 && isEdit) {
      editingSlug = null;
      el("cfgSlug").disabled = false;
      res = await fetch(apiUrl("/api/admin/clients"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.detail;
      showMsg(
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
            : "Falha ao salvar",
        false
      );
      return;
    }
    showMsg("Cliente salvo com sucesso.", true);
    await loadClients();
    fillForm(data);
  });

  await ensureAdmin();
}

init();
