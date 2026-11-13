/* Technical overview: DFA visualiser, regex, classification and routing demos */
(function () {
  "use strict";
  const { api, esc, toast, categoryBadge, priorityBadge, keywordsHtml } = window.CNW;
  const SVGNS = "http://www.w3.org/2000/svg";
  const R = 21;
  const CX = 92, CY = 66, OX = 70, OY = 40;

  // Diagram layout (column, row) - purely visual; transitions come from the backend.
  const LAYOUT = {
    q0: [0, 2.5], q1: [1, 1], q2: [2, 1], q3: [3, 1], q4: [4, 1], q5: [1, 4], q6: [2, 4], q7: [3, 4], q8: [5, 2.5],
    q9: [6, 0], q10: [7, 0], q11: [8, 0], q12: [9, 0],
    q13: [6, 1.5], q14: [7, 1], q15: [8, 1], q16: [7, 2], q17: [8, 2],
    q18: [6, 3], q19: [7, 3], q20: [8, 3],
    q21: [6, 4], q22: [7, 4], q23: [8, 4], q24: [9, 4],
    q25: [6, 5], q26: [7, 5], q27: [8, 5], q28: [9, 5],
    q29: [10.2, 2.5], q30: [11.3, 2.5], qD: [2.5, 6],
  };
  const pos = (id) => ({ x: OX + LAYOUT[id][0] * CX, y: OY + LAYOUT[id][1] * CY });

  let def = null;
  let run = null;   // last validation result
  let stepIdx = 0;
  let timer = null;

  function el(tag, attrs, parent) {
    const n = document.createElementNS(SVGNS, tag);
    Object.entries(attrs || {}).forEach(([k, v]) => n.setAttribute(k, v));
    if (parent) parent.appendChild(n);
    return n;
  }

  function edgePath(a, b) {
    const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
    const ux = dx / len, uy = dy / len;
    return { x1: a.x + ux * R, y1: a.y + uy * R, x2: b.x - ux * (R + 4), y2: b.y - uy * (R + 4), ux, uy };
  }

  function drawDiagram() {
    const svg = document.getElementById("dfaSvg");
    svg.innerHTML = "";
    const W = OX * 2 + 11.3 * CX + 10, H = OY * 2 + 6 * CY;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.setAttribute("width", W);
    const defs = el("defs", {}, svg);
    [["arrow", "#94a3b8"], ["arrowOn", "#2a78d6"], ["arrowDead", "#c62828"]].forEach(([id, c]) => {
      const m = el("marker", { id, viewBox: "0 0 10 10", refX: 8, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" }, defs);
      el("path", { d: "M0,0 L10,5 L0,10 z", fill: c }, m);
    });
    const edges = el("g", {}, svg);
    // start arrow
    const s = pos("q0");
    el("path", { d: "M" + (s.x - 40) + "," + s.y + " L" + (s.x - R - 4) + "," + s.y, stroke: "#0b1f3a", "stroke-width": 2, "marker-end": "url(#arrow)" }, edges);
    el("text", { x: s.x - 48, y: s.y - 8, "font-size": 10, "font-weight": 700, fill: "#0b1f3a" }, edges).textContent = "start";

    def.transitions.forEach((t) => {
      const p = edgePath(pos(t.from), pos(t.to));
      const g = el("g", { class: "dfa-edge", "data-edge": t.from + ">" + t.to }, edges);
      el("path", { d: "M" + p.x1 + "," + p.y1 + " L" + p.x2 + "," + p.y2, "marker-end": "url(#arrow)" }, g);
      const f = t.to === "q29" ? 0.35 : 0.5;
      const lx = p.x1 + (p.x2 - p.x1) * f - p.uy * 9, ly = p.y1 + (p.y2 - p.y1) * f + p.ux * 9 - 2;
      el("text", { x: lx, y: ly }, g).textContent = t.symbol === "DIGIT" ? "0-9" : t.symbol;
    });
    el("g", { id: "deadEdgeLayer" }, svg);

    const nodes = el("g", {}, svg);
    def.states.forEach((st) => {
      const p = pos(st.id);
      const cls = "dfa-state" + (st.accepting ? " accepting" : "") + (st.dead ? " dead" : "");
      const g = el("g", { class: cls, id: "st-" + st.id }, nodes);
      el("title", {}, g).textContent = st.id + ": " + st.label;
      if (st.accepting) el("circle", { class: "outer", cx: p.x, cy: p.y, r: R + 4 }, g);
      el("circle", { class: "inner", cx: p.x, cy: p.y, r: R }, g);
      el("text", { x: p.x, y: p.y - 5 }, g).textContent = st.id;
      el("text", { class: "sub", x: p.x, y: p.y + 8 }, g).textContent = st.label.replace(" ✓", "").replace(" (ACCEPT)", "").replace("Separator ", "sep").replace("Dead / Reject", "dead").slice(0, 6);
    });
    const d = pos("qD");
    el("text", { x: d.x + R + 10, y: d.y + 4, "font-size": 11, fill: "#991b1b" }, svg).textContent = "Every undefined δ(q, a) goes to the absorbing dead state qD";
  }

  function renderTable() {
    const byState = {};
    def.transitions.forEach((t) => (byState[t.from] = byState[t.from] || []).push(t));
    document.getElementById("ttRows").innerHTML = def.states.map((s) => {
      const ts = (byState[s.id] || []).map((t) => '<span class="kw">' + esc(t.symbol === "DIGIT" ? "0-9" : t.symbol) + " → " + esc(t.to) + "</span>").join("");
      const type = s.initial ? '<span class="badge b-assigned">Initial</span>' : s.accepting ? '<span class="badge b-resolved">Accepting</span>' : s.dead ? '<span class="badge b-busy">Dead</span>' : "";
      return '<tr><td class="mono fw-bold">' + esc(s.id) + "</td><td>" + esc(s.label) + "</td><td>" + (ts || '<span class="text-muted">all → qD</span>') + "</td><td>" + type + "</td></tr>";
    }).join("");
  }

  function clearHighlight() {
    document.querySelectorAll(".dfa-state").forEach((n) => n.classList.remove("current", "visited"));
    document.querySelectorAll(".dfa-edge").forEach((n) => { n.classList.remove("taken"); n.querySelector("path").setAttribute("marker-end", "url(#arrow)"); });
    document.getElementById("deadEdgeLayer").innerHTML = "";
  }

  function setCurrent(id) {
    document.querySelectorAll(".dfa-state.current").forEach((n) => { n.classList.remove("current"); n.classList.add("visited"); });
    const n = document.getElementById("st-" + id);
    if (n) n.classList.add("current");
  }

  function renderTape(upto) {
    const input = run.identifier;
    const deadAt = run.trace.findIndex((t) => t.to === "qD");
    document.getElementById("tape").innerHTML = (input.length ? Array.from(input) : [" "]).map((ch, i) => {
      let cls = "";
      if (i < upto) cls = (i === deadAt) ? "bad" : "read";
      if (i === upto && upto < input.length) cls = "head";
      return '<span class="' + cls + '">' + esc(ch === " " ? "␣" : ch) + "</span>";
    }).join("");
  }

  function showStep(i) {
    // i = number of transitions applied
    if (i === 0) { clearHighlight(); setCurrent("q0"); }
    else {
      const t = run.trace[i - 1];
      if (t.to === "qD") {
        const p = edgePath(pos(t.from), pos("qD"));
        const g = el("g", { class: "dfa-edge taken" }, document.getElementById("deadEdgeLayer"));
        el("path", { d: "M" + p.x1 + "," + p.y1 + " L" + p.x2 + "," + p.y2, stroke: "#c62828", "stroke-dasharray": "5 4", "marker-end": "url(#arrowDead)", style: "stroke:#c62828" }, g);
        el("text", { x: (p.x1 + p.x2) / 2 + 8, y: (p.y1 + p.y2) / 2, style: "fill:#c62828" }, g).textContent = "'" + t.char + "'";
      } else {
        const e = document.querySelector('[data-edge="' + t.from + ">" + t.to + '"]');
        if (e) { e.classList.add("taken"); e.querySelector("path").setAttribute("marker-end", "url(#arrowOn)"); }
      }
      setCurrent(t.to);
    }
    renderTape(i);
    document.getElementById("traceRows").innerHTML = run.trace.slice(0, i).map((t) =>
      "<tr class='" + (t.to === "qD" ? "table-danger" : "") + "'><td>" + t.step + '</td><td class="mono">' + esc(t.from) + '</td><td class="mono fw-bold">\'' + esc(t.char) + "'</td><td class='mono'>" + esc(t.to) + "</td></tr>").join("");
    const done = i >= run.trace.length;
    const status = document.getElementById("dfaStatus");
    if (!done) {
      const cur = i === 0 ? "q0" : run.trace[i - 1].to;
      status.className = "alert alert-primary mb-0";
      status.innerHTML = "Current state <strong class='mono'>" + esc(cur) + "</strong>. Next symbol: <strong class='mono'>'" + esc(run.identifier[i]) + "'</strong>";
    } else {
      status.className = "alert mb-0 " + (run.valid ? "alert-success" : "alert-danger");
      status.innerHTML = (run.valid ? '<i class="bi bi-check-circle-fill me-1"></i><strong>ACCEPTED</strong>' : '<i class="bi bi-x-circle-fill me-1"></i><strong>REJECTED</strong>') +
        " — final state <strong class='mono'>" + esc(run.final_state) + "</strong> (" + esc(run.final_state_label) + ").<br>" + esc(run.message);
    }
  }

  async function validate() {
    clearInterval(timer);
    const id = document.getElementById("dfaInput").value;
    const res = await api("POST", "/api/validate/dfa", { identifier: id });
    run = res.data;
    stepIdx = 0;
    showStep(0);
  }

  async function animate() {
    await validate();
    timer = setInterval(() => {
      if (stepIdx >= run.trace.length) { clearInterval(timer); return; }
      stepIdx += 1;
      showStep(stepIdx);
    }, 420);
  }

  document.getElementById("dfaForm").addEventListener("submit", (e) => { e.preventDefault(); animate().catch((er) => toast(er.message, "danger")); });
  document.getElementById("stepBtn").addEventListener("click", async () => {
    clearInterval(timer);
    if (!run || run.identifier !== document.getElementById("dfaInput").value) { await validate(); return; }
    if (stepIdx < run.trace.length) { stepIdx += 1; showStep(stepIdx); }
  });
  document.getElementById("resetBtn").addEventListener("click", () => { clearInterval(timer); if (run) { stepIdx = 0; showStep(0); } });

  const SAMPLES = ["WIFI-HOST-2", "LAN-LAB-1", "WIFI-CANT-5", "LAN-SPRT-4", "WIFI-HOST", "LAN-LAB-12", "BLUETOOTH-HOST-2", "WIFI-XYZ-3", "WIFI--HOST-2", "WIFI-HOST-A", "wifi-host-2"];
  document.getElementById("samples").innerHTML = SAMPLES.map((s, i) =>
    '<button type="button" class="btn btn-sm ' + (i < 4 ? "btn-outline-success" : "btn-outline-danger") + ' mono" data-sample="' + esc(s) + '">' + esc(s) + "</button>").join("");
  document.getElementById("samples").addEventListener("click", (e) => {
    const b = e.target.closest("[data-sample]");
    if (b) { document.getElementById("dfaInput").value = b.dataset.sample; animate().catch((er) => toast(er.message, "danger")); }
  });

  // ---------------- Regex & comparison
  const compareList = ["WIFI-HOST-2", "LAN-LAB-1", "WIFI-ADM-3", "LAN-LIB-0", "WIFI-CANT-5", "LAN-SPRT-4", "WIFI-HOST", "LAN-LAB-12", "BLUETOOTH-HOST-2", "WIFI-XYZ-3", "WIFI--HOST-2", "WIFI-HOST-A", "WIFI-HOST-22", "wifi-host-2"];
  const verdict = (v) => v === "Valid" ? '<span class="badge b-resolved">Valid</span>' : '<span class="badge b-busy">Invalid</span>';
  async function loadCompare() {
    const res = await api("POST", "/api/validate/compare", { identifiers: compareList });
    document.getElementById("compareRows").innerHTML = res.data.rows.map((r) =>
      '<tr><td class="mono">' + esc(r.identifier) + "</td><td>" + verdict(r.dfa) + '</td><td class="mono small">' + esc(r.dfa_final_state) + "</td><td>" + verdict(r.regex) +
      "</td><td>" + (r.match === "Yes" ? '<i class="bi bi-check-circle-fill text-success"></i> Yes' : '<i class="bi bi-x-circle-fill text-danger"></i> No') + '</td><td class="small">' + esc(r.message) + "</td></tr>").join("");
    document.getElementById("agreeBadge").innerHTML = res.data.all_agree ? '<span class="badge b-resolved">All ' + res.data.rows.length + " agree</span>" : '<span class="badge b-busy">Disagreement found</span>';
  }
  document.getElementById("compareForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const v = document.getElementById("compareInput").value;
    if (!v) return;
    compareList.unshift(v);
    document.getElementById("compareInput").value = "";
    loadCompare().catch((er) => toast(er.message, "danger"));
  });
  document.getElementById("regexForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await api("POST", "/api/validate/regex", { identifier: document.getElementById("regexInput").value });
    const r = res.data;
    document.getElementById("regexResult").innerHTML = '<div class="alert ' + (r.valid ? "alert-success" : "alert-danger") + ' mb-0"><strong>' + esc(r.result) + "</strong> — " + esc(r.message) +
      (r.groups ? '<div class="small mt-1">Groups: device=<span class="mono">' + esc(r.groups.device_type) + "</span>, location=<span class='mono'>" + esc(r.groups.location_code) + "</span>, floor=<span class='mono'>" + esc(r.groups.floor) + "</span></div>" : "") + "</div>";
  });

  // ---------------- Classification
  const CLASS_SAMPLES = ["My WiFi is disconnected and internet is very slow.", "Router failure in the lab, switch port damaged.", "IP conflict and DNS error on my laptop.",
    "Unauthorized device attempted to access the network.", "The projector remote is missing."];
  document.getElementById("classSamples").innerHTML = CLASS_SAMPLES.map((s) => '<button class="btn btn-sm btn-outline-secondary" data-ctext="' + esc(s) + '">' + esc(s.slice(0, 28)) + "…</button>").join("");
  document.getElementById("classSamples").addEventListener("click", (e) => {
    const b = e.target.closest("[data-ctext]");
    if (b) { document.getElementById("classText").value = b.dataset.ctext; classify(); }
  });
  async function classify() {
    const res = await api("POST", "/api/classify", { description: document.getElementById("classText").value });
    const r = res.data;
    document.getElementById("classResult").innerHTML =
      '<div class="d-flex flex-wrap gap-2 align-items-center mb-2"><span class="text-muted small">Selected:</span>' + categoryBadge(r.category) + priorityBadge(r.priority) + "</div>" +
      '<div class="small mb-2"><span class="text-muted">All detected categories:</span> ' + r.detected_categories.map(categoryBadge).join(" ") + "</div>" +
      '<div class="small mb-2"><span class="text-muted">Matched keywords:</span> ' + keywordsHtml(r.matched_keywords) + "</div>" +
      '<div class="alert alert-info small mb-0">' + esc(r.explanation) + "</div>";
  }
  document.getElementById("classBtn").addEventListener("click", () => classify().catch((er) => toast(er.message, "danger")));
  async function loadKeywords() {
    const res = await api("GET", "/api/classify/keywords");
    const d = res.data;
    document.getElementById("keywordBox").innerHTML =
      '<p class="small mb-2"><strong>Precedence:</strong> ' + d.precedence.map(esc).join(" &gt; ") + "</p>" +
      Object.entries(d.keywords).map(([cat, kws]) => '<div class="mb-2">' + categoryBadge(cat) + " " + priorityBadge(d.priority_map[cat]) + '<div class="mt-1">' + kws.map((k) => '<span class="kw">' + esc(k) + "</span>").join("") + "</div></div>").join("") +
      '<div>' + categoryBadge("Unknown") + " " + priorityBadge("Low") + ' <span class="small text-muted">— no keyword matched</span></div>';
  }

  // ---------------- Routing
  document.getElementById("routeForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const out = document.getElementById("routeResult");
    try {
      const res = await api("POST", "/api/routing/preview", { identifier: document.getElementById("routeInput").value });
      const d = res.data;
      const nodes = [{ stage: "Complaint", detail: document.getElementById("routeInput").value, result: "ok" }].concat(d.steps);
      out.innerHTML = '<div class="routing-flow mb-3">' + nodes.map((s, i) => (i ? '<div class="arrow"><i class="bi bi-arrow-right"></i></div>' : "") +
        '<div class="node ' + esc(s.result) + '"><div class="t">' + esc(s.stage) + "</div>" + esc(s.detail) + "</div>").join("") + "</div>" +
        '<div class="alert ' + (d.admin ? "alert-success" : "alert-warning") + ' mb-0"><strong>Outcome: ' + esc(d.outcome.replace(/_/g, " ")) + "</strong> — " +
        (d.admin ? "administrator selected by the backend: <strong>" + esc(d.admin.name) + "</strong> (" + esc(d.admin.admin_code) + ")" : "complaint would wait in the " + esc(d.zone_code) + " priority queue") + ".</div>";
    } catch (er) { out.innerHTML = '<div class="alert alert-danger mb-0">Rejected before routing: ' + esc(er.message) + "</div>"; }
  });

  (async function init() {
    try {
      const res = await api("GET", "/api/dfa/definition");
      def = res.data.dfa;
      document.getElementById("regexPattern").textContent = res.data.regex;
      drawDiagram();
      renderTable();
      await animate();
      await loadCompare();
      await loadKeywords();
      classify();
    } catch (e) { toast(e.message, "danger"); }
  })();
})();
