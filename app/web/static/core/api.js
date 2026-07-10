import { clearSession, state } from "./state.js";

function getErrorMessage(data) {
  return data?.error?.message || data?.detail || "요청을 처리하지 못했습니다.";
}

export function isSessionExpiredError(error) {
  return error?.name === "SessionExpiredError";
}

export async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };

  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }

  if (options.json) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.json);
  }

  const response = await fetch(path, { ...options, headers });
  const data = response.status === 204 ? null : await response.json();

  if (!response.ok) {
    if (response.status === 401 && data?.error?.code === "invalid_access_token") {
      const error = new Error("로그인이 만료되었습니다. 다시 로그인해 주세요.");
      error.name = "SessionExpiredError";
      clearSession();
      document.dispatchEvent(
        new CustomEvent("auth:session-expired", {
          detail: {
            message: error.message,
          },
        }),
      );
      throw error;
    }

    throw new Error(getErrorMessage(data));
  }

  return data;
}

export async function loginRequest(email, password) {
  const form = new URLSearchParams({ username: email, password });
  const response = await fetch("/auth/login", {
    method: "POST",
    body: form,
  });
  const data = await response.json();

  if (!response.ok) {
    throw new Error(getErrorMessage(data));
  }

  return data;
}
