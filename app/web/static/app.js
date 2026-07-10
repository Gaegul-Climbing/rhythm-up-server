import { initAuth } from "./features/auth.js";
import { initBooking, loadBranches } from "./features/booking.js";
import { initPayment } from "./features/payment.js";
import { initReservations, loadReservations } from "./features/reservations.js";
import { $$ } from "./core/dom.js";

export function showView(name) {
  $$(".view").forEach((view) => view.classList.remove("active"));
  document.querySelector(`#${name}View`).classList.add("active");

  if (name === "booking") {
    loadBranches();
  }

  if (name === "reservations") {
    loadReservations();
  }

  scrollTo({ top: 0, behavior: "smooth" });
}

$$('[data-view]').forEach((button) => {
  button.addEventListener("click", () => showView(button.dataset.view));
});

initAuth(showView);
initBooking();
initPayment(showView);
initReservations(showView);
