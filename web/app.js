// ---------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------
const API_BASE_URL = "https://api-mactitan.useomniagents.xyz";

// ---------------------------------------------------------------------
// State
// ---------------------------------------------------------------------
let conversationHistory = [];
let activeChart = null; // track Chart.js instance so we can destroy before redraw

// ---------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------
const chatThread = document.getElementById("chatThread");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const workspaceBody = document.getElementById("workspaceBody");
const appEl = document.querySelector(".app");
const mobileToggle = document.getElementById("mobileToggle");

// ---------------------------------------------------------------------
// Orb thinking indicator — ported from a React "lattice orb" component.
// 3x3 grid, S3 variant: one glowing head with a decaying tail travels
// the ring perimeter clockwise; the single interior cell stays still.
// Math (ring order, delay, swirl offsets) preserved from the source;
// only the render target (plain DOM strings, not React) changed.
// ---------------------------------------------------------------------

const ORB_N = 3;
const ORB_PITCH = 7; // px, center-to-center spacing (tuned for a 20px box)
const ORB_MID = (ORB_N - 1) / 2;
const ORB_SWIRL = 1.05; // radians, ~60°
const ORB_SPREAD = 1.6;

const ORB_RING = (() => {
  const ring = [];
  for (let x = 0; x < ORB_N; x++) ring.push([x, 0]);
  for (let y = 1; y < ORB_N; y++) ring.push([ORB_N - 1, y]);
  for (let x = ORB_N - 2; x >= 0; x--) ring.push([x, ORB_N - 1]);
  for (let y = ORB_N - 2; y >= 1; y--) ring.push([0, y]);
  return ring;
})();

const ORB_RING_INDEX = new Map(ORB_RING.map(([x, y], i) => [`${x},${y}`, i]));

function orbCellDelay(x, y) {
  const i = ORB_RING_INDEX.get(`${x},${y}`);
  if (i === undefined) return 0;
  return -(((ORB_RING.length - i) % ORB_RING.length) / ORB_RING.length) * 1700;
}

function orbSwirl(x, y, angle) {
  const dx = x - ORB_MID;
  const dy = y - ORB_MID;
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  return [
    ((dx * cos - dy * sin) * ORB_SPREAD - dx) * ORB_PITCH,
    ((dx * sin + dy * cos) * ORB_SPREAD - dy) * ORB_PITCH,
  ];
}

function buildOrbCellsHtml() {
  let html = "";
  for (let y = 0; y < ORB_N; y++) {
    for (let x = 0; x < ORB_N; x++) {
      const [ax, ay] = orbSwirl(x, y, -ORB_SWIRL);
      const [bx, by] = orbSwirl(x, y, ORB_SWIRL);
      const still = !ORB_RING_INDEX.has(`${x},${y}`);
      const mid = x === ORB_MID && y === ORB_MID;
      const delay = orbCellDelay(x, y);
      const style = [
        `left:${x * ORB_PITCH}px`,
        `top:${y * ORB_PITCH}px`,
        `animation-delay:${delay}ms`,
        `--orb-ax:${ax}px`,
        `--orb-ay:${ay}px`,
        `--orb-bx:${bx}px`,
        `--orb-by:${by}px`,
      ].join(";");
      html += `<span class="orb-cell"${still ? " data-still" : ""}${mid ? " data-mid" : ""} style="${style}"></span>`;
    }
  }
  return html;
}

// ---------------------------------------------------------------------
// Chat rendering
// ---------------------------------------------------------------------

function appendUserMessage(text) {
  const msg = document.createElement("div");
  msg.className = "msg msg-user";
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = text;
  msg.appendChild(bubble);
  chatThread.appendChild(msg);
  scrollChatToBottom();
}

function appendAssistantMessage(markdownText) {
  const msg = document.createElement("div");
  msg.className = "msg msg-assistant";
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.innerHTML = marked.parse(markdownText);
  msg.appendChild(bubble);
  chatThread.appendChild(msg);
  scrollChatToBottom();
}

function showThinking() {
  const msg = document.createElement("div");
  msg.className = "msg msg-assistant";
  msg.id = "thinkingMsg";
  const bubble = document.createElement("div");
  bubble.className = "orb-thinking";
  bubble.innerHTML = `<span class="orb">${buildOrbCellsHtml()}</span><span class="orb-thinking-text">Crunching the numbers…</span>`;
  msg.appendChild(bubble);
  chatThread.appendChild(msg);
  scrollChatToBottom();
}

function removeThinking() {
  const el = document.getElementById("thinkingMsg");
  if (el) el.remove();
}

function scrollChatToBottom() {
  chatThread.scrollTop = chatThread.scrollHeight;
}

// ---------------------------------------------------------------------
// Sending messages
// ---------------------------------------------------------------------

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  chatInput.value = "";
  sendBtn.disabled = true;

  appendUserMessage(text);
  showThinking();

  try {
    const resp = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: conversationHistory }),
    });

    if (!resp.ok) {
      throw new Error(`Server returned ${resp.status}`);
    }

    const data = await resp.json();
    conversationHistory = data.history;

    removeThinking();
    appendAssistantMessage(data.answer);

    if (data.tool_results && data.tool_results.length > 0) {
      renderWorkspace(data.tool_results);
    }
    // If no tools were called (e.g. a greeting), the workspace panel
    // deliberately keeps showing whatever it last displayed.
  } catch (err) {
    removeThinking();
    appendAssistantMessage(
      "Something went wrong reaching the research desk. Please try again in a moment."
    );
    console.error(err);
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
  }
}

sendBtn.addEventListener("click", sendMessage);
chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});

// ---------------------------------------------------------------------
// Workspace panel rendering — adapts to whichever tool(s) were called
// ---------------------------------------------------------------------

function renderWorkspace(toolResults) {
  workspaceBody.innerHTML = "";

  toolResults.forEach((tr) => {
    const section = document.createElement("div");
    section.className = "ws-section";

    if (tr.result && tr.result.error) {
      section.appendChild(renderError(tr.result.error));
    } else {
      switch (tr.tool) {
        case "get_event_reaction":
          section.appendChild(renderEventReaction(tr.result));
          break;
        case "get_sector_sensitivity":
          section.appendChild(renderSectorSensitivity(tr.result));
          break;
        case "get_current_volatility":
          section.appendChild(renderVolatility(tr.result));
          break;
        case "get_upcoming_event":
          section.appendChild(renderUpcomingEvent(tr.result));
          break;
        case "get_cpi_breakdown":
          section.appendChild(renderCpiBreakdown(tr.result));
          break;
        default:
          section.appendChild(renderError(`Unknown tool result: ${tr.tool}`));
      }
    }

    workspaceBody.appendChild(section);
  });
}

function renderError(message) {
  const div = document.createElement("div");
  div.className = "stat-card-large";
  div.innerHTML = `
    <div class="stat-value stat-negative" style="font-size:20px;">Data unavailable</div>
    <div class="stat-label">${escapeHtml(message)}</div>
  `;
  return div;
}

function pctClass(value) {
  if (value > 0) return "stat-positive";
  if (value < 0) return "stat-negative";
  return "stat-neutral";
}

function fmtPct(value) {
  const pct = (value * 100).toFixed(2);
  return (value > 0 ? "+" : "") + pct + "%";
}

// --- Event reaction: ticker vs macro events -----------------------------

function renderEventReaction(result) {
  const wrap = document.createElement("div");
  const summary = result.summary;

  wrap.innerHTML = `
    <div class="ws-title">${result.ticker} vs ${result.event_type.toUpperCase()}</div>
    <div class="ws-subtitle">${summary.event_count} historical events analyzed</div>
    <div class="stat-row">
      <div class="stat-card-small">
        <div class="stat-value ${pctClass(summary.avg_pct_move)}">${fmtPct(summary.avg_pct_move)}</div>
        <div class="stat-label">Avg move</div>
      </div>
      <div class="stat-card-small">
        <div class="stat-value stat-neutral">${(summary.avg_volatility * 100).toFixed(2)}%</div>
        <div class="stat-label">Avg volatility</div>
      </div>
      <div class="stat-card-small">
        <div class="stat-value stat-neutral" style="text-transform:capitalize;">${summary.consistent_direction}</div>
        <div class="stat-label">Direction</div>
      </div>
    </div>
    <div class="chart-container"><canvas id="eventChart"></canvas></div>
  `;

  requestAnimationFrame(() => {
    const ctx = document.getElementById("eventChart");
    if (activeChart) activeChart.destroy();
    const reactions = result.individual_reactions;
    activeChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: reactions.map((r) => r.event_date),
        datasets: [{
          label: "Price move",
          data: reactions.map((r) => (r.pct_move * 100).toFixed(2)),
          backgroundColor: reactions.map((r) => (r.pct_move >= 0 ? "#4ADE80" : "#F87171")),
          borderRadius: 6,
        }],
      },
      options: chartBaseOptions("% move"),
    });
  });

  return wrap;
}

// --- Sector sensitivity ---------------------------------------------------

function renderSectorSensitivity(result) {
  const wrap = document.createElement("div");
  wrap.innerHTML = `
    <div class="ws-title">Sector sensitivity — ${result.event_type.toUpperCase()}</div>
    <div class="ws-subtitle">Ranked by average absolute move</div>
    <div class="chart-container" style="height:${Math.max(340, result.sector_ranking.length * 34)}px;">
      <canvas id="sectorChart"></canvas>
    </div>
  `;

  requestAnimationFrame(() => {
    const ctx = document.getElementById("sectorChart");
    if (activeChart) activeChart.destroy();
    const ranked = result.sector_ranking;
    activeChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: ranked.map((r) => r.sector),
        datasets: [{
          label: "Avg abs move",
          data: ranked.map((r) => (r.avg_abs_move * 100).toFixed(2)),
          backgroundColor: "#5B8DEF",
          borderRadius: 6,
        }],
      },
      options: { ...chartBaseOptions("% move"), indexAxis: "y" },
    });
  });

  return wrap;
}

// --- Volatility -------------------------------------------------------

function renderVolatility(result) {
  const wrap = document.createElement("div");
  const elevatedLabel = result.elevated === null ? "Unknown" : result.elevated ? "Elevated" : "Normal";
  const elevatedClass = result.elevated === null ? "stat-neutral" : result.elevated ? "stat-negative" : "stat-positive";

  wrap.innerHTML = `
    <div class="ws-title">${result.ticker} volatility</div>
    <div class="ws-subtitle">Recent vs. own baseline</div>
    <div class="stat-card-large">
      <div class="stat-value ${elevatedClass}">${result.ratio !== null ? result.ratio + "×" : "—"}</div>
      <div class="stat-label">${elevatedLabel} relative to baseline</div>
    </div>
    <div class="stat-row">
      <div class="stat-card-small">
        <div class="stat-value stat-neutral">${result.recent_volatility !== null ? (result.recent_volatility * 100).toFixed(2) + "%" : "—"}</div>
        <div class="stat-label">Recent volatility</div>
      </div>
      <div class="stat-card-small">
        <div class="stat-value stat-neutral">${result.baseline_volatility !== null ? (result.baseline_volatility * 100).toFixed(2) + "%" : "—"}</div>
        <div class="stat-label">Baseline volatility</div>
      </div>
    </div>
  `;
  return wrap;
}

// --- Upcoming event -----------------------------------------------------

function renderUpcomingEvent(result) {
  const wrap = document.createElement("div");
  wrap.innerHTML = `
    <div class="ws-title">Next ${result.event_type.toUpperCase()}</div>
    <div class="stat-card-large">
      <div class="stat-value stat-neutral">${result.next_date || "Not yet known"}</div>
      <div class="stat-label">Official Fed / BLS calendar</div>
    </div>
  `;
  return wrap;
}

// --- CPI breakdown --------------------------------------------------------

function renderCpiBreakdown(result) {
  const wrap = document.createElement("div");
  const latest = result.latest;
  const components = ["headline", "core", "food", "energy", "shelter"];

  const statCards = components
    .filter((c) => latest[c] !== undefined)
    .map((c) => `
      <div class="stat-card-small">
        <div class="stat-value stat-neutral">${latest[c]}</div>
        <div class="stat-label" style="text-transform:capitalize;">${c}</div>
      </div>
    `).join("");

  const historyRows = result.recent_history
    .map((row) => `
      <tr>
        <td>${row.reference_month}</td>
        <td>${row.headline ?? "—"}</td>
        <td>${row.energy ?? "—"}</td>
        <td>${row.shelter ?? "—"}</td>
      </tr>
    `).join("");

  wrap.innerHTML = `
    <div class="ws-title">CPI breakdown</div>
    <div class="ws-subtitle">Latest: ${latest.reference_month} (released ${latest.release_date})</div>
    <div class="stat-row">${statCards}</div>
    <div class="data-table-wrap">
      <table class="data-table">
        <thead><tr><th>Month</th><th>Headline</th><th>Energy</th><th>Shelter</th></tr></thead>
        <tbody>${historyRows}</tbody>
      </table>
    </div>
  `;
  return wrap;
}

// --- Chart.js shared styling ---------------------------------------------

function chartBaseOptions(yLabel) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: {
        ticks: { color: "#8B93A7", font: { family: "JetBrains Mono", size: 11 } },
        grid: { color: "rgba(255,255,255,0.05)" },
      },
      y: {
        ticks: { color: "#8B93A7", font: { family: "JetBrains Mono", size: 11 } },
        grid: { color: "rgba(255,255,255,0.05)" },
        title: { display: true, text: yLabel, color: "#5A6274" },
      },
    },
  };
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------------------------------------------------------------------
// Mobile view toggle
// ---------------------------------------------------------------------

mobileToggle.addEventListener("click", (e) => {
  const btn = e.target.closest(".mobile-toggle-btn");
  if (!btn) return;

  document.querySelectorAll(".mobile-toggle-btn").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");

  appEl.classList.remove("view-chat", "view-workspace");
  appEl.classList.add(`view-${btn.dataset.view}`);
});
