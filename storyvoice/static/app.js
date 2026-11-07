const $ = (s) => document.querySelector(s);
const MOOD_COLORS = {calm:"#5aa9e6", joyful:"#ffd166", sad:"#6c7a99", suspense:"#ef8354", horror:"#b5172b",
  romantic:"#ff7eb6", epic:"#c77dff", mystery:"#3d5a80", inspirational:"#38d2b4", whimsical:"#a7e163", informative:"#9aa1b2"};
const state = { item: null };

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 2600); }
async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || r.statusText);
  return data;
}
const postJSON = (path, body) => api(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
async function pollJob(id, onTick) {
  for (;;) {
    const j = await api(`/api/jobs/${id}`);
    onTick?.(j);
    if (j.status === "done") return j.result;
    if (j.status === "error") throw new Error(j.error);
    await new Promise((r) => setTimeout(r, 1200));
  }
}
function status(el, msg, err = false) { el.textContent = msg; el.classList.toggle("err", err); }
function showTab(name) {
  document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === name));
  if (name === "library") loadLibrary();
}
document.querySelectorAll("nav button").forEach((b) => b.onclick = () => showTab(b.dataset.tab));

/* ---------- Find PDFs ---------- */
function renderResults(results) {
  const box = $("#findResults");
  if (!results.length) { box.innerHTML = `<div class="card muted">No results. Try another search or page.</div>`; return; }
  box.innerHTML = "";
  results.forEach((r) => {
    const el = document.createElement("div");
    el.className = "item";
    el.innerHTML = `<div><div class="t">${esc(r.title)}</div>
      <div class="s"><span class="tag">${esc(r.source)}</span>${esc(r.author || "")} ${esc(r.year || "")}
      ${r.page ? `· <a href="${esc(r.page)}" target="_blank" rel="noopener">view page</a>` : ""}</div></div>
      <div class="acts"><button>⬇ Save to library</button></div>`;
    el.querySelector("button").onclick = async (e) => {
      const btn = e.target; btn.disabled = true; btn.textContent = "Downloading…";
      try {
        const item = await postJSON("/api/pdf/download", {url: r.url || r.resolve || "", text_url: r.text_url || "", title: r.title});
        btn.textContent = "✓ Saved"; toast(`Saved “${item.title}”`);
        const go = document.createElement("button"); go.className = "primary"; go.textContent = "🔊 Listen";
        go.onclick = () => openForListening(item.id); btn.after(go);
      } catch (err) { btn.disabled = false; btn.textContent = "Retry"; toast(err.message); }
    };
    box.appendChild(el);
  });
}
$("#searchForm").onsubmit = async (e) => {
  e.preventDefault(); $("#findResults").innerHTML = `<div class="card muted">Searching…</div>`;
  try { renderResults((await api(`/api/pdf/search?q=${encodeURIComponent($("#searchQ").value)}`)).results); }
  catch (err) { $("#findResults").innerHTML = `<div class="card status err">${esc(err.message)}</div>`; }
};
$("#scanForm").onsubmit = async (e) => {
  e.preventDefault(); $("#findResults").innerHTML = `<div class="card muted">Scanning page…</div>`;
  try { renderResults((await api(`/api/pdf/scan?url=${encodeURIComponent($("#scanUrl").value)}`)).results); }
  catch (err) { $("#findResults").innerHTML = `<div class="card status err">${esc(err.message)}</div>`; }
};
$("#pdfUpload").onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return;
  const fd = new FormData(); fd.append("file", f);
  try { const item = await api("/api/pdf/upload", {method: "POST", body: fd}); toast(`Added “${item.title}”`); openForListening(item.id); }
  catch (err) { toast(err.message); }
};

/* ---------- Video -> script ---------- */
let videoItem = null;
$("#videoForm").onsubmit = async (e) => {
  e.preventDefault();
  const st = $("#videoStatus"), fd = new FormData();
  fd.append("url", $("#videoUrl").value.trim()); fd.append("language", $("#videoLang").value);
  if ($("#videoFile").files[0]) fd.append("file", $("#videoFile").files[0]);
  const btn = e.submitter; btn.disabled = true;
  try {
    status(st, "Uploading…");
    const {job} = await api("/api/video/transcribe", {method: "POST", body: fd});
    const res = await pollJob(job, (j) => status(st, j.message));
    videoItem = res.item;
    $("#videoTitle").textContent = res.title; $("#videoScript").value = res.script;
    $("#videoOut").classList.remove("hidden");
    status(st, `✓ Script ready (${res.method === "captions" ? "from captions" : "AI transcription"}) — saved to library.`);
  } catch (err) { status(st, err.message, true); }
  btn.disabled = false;
};
$("#videoSave").onclick = async () => {
  await api(`/api/library/${videoItem.id}/text`, {method: "PUT", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({title: $("#videoTitle").textContent, text: $("#videoScript").value})});
  toast("Saved");
};
$("#videoListen").onclick = async () => { await $("#videoSave").onclick(); openForListening(videoItem.id); };

/* ---------- Library ---------- */
async function loadLibrary() {
  const {items} = await api("/api/library"), box = $("#libList");
  box.innerHTML = items.length ? "" : `<div class="card muted">Your library is empty — find a PDF, convert a video or paste a script.</div>`;
  const icon = {pdf: "📕", book: "📗", transcript: "🎬", script: "📝"};
  items.forEach((it) => {
    const el = document.createElement("div"); el.className = "item";
    const m = it.meta || {};
    el.innerHTML = `<div><div class="t">${icon[it.kind] || "📄"} ${esc(it.title)}</div>
      <div class="s"><span class="tag">${esc(it.kind)}</span>${m.pages ? m.pages + " pages · " : ""}${new Date(it.created * 1000).toLocaleDateString()}</div></div>
      <div class="acts">${it.file ? `<a class="button" href="/api/library/${it.id}/file">PDF</a>` : ""}
      <button class="primary" data-a="listen">🔊 Listen</button><button data-a="del">🗑</button></div>`;
    el.querySelector('[data-a="listen"]').onclick = () => openForListening(it.id);
    el.querySelector('[data-a="del"]').onclick = async () => { if (confirm(`Delete “${it.title}”?`)) { await api(`/api/library/${it.id}`, {method: "DELETE"}); loadLibrary(); } };
    box.appendChild(el);
  });
}
$("#scriptSave").onclick = async () => {
  if (!$("#scriptText").value.trim()) return toast("Write something first");
  const item = await postJSON("/api/library/script", {title: $("#scriptTitle").value || "My script", text: $("#scriptText").value});
  toast("Saved"); loadLibrary(); return item;
};
$("#scriptListen").onclick = async () => { const item = await $("#scriptSave").onclick(); if (item) openForListening(item.id); };

/* ---------- Listen ---------- */
async function openForListening(id) {
  const it = await api(`/api/library/${id}`);
  state.item = it;
  $("#listenTitle").textContent = it.title;
  const pages = it.text.split("\f");
  const words = it.text.split(/\s+/).filter(Boolean).length;
  $("#listenInfo").textContent = `${words.toLocaleString()} words · about ${Math.max(1, Math.round(words / 150))} min of listening`;
  $("#pageRange").classList.toggle("hidden", pages.length < 2);
  $("#listenText").classList.toggle("hidden", pages.length >= 2);
  if (pages.length >= 2) {
    $("#pageFrom").value = 1; $("#pageFrom").max = $("#pageTo").max = pages.length;
    $("#pageTo").value = Math.min(pages.length, 5);
    $("#pageCount").textContent = `of ${pages.length} — long books take a while, start with a few pages`;
  } else $("#listenText").value = it.text;
  $("#analysis").textContent = ""; showTab("listen");
}
function narrBody() {
  const paged = state.item && !$("#pageRange").classList.contains("hidden");
  return {
    text: paged ? "" : $("#listenText").value,
    item_id: paged ? state.item.id : "",
    page_from: paged ? +$("#pageFrom").value : 0, page_to: paged ? +$("#pageTo").value : 0,
    accent: $("#accent").value, gender: $("#gender").value, genre: $("#genre").value, mood: $("#moodSel").value,
    speed: +$("#speed").value, music: $("#musicOn").checked, music_volume: $("#musicVol").value / 100,
  };
}
$("#listenText").oninput = () => { if (!$("#pageRange").classList.contains("hidden")) return; state.item = null; };
$("#speed").oninput = (e) => $("#speedV").textContent = `${e.target.value > 0 ? "+" : ""}${e.target.value}%`;
$("#musicVol").oninput = (e) => { $("#musicV").textContent = `${e.target.value}%`; $("#musicPreview").volume = Math.min(1, e.target.value / 50); };
$("#analyseBtn").onclick = async () => {
  try {
    const a = await postJSON("/api/analyse", narrBody());
    const moods = Object.entries(a.moods).sort((x, y) => y[1] - x[1]).map(([m, n]) => `${m} ×${n}`).join(", ");
    status($("#analysis"), `Genre: ${a.genre} · Language: ${a.language} · Moods: ${moods} · ~${a.est_minutes} min (${a.engine === "claude" ? "AI" : "offline"} analysis)`);
  } catch (err) { status($("#analysis"), err.message, true); }
};
$("#previewMusic").onclick = async () => {
  const p = $("#musicPreview");
  if (!p.paused) { p.pause(); $("#previewMusic").textContent = "▶ Preview music"; return; }
  let m = $("#moodSel").value;
  if (!m) { try { const a = await postJSON("/api/analyse", narrBody()); m = Object.entries(a.moods).sort((x, y) => y[1] - x[1])[0][0]; } catch { m = "calm"; } }
  p.src = `/api/music/${m}.wav?seconds=30`; p.loop = true; p.volume = Math.min(1, $("#musicVol").value / 50); p.play();
  $("#previewMusic").textContent = `⏸ ${m} music`;
};
$("#narrateBtn").onclick = async () => {
  const btn = $("#narrateBtn"), st = $("#narrStatus"), bar = $("#narrBar");
  btn.disabled = true; bar.classList.remove("hidden"); $("#musicPreview").pause();
  try {
    const {job} = await postJSON("/api/narrate", narrBody());
    const res = await pollJob(job, (j) => { status(st, j.message); bar.firstElementChild.style.width = `${j.progress * 100}%`; });
    status(st, `✓ ${Math.round(res.duration / 60 * 10) / 10} min of audio · genre: ${res.genre}`);
    showPlayer(res);
  } catch (err) { status(st, err.message, true); }
  btn.disabled = false; setTimeout(() => bar.classList.add("hidden"), 800);
};
function showPlayer(res) {
  $("#player").classList.remove("hidden");
  const audio = $("#audio"); audio.src = res.audio; $("#dl").href = res.audio;
  $("#dl").download = `${($("#listenTitle").textContent || "story").slice(0, 60)}.mp3`;
  const voices = [...new Set(res.timeline.map((t) => t.voice))].join(", ");
  $("#playerInfo").textContent = `Voices: ${voices}${res.timeline[0]?.engine === "espeak" ? " (offline voice — connect to internet for natural voices)" : ""}`;
  const strip = $("#moodStrip"), follow = $("#follow");
  strip.innerHTML = ""; follow.innerHTML = "";
  res.timeline.forEach((seg) => {
    const d = document.createElement("div");
    d.style.flex = seg.end - seg.start; d.style.background = MOOD_COLORS[seg.mood] || "#888"; d.title = seg.mood;
    d.onclick = () => { audio.currentTime = seg.start; audio.play(); };
    strip.appendChild(d);
    const p = document.createElement("p");
    p.innerHTML = `<span class="m" style="color:${MOOD_COLORS[seg.mood]}">${seg.mood}</span>${esc(seg.text)}`;
    p.onclick = d.onclick; follow.appendChild(p);
  });
  let last = -1;
  audio.ontimeupdate = () => {
    const i = res.timeline.findIndex((s) => audio.currentTime >= s.start && audio.currentTime < s.end);
    if (i === last || i < 0) return;
    follow.children[last]?.classList.remove("now"); follow.children[i].classList.add("now");
    follow.children[i].scrollIntoView({block: "nearest", behavior: "smooth"}); last = i;
  };
  audio.play().catch(() => {});
}

/* ---------- init ---------- */
api("/api/meta").then((m) => {
  m.genres.forEach((g) => $("#genre").insertAdjacentHTML("beforeend", `<option value="${g}">${g}</option>`));
  m.moods.forEach((x) => $("#moodSel").insertAdjacentHTML("beforeend", `<option value="${x}">${x}</option>`));
});
