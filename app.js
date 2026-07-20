/* Cadence — an energy-aware task companion.
   You rate tasks by Impact and Effort; you tell Cadence your current energy;
   it tells you the single best thing to do right now. Self-contained, no deps,
   state persisted to localStorage. */

(function () {
  "use strict";

  const KEY = "cadence.state.v1";
  const ENERGY_WORDS = { 1: "Low", 2: "Medium", 3: "High" };
  const RING_R = 96;
  const RING_C = 2 * Math.PI * RING_R;

  // ---------- State ----------
  const defaultState = () => ({
    tasks: [],
    sessions: [],          // timestamps of completed focus sessions
    energyLog: [],         // { t, level }
    currentEnergy: 2,
    focusMin: 25,
    stats: { tasksCompleted: 0 },
  });

  let state = load();
  let focusTaskId = null;   // ephemeral: a task the user explicitly picked

  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return defaultState();
      return Object.assign(defaultState(), JSON.parse(raw));
    } catch (e) {
      console.warn("Cadence: could not load state", e);
      return defaultState();
    }
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); }
    catch (e) { console.warn("Cadence: could not save state", e); }
  }

  // ---------- Helpers ----------
  const $ = (sel) => document.querySelector(sel);
  const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  function todayKey(d = new Date()) {
    const x = new Date(d);
    x.setMinutes(x.getMinutes() - x.getTimezoneOffset());
    return x.toISOString().slice(0, 10);
  }
  function escapeHtml(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  const activeTasks = () => state.tasks.filter((t) => !t.done);

  // ---------- The core: energy-aware fit ----------
  // Higher is better. Rewards impact; matches effort to the energy you have.
  function fitScore(task, energy) {
    const base = task.impact * 10;
    const gap = energy - task.effort;      // >= 0 means you have enough energy
    if (gap < 0) return base - 8 * -gap;   // demote tasks too demanding right now
    return base + (2 - gap);               // small nudge toward using energy well
  }

  function reason(task, energy) {
    const impactPart =
      task.impact === 3 ? "High impact" :
      task.impact === 2 ? "Solid impact" : "Low-stakes";
    const gap = energy - task.effort;
    let fitPart;
    if (gap < 0) {
      fitPart = "and though it's a stretch for your energy right now, nothing lighter beats it";
    } else if (task.effort === energy) {
      fitPart = "and its effort matches your energy exactly";
    } else if (gap >= 2 && energy >= 2) {
      fitPart = "and it's light enough to knock out fast";
    } else {
      fitPart = "and it sits comfortably within your energy";
    }
    return `${impactPart}, ${fitPart}.`;
  }

  // Sort active tasks best-first for a given energy.
  function ranked(energy) {
    return activeTasks()
      .map((t) => ({ t, score: fitScore(t, energy) }))
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        const ad = a.t.due || "9999", bd = b.t.due || "9999";
        if (ad !== bd) return ad < bd ? -1 : 1;
        return a.t.createdAt - b.t.createdAt;
      });
  }

  // ---------- Task actions ----------
  function addTask(title, impact, effort, due) {
    state.tasks.push({
      id: uid(), title: title.trim(),
      impact: +impact, effort: +effort, due: due || null,
      done: false, createdAt: Date.now(),
    });
    save(); renderAll();
  }
  function toggleTask(id) {
    const t = state.tasks.find((t) => t.id === id);
    if (!t) return;
    t.done = !t.done;
    if (t.done) state.stats.tasksCompleted += 1;
    if (t.done && focusTaskId === id) focusTaskId = null;
    save(); renderAll();
  }
  function deleteTask(id) {
    state.tasks = state.tasks.filter((t) => t.id !== id);
    if (focusTaskId === id) focusTaskId = null;
    save(); renderAll();
  }

  // ---------- Energy ----------
  function setEnergy(level) {
    state.currentEnergy = level;
    state.energyLog.push({ t: Date.now(), level });
    save(); renderAll();
  }

  // ---------- Focus timer ----------
  const timer = {
    remaining: state.focusMin * 60,
    running: false,
    handle: null,
    start() {
      if (this.running) return;
      if (this.remaining <= 0) this.remaining = state.focusMin * 60;
      this.running = true;
      this.handle = setInterval(() => this.tick(), 1000);
      renderTimer();
    },
    pause() {
      this.running = false;
      clearInterval(this.handle);
      renderTimer();
    },
    reset() {
      this.pause();
      this.remaining = state.focusMin * 60;
      renderTimer();
    },
    setMinutes(min) {
      state.focusMin = min; save();
      if (!this.running) this.remaining = min * 60;
      renderTimer();
    },
    tick() {
      this.remaining -= 1;
      if (this.remaining <= 0) { this.complete(); return; }
      renderTimer();
    },
    complete() {
      this.pause();
      this.remaining = 0;
      state.sessions.push(Date.now());
      save();
      renderTimer("done");
      renderMomentum();
      renderStreak();
      setTimeout(() => { this.remaining = state.focusMin * 60; renderTimer(); }, 1800);
    },
  };

  function fmtTime(sec) {
    const m = Math.floor(sec / 60), s = sec % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  function renderTimer(forceSub) {
    const total = state.focusMin * 60;
    const frac = Math.max(0, Math.min(1, timer.remaining / total));
    $("#ring-time").textContent = fmtTime(Math.max(0, timer.remaining));
    const ring = $("#ring-progress");
    ring.style.strokeDasharray = RING_C;
    ring.style.strokeDashoffset = RING_C * (1 - frac);
    $(".ring").classList.toggle("running", timer.running);
    $("#timer-toggle").textContent = timer.running ? "Pause" : "Start";
    $("#ring-sub").textContent =
      forceSub === "done" ? "session done ✓" :
      timer.running ? "focusing" :
      timer.remaining < total ? "paused" : "ready";
  }

  // ---------- Rendering ----------
  function renderEnergyButtons() {
    document.querySelectorAll(".energy-btn").forEach((b) => {
      b.classList.toggle("active", +b.dataset.energy === state.currentEnergy);
    });
  }

  function badge(kind, level, label) {
    return `<span class="badge ${kind}-${level}"><span class="dot"></span>${label} ${["", "low", "med", "high"][level] || ""}</span>`;
  }
  function dueBadge(task) {
    if (!task.due) return "";
    const overdue = task.due < todayKey();
    const d = new Date(task.due + "T00:00:00");
    const label = d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    return `<span class="badge due ${overdue ? "overdue" : ""}">📅 ${label}</span>`;
  }

  function renderNow() {
    const energy = state.currentEnergy;
    const list = ranked(energy);
    const body = $("#rc-body");

    let chosen = null, isPinned = false;
    if (focusTaskId) {
      const pin = state.tasks.find((t) => t.id === focusTaskId && !t.done);
      if (pin) { chosen = { t: pin, score: fitScore(pin, energy) }; isPinned = true; }
    }
    if (!chosen) chosen = list[0];

    if (!chosen) {
      body.innerHTML = `<div class="rc-empty">No active tasks. Add a few in <strong>Tasks</strong> and Cadence will pick your best next move.</div>`;
    } else {
      const t = chosen.t;
      body.innerHTML = `
        <div class="rc-task-title">${escapeHtml(t.title)}</div>
        <div class="rc-badges">
          ${badge("impact", t.impact, "Impact")}
          ${badge("effort", t.effort, "Effort")}
          <span class="badge fit">fit ${chosen.score}</span>
          ${dueBadge(t)}
        </div>
        <div class="rc-reason">${isPinned ? "You picked this one — go." : reason(t, energy)}</div>
        <div class="rc-actions">
          <button class="btn primary" id="rc-start">Start focus</button>
          <button class="btn ghost" id="rc-done">Mark done</button>
        </div>`;
      $("#rc-start").addEventListener("click", () => { switchTab("now"); timer.start(); });
      $("#rc-done").addEventListener("click", () => toggleTask(t.id));
    }

    // Shortlist: next best after the chosen one
    const chosenId = chosen ? chosen.t.id : null;
    const rest = list.filter((r) => r.t.id !== chosenId).slice(0, 3);
    const ul = $("#shortlist-list");
    ul.innerHTML = "";
    if (rest.length === 0) {
      ul.innerHTML = `<li class="hint" style="padding:6px 2px">Nothing else queued.</li>`;
    } else {
      rest.forEach((r, i) => {
        const li = document.createElement("li");
        li.className = "shortlist-item";
        li.innerHTML = `
          <span class="shortlist-rank">${i + 1}</span>
          <span class="shortlist-title">${escapeHtml(r.t.title)}</span>
          <span class="shortlist-fit">fit ${r.score}</span>`;
        li.addEventListener("click", () => { focusTaskId = r.t.id; renderNow(); });
        ul.appendChild(li);
      });
    }
  }

  let taskFilter = "active";
  function renderTasks() {
    const energy = state.currentEnergy;
    const list = $("#task-list");
    list.innerHTML = "";

    let items = state.tasks.slice();
    if (taskFilter === "active") items = items.filter((t) => !t.done);
    else if (taskFilter === "done") items = items.filter((t) => t.done);

    items.sort((a, b) => {
      if (a.done !== b.done) return a.done ? 1 : -1;
      return fitScore(b, energy) - fitScore(a, energy);
    });

    $("#tasks-empty").classList.toggle("hidden", items.length > 0);

    for (const t of items) {
      const li = document.createElement("li");
      li.className = "task-item" + (t.done ? " done" : "");
      li.innerHTML = `
        <input type="checkbox" class="checkbox" ${t.done ? "checked" : ""} aria-label="Complete" />
        <div class="task-body">
          <div class="task-name">${escapeHtml(t.title)}</div>
          <div class="task-meta">
            ${badge("impact", t.impact, "Impact")}
            ${badge("effort", t.effort, "Effort")}
            ${t.done ? "" : `<span class="badge fit">fit ${fitScore(t, energy)}</span>`}
            ${dueBadge(t)}
          </div>
        </div>
        ${t.done ? "" : `<button class="icon-btn focus-btn" title="Focus this now">◎</button>`}
        <button class="icon-btn del" title="Delete">✕</button>`;
      li.querySelector(".checkbox").addEventListener("change", () => toggleTask(t.id));
      li.querySelector(".del").addEventListener("click", () => deleteTask(t.id));
      const fb = li.querySelector(".focus-btn");
      if (fb) fb.addEventListener("click", () => { focusTaskId = t.id; switchTab("now"); });
      list.appendChild(li);
    }
  }

  function renderMatrix() {
    const svg = $("#matrix-svg");
    const W = 480, H = 420, padL = 46, padR = 18, padT = 20, padB = 46;
    const plotW = W - padL - padR, plotH = H - padT - padB;
    // Inset the data region so extreme-value nodes don't sit on the frame/labels.
    const inset = 46;
    const gx0 = padL + inset, gx1 = padL + plotW - inset;
    const gy0 = padT + inset, gy1 = padT + plotH - inset;
    const xFor = (effort) => gx0 + ((effort - 1) / 2) * (gx1 - gx0);
    const yFor = (impact) => gy0 + ((3 - impact) / 2) * (gy1 - gy0);

    const parts = [];
    // frame
    parts.push(`<rect x="${padL}" y="${padT}" width="${plotW}" height="${plotH}" fill="none" class="grid-line" rx="8"/>`);
    // mid lines
    parts.push(`<line x1="${padL + plotW / 2}" y1="${padT}" x2="${padL + plotW / 2}" y2="${padT + plotH}" class="grid-mid"/>`);
    parts.push(`<line x1="${padL}" y1="${padT + plotH / 2}" x2="${padL + plotW}" y2="${padT + plotH / 2}" class="grid-mid"/>`);
    // quadrant labels
    parts.push(`<text x="${padL + 10}" y="${padT + 20}" class="quad-label">Quick wins</text>`);
    parts.push(`<text x="${padL + plotW - 10}" y="${padT + 20}" class="quad-label" text-anchor="end">Big bets</text>`);
    parts.push(`<text x="${padL + 10}" y="${padT + plotH - 8}" class="quad-label">Fill-ins</text>`);
    parts.push(`<text x="${padL + plotW - 10}" y="${padT + plotH - 8}" class="quad-label" text-anchor="end">Time sinks</text>`);
    // axis labels
    parts.push(`<text x="${padL + plotW / 2}" y="${H - 14}" class="axis-label" text-anchor="middle">Effort →</text>`);
    parts.push(`<text x="16" y="${padT + plotH / 2}" class="axis-label" text-anchor="middle" transform="rotate(-90 16 ${padT + plotH / 2})">Impact →</text>`);

    const colors = { 1: "#4ea8ff", 2: "#ffb340", 3: "#46e0a0" };
    const nodes = activeTasks();
    nodes.forEach((t) => {
      // deterministic jitter so overlapping tasks fan out a little
      let h = 0; for (const c of t.id) h = (h * 31 + c.charCodeAt(0)) & 0xffff;
      const jx = ((h % 20) - 10), jy = (((h >> 5) % 20) - 10);
      const cx = Math.max(gx0 - 10, Math.min(gx1 + 10, xFor(t.effort) + jx));
      const cy = Math.max(gy0 - 10, Math.min(gy1 + 10, yFor(t.impact) + jy));
      parts.push(
        `<circle class="node" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="9" ` +
        `fill="${colors[t.impact]}" fill-opacity="0.85" stroke="${colors[t.impact]}" ` +
        `data-title="${escapeHtml(t.title)}" data-id="${t.id}"/>`
      );
    });
    svg.innerHTML = parts.join("");

    const tip = $("#matrix-tip");
    svg.querySelectorAll(".node").forEach((node) => {
      node.addEventListener("mouseenter", (e) => {
        const r = svg.getBoundingClientRect(), wrap = svg.parentElement.getBoundingClientRect();
        const cx = +node.getAttribute("cx"), cy = +node.getAttribute("cy");
        tip.textContent = node.dataset.title;
        tip.style.left = (r.left - wrap.left + (cx / W) * r.width) + "px";
        tip.style.top = (r.top - wrap.top + (cy / H) * r.height) + "px";
        tip.hidden = false;
      });
      node.addEventListener("mouseleave", () => { tip.hidden = true; });
      node.addEventListener("click", () => { focusTaskId = node.dataset.id; switchTab("now"); });
    });
  }

  function sessionsOn(dayKey) {
    return state.sessions.filter((ts) => todayKey(new Date(ts)) === dayKey).length;
  }
  function computeStreak() {
    let streak = 0;
    const d = new Date();
    // allow today to be empty without breaking a streak earned through yesterday
    if (sessionsOn(todayKey(d)) === 0) d.setDate(d.getDate() - 1);
    while (sessionsOn(todayKey(d)) > 0) { streak++; d.setDate(d.getDate() - 1); }
    return streak;
  }

  function renderStreak() {
    $("#streak-count").textContent = computeStreak();
  }

  function renderMomentum() {
    $("#stat-today").textContent = sessionsOn(todayKey());
    $("#stat-total").textContent = state.sessions.length;
    $("#stat-done").textContent = state.stats.tasksCompleted;

    // 7-day bars
    const bars = $("#bars");
    bars.innerHTML = "";
    const days = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date(); d.setDate(d.getDate() - i);
      days.push({ key: todayKey(d), label: d.toLocaleDateString(undefined, { weekday: "short" })[0] });
    }
    const counts = days.map((d) => sessionsOn(d.key));
    const max = Math.max(1, ...counts);
    days.forEach((d, i) => {
      const col = document.createElement("div");
      col.className = "bar-col";
      const pct = (counts[i] / max) * 100;
      col.innerHTML = `
        <div class="bar" style="height:${counts[i] ? Math.max(6, pct) : 0}%">
          ${counts[i] ? `<span class="bar-val">${counts[i]}</span>` : ""}
        </div>
        <div class="bar-day">${d.label}</div>`;
      bars.appendChild(col);
    });

    renderEnergySpark();
  }

  function renderEnergySpark() {
    const svg = $("#energy-spark");
    const today = todayKey();
    const pts = state.energyLog.filter((e) => todayKey(new Date(e.t)) === today);
    const hint = $("#energy-hint");
    if (pts.length === 0) {
      svg.innerHTML = "";
      hint.classList.remove("hidden");
      return;
    }
    hint.classList.add("hidden");
    const W = 480, H = 90, pad = 16;
    const xFor = (i) => pad + (pts.length === 1 ? (W - 2 * pad) / 2 : (i / (pts.length - 1)) * (W - 2 * pad));
    const yFor = (lvl) => H - pad - ((lvl - 1) / 2) * (H - 2 * pad);
    const colors = { 1: "#4ea8ff", 2: "#ffb340", 3: "#46e0a0" };
    let path = "";
    pts.forEach((p, i) => { path += (i ? "L" : "M") + xFor(i).toFixed(1) + " " + yFor(p.level).toFixed(1) + " "; });
    const dots = pts.map((p, i) =>
      `<circle cx="${xFor(i).toFixed(1)}" cy="${yFor(p.level).toFixed(1)}" r="4" fill="${colors[p.level]}"/>`
    ).join("");
    svg.innerHTML =
      `<path d="${path}" fill="none" stroke="#7c8cff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>${dots}`;
  }

  function renderCounts() {
    $("#tab-count").textContent = activeTasks().length;
  }

  function renderAll() {
    renderEnergyButtons();
    renderCounts();
    renderStreak();
    renderNow();
    renderTasks();
    renderMatrix();
    renderMomentum();
    renderTimer();
  }

  // ---------- Tabs ----------
  function switchTab(name) {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
    document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === "panel-" + name));
    if (name === "matrix") renderMatrix();
  }

  // ---------- Events ----------
  function bind() {
    $("#task-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const input = $("#task-input");
      if (!input.value.trim()) return;
      addTask(input.value, $("#task-impact").value, $("#task-effort").value, $("#task-due").value);
      input.value = ""; $("#task-due").value = ""; input.focus();
    });

    document.querySelectorAll(".energy-btn").forEach((b) =>
      b.addEventListener("click", () => setEnergy(+b.dataset.energy)));

    document.querySelectorAll(".tab").forEach((t) =>
      t.addEventListener("click", () => switchTab(t.dataset.tab)));

    document.querySelectorAll(".chip-btn").forEach((b) =>
      b.addEventListener("click", () => {
        taskFilter = b.dataset.filter;
        document.querySelectorAll(".chip-btn").forEach((x) => x.classList.toggle("active", x === b));
        renderTasks();
      }));

    document.querySelectorAll(".preset").forEach((p) =>
      p.addEventListener("click", () => {
        document.querySelectorAll(".preset").forEach((x) => x.classList.toggle("active", x === p));
        timer.setMinutes(+p.dataset.min);
      }));

    $("#timer-toggle").addEventListener("click", () => timer.running ? timer.pause() : timer.start());
    $("#timer-reset").addEventListener("click", () => timer.reset());
  }

  // ---------- First run ----------
  function seed() {
    if (state.tasks.length === 0 && localStorage.getItem(KEY) === null) {
      addTask("Outline the Q3 strategy memo", 3, 3, null);       // big bet
      addTask("Reply to the two blocking emails", 3, 1, todayKey()); // quick win
      addTask("Tidy the shared drive folders", 1, 2, null);      // fill-in
    }
  }

  // Small automation surface (used by tests / power users).
  window.__cadence = {
    get state() { return state; },
    fitScore, ranked, computeStreak,
    completeFocusSession() { timer.complete(); },
    setEnergy,
  };

  // ---------- Boot ----------
  document.querySelector(".preset[data-min='25']").classList.add("active");
  bind();
  seed();
  renderAll();
})();
