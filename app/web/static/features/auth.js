import { api, loginRequest } from "../core/api.js";
import { $, $$, showToast } from "../core/dom.js";
import { clearSession, saveToken, state } from "../core/state.js";

function updateAuthButton(showView) {
  const authButton = $("#authButton");
  authButton.textContent = state.token ? "로그아웃" : "로그인";

  if (!state.token) {
    authButton.onclick = () => showView("auth");
    return;
  }

  authButton.onclick = (event) => {
    event.stopPropagation();
    clearSession();
    updateAuthButton(showView);
    showView("home");
    showToast("로그아웃되었습니다.");
  };
}

async function login(email, password, showView) {
  const data = await loginRequest(email, password);
  saveToken(data.access_token);
  updateAuthButton(showView);
}

function initAuthTabs() {
  $$("[data-auth-tab]").forEach((button) => {
    button.onclick = () => {
      $$("[data-auth-tab]").forEach((tab) => {
        tab.classList.toggle("active", tab === button);
      });

      const isLoginTab = button.dataset.authTab === "login";
      $("#loginForm").classList.toggle("hidden", !isLoginTab);
      $("#signupForm").classList.toggle("hidden", isLoginTab);
    };
  });
}

function initLoginForm(showView) {
  $("#loginForm").onsubmit = async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);

    try {
      await login(form.get("email"), form.get("password"), showView);
      showToast("반가워요. 로그인되었습니다.");
      showView("booking");
    } catch (error) {
      showToast(error.message);
    }
  };
}

function initSignupForm(showView) {
  $("#signupForm").onsubmit = async (event) => {
    event.preventDefault();
    const form = Object.fromEntries(new FormData(event.target));

    try {
      await api("/auth/signup", { method: "POST", json: form });
      await login(form.email, form.password, showView);
      showToast("가입이 완료되었습니다!");
      showView("booking");
    } catch (error) {
      showToast(error.message);
    }
  };
}

function initExpiredSessionHandler(showView) {
  document.addEventListener("auth:session-expired", (event) => {
    clearSession();
    updateAuthButton(showView);
    showView("auth");
    showToast(event.detail?.message || "로그인이 만료되었습니다. 다시 로그인해 주세요.");
  });
}

export function initAuth(showView) {
  updateAuthButton(showView);
  initAuthTabs();
  initLoginForm(showView);
  initSignupForm(showView);
  initExpiredSessionHandler(showView);
}
