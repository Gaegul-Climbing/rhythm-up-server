import { api, isSessionExpiredError } from "../core/api.js";
import { $, showToast } from "../core/dom.js";
import { createId } from "../core/format.js";
import { state } from "../core/state.js";

function openPaymentModal(message = "결제를 준비하고 있어요.") {
  $("#paymentModal").classList.remove("hidden");
  $("#paySpinner").classList.remove("hidden");
  $("#paySuccess").classList.add("hidden");
  $("#modalClose").classList.add("hidden");
  $("#payTitle").textContent = "결제를 확인하고 있어요";
  $("#payMessage").textContent = message;
}

function showPaymentSuccess(message = "예약이 확정되었습니다. 이제 연습만 하면 됩니다!") {
  $("#paySpinner").classList.add("hidden");
  $("#paySuccess").classList.remove("hidden");
  $("#payTitle").textContent = "예약이 확정됐어요";
  $("#payMessage").textContent = message;
  $("#modalClose").textContent = "내 예약 확인";
  $("#modalClose").classList.remove("hidden");
}

function showPaymentError(error) {
  $("#paySpinner").classList.add("hidden");
  $("#paySuccess").classList.add("hidden");
  $("#payTitle").textContent = "예약을 완료하지 못했어요";
  $("#payMessage").textContent = error.message || "결제 처리 중 문제가 발생했습니다.";
  $("#modalClose").textContent = "닫기";
  $("#modalClose").classList.remove("hidden");
}

async function createHold() {
  return api("/reservation-holds", {
    method: "POST",
    json: {
      branch_id: state.branch.id,
      room_id: state.room.id,
      start_at: state.slot,
      duration_hours: Number($("#duration").value),
    },
  });
}

async function createPaymentOrder(holdId) {
  return api("/payment-orders", {
    method: "POST",
    headers: { "Idempotency-Key": `web-order-${createId()}` },
    json: { hold_id: holdId },
  });
}

async function createPayment(orderId) {
  return api("/payments", {
    method: "POST",
    headers: { "Idempotency-Key": `web-payment-${createId()}` },
    json: { order_id: orderId },
  });
}

async function approveMockPayment(paymentId) {
  return api(`/mock-payment-provider/payments/${paymentId}/complete`, {
    method: "POST",
    json: { outcome: "approved", deliver_event: true },
  });
}

async function confirmTossPayment({ paymentKey, orderId, amount }) {
  return api("/payments/toss/confirm", {
    method: "POST",
    headers: { "Idempotency-Key": `toss-confirm-${orderId}` },
    json: {
      payment_key: paymentKey,
      order_id: orderId,
      amount: Number(amount),
    },
  });
}

async function requestTossPayment(checkout) {
  if (!window.TossPayments) {
    throw new Error("토스페이먼츠 SDK를 불러오지 못했습니다.");
  }

  const tossPayments = window.TossPayments(checkout.client_key);

  if (typeof tossPayments.payment === "function") {
    const payment = tossPayments.payment({
      customerKey: window.TossPayments.ANONYMOUS,
    });
    await payment.requestPayment({
      method: "CARD",
      amount: {
        currency: checkout.currency,
        value: checkout.amount,
      },
      orderId: checkout.order_id,
      orderName: checkout.order_name,
      successUrl: checkout.success_url,
      failUrl: checkout.fail_url,
    });
    return;
  }

  await tossPayments.requestPayment("카드", {
    amount: checkout.amount,
    orderId: checkout.order_id,
    orderName: checkout.order_name,
    successUrl: checkout.success_url,
    failUrl: checkout.fail_url,
  });
}

async function completeLocalPayment(payment) {
  await approveMockPayment(payment.id);
  showPaymentSuccess();
}

async function completeExternalPayment(payment) {
  if (payment.checkout?.provider === "toss") {
    await requestTossPayment(payment.checkout);
    return;
  }

  await completeLocalPayment(payment);
}

async function pay(showView) {
  if (!state.token) {
    showToast("예약하려면 먼저 로그인해 주세요.");
    showView("auth");
    return;
  }

  openPaymentModal("예약 공간을 잠시 잡아두고 결제 주문을 만들고 있어요.");

  try {
    const hold = await createHold();
    const order = await createPaymentOrder(hold.id);
    const payment = await createPayment(order.id);

    await completeExternalPayment(payment);
  } catch (error) {
    if (isSessionExpiredError(error)) {
      $("#paymentModal").classList.add("hidden");
      return;
    }
    showPaymentError(error);
  }
}

async function handleTossRedirect(showView) {
  const params = new URLSearchParams(window.location.search);
  const result = params.get("paymentResult");

  if (!result) {
    return;
  }

  window.history.replaceState({}, document.title, window.location.pathname);
  openPaymentModal("토스페이먼츠 결제 결과를 서버에서 승인하고 있어요.");

  if (result === "fail") {
    showPaymentError(
      new Error(params.get("message") || "결제가 취소되었거나 실패했습니다."),
    );
    return;
  }

  try {
    await confirmTossPayment({
      paymentKey: params.get("paymentKey"),
      orderId: params.get("orderId"),
      amount: params.get("amount"),
    });
    showPaymentSuccess("토스페이먼츠 결제가 승인되었고 예약이 확정되었습니다.");
    showView("reservations");
  } catch (error) {
    if (isSessionExpiredError(error)) {
      $("#paymentModal").classList.add("hidden");
      return;
    }
    showPaymentError(error);
  }
}

export function initPayment(showView) {
  $("#payButton").onclick = () => pay(showView);
  $("#modalClose").onclick = () => {
    $("#paymentModal").classList.add("hidden");
    $("#modalClose").textContent = "내 예약 확인";
    showView("reservations");
  };
  handleTossRedirect(showView);
}
