/* Shared front-end helpers for CAMPUS NETWATCH */
(function () {
  "use strict";

  const csrfMeta = document.querySelector('meta[name="csrf-token"]');

  function esc(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  async function api(method, url, body) {
    const opts = { method, headers: { Accept: "application/json" }, credentials: "same-origin" };
    if (method !== "GET") {
      opts.headers["Content-Type"] = "application/json";
      opts.headers["X-CSRFToken"] = csrfMeta ? csrfMeta.content : "";
      opts.body = JSON.stringify(body || {});
    }
    let res;
    try {
      res = await fetch(url, opts);
    } catch (e) {
      const err = new Error("Network error - is the server running?");
      err.payload = {};
      throw err;
    }
    let payload = {};
    try { payload = await res.json(); } catch (e) { payload = {}; }
    if (res.status === 401 && !url.startsWith("/api/auth/")) {
      window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);
    }
    if (!res.ok || payload.success === false) {
      const err = new Error(payload.error || ("Request failed (" + res.status + ")"));
      err.status = res.status;
      err.payload = payload;
      throw err;
    }
    return payload;
  }

  function toast(message, type) {
    const container = document.getElementById("toastContainer");
    if (!container) { alert(message); return; }
    const colors = { success: "text-bg-success", danger: "text-bg-danger", warning: "text-bg-warning", info: "text-bg-primary" };
    const el = document.createElement("div");
    el.className = "toast align-items-center border-0 " + (colors[type] || colors.info);
    el.setAttribute("role", "status");
    el.innerHTML = '<div class="d-flex"><div class="toast-body">' + esc(message) +
      '</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div>';
    container.appendChild(el);
    const t = new bootstrap.Toast(el, { delay: 4500 });
    t.show();
    el.addEventListener("hidden.bs.toast", () => el.remove());
  }

  const STATUS_CLASS = { "Pending": "b-pending", "Assigned": "b-assigned", "In Progress": "b-inprogress", "Resolved": "b-resolved" };
  const STATUS_ICON = { "Pending": "bi-hourglass-split", "Assigned": "bi-person-check", "In Progress": "bi-tools", "Resolved": "bi-check-circle" };
  const PRIORITY_CLASS = { "Critical": "b-critical", "High": "b-high", "Medium": "b-medium", "Low": "b-low" };
  const PRIORITY_ICON = { "Critical": "bi-exclamation-octagon-fill", "High": "bi-arrow-up-circle-fill", "Medium": "bi-dash-circle-fill", "Low": "bi-arrow-down-circle" };
  const CATEGORY_ICON = { "Connectivity": "bi-wifi-off", "Hardware": "bi-hdd-network", "Configuration": "bi-sliders", "Security": "bi-shield-exclamation", "Unknown": "bi-question-circle" };

  function statusBadge(s) {
    return '<span class="badge ' + (STATUS_CLASS[s] || "b-low") + '"><i class="bi ' + (STATUS_ICON[s] || "") + ' me-1"></i>' + esc(s) + "</span>";
  }
  function priorityBadge(p) {
    return '<span class="badge ' + (PRIORITY_CLASS[p] || "b-low") + '"><i class="bi ' + (PRIORITY_ICON[p] || "") + ' me-1"></i>' + esc(p) + "</span>";
  }
  function categoryBadge(c) {
    return '<span class="badge b-cat' + (c === "Security" ? " b-cat-security" : "") + '"><i class="bi ' + (CATEGORY_ICON[c] || "") + ' me-1"></i>' + esc(c) + "</span>";
  }
  function availabilityBadge(a, active) {
    if (active === false || active === 0) return '<span class="badge b-inactive"><span class="dot dot-gray"></span>Inactive</span>';
    return a === "Available"
      ? '<span class="badge b-available"><span class="dot dot-green"></span>Available</span>'
      : '<span class="badge b-busy"><span class="dot dot-red"></span>Busy</span>';
  }

  function fmtDate(s) {
    if (!s) return "—";
    const d = new Date(s.replace(" ", "T"));
    if (isNaN(d)) return esc(s);
    return d.toLocaleString(undefined, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  function keywordsHtml(matched) {
    const out = [];
    Object.keys(matched || {}).forEach((cat) => (matched[cat] || []).forEach((k) => out.push('<span class="kw" title="' + esc(cat) + '">' + esc(k) + "</span>")));
    return out.length ? out.join("") : '<span class="text-muted">None</span>';
  }

  function timelineHtml(history) {
    if (!history || !history.length) return '<p class="text-muted mb-0">No history recorded.</p>';
    return '<ul class="timeline">' + history.map((h) =>
      '<li class="t-' + esc((h.new_status || "").replace(" ", "-")) + '">' +
      '<div class="d-flex flex-wrap gap-2 align-items-center"><strong>' + esc(h.action.replace(/_/g, " ")) + "</strong>" +
      (h.previous_status && h.previous_status !== h.new_status ? statusBadge(h.previous_status) + '<i class="bi bi-arrow-right"></i>' : "") +
      statusBadge(h.new_status) + "</div>" +
      (h.remarks ? '<div class="small mt-1">' + esc(h.remarks) + "</div>" : "") +
      '<div class="t-time">' + fmtDate(h.changed_at) + " · by " + esc(h.changed_by_name) + "</div></li>").join("") + "</ul>";
  }

  function detailHtml(c, history, queue) {
    const row = (k, v) => '<div class="col-sm-6 mb-2"><div class="text-muted small">' + k + '</div><div class="fw-semibold">' + v + "</div></div>";
    return '<div class="row">' +
      row("Complaint ID", '<span class="mono">' + esc(c.complaint_id) + "</span>") +
      row("Status", statusBadge(c.status) + (queue ? ' <span class="badge b-pending ms-1">Queue position ' + esc(queue.queue_position) + "</span>" : "")) +
      row("Identifier", '<span class="mono">' + esc(c.identifier) + "</span>") +
      row("Campus zone", esc(c.location_name) + " (" + esc(c.location_code) + "), floor " + esc(c.floor_number)) +
      row("Category", categoryBadge(c.category)) +
      row("Priority", priorityBadge(c.priority)) +
      row("Submitted by", esc(c.user_name) + ' <span class="text-muted">(' + esc(c.institutional_id) + ")</span>") +
      row("Assigned administrator", c.admin_name ? esc(c.admin_name) + ' <span class="text-muted small">(' + esc(c.admin_code) + ")</span>" : '<span class="text-warning-emphasis">Waiting for assignment</span>') +
      row("Submitted", fmtDate(c.submission_time)) +
      row("Resolved", fmtDate(c.resolved_time)) +
      '<div class="col-12 mb-2"><div class="text-muted small">Description</div><div>' + esc(c.description) + "</div></div>" +
      '<div class="col-12 mb-3"><div class="text-muted small">Matched keywords</div><div>' + keywordsHtml(c.matched_keywords) + "</div></div>" +
      '</div><h6 class="fw-bold mt-2"><i class="bi bi-clock-history me-1"></i>Status history</h6>' + timelineHtml(history);
  }

  async function showComplaint(complaintId) {
    const modalEl = document.getElementById("complaintModal");
    const body = modalEl.querySelector(".modal-body");
    body.innerHTML = '<div class="text-center p-4"><div class="spinner-border text-primary"></div></div>';
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
    try {
      const res = await api("GET", "/api/complaints/track/" + encodeURIComponent(complaintId));
      body.innerHTML = detailHtml(res.data.complaint, res.data.history, res.data.queue);
    } catch (e) {
      body.innerHTML = '<div class="alert alert-danger mb-0">' + esc(e.message) + "</div>";
    }
  }

  function emptyRow(cols, text) {
    return '<tr><td colspan="' + cols + '"><div class="empty-state"><i class="bi bi-inbox"></i>' + esc(text) + "</div></td></tr>";
  }

  document.addEventListener("click", (ev) => {
    const link = ev.target.closest("[data-complaint]");
    if (link) { ev.preventDefault(); showComplaint(link.getAttribute("data-complaint")); }
    const logout = ev.target.closest("[data-logout]");
    if (logout) {
      ev.preventDefault();
      api("POST", "/api/auth/logout").finally(() => { window.location.href = "/login"; });
    }
  });

  window.CNW = { api, toast, esc, statusBadge, priorityBadge, categoryBadge, availabilityBadge, fmtDate,
    keywordsHtml, timelineHtml, detailHtml, showComplaint, emptyRow };
})();
