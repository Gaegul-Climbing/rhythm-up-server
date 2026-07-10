export const state = {
  token: localStorage.getItem("rhythm_token"),
  user: null,
  branch: null,
  room: null,
  slot: null,
};

export function saveToken(token) {
  state.token = token;
  localStorage.setItem("rhythm_token", token);
}

export function clearSession() {
  localStorage.removeItem("rhythm_token");
  state.token = null;
  state.user = null;
}
