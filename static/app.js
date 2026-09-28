const grid = document.querySelector("#itemGrid");
const emptyState = document.querySelector("#emptyState");
const reportDialog = document.querySelector("#reportDialog");
const detailDialog = document.querySelector("#detailDialog");
const reportForm = document.querySelector("#reportForm");
const formError = document.querySelector("#formError");
const toast = document.querySelector("#toast");
const studentId = Number(document.querySelector('meta[name="student-id"]').content) || null;
let selectedKind = "all";
let searchTimer;

const categoryTones = {
  Electronics: "tone-blue",
  Accessories: "tone-green",
  Books: "tone-yellow",
  Clothing: "tone-orange",
  "ID & Cards": "tone-blue",
  Other: "tone-green",
};

const iconForCategory = (category) => {
  if (category === "Electronics") return '<svg viewBox="0 0 48 48"><rect x="11" y="8" width="26" height="31" rx="4"/><path d="M19 13h10M21 34h6"/><circle cx="24" cy="23" r="5"/></svg>';
  if (category === "Books") return '<svg viewBox="0 0 48 48"><path d="M10 12a4 4 0 0 1 4-4h22v31H14a4 4 0 0 1-4-4zM10 12v23M17 14h12M17 19h12"/></svg>';
  if (category === "ID & Cards") return '<svg viewBox="0 0 48 48"><rect x="7" y="12" width="34" height="24" rx="4"/><circle cx="17" cy="22" r="4"/><path d="M11 31c1-4 10-4 12 0M27 21h9M27 27h7"/></svg>';
  if (category === "Clothing") return '<svg viewBox="0 0 48 48"><path d="m17 11 7-4 7 4 10 6-5 8-5-3v18H17V22l-5 3-5-8zM20 9c0 5 8 5 8 0"/></svg>';
  if (category === "Accessories") return '<svg viewBox="0 0 48 48"><path d="M18 13V9a6 6 0 0 1 12 0v4M14 13h20l4 27H10z"/><path d="M19 21h10"/></svg>';
  return '<svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="14"/><path d="M24 17v14M17 24h14"/></svg>';
};

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function imageMarkup(item, detail = false) {
  const tone = categoryTones[item.category] || "tone-green";
  const visual = item.image
    ? `<img src="/static/uploads/${encodeURIComponent(item.image)}" alt="${escapeHtml(item.title)}" loading="lazy">`
    : `<span class="placeholder-art ${tone}">${iconForCategory(item.category)}</span>`;
  if (detail) return visual;
  return `${visual}<span class="kind-badge ${item.kind}"><i class="kind-dot"></i>${item.kind.toUpperCase()}</span>`;
}

function dateLabel(value) {
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date);
}

function renderItem(item) {
  return `<article class="item-card" data-item-id="${item.id}" tabindex="0" aria-label="${escapeHtml(item.kind)}: ${escapeHtml(item.title)}">
    <div class="card-image">${imageMarkup(item)}</div>
    <div class="card-content"><span class="card-category">${escapeHtml(item.category)}</span><h3 class="card-title">${escapeHtml(item.title)}</h3><p class="card-description">${escapeHtml(item.description)}</p>
    <div class="card-meta"><span class="card-location"><svg viewBox="0 0 20 20"><path d="M16 8.3c0 4.2-6 9-6 9s-6-4.8-6-9a6 6 0 1 1 12 0Z"/><circle cx="10" cy="8" r="2"/></svg><span>${escapeHtml(item.location)}</span></span><span class="card-date">${dateLabel(item.event_date)}</span></div></div></article>`;
}

async function loadItems() {
  const params = new URLSearchParams({ kind: selectedKind, category: document.querySelector("#categoryFilter").value, q: document.querySelector("#searchInput").value.trim() });
  try {
    const response = await fetch(`/api/items?${params}`);
    const data = await response.json();
    grid.innerHTML = data.items.map(renderItem).join("");
    document.querySelector("#totalCount").textContent = data.counts.total || 0;
    document.querySelector("#foundCount").textContent = data.counts.found || 0;
    document.querySelector("#lostCount").textContent = data.counts.lost || 0;
    document.querySelector("#resultCount").textContent = `${data.items.length} ${data.items.length === 1 ? "listing" : "listings"}`;
    emptyState.hidden = data.items.length !== 0;
  } catch (_error) {
    grid.innerHTML = "";
    document.querySelector("#resultCount").textContent = "Could not load listings";
    emptyState.hidden = false;
  }
}

function openReport() {
  formError.textContent = "";
  reportDialog.showModal();
}

document.querySelector("#openReport")?.addEventListener("click", openReport);
if (document.querySelector("#bottomReport")?.tagName === "BUTTON") document.querySelector("#bottomReport").addEventListener("click", openReport);
if (document.querySelector("#emptyPost")?.tagName === "BUTTON") document.querySelector("#emptyPost").addEventListener("click", openReport);
document.querySelectorAll(".close-dialog").forEach((button) => button.addEventListener("click", () => reportDialog.close()));
document.querySelectorAll(".segment").forEach((button) => button.addEventListener("click", () => {
  selectedKind = button.dataset.kind;
  document.querySelectorAll(".segment").forEach((segment) => segment.classList.toggle("active", segment === button));
  loadItems();
}));
document.querySelector("#categoryFilter").addEventListener("change", loadItems);
document.querySelector("#searchInput").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadItems, 180);
});

async function showDetails(itemId) {
  try {
    const response = await fetch("/api/items");
    const data = await response.json();
    const item = data.items.find((entry) => entry.id === Number(itemId));
    if (!item) return;
    const image = imageMarkup(item, true);
    document.querySelector("#detailContent").innerHTML = `<div class="detail-photo">${image}<button class="icon-button detail-close" type="button" aria-label="Close"><svg viewBox="0 0 20 20"><path d="m5 5 10 10M15 5 5 15"/></svg></button></div>
      <div class="detail-body"><span class="kind-badge ${item.kind}"><i class="kind-dot"></i>${item.kind.toUpperCase()}</span><p class="card-category" style="margin-top:16px">${escapeHtml(item.category)}</p><h2>${escapeHtml(item.title)}</h2><p class="detail-description">${escapeHtml(item.description)}</p>
      <div class="detail-facts"><div class="detail-fact"><span>Location</span><strong>${escapeHtml(item.location)}</strong></div><div class="detail-fact"><span>${item.kind === "lost" ? "Lost on" : "Found on"}</span><strong>${dateLabel(item.event_date)}</strong></div></div>
      <div class="contact-row"><a class="button button-dark" href="mailto:${encodeURIComponent(item.contact)}?subject=${encodeURIComponent(`Campus ${item.kind} item: ${item.title}`)}"><svg viewBox="0 0 20 20"><rect x="3" y="5" width="14" height="10" rx="1.5"/><path d="m4 6 6 5 6-5"/></svg>Contact poster</a>${studentId && item.owner_id === studentId ? '<button class="button button-quiet" id="resolveItem"><svg viewBox="0 0 20 20"><path d="m4 10 4 4 8-8"/></svg>Mark resolved</button>' : ""}</div></div>`;
    detailDialog.showModal();
    document.querySelector(".detail-close").addEventListener("click", () => detailDialog.close());
    document.querySelector("#resolveItem")?.addEventListener("click", async () => {
      const result = await fetch(`/api/items/${item.id}/resolve`, { method: "POST" });
      if (result.ok) {
        detailDialog.close();
        showToast("Listing marked as resolved");
        loadItems();
      }
    });
  } catch (_error) {
    showToast("Could not open this listing");
  }
}

grid.addEventListener("click", (event) => {
  const card = event.target.closest(".item-card");
  if (card) showDetails(card.dataset.itemId);
});
grid.addEventListener("keydown", (event) => {
  if ((event.key === "Enter" || event.key === " ") && event.target.matches(".item-card")) {
    event.preventDefault();
    showDetails(event.target.dataset.itemId);
  }
});

let toastTimer;
function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
}

reportForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.textContent = "";
  const submitButton = document.querySelector("#submitPost");
  submitButton.disabled = true;
  submitButton.firstChild.textContent = "Publishing… ";
  try {
    const response = await fetch("/api/items", { method: "POST", body: new FormData(reportForm) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not publish this listing.");
    reportDialog.close();
    reportForm.reset();
    selectedKind = "all";
    document.querySelectorAll(".segment").forEach((segment) => segment.classList.toggle("active", segment.dataset.kind === "all"));
    document.querySelector("#categoryFilter").value = "all";
    document.querySelector("#searchInput").value = "";
    showToast("Your listing is on the board");
    await loadItems();
  } catch (error) {
    formError.textContent = error.message;
  } finally {
    submitButton.disabled = false;
    submitButton.firstChild.textContent = "Publish listing ";
  }
});

loadItems();
if (reportDialog && new URLSearchParams(window.location.search).get("post") === "1") openReport();
