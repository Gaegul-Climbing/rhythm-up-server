export const createId = () => crypto.randomUUID();

export const formatWon = (amount) =>
  `${new Intl.NumberFormat("ko-KR").format(amount)}원`;

export function formatTime(date) {
  return date.toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}
