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

async function initLoginPage() {
  const me = await checkAuth();
  if (me && me.authenticated) {
    window.location.href = "/";
    return;
  }

  const form = document.getElementById("loginForm");
  const btn = document.getElementById("btnLogin");
  if (!form) return;

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    btn.disabled = true;
    document.getElementById("loginError")?.classList.add("hidden");

    const user = document.getElementById("loginUser").value.trim();
    const password = document.getElementById("loginPassword").value;

    try {
      const res = await fetch(apiUrl("/api/auth/faz/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ user, password }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Credenciais inválidas");
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
