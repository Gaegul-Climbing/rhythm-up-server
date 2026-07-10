import { api, isSessionExpiredError } from "../core/api.js";
import { $, showToast } from "../core/dom.js";
import { formatTime } from "../core/format.js";
import { state } from "../core/state.js";

function reservationCard(reservation) {
  const startAt = new Date(reservation.start_at);
  const endAt = new Date(reservation.end_at);
  const month = startAt.toLocaleDateString("ko-KR", { month: "short" });
  const statusControl =
    reservation.status === "confirmed"
      ? `<button class="status" data-cancel-reservation="${reservation.id}">
           예약 취소
         </button>`
      : '<span class="status">취소됨</span>';

  return `
    <article class="reservation-card">
      <div class="reservation-date">
        <small>${month}</small>
        <b>${startAt.getDate()}</b>
      </div>
      <div>
        <h3>예약된 연습실</h3>
        <p>${formatTime(startAt)} — ${formatTime(endAt)}</p>
      </div>
      ${statusControl}
    </article>
  `;
}

async function cancelReservation(reservationId) {
  if (!confirm("이 예약을 취소할까요?")) {
    return;
  }

  try {
    await api(`/reservations/${reservationId}`, { method: "DELETE" });
    showToast("예약을 취소했습니다.");
    loadReservations();
  } catch (error) {
    if (isSessionExpiredError(error)) {
      return;
    }
    showToast(error.message);
  }
}

function bindCancelButtons() {
  document.querySelectorAll("[data-cancel-reservation]").forEach((button) => {
    button.onclick = () => cancelReservation(button.dataset.cancelReservation);
  });
}

export async function loadReservations() {
  const list = $("#reservationList");

  if (!state.token) {
    list.innerHTML = `
      <div class="empty">
        로그인하면 예약 내역을 확인할 수 있어요.<br><br>
        <button class="primary" data-reservation-login>로그인</button>
      </div>
    `;
    return;
  }

  try {
    const reservations = await api("/reservations");
    list.innerHTML = reservations.length
      ? reservations.map(reservationCard).join("")
      : `
          <div class="empty">
            아직 예약이 없습니다.<br>첫 연습을 예약해 보세요!
          </div>
        `;
    bindCancelButtons();
  } catch (error) {
    if (isSessionExpiredError(error)) {
      return;
    }
    showToast(error.message);
  }
}

export function initReservations(showView) {
  $("#reservationList").addEventListener("click", (event) => {
    if (event.target.matches("[data-reservation-login]")) {
      showView("auth");
    }
  });
}
