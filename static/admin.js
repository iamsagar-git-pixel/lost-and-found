const rows = document.querySelector("#adminRows");
const empty = document.querySelector("#adminEmpty");
const studentRows = document.querySelector("#studentRows");
const studentEmpty = document.querySelector("#studentEmpty");
const csrf = document.querySelector('meta[name="csrf-token"]').content;
let allItems = [];
let allStudents = [];
let toastTimer;

function safe(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

function prettyDate(value) {
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.valueOf()) ? safe(value) : new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(date);
}

function renderRows() {
  const query = document.querySelector("#adminSearch").value.trim().toLowerCase();
  const status = document.querySelector("#statusFilter").value;
  const kind = document.querySelector("#kindFilter").value;
  const filtered = allItems.filter((item) => {
    const matchesSearch = [item.title, item.description, item.location, item.contact, item.category].some((value) => String(value).toLowerCase().includes(query));
    return matchesSearch && (status === "all" || item.status === status) && (kind === "all" || item.kind === kind);
  });
  document.querySelector("#adminResultCount").textContent = `${filtered.length} ${filtered.length === 1 ? "report" : "reports"}`;
  empty.hidden = filtered.length !== 0;
  rows.innerHTML = filtered.map((item) => `<tr>
    <td><div class="admin-item"><span class="admin-item-icon ${item.kind}">${item.kind === "lost" ? "L" : "F"}</span><div><strong>${safe(item.title)}</strong><small>${safe(item.category)}</small></div></div></td>
    <td><span class="type-label ${item.kind}">${safe(item.kind)}</span></td>
    <td class="location-cell">${safe(item.location)}</td>
    <td><a class="contact-email" href="mailto:${encodeURIComponent(item.contact)}">${safe(item.contact)}</a></td>
    <td class="date-cell">${prettyDate(item.event_date)}</td>
    <td><span class="status-label ${item.status}"><i></i>${safe(item.status)}</span></td>
    <td><button class="status-action" type="button" data-id="${item.id}" data-next="${item.status === "open" ? "resolved" : "open"}">${item.status === "open" ? "Resolve" : "Reopen"}</button></td>
  </tr>`).join("");
}

async function loadAdminItems() {
  try {
    const [itemsResponse, studentsResponse] = await Promise.all([fetch("/api/admin/items"), fetch("/api/admin/students")]);
    if (itemsResponse.status === 401 || studentsResponse.status === 401) {
      window.location.assign("/admin");
      return;
    }
    const data = await itemsResponse.json();
    const studentData = await studentsResponse.json();
    allItems = data.items;
    allStudents = studentData.students;
    document.querySelector("#statTotal").textContent = data.counts.total;
    document.querySelector("#statOpen").textContent = data.counts.open;
    document.querySelector("#statResolved").textContent = data.counts.resolved;
    document.querySelector("#statLost").textContent = data.counts.lost;
    document.querySelector("#statFound").textContent = data.counts.found;
    document.querySelector("#statPendingStudents").textContent = studentData.pending;
    document.querySelector("#pendingStudentCount").textContent = studentData.pending;
    renderRows();
    renderStudents();
  } catch (_error) {
    document.querySelector("#adminResultCount").textContent = "Could not load reports";
  }
}

function renderStudents() {
  studentEmpty.hidden = allStudents.length !== 0;
  studentRows.innerHTML = allStudents.map((student) => {
    const pending = student.status === "pending";
    const actions = pending
      ? `<div class="decision-actions"><button type="button" class="approve-action" data-id="${student.id}" data-decision="approve">Approve</button><button type="button" class="reject-action" data-id="${student.id}" data-decision="reject">Reject</button></div>`
      : `<span class="status-label ${student.status === "active" ? "open" : "resolved"}"><i></i>${student.status === "active" ? "active" : "rejected"}</span>`;
    return `<tr><td><strong class="student-admin-name">${safe(student.full_name)}</strong></td><td><a class="contact-email" href="mailto:${encodeURIComponent(student.email)}">${safe(student.email)}</a></td><td class="date-cell">${prettyDate(student.created_at.slice(0, 10))}</td><td><a class="id-review-link" href="/admin/students/${student.id}/id-card" target="_blank" rel="noopener">View ID card</a></td><td><span class="status-label ${pending ? "resolved" : "open"}"><i></i>${safe(student.status)}</span></td><td>${actions}</td></tr>`;
  }).join("");
}

function showAdminToast(message) {
  const toast = document.querySelector("#adminToast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2400);
}

document.querySelector("#adminSearch").addEventListener("input", renderRows);
document.querySelector("#statusFilter").addEventListener("change", renderRows);
document.querySelector("#kindFilter").addEventListener("change", renderRows);
document.querySelector("#refreshItems").addEventListener("click", loadAdminItems);
rows.addEventListener("click", async (event) => {
  const button = event.target.closest(".status-action");
  if (!button) return;
  button.disabled = true;
  try {
    const response = await fetch(`/api/admin/items/${button.dataset.id}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ status: button.dataset.next }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not update status.");
    showAdminToast(button.dataset.next === "resolved" ? "Listing resolved" : "Listing reopened");
    await loadAdminItems();
  } catch (error) {
    showAdminToast(error.message);
    button.disabled = false;
  }
});

studentRows.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-decision]");
  if (!button) return;
  button.disabled = true;
  try {
    const response = await fetch(`/api/admin/students/${button.dataset.id}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ decision: button.dataset.decision }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not update student status.");
    showAdminToast(button.dataset.decision === "approve" ? "Student account activated" : "Registration rejected");
    await loadAdminItems();
  } catch (error) {
    showAdminToast(error.message);
    button.disabled = false;
  }
});

loadAdminItems();
