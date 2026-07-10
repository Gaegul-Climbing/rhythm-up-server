import { api, isSessionExpiredError } from "../core/api.js";
import { $, $$, showToast } from "../core/dom.js";
import { formatTime, formatWon } from "../core/format.js";
import { state } from "../core/state.js";

function branchCard(branch, index) {
  const status = branch.status === "open" ? "OPEN" : "CLOSED";

  return `
    <button class="choice-card" data-branch="${branch.id}">
      <span class="num">0${index + 1} · ${status}</span>
      <h3>${branch.name}</h3>
      <p>${branch.address}</p>
      <p>${branch.opens_at.slice(0, 5)} — ${branch.closes_at.slice(0, 5)}</p>
    </button>
  `;
}

function roomCard(room) {
  const roomTypes = { vocal: "VOCAL", band: "BAND", dance: "DANCE" };
  const roomType = roomTypes[room.room_type] || room.room_type;

  return `
    <button class="room-card" data-room="${room.id}">
      <small>${roomType} · 최대 ${room.max_capacity}인</small>
      <h3>${room.name}</h3>
      <p>권장 ${room.recommended_capacity}인</p>
      <strong>${formatWon(room.hourly_rate)} / 시간</strong>
    </button>
  `;
}

function slotButton(slot) {
  const time = formatTime(new Date(slot.start_at));
  const disabled = slot.available ? "" : "disabled";

  return `
    <button class="slot" data-start="${slot.start_at}" ${disabled}>
      ${time}
    </button>
  `;
}

export async function loadBranches() {
  try {
    const branches = await api("/branches");
    const grid = $("#branchGrid");

    grid.classList.remove("loading");
    grid.innerHTML = branches.length
      ? branches.map(branchCard).join("")
      : '<div class="empty">운영 중인 지점이 없습니다.</div>';

    grid.querySelectorAll("[data-branch]").forEach((element, index) => {
      element.onclick = () => selectBranch(branches[index], element);
    });
  } catch (error) {
    if (isSessionExpiredError(error)) {
      return;
    }
    showToast(error.message);
  }
}

async function selectBranch(branch, selectedElement) {
  state.branch = branch;

  $$('[data-branch]').forEach((element) => {
    element.classList.remove("selected");
  });
  selectedElement.classList.add("selected");

  try {
    const rooms = await api(`/branches/${branch.id}/rooms`);
    const roomGrid = $("#roomGrid");

    roomGrid.innerHTML = rooms.map(roomCard).join("");
    $("#roomPanel").classList.remove("hidden");

    roomGrid.querySelectorAll("[data-room]").forEach((element, index) => {
      element.onclick = () => selectRoom(rooms[index], element);
    });

    $$(".progress div")[1].classList.add("on");
    $("#roomPanel").scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    if (isSessionExpiredError(error)) {
      return;
    }
    showToast(error.message);
  }
}

function selectRoom(room, selectedElement) {
  state.room = room;

  $$('[data-room]').forEach((element) => {
    element.classList.remove("selected");
  });
  selectedElement.classList.add("selected");
  $("#timePanel").classList.remove("hidden");

  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const tomorrowValue = tomorrow.toISOString().slice(0, 10);

  $("#bookingDate").min = tomorrowValue;
  $("#bookingDate").value = tomorrowValue;
  $$(".progress div")[2].classList.add("on");

  loadSlots();
  $("#timePanel").scrollIntoView({ behavior: "smooth", block: "center" });
}

async function loadSlots() {
  if (!state.room) {
    return;
  }

  const date = $("#bookingDate").value;
  const path =
    `/branches/${state.branch.id}/rooms/${state.room.id}` +
    `/availability?date=${date}`;

  try {
    const availability = await api(path);
    const slotGrid = $("#slotGrid");

    slotGrid.innerHTML = availability.slots.length
      ? availability.slots.map(slotButton).join("")
      : "<p>선택할 수 있는 시간이 없습니다.</p>";

    $$(".slot:not(:disabled)").forEach((element) => {
      element.onclick = () => selectSlot(element.dataset.start, element);
    });
  } catch (error) {
    if (isSessionExpiredError(error)) {
      return;
    }
    showToast(error.message);
  }
}

function selectSlot(startAt, selectedElement) {
  state.slot = startAt;

  $$(".slot").forEach((element) => element.classList.remove("selected"));
  selectedElement.classList.add("selected");

  const duration = Number($("#duration").value);
  const startDate = new Date(startAt);
  const date = startDate.toLocaleDateString("ko-KR");
  const time = formatTime(startDate);

  $("#checkoutTitle").textContent = `${state.branch.name} · ${state.room.name}`;
  $("#checkoutTime").textContent = `${date} ${time} · ${duration}시간`;
  $("#checkoutPrice").textContent = formatWon(state.room.hourly_rate * duration);
  $("#checkout").classList.remove("hidden");
  $$(".progress div")[3].classList.add("on");
}

export function initBooking() {
  $("#bookingDate").onchange = loadSlots;
  $("#duration").onchange = () => {
    state.slot = null;
    $("#checkout").classList.add("hidden");
    loadSlots();
  };
}
