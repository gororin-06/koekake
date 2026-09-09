const tabs = document.querySelectorAll(".tab");
const postList = document.getElementById("post-list");
const emptyState = document.getElementById("empty-state");
const infoDialog = document.getElementById("info-dialog");
const composeDialog = document.getElementById("compose-dialog");
const toast = document.getElementById("toast");

function openDialog(dialog) {
  if (!dialog.open) dialog.showModal();
}

document.getElementById("open-info").addEventListener("click", () => openDialog(infoDialog));
document.getElementById("open-info-side").addEventListener("click", () => openDialog(infoDialog));
document.getElementById("open-compose").addEventListener("click", () => openDialog(composeDialog));

document.querySelectorAll("[data-close]").forEach((button) => {
  button.addEventListener("click", () => document.getElementById(button.dataset.close).close());
});

[infoDialog, composeDialog].forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
});

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    const filter = tab.dataset.filter;
    let visibleCount = 0;
    postList.querySelectorAll(".post").forEach((post) => {
      const visible = filter === "all" || post.dataset.category === filter;
      post.hidden = !visible;
      if (visible) visibleCount += 1;
    });
    emptyState.hidden = visibleCount !== 0;
  });
});

document.getElementById("refresh-button").addEventListener("click", (event) => {
  const button = event.currentTarget;
  button.classList.add("spinning");
  window.setTimeout(() => {
    button.classList.remove("spinning");
    showToast("最新の情報に更新しました");
  }, 450);
});

document.querySelectorAll(".help-button").forEach((button) => {
  button.addEventListener("click", () => {
    button.disabled = true;
    button.textContent = "管理者に伝えました";
    showToast("運営本部にお知らせしました");
  });
});

const categoryLabels = {
  supply: ["物資が必要", "物", "supply-icon", "tag-supply"],
  support: ["提供できます", "支", "support-icon", "tag-support"],
  child: ["子ども・見守り", "子", "child-icon", "tag-child"],
  health: ["健康・体調", "健", "health-icon", "tag-health"]
};

document.getElementById("compose-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const category = document.getElementById("category").value;
  const location = document.getElementById("location").value.trim();
  const message = document.getElementById("message").value.trim();
  const [label, icon, iconClass, tagClass] = categoryLabels[category];
  const now = new Date();
  const time = `${now.getHours()}:${String(now.getMinutes()).padStart(2, "0")}`;

  const article = document.createElement("article");
  article.className = "post";
  article.dataset.category = category;
  article.innerHTML = `
    <div class="post-icon ${iconClass}" aria-hidden="true">${icon}</div>
    <div class="post-body">
      <div class="post-meta"><strong></strong><time></time></div>
      <div class="post-tags"><span class="tag ${tagClass}">${label}</span><span class="status open">未対応</span></div>
      <p class="post-text"></p>
    </div>`;
  article.querySelector("strong").textContent = location;
  article.querySelector("time").textContent = time;
  article.querySelector(".post-text").textContent = message;
  postList.prepend(article);

  tabs.forEach((item) => item.classList.toggle("active", item.dataset.filter === "all"));
  postList.querySelectorAll(".post").forEach((post) => { post.hidden = false; });
  emptyState.hidden = true;
  event.currentTarget.reset();
  composeDialog.close();
  showToast("掲示板に投稿しました");
  article.scrollIntoView({ behavior: "smooth", block: "center" });
});

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2200);
}
