/* TaskFlow — a minimal task manager MVP.
   State persists to localStorage; no backend, no build step. */

(function () {
  "use strict";

  const STORAGE_KEY = "taskflow.tasks.v1";

  /** @type {{id:string,title:string,priority:string,due:string|null,done:boolean,createdAt:number}[]} */
  let tasks = load();
  let filter = "all";

  // Elements
  const form = document.getElementById("task-form");
  const input = document.getElementById("task-input");
  const priority = document.getElementById("task-priority");
  const due = document.getElementById("task-due");
  const list = document.getElementById("task-list");
  const emptyState = document.getElementById("empty-state");
  const viewTitle = document.getElementById("view-title");
  const viewSub = document.getElementById("view-sub");
  const progressFill = document.getElementById("progress-fill");
  const progressPct = document.getElementById("progress-pct");
  const filterButtons = Array.from(document.querySelectorAll(".filter-btn"));

  const VIEW_META = {
    all: { title: "Inbox", sub: "Everything on your plate" },
    today: { title: "Today", sub: "Due today or overdue" },
    active: { title: "Active", sub: "Still to do" },
    completed: { title: "Completed", sub: "Nice work" },
  };

  // --- Persistence ---
  function load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      console.warn("Could not read saved tasks:", e);
      return [];
    }
  }

  function save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
    } catch (e) {
      console.warn("Could not save tasks:", e);
    }
  }

  // --- Helpers ---
  function uid() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  }

  function todayStr() {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 10);
  }

  function isOverdue(task) {
    return !task.done && task.due && task.due < todayStr();
  }

  function isDueToday(task) {
    return task.due && task.due <= todayStr();
  }

  function matchesFilter(task) {
    switch (filter) {
      case "active": return !task.done;
      case "completed": return task.done;
      case "today": return !task.done && isDueToday(task);
      default: return true;
    }
  }

  function formatDue(dateStr) {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  const PRIORITY_RANK = { high: 0, medium: 1, low: 2 };

  function sortTasks(a, b) {
    if (a.done !== b.done) return a.done ? 1 : -1;
    const pr = PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority];
    if (pr !== 0) return pr;
    return a.createdAt - b.createdAt;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  // --- Actions ---
  function addTask(title, prio, dueDate) {
    tasks.push({
      id: uid(),
      title: title.trim(),
      priority: prio,
      due: dueDate || null,
      done: false,
      createdAt: Date.now(),
    });
    save();
    render();
  }

  function toggleTask(id) {
    const t = tasks.find((t) => t.id === id);
    if (t) { t.done = !t.done; save(); render(); }
  }

  function deleteTask(id) {
    tasks = tasks.filter((t) => t.id !== id);
    save();
    render();
  }

  // --- Rendering ---
  function updateCounts() {
    const counts = {
      all: tasks.length,
      active: tasks.filter((t) => !t.done).length,
      completed: tasks.filter((t) => t.done).length,
      today: tasks.filter((t) => !t.done && isDueToday(t)).length,
    };
    document.querySelectorAll(".count").forEach((el) => {
      el.textContent = counts[el.dataset.count] ?? 0;
    });

    const total = tasks.length;
    const done = counts.completed;
    const pct = total ? Math.round((done / total) * 100) : 0;
    progressFill.style.width = pct + "%";
    progressPct.textContent = pct + "%";
  }

  function render() {
    updateCounts();

    const meta = VIEW_META[filter];
    viewTitle.textContent = meta.title;
    viewSub.textContent = meta.sub;

    const visible = tasks.filter(matchesFilter).sort(sortTasks);
    list.innerHTML = "";

    if (visible.length === 0) {
      emptyState.classList.remove("hidden");
      return;
    }
    emptyState.classList.add("hidden");

    for (const task of visible) {
      const li = document.createElement("li");
      li.className = "task-item" + (task.done ? " completed" : "");

      const dueHtml = task.due
        ? `<span class="due ${isOverdue(task) ? "overdue" : ""}">📅 ${formatDue(task.due)}</span>`
        : "";

      li.innerHTML = `
        <input type="checkbox" class="checkbox" ${task.done ? "checked" : ""}
               aria-label="Mark complete" />
        <div class="task-body">
          <div class="task-title">${escapeHtml(task.title)}</div>
          <div class="task-meta">
            <span class="badge ${task.priority}">${task.priority}</span>
            ${dueHtml}
          </div>
        </div>
        <button class="delete-btn" aria-label="Delete task">✕</button>
      `;

      li.querySelector(".checkbox").addEventListener("change", () => toggleTask(task.id));
      li.querySelector(".delete-btn").addEventListener("click", () => deleteTask(task.id));
      list.appendChild(li);
    }
  }

  // --- Events ---
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const title = input.value.trim();
    if (!title) return;
    addTask(title, priority.value, due.value);
    input.value = "";
    due.value = "";
    input.focus();
  });

  filterButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      filter = btn.dataset.filter;
      filterButtons.forEach((b) => b.classList.toggle("active", b === btn));
      render();
    });
  });

  // Seed a couple of example tasks on first ever run.
  if (tasks.length === 0 && localStorage.getItem(STORAGE_KEY) === null) {
    addTask("Welcome to TaskFlow — click the circle to complete a task", "medium", todayStr());
    addTask("Add your first real task above", "high", null);
  } else {
    render();
  }
})();
