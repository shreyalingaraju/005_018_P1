/* Network administrator dashboard */
(function () {
  "use strict";
  const { api, esc, toast, statusBadge, priorityBadge, categoryBadge, availabilityBadge, fmtDate, emptyRow } = window.CNW;
  const cfg = window.CNW_ADMIN;
  const cols = cfg.isCentral ? 10 : 9;
  let pending = null;

  function actions(c) {
    const view = '<button class="btn btn-sm btn-outline-secondary" data-complaint="' + esc(c.complaint_id) + '" title="View details" aria-label="View details"><i class="bi bi-eye"></i></button>';
    const canAct = cfg.isCentral || c.assigned_admin_id === cfg.adminId;
    let btn = "";
    if (canAct && c.status === "Assigned") btn = '<button class="btn btn-sm btn-primary" data-status="In Progress" data-id="' + esc(c.complaint_id) + '"><i class="bi bi-play-fill me-1"></i>Start</button>';
    if (canAct && c.status === "In Progress") btn = '<button class="btn btn-sm btn-success" data-status="Resolved" data-id="' + esc(c.complaint_id) + '"><i class="bi bi-check2 me-1"></i>Resolve</button>';
    return '<div class="d-flex gap-1 justify-content-end">' + btn + view + "</div>";
  }

  async function loadMe() {
    if (!cfg.adminId) return;
    const res = await api("GET", "/api/admins/me/complaints");
    const a = res.data.admin, s = res.data.summary;
    document.getElementById("availBadge").innerHTML = availabilityBadge(a.availability, a.is_active);
    document.getElementById(a.availability === "Available" ? "availOn" : "availOff").checked = true;
    if (!cfg.isCentral) {
      document.getElementById("sAssigned").textContent = s.Assigned;
      document.getElementById("sProgress").textContent = s["In Progress"];
      document.getElementById("sResolved").textContent = s.Resolved;
    }
  }

  async function loadQueue() {
    try {
      const res = await api("GET", cfg.isCentral ? "/api/routing/queue" : "/api/routing/queue?zone=" + encodeURIComponent(cfg.zone));
      document.getElementById("sWaiting").textContent = res.data.queue.length;
    } catch (e) { document.getElementById("sWaiting").textContent = "–"; }
  }

  async function loadRows() {
    const p = new URLSearchParams();
    const st = document.getElementById("fStatus").value, pr = document.getElementById("fPriority").value;
    if (st) p.set("status", st);
    if (pr) p.set("priority", pr);
    const onlyMine = document.getElementById("onlyMine");
    let url = "/api/complaints?" + p.toString();
    if (onlyMine && onlyMine.checked) url = "/api/admins/" + cfg.adminId + "/complaints";
    const res = await api("GET", url);
    let rows = res.data.complaints;
    if (onlyMine && onlyMine.checked) rows = rows.filter((c) => (!st || c.status === st) && (!pr || c.priority === pr));
    if (cfg.isCentral) {
      const count = (s) => rows.filter((c) => c.status === s).length;
      document.getElementById("sAssigned").textContent = count("Assigned");
      document.getElementById("sProgress").textContent = count("In Progress");
      document.getElementById("sResolved").textContent = count("Resolved");
    }
    document.getElementById("rows").innerHTML = rows.length ? rows.map((c) =>
      "<tr>" +
      '<td><a href="#" class="cid-link" data-complaint="' + esc(c.complaint_id) + '">' + esc(c.complaint_id) + "</a></td>" +
      "<td>" + esc(c.user_name) + '<div class="small text-muted">' + esc(c.institutional_id) + "</div></td>" +
      "<td>" + esc(c.location_name) + '<div class="small mono text-muted">' + esc(c.identifier) + "</div></td>" +
      '<td class="desc-cell" title="' + esc(c.description) + '">' + esc(c.description) + "</td>" +
      "<td>" + categoryBadge(c.category) + "</td>" +
      "<td>" + priorityBadge(c.priority) + "</td>" +
      '<td class="small">' + fmtDate(c.submission_time) + "</td>" +
      "<td>" + statusBadge(c.status) + "</td>" +
      (cfg.isCentral ? "<td>" + (c.admin_name ? esc(c.admin_name) : '<span class="text-muted">Queue</span>') + "</td>" : "") +
      "<td>" + actions(c) + "</td></tr>").join("")
      : emptyRow(cols, "No complaints here yet.");
  }

  async function refresh() {
    try { await Promise.all([loadMe(), loadRows(), loadQueue()]); }
    catch (e) { toast(e.message, "danger"); }
  }

  document.querySelectorAll('input[name="avail"]').forEach((r) => r.addEventListener("change", async () => {
    try {
      const res = await api("PATCH", "/api/admins/" + cfg.adminId + "/availability", { availability: r.value });
      toast(res.message, res.data.processed.length ? "success" : "info");
      refresh();
    } catch (e) { toast(e.message, "danger"); refresh(); }
  }));

  const modal = new bootstrap.Modal(document.getElementById("statusModal"));
  document.getElementById("rows").addEventListener("click", (e) => {
    const b = e.target.closest("[data-status]");
    if (!b) return;
    pending = { id: b.dataset.id, status: b.dataset.status };
    document.getElementById("smId").textContent = pending.id;
    document.getElementById("smStatus").innerHTML = statusBadge(pending.status);
    document.getElementById("smRemarks").value = "";
    modal.show();
  });
  document.getElementById("smConfirm").addEventListener("click", async () => {
    if (!pending) return;
    try {
      const res = await api("PATCH", "/api/complaints/" + encodeURIComponent(pending.id) + "/status",
        { status: pending.status, remarks: document.getElementById("smRemarks").value });
      toast(res.message, "success");
      modal.hide();
      refresh();
    } catch (e) { toast(e.message, "danger"); }
  });

  ["fStatus", "fPriority", "onlyMine"].forEach((id) => { const el = document.getElementById(id); if (el) el.addEventListener("change", refresh); });
  refresh();
  setInterval(refresh, 20000);
})();
