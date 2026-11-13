/* Complaint submission page */
(function () {
  "use strict";
  const { api, esc, toast, statusBadge, priorityBadge, categoryBadge, keywordsHtml } = window.CNW;
  const form = document.getElementById("complaintForm");
  const preview = document.getElementById("idPreview");
  const alertEl = document.getElementById("formAlert");
  let classifyTimer = null;

  const val = (n) => form.elements[n].value;
  const identifier = () => (val("device_type") && val("location_code") && val("floor") !== "")
    ? val("device_type") + "-" + val("location_code") + "-" + val("floor") : null;

  function verdict(ok) {
    return ok ? '<span class="text-success"><i class="bi bi-check-circle-fill me-1"></i>Valid</span>'
      : '<span class="text-danger"><i class="bi bi-x-circle-fill me-1"></i>Invalid</span>';
  }

  async function refreshIdentifier() {
    const d = val("device_type") || "____", l = val("location_code") || "____", f = val("floor") === "" ? "_" : val("floor");
    preview.innerHTML = '<span class="seg-dev">' + esc(d) + '</span>-<span class="seg-loc">' + esc(l) + '</span>-<span class="seg-flr">' + esc(f) + "</span>";
    const id = identifier();
    if (!id) return;
    try {
      const res = await api("POST", "/api/validate", { identifier: id });
      document.getElementById("liveDfa").innerHTML = verdict(res.data.dfa.valid) + ' <span class="small text-muted mono">' + esc(res.data.dfa.final_state) + "</span>";
      document.getElementById("liveRegex").innerHTML = verdict(res.data.regex.valid);
      document.getElementById("liveMsg").textContent = res.data.message;
    } catch (e) { /* preview only */ }
  }

  async function refreshClassification() {
    const text = val("description");
    document.getElementById("descCount").textContent = text.length;
    if (text.trim().length < 5) { document.getElementById("liveCat").textContent = "—"; document.getElementById("livePrio").textContent = "—"; return; }
    try {
      const res = await api("POST", "/api/classify", { description: text });
      document.getElementById("liveCat").innerHTML = categoryBadge(res.data.category);
      document.getElementById("livePrio").innerHTML = priorityBadge(res.data.priority);
    } catch (e) { /* preview only */ }
  }

  ["device_type", "location_code", "floor"].forEach((n) => form.elements[n].addEventListener("change", refreshIdentifier));
  form.elements.description.addEventListener("input", () => { clearTimeout(classifyTimer); classifyTimer = setTimeout(refreshClassification, 300); });
  document.getElementById("resetBtn").addEventListener("click", () => setTimeout(() => { refreshIdentifier(); refreshClassification(); }, 0));

  function showErrors(errors) {
    Object.entries(errors).forEach(([k, msg]) => {
      const el = form.elements[k];
      if (!el) return;
      el.classList.add("is-invalid");
      const fb = el.parentElement.querySelector(".invalid-feedback");
      if (fb) fb.textContent = msg;
    });
  }

  function renderResult(d) {
    const c = d.complaint, v = d.validation, cl = d.classification, r = d.routing;
    const step = (cls, icon, title, detail) => '<li><span class="step-icon step-' + cls + '"><i class="bi ' + icon + '"></i></span><div><div class="fw-semibold">' + title + '</div><div class="small text-muted">' + detail + "</div></div></li>";
    const assigned = r.admin
      ? '<div class="alert alert-success d-flex gap-2 mb-3"><i class="bi bi-person-check-fill fs-5"></i><div>Assigned to <strong>' + esc(r.admin.name) + "</strong> (" + esc(r.admin.admin_code) + ")" +
        (r.outcome === "ASSIGNED_BACKUP" ? "<br><small>Primary administrator was busy — routed to the backup administrator.</small>" : "") + "</div></div>"
      : '<div class="alert alert-warning d-flex gap-2 mb-3"><i class="bi bi-hourglass-split fs-5"></i><div><strong>Waiting for assignment.</strong> All administrators for ' + esc(r.zone_name) +
        " are busy. Your complaint is at position <strong>" + esc(r.queue_position) + "</strong> in the " + esc(c.priority) + "-priority queue.</div></div>";
    document.getElementById("resultBody").innerHTML =
      '<div class="text-center mb-3"><div class="small text-muted">Complaint ID</div><div class="fs-4 fw-bold mono">' + esc(c.complaint_id) + "</div>" +
      '<button class="btn btn-sm btn-outline-primary mt-1" data-complaint="' + esc(c.complaint_id) + '"><i class="bi bi-eye me-1"></i>View details</button></div>' +
      assigned +
      '<ul class="pipeline">' +
      step("ok", "bi-upc", "Validated identifier", '<span class="mono">' + esc(v.identifier) + "</span>") +
      step("ok", "bi-diagram-2", "DFA result: " + esc(v.dfa.result), "Final state " + esc(v.dfa.final_state) + " — " + esc(v.dfa.final_state_label)) +
      step("ok", "bi-regex", "Regex result: " + esc(v.regex.result), '<span class="mono">' + esc(v.regex.pattern) + "</span>") +
      step(v.match ? "ok" : "fail", "bi-arrow-left-right", "DFA ↔ Regex agreement", v.match ? "Both validators agree" : "Mismatch") +
      step("ok", "bi-tags", "Detected category: " + categoryBadge(cl.category), esc(cl.explanation) + "<div class='mt-1'>" + keywordsHtml(cl.matched_keywords) + "</div>") +
      step("ok", "bi-flag", "Priority: " + priorityBadge(c.priority), "Detected categories: " + esc(cl.detected_categories.join(", "))) +
      r.steps.map((s) => step(s.result === "ok" ? "ok" : s.result === "fail" ? "fail" : "warn", "bi-signpost-split", esc(s.stage), esc(s.detail))).join("") +
      step(c.status === "Pending" ? "warn" : "ok", "bi-activity", "Initial status: " + statusBadge(c.status), "Status will update as the administrator works on it.") +
      "</ul>";
    const card = document.getElementById("resultCard");
    card.classList.remove("d-none");
    card.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderRejection(err) {
    const v = err.payload && err.payload.details && err.payload.details.validation;
    let html = '<div class="alert alert-danger"><i class="bi bi-x-octagon-fill me-1"></i><strong>Complaint rejected.</strong> ' + esc(err.message) + "</div>";
    if (v) {
      html += '<table class="table table-sm"><tbody>' +
        "<tr><th>Identifier</th><td class='mono'>" + esc(v.identifier) + "</td></tr>" +
        "<tr><th>DFA</th><td>" + verdict(v.dfa.valid === undefined ? v.dfa.result === "Valid" : v.dfa.valid) + " (state " + esc(v.dfa.final_state) + ")</td></tr>" +
        "<tr><th>Regex</th><td>" + verdict(v.regex.result === "Valid") + "</td></tr>" +
        "<tr><th>Agreement</th><td>" + (v.match ? "Yes" : "No") + "</td></tr></tbody></table>";
    }
    html += '<p class="small text-muted mb-0">No complaint record was created.</p>';
    document.getElementById("resultBody").innerHTML = html;
    document.getElementById("resultCard").classList.remove("d-none");
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    form.querySelectorAll(".is-invalid").forEach((el) => el.classList.remove("is-invalid"));
    alertEl.classList.add("d-none");
    const errors = {};
    if (val("name").trim().length < 2) errors.name = "Enter your name.";
    if (!/^[A-Za-z0-9]{3,20}$/.test(val("institutional_id").trim())) errors.institutional_id = "3-20 letters or digits.";
    if (!val("device_type")) errors.device_type = "Select a device type.";
    if (!val("location_code")) errors.location_code = "Select a location.";
    if (val("floor") === "") errors.floor = "Select a floor.";
    if (val("description").trim().length < 10) errors.description = "Describe the problem (min 10 characters).";
    if (Object.keys(errors).length) { showErrors(errors); return; }

    const btn = document.getElementById("submitBtn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Validating & routing…';
    try {
      const res = await api("POST", "/api/complaints", Object.fromEntries(new FormData(form).entries()));
      toast(res.message, res.data.routing.admin ? "success" : "warning");
      renderResult(res.data);
      form.elements.description.value = "";
      refreshClassification();
    } catch (err) {
      alertEl.textContent = err.message;
      alertEl.classList.remove("d-none");
      if (err.payload && err.payload.details && err.payload.details.fields) showErrors(err.payload.details.fields);
      if (err.status === 400) renderRejection(err);
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-send me-1"></i>Submit complaint';
    }
  });

  refreshIdentifier();
})();
