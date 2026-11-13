/* Analytics dashboard - every chart is fed from /api/analytics/report */
(function () {
  "use strict";
  const { api, esc, toast } = window.CNW;

  // Validated categorical palette (fixed order, never cycled) + reserved status colours.
  const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
  const STATUS = { good: "#15803d", warning: "#d97706", serious: "#c2410c", critical: "#c62828", neutral: "#94a3b8" };
  const PRIORITY_COLORS = { Critical: STATUS.critical, High: STATUS.serious, Medium: "#e5b000", Low: STATUS.neutral };
  const STATUS_COLORS = { Pending: STATUS.warning, Assigned: SERIES[0], "In Progress": SERIES[6], Resolved: STATUS.good };

  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.color = "#5b6474";
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.tooltip.backgroundColor = "#0b1f3a";
  Chart.defaults.plugins.tooltip.padding = 10;

  const charts = {};
  const grid = { color: "#eef1f5" };
  const barStyle = { borderRadius: 4, borderSkipped: "start", maxBarThickness: 42, borderColor: "#fff", borderWidth: 2 };

  function draw(id, config) {
    if (charts[id]) {
      charts[id].data = config.data;
      charts[id].update();
      return;
    }
    charts[id] = new Chart(document.getElementById(id), config);
  }

  function doughnut(id, labels, values, colors) {
    const total = values.reduce((a, b) => a + b, 0);
    draw(id, {
      type: "doughnut",
      data: { labels, datasets: [{ data: values, backgroundColor: colors, borderColor: "#fff", borderWidth: 2, hoverOffset: 6 }] },
      options: {
        maintainAspectRatio: false, cutout: "62%",
        plugins: {
          legend: { position: "bottom" },
          tooltip: { callbacks: { label: (c) => " " + c.label + ": " + c.parsed + (total ? " (" + Math.round(100 * c.parsed / total) + "%)" : "") } },
        },
      },
    });
  }

  function render(d) {
    const o = d.overview;
    document.getElementById("kTotal").textContent = o.total;
    document.getElementById("kResolved").textContent = o.resolved;
    document.getElementById("kUnresolved").textContent = o.unresolved;
    document.getElementById("kCritical").textContent = o.critical;
    document.getElementById("kAvg").textContent = o.avg_resolution_hours === null ? "—"
      : (o.avg_resolution_hours >= 24 ? (o.avg_resolution_hours / 24).toFixed(1) + " d" : o.avg_resolution_hours.toFixed(1) + " h");

    const zoneLabels = d.zones.map((z) => z.location_name);
    draw("zoneChart", {
      type: "bar",
      data: {
        labels: zoneLabels,
        datasets: [
          Object.assign({ label: "Resolved", data: d.zones.map((z) => z.resolved), backgroundColor: STATUS.good }, barStyle),
          Object.assign({ label: "Unresolved", data: d.zones.map((z) => z.unresolved), backgroundColor: STATUS.warning }, barStyle),
        ],
      },
      options: {
        maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 }, grid } },
        plugins: { legend: { position: "top", align: "end" } },
      },
    });

    doughnut("categoryChart", d.categories.map((c) => c.label), d.categories.map((c) => c.count), SERIES.slice(0, d.categories.length));
    doughnut("priorityChart", d.priorities.map((p) => p.label), d.priorities.map((p) => p.count), d.priorities.map((p) => PRIORITY_COLORS[p.label]));

    draw("resolvedChart", {
      type: "bar",
      data: { labels: ["Resolved", "Unresolved"], datasets: [Object.assign({ label: "Complaints", data: [o.resolved, o.unresolved], backgroundColor: [STATUS.good, STATUS.warning] }, barStyle)] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { beginAtZero: true, ticks: { precision: 0 }, grid } } },
    });

    draw("statusChart", {
      type: "bar",
      data: { labels: d.statuses.map((s) => s.label), datasets: [Object.assign({ label: "Complaints", data: d.statuses.map((s) => s.count), backgroundColor: d.statuses.map((s) => STATUS_COLORS[s.label]) }, barStyle)] },
      options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { grid: { display: false } }, x: { beginAtZero: true, ticks: { precision: 0 }, grid } } },
    });

    // Zero-fill every day in the range so the series is continuous.
    const tl = [];
    if (d.timeline.length) {
      const map = Object.fromEntries(d.timeline.map((t) => [t.day, t]));
      const day = new Date(d.timeline[0].day + "T00:00:00"), end = new Date(d.timeline[d.timeline.length - 1].day + "T00:00:00");
      for (; day <= end; day.setDate(day.getDate() + 1)) {
        const k = day.getFullYear() + "-" + String(day.getMonth() + 1).padStart(2, "0") + "-" + String(day.getDate()).padStart(2, "0");
        tl.push(map[k] || { day: k, submitted: 0, resolved: 0 });
      }
    }
    d.timeline = tl;
    draw("timelineChart", {
      type: "line",
      data: {
        labels: d.timeline.map((t) => t.day),
        datasets: [
          { label: "Submitted", data: d.timeline.map((t) => t.submitted), borderColor: SERIES[0], backgroundColor: SERIES[0], borderWidth: 2, pointRadius: 4, tension: 0 },
          { label: "Resolved (of those submitted)", data: d.timeline.map((t) => t.resolved), borderColor: SERIES[1], backgroundColor: SERIES[1], borderWidth: 2, pointRadius: 4, tension: 0 },
        ],
      },
      options: {
        maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        scales: { x: { grid: { display: false } }, y: { beginAtZero: true, ticks: { precision: 0 }, grid } },
        plugins: { legend: { position: "top", align: "end" } },
      },
    });

    document.getElementById("zoneTable").innerHTML = d.zones.map((z) =>
      "<tr><td>" + esc(z.location_name) + '</td><td class="mono">' + esc(z.location_code) + '</td><td class="text-end">' + z.total +
      '</td><td class="text-end">' + z.resolved + '</td><td class="text-end">' + z.unresolved + '</td><td class="text-end">' + z.critical +
      '</td><td class="text-end">' + (z.total ? Math.round(100 * z.resolved / z.total) + "%" : "—") + "</td></tr>").join("");
    document.getElementById("updatedAt").textContent = "Updated " + new Date().toLocaleTimeString();
  }

  async function load() {
    const p = new URLSearchParams();
    const f = document.getElementById("from").value, t = document.getElementById("to").value;
    if (f) p.set("from", f);
    if (t) p.set("to", t);
    try { render((await api("GET", "/api/analytics/report?" + p.toString())).data); }
    catch (e) { toast(e.message, "danger"); }
  }

  document.getElementById("rangeForm").addEventListener("submit", (e) => { e.preventDefault(); load(); });
  document.querySelectorAll("[data-days]").forEach((b) => b.addEventListener("click", () => {
    const days = Number(b.dataset.days);
    const iso = (d) => d.toISOString().slice(0, 10);
    if (days) {
      const now = new Date(); const start = new Date(now.getTime() - days * 86400000);
      document.getElementById("from").value = iso(start); document.getElementById("to").value = iso(now);
    } else { document.getElementById("from").value = ""; document.getElementById("to").value = ""; }
    load();
  }));
  load();
  setInterval(load, 30000); // reflect new complaints and status changes
})();
