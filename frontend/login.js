const API_BASE = window.location.origin;

const API = { credentials: "include" };

function apiUrl(path) {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

async function checkAuth() {
  const res = await fetch(apiUrl("/api/auth/me"), API);
  if (!res.ok) return null;
  return res.json();
}

async function requireAuth(redirectToLogin = true) {
  const me = await checkAuth();
  if (!me || !me.authenticated) {
    if (redirectToLogin) {
      window.location.href = "/login.html";
    }
    return null;
  }
  return me;
}

async function logout() {
  await fetch(apiUrl("/api/auth/logout"), { method: "POST", ...API });
  window.location.href = "/login.html";
}

function showLoginError(msg) {
  const box = document.getElementById("loginError");
  if (!box) return;
  box.textContent = msg;
  box.classList.remove("hidden");
}

async function loadClients() {
  const select = document.getElementById("loginClient");
  const hint = document.getElementById("loginAdomHint");
  const field = document.getElementById("clientField");
  if (!select) return [];

  const res = await fetch(apiUrl("/api/clients"), API);
  if (!res.ok) {
    throw new Error("Não foi possível carregar a lista de clientes.");
  }
  const clients = await res.json();
  select.innerHTML = clients
    .map(
      (c) =>
        `<option value="${c.slug}" data-adom="${c.adom}">${c.display_name} (${c.adom})</option>`
    )
    .join("");

  if (clients.length <= 1 && field) {
    field.classList.add("hidden");
  }

  const updateHint = () => {
    const opt = select.selectedOptions[0];
    if (hint && opt) {
      hint.textContent = `ADOM: ${opt.dataset.adom || "—"}`;
    }
  };
  select.addEventListener("change", updateHint);
  updateHint();
  return clients;
}

async function initLoginPage() {
  const me = await checkAuth();
  if (me && me.authenticated) {
    window.location.href = "/";
    return;
  }

  const form = document.getElementById("loginForm");
  const btn = document.getElementById("btnLogin");
  if (!form) return;

  try {
    const clients = await loadClients();
    if (!clients.length) {
      showLoginError("Nenhum cliente cadastrado. Use a engrenagem (Administração) para cadastrar.");
      btn.disabled = true;
      return;
    }
  } catch (err) {
    showLoginError(err.message || "Falha ao carregar clientes");
  }

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    btn.disabled = true;
    document.getElementById("loginError")?.classList.add("hidden");

    const user = document.getElementById("loginUser").value.trim();
    const password = document.getElementById("loginPassword").value;
    const clientSlug = document.getElementById("loginClient")?.value || "";

    try {
      const res = await fetch(apiUrl("/api/auth/faz/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ user, password, client_slug: clientSlug }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = typeof err.detail === "string" ? err.detail : null;
        if (res.status === 503) {
          throw new Error(detail || "Não foi possível conectar ao FortiAnalyzer. Verifique rede/VPN.");
        }
        if (res.status === 429) {
          throw new Error(detail || "Muitas tentativas. Aguarde alguns minutos.");
        }
        if (res.status >= 500) {
          throw new Error(detail || "Erro interno no servidor. Tente novamente.");
        }
        throw new Error(detail || "Credenciais inválidas");
      }
      window.location.href = "/";
    } catch (err) {
      showLoginError(err.message || "Falha no login");
      btn.disabled = false;
    }
  });
}

if (document.getElementById("loginForm")) {
  initLoginPage();
}
