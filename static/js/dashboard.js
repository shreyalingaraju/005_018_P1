/* Student / faculty dashboard */
(function () {
  "use strict";
  const { api, esc, statusBadge, priorityBadge, categoryBadge, fmtDate, emptyRow, toast } = window.CNW;
  const form = document.getElementById("filterForm");
  let timer = null;

  async function load() {
    const params = new URLSearchParams(new FormData(form));
    try {
      const res = await api("GET", "/api/complaints/my?" + params.toString());
      const s = res.data.summary;
      document.getElementById("sTotal").textContent = s.Total;
      document.getElementById("sPending").textContent = s.Pending;
      document.getElementById("sAssigned").textContent = s.Assigned;
      document.getElementById("sProgress").textContent = s["In Progress"];
      document.getElementById("sResolved").textContent = s.Resolved;
      const rows = res.data.complaints;
      document.getElementById("rows").innerHTML = rows.length ? rows.map((c) =>
        "<tr>" +
        '<td><a class="cid-link" data-complaint="' + esc(c.complaint_id) + '" href="#">' + esc(c.complaint_id) + "</a></td>" +
        "<td>" + esc(c.location_name) + '<div class="small text-muted mono">' + esc(c.identifier) + "</div></td>" +
        "<td>" + (c.device_type === "WIFI" ? '<i class="bi bi-wifi me-1"></i>' : '<i class="bi bi-ethernet me-1"></i>') + esc(c.device_type) + "</td>" +
        "<td>" + categoryBadge(c.category) + "</td>" +
        "<td>" + priorityBadge(c.priority) + "</td>" +
        "<td>" + statusBadge(c.status) + "</td>" +
        "<td>" + (c.admin_name ? esc(c.admin_name) : '<span class="text-muted">In queue</span>') + "</td>" +
        '<td class="small">' + fmtDate(c.submission_time) + "</td></tr>").join("")
        : emptyRow(8, "No complaints match. Use “Report a fault” to submit one.");
    } catch (e) { toast(e.message, "danger"); }
  }

  form.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(load, 250); });
  form.addEventListener("submit", (e) => { e.preventDefault(); load(); });
  load();
  setInterval(load, 20000); // keep statuses fresh
})();
