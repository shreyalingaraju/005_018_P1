/* Routing management dashboard (central administrator) */
(function () {
  "use strict";
  const { api, esc, toast, priorityBadge, availabilityBadge, fmtDate, emptyRow } = window.CNW;
  let admins = [];
  let zones = [];
  let editingZone = null;
  let editingAdmin = null;

  const ZONE_ICON = { HOST: "bi-house-door", LAB: "bi-pc-display", ADM: "bi-building", LIB: "bi-book", CANT: "bi-cup-hot", SPRT: "bi-trophy" };

  function adminLine(label, name, code, avail, active) {
    return '<div class="admin-row"><div><div class="small text-muted">' + label + '</div><div class="fw-semibold">' +
      esc(name || "Not configured") + ' <span class="small text-muted mono">' + esc(code || "") + "</span></div></div>" +
      availabilityBadge(avail, active) + "</div>";
  }

  function renderZones(data) {
    zones = data.zones;
    const stat = (n, l) => '<div class="col zone-stat"><div class="n">' + n + '</div><div class="l">' + l + "</div></div>";
    const cards = zones.map((z) =>
      '<div class="col-md-6 col-xl-4"><div class="card zone-card h-100"><div class="card-body">' +
      '<div class="d-flex align-items-center mb-2"><i class="bi ' + (ZONE_ICON[z.location_code] || "bi-geo-alt") + ' fs-4 text-primary me-2"></i>' +
      '<div class="fw-bold">' + esc(z.location_name) + '</div><span class="zone-code ms-auto">' + esc(z.location_code) + "</span></div>" +
      adminLine("Primary", z.primary_name, z.primary_code, z.primary_availability, z.primary_active) +
      adminLine("Backup", z.backup_name, z.backup_code, z.backup_availability, z.backup_active) +
      '<div class="row mt-3 g-0">' + stat(z.total, "Total") + stat(z.assigned, "Assigned") +
      stat('<span class="' + (z.waiting ? "text-warning-emphasis" : "") + '">' + z.waiting + "</span>", "Waiting") + stat(z.resolved, "Resolved") + "</div>" +
      "</div></div></div>").join("");
    document.getElementById("zoneCards").innerHTML = cards +
      (data.central_waiting ? '<div class="col-12"><div class="alert alert-warning mb-0"><i class="bi bi-exclamation-triangle me-1"></i>' +
        data.central_waiting + " complaint(s) from unregistered zones are waiting for the central administrator.</div></div>" : "");

    document.getElementById("routingRows").innerHTML = zones.map((z) =>
      '<tr><td><span class="zone-code mono">' + esc(z.location_code) + "</span></td><td>" + esc(z.location_name) + "</td>" +
      "<td>" + esc(z.primary_name || "—") + '<div class="small">' + availabilityBadge(z.primary_availability, z.primary_active) + "</div></td>" +
      "<td>" + esc(z.backup_name || "—") + '<div class="small">' + availabilityBadge(z.backup_availability, z.backup_active) + "</div></td>" +
      '<td class="small text-muted">' + fmtDate(z.updated_at) + "</td>" +
      '<td class="text-end"><button class="btn btn-sm btn-outline-primary" data-edit-zone="' + esc(z.location_code) + '" aria-label="Edit routing for ' + esc(z.location_code) + '"><i class="bi bi-pencil"></i></button></td></tr>').join("");

    document.getElementById("aaZone").innerHTML = zones.map((z) => '<option value="' + esc(z.location_code) + '">' + esc(z.location_code) + "</option>").join("");
  }

  function renderAdmins() {
    document.getElementById("adminRows").innerHTML = admins.map((a) =>
      "<tr><td class='fw-semibold'>" + esc(a.name) + '<div class="small text-muted">' + esc(a.email) + "</div></td>" +
      '<td class="mono small">' + esc(a.admin_code) + "</td><td>" + esc(a.assigned_zone) + "</td>" +
      '<td class="text-capitalize">' + esc(a.admin_role) + "</td><td>" + a.open_complaints + "</td><td>" + a.resolved_complaints + "</td>" +
      "<td>" + availabilityBadge(a.availability, true) + "</td>" +
      "<td>" + (a.is_active ? '<i class="bi bi-check-circle-fill text-success" aria-label="Active"></i>' : '<i class="bi bi-x-circle text-muted" aria-label="Inactive"></i>') + "</td>" +
      '<td class="text-end text-nowrap"><button class="btn btn-sm ' + (a.availability === "Available" ? "btn-outline-danger" : "btn-outline-success") +
      '" data-toggle-avail="' + a.id + '" data-next="' + (a.availability === "Available" ? "Busy" : "Available") + '">Set ' +
      (a.availability === "Available" ? "Busy" : "Available") + "</button> " +
      '<button class="btn btn-sm btn-outline-secondary" data-edit-admin="' + a.id + '" aria-label="Edit ' + esc(a.name) + '"><i class="bi bi-pencil"></i></button></td></tr>').join("");
    const options = admins.filter((a) => a.is_active).map((a) => '<option value="' + a.id + '">' + esc(a.name) + " (" + esc(a.admin_code) + ")</option>").join("");
    document.getElementById("raAdmin").innerHTML = options;
  }

  function renderQueue(queue) {
    document.getElementById("queueCount").textContent = queue.length;
    document.getElementById("queueRows").innerHTML = queue.length ? queue.map((q) =>
      "<tr><td>" + q.queue_position + '</td><td><a href="#" class="cid-link" data-complaint="' + esc(q.complaint_id) + '">' + esc(q.complaint_id) +
      '</a><div class="small text-muted text-truncate" style="max-width:180px">' + esc(q.category) + " · " + esc(q.identifier) + "</div></td>" +
      '<td><span class="zone-code mono">' + esc(q.zone_code) + "</span></td><td>" + priorityBadge(q.priority) + '</td><td class="small">' + fmtDate(q.queued_at) + "</td>" +
      '<td><button class="btn btn-sm btn-outline-primary" data-reassign="' + esc(q.complaint_id) + '" title="Assign manually" aria-label="Assign manually"><i class="bi bi-person-plus"></i></button></td></tr>').join("")
      : emptyRow(6, "Queue is empty — every complaint has an administrator.");
  }

  function renderHistory(data) {
    document.getElementById("historyRows").innerHTML = data.history.length ? data.history.map((h) =>
      '<tr><td class="small text-nowrap text-muted">' + fmtDate(h.changed_at) + '</td><td><span class="badge b-cat">' + esc(h.action.replace(/_/g, " ")) +
      '</span></td><td><a href="#" class="cid-link" data-complaint="' + esc(h.complaint_id) + '">' + esc(h.complaint_id) + '</a><div class="small">' + esc(h.remarks || "") + "</div></td></tr>").join("")
      : emptyRow(3, "No reassignments, backup routing or queue events yet.");
    document.getElementById("auditRows").innerHTML = data.audit.length ? data.audit.map((a) =>
      '<tr><td class="small text-nowrap text-muted">' + fmtDate(a.created_at) + '</td><td><span class="badge b-cat">' + esc(a.action) + "</span></td><td class='small'>" +
      esc(a.actor_name) + " · " + esc(a.entity_type) + " " + esc(a.entity_id || "") + "<div class='text-muted'>" + esc(a.details || "") + "</div></td></tr>").join("")
      : emptyRow(3, "No administrative activity recorded yet.");
  }

  async function refresh() {
    try {
      const [z, a, q, h] = await Promise.all([api("GET", "/api/routing/zones"), api("GET", "/api/admins"),
        api("GET", "/api/routing/queue"), api("GET", "/api/routing/history")]);
      admins = a.data.admins;
      renderZones(z.data);
      renderAdmins();
      renderQueue(q.data.queue);
      renderHistory(h.data);
    } catch (e) { toast(e.message, "danger"); }
  }

  // ---- routing table edit
  const routeModal = new bootstrap.Modal(document.getElementById("routeModal"));
  document.getElementById("routingRows").addEventListener("click", (e) => {
    const b = e.target.closest("[data-edit-zone]");
    if (!b) return;
    editingZone = zones.find((z) => z.location_code === b.dataset.editZone);
    const opts = admins.filter((a) => a.admin_role !== "central").map((a) => '<option value="' + a.id + '">' + esc(a.name) + " (" + esc(a.admin_code) + ")" + (a.is_active ? "" : " – inactive") + "</option>").join("");
    document.getElementById("rmCode").textContent = editingZone.location_code;
    document.getElementById("rmPrimary").innerHTML = opts;
    document.getElementById("rmBackup").innerHTML = opts;
    document.getElementById("rmPrimary").value = editingZone.primary_id;
    document.getElementById("rmBackup").value = editingZone.backup_id;
    routeModal.show();
  });
  document.getElementById("rmSave").addEventListener("click", async () => {
    try {
      const res = await api("PATCH", "/api/routing/table/" + editingZone.location_code, {
        primary_admin_id: document.getElementById("rmPrimary").value, backup_admin_id: document.getElementById("rmBackup").value });
      toast(res.message + (res.data.processed.length ? " " + res.data.processed.length + " queued complaint(s) assigned." : ""), "success");
      routeModal.hide();
      refresh();
    } catch (e) { toast(e.message, "danger"); }
  });

  // ---- administrator actions
  const editModal = new bootstrap.Modal(document.getElementById("editAdminModal"));
  document.getElementById("adminRows").addEventListener("click", async (e) => {
    const t = e.target.closest("[data-toggle-avail]");
    if (t) {
      try {
        const res = await api("PATCH", "/api/admins/" + t.dataset.toggleAvail + "/availability", { availability: t.dataset.next });
        toast(res.message, res.data.processed.length ? "success" : "info");
        refresh();
      } catch (err) { toast(err.message, "danger"); }
      return;
    }
    const ed = e.target.closest("[data-edit-admin]");
    if (ed) {
      editingAdmin = admins.find((a) => String(a.id) === ed.dataset.editAdmin);
      document.getElementById("eaCode").textContent = editingAdmin.admin_code;
      document.getElementById("eaName").value = editingAdmin.name;
      document.getElementById("eaActive").checked = editingAdmin.is_active;
      editModal.show();
    }
  });
  document.getElementById("eaSave").addEventListener("click", async () => {
    try {
      await api("PATCH", "/api/admins/" + editingAdmin.id, { name: document.getElementById("eaName").value, is_active: document.getElementById("eaActive").checked });
      toast("Administrator updated.", "success");
      editModal.hide();
      refresh();
    } catch (e) { toast(e.message, "danger"); }
  });

  document.getElementById("addAdminForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const alertEl = document.getElementById("aaAlert");
    alertEl.classList.add("d-none");
    try {
      const res = await api("POST", "/api/admins", Object.fromEntries(new FormData(e.target).entries()));
      toast(res.message, "success");
      bootstrap.Modal.getInstance(document.getElementById("addAdminModal")).hide();
      e.target.reset();
      refresh();
    } catch (err) {
      const d = err.payload && err.payload.details ? " " + Object.values(err.payload.details).join(" ") : "";
      alertEl.textContent = err.message + d;
      alertEl.classList.remove("d-none");
    }
  });

  // ---- queue & reassignment
  document.getElementById("processQueueBtn").addEventListener("click", async () => {
    try {
      const res = await api("POST", "/api/routing/process-queue", {});
      toast(res.message, res.data.assigned.length ? "success" : "warning");
      refresh();
    } catch (e) { toast(e.message, "danger"); }
  });
  document.getElementById("queueRows").addEventListener("click", (e) => {
    const b = e.target.closest("[data-reassign]");
    if (!b) return;
    document.getElementById("raId").value = b.dataset.reassign;
    document.getElementById("raId").scrollIntoView({ behavior: "smooth", block: "center" });
    document.getElementById("raAdmin").focus();
  });
  document.getElementById("reassignForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("raId").value.trim().toUpperCase();
    if (!id) return;
    try {
      const res = await api("PATCH", "/api/routing/assignments/" + encodeURIComponent(id),
        { admin_id: document.getElementById("raAdmin").value, remarks: document.getElementById("raRemarks").value });
      toast(res.message, "success");
      e.target.reset();
      refresh();
    } catch (err) { toast(err.message, "danger"); }
  });

  document.getElementById("refreshBtn").addEventListener("click", refresh);
  refresh();
  setInterval(refresh, 20000);
})();
