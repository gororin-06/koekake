const loginScreen = document.getElementById("login-screen");
const adminApp = document.getElementById("admin-app");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const noticeDialog = document.getElementById("notice-dialog");
const toast = document.getElementById("toast");

function enterAdmin() {
  loginScreen.hidden = true;
  adminApp.hidden = false;
  window.scrollTo(0, 0);
}

if (sessionStorage.getItem("shelter-admin-demo") === "yes") enterAdmin();

loginForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const pin = document.getElementById("admin-pin").value;
  if (pin !== "4286") {
    loginError.hidden = false;
    document.getElementById("admin-pin").select();
    return;
  }
  loginError.hidden = true;
  sessionStorage.setItem("shelter-admin-demo", "yes");
  enterAdmin();
});

document.getElementById("logout-button").addEventListener("click", () => {
  sessionStorage.removeItem("shelter-admin-demo");
  adminApp.hidden = true;
  loginScreen.hidden = false;
  loginForm.reset();
});

function openNoticeDialog() {
  if (!noticeDialog.open) noticeDialog.showModal();
}

document.getElementById("open-notice").addEventListener("click", openNoticeDialog);
document.getElementById("edit-notice").addEventListener("click", openNoticeDialog);

document.querySelectorAll("[data-close]").forEach((button) => {
  button.addEventListener("click", () => document.getElementById(button.dataset.close).close());
});

noticeDialog.addEventListener("click", (event) => {
  if (event.target === noticeDialog) noticeDialog.close();
});

document.getElementById("notice-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const message = document.getElementById("notice-message").value.trim();
  const priority = document.getElementById("notice-priority").value;
  document.getElementById("notice-text").textContent = message;
  const badge = document.querySelector(".priority-badge");
  badge.textContent = priority;
  badge.classList.toggle("normal", priority === "通常");
  noticeDialog.close();
  showToast("お知らせを公開しました");
  updateClock();
});

document.querySelectorAll(".status-select").forEach((select) => {
  select.addEventListener("change", () => {
    select.closest(".admin-post-row").dataset.status = select.value;
    applyFilter();
    showToast("対応状況を変更しました");
    updateClock();
  });
});

document.querySelectorAll(".visibility-button").forEach((button) => {
  button.addEventListener("click", () => {
    const row = button.closest(".admin-post-row");
    const hidden = row.classList.toggle("is-hidden");
    button.textContent = hidden ? "再表示" : "非表示";
    showToast(hidden ? "投稿を非表示にしました" : "投稿を再表示しました");
    updateClock();
  });
});

const adminFilter = document.getElementById("admin-filter");
adminFilter.addEventListener("change", applyFilter);

function applyFilter() {
  const filter = adminFilter.value;
  let visible = 0;
  document.querySelectorAll(".admin-post-row").forEach((row) => {
    const show = filter === "all" || row.dataset.status === filter;
    row.hidden = !show;
    if (show) visible += 1;
  });
  document.getElementById("admin-empty").hidden = visible !== 0;
}

document.querySelector("[data-scroll-post]").addEventListener("click", (event) => {
  const row = document.getElementById(event.currentTarget.dataset.scrollPost);
  row.scrollIntoView({ behavior: "smooth", block: "center" });
  row.classList.add("highlight-row");
  window.setTimeout(() => row.classList.remove("highlight-row"), 1300);
});

document.getElementById("settings-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const saved = document.getElementById("saved-label");
  saved.textContent = "保存しました";
  showToast("避難所情報を更新しました");
  updateClock();
  window.setTimeout(() => { saved.textContent = "保存済み"; }, 1800);
});

function updateClock() {
  const now = new Date();
  document.getElementById("last-updated").textContent = `${now.getHours()}:${String(now.getMinutes()).padStart(2, "0")}`;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2200);
}
