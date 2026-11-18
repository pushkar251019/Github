'use strict';
// SweepGuard: browser-only counter-surveillance toolkit. No data leaves the device.

const $ = id => document.getElementById(id);
const stops = {}; // tab -> stop function for active sensors

// ---------- Tabs ----------
$('tabs').addEventListener('click', e => {
  const t = e.target.dataset.t; if (!t) return;
  document.querySelectorAll('nav button').forEach(b => b.classList.toggle('on', b.dataset.t === t));
  document.querySelectorAll('section').forEach(s => s.classList.toggle('on', s.id === t));
  // Stop camera users when leaving their tab (only one camera at a time on most phones)
  for (const k of ['lens', 'ir']) if (k !== t && stops[k]) { stops[k](); delete stops[k]; }
});

function fitCanvas(c) {
  const dpr = devicePixelRatio || 1, w = c.clientWidth, h = c.clientHeight || +c.getAttribute('height');
  if (c.width !== Math.round(w * dpr)) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); }
  const g = c.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); return [g, w, h];
}

// ---------- Support matrix ----------
(function support() {
  const rows = [
    ['Secure context (HTTPS)', window.isSecureContext],
    ['Magnetometer sensor', 'Magnetometer' in window],
    ['Camera', !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)],
    ['Microphone', !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)],
    ['Bluetooth (pick device)', !!navigator.bluetooth],
    ['Bluetooth (live scan)', !!(navigator.bluetooth && navigator.bluetooth.requestLEScan)],
  ];
  $('support').innerHTML = rows.map(([n, ok]) =>
    `<div class="dev"><span>${n}</span><span class="pill ${ok ? 'ok' : 'warn'}">${ok ? 'available' : 'not available'}</span></div>`).join('') +
    `<p class="unit" style="margin-top:8px">Works best in <b>Chrome on Android</b>. iPhone Safari supports the camera and microphone tools only, because Apple blocks web access to the magnetometer and Bluetooth. Live Bluetooth scan needs <code>chrome://flags/#enable-experimental-web-platform-features</code> turned on.</p>`;
  if ('serviceWorker' in navigator && location.protocol.startsWith('http')) navigator.serviceWorker.register('sw.js').catch(() => {});
})();

// ---------- Magnetic detector ----------
(function magnetic() {
  let sensor, base = null, hist = [], ac, osc, gain, last = null;
  const status = $('magStatus');
  $('magStart').onclick = async () => {
    if (sensor) { stop(); return; }
    if (!('Magnetometer' in window)) { status.textContent = 'This browser has no magnetometer access. Use Chrome on Android, or a free native app such as "Physics Toolbox Magnetometer".'; return; }
    try {
      if (navigator.permissions) { const p = await navigator.permissions.query({ name: 'magnetometer' }).catch(() => null); if (p && p.state === 'denied') throw new Error('Permission denied'); }
      sensor = new Magnetometer({ frequency: 30 });
      sensor.onerror = e => { status.textContent = 'Sensor error: ' + (e.error && e.error.message || e.error); stop(); };
      sensor.onreading = () => {
        const tot = Math.hypot(sensor.x, sensor.y, sensor.z);
        const v = { x: sensor.x, y: sensor.y, z: sensor.z, tot };
        if (!base) base = v;
        last = v;
        const d = Math.hypot(v.x - base.x, v.y - base.y, v.z - base.z);
        update(d, tot);
      };
      sensor.start();
      $('magStart').textContent = 'Stop'; $('magCal').disabled = false;
      status.textContent = 'Reading… hold still away from metal and press Calibrate.';
    } catch (e) { status.textContent = 'Could not start the magnetometer: ' + e.message; sensor = null; }
  };
  $('magCal').onclick = () => { if (last) { base = last; hist = []; status.textContent = 'Zeroed. Now sweep slowly.'; } };
  function stop() { sensor && sensor.stop(); sensor = null; if (osc) { osc.stop(); osc = null; } $('magStart').textContent = 'Start'; $('magCal').disabled = true; }
  function update(d, tot) {
    $('magVal').textContent = d.toFixed(1);
    $('magTot').textContent = tot.toFixed(1);
    $('magBar').style.width = Math.min(100, d / 1.5) + '%';
    const lvl = d > 60 ? ['bad', 'STRONG source'] : d > 20 ? ['warn', 'Electronics nearby'] : ['ok', 'Normal'];
    $('magFlag').innerHTML = `<span class="pill ${lvl[0]}">${lvl[1]}</span>`;
    hist.push(d); if (hist.length > 200) hist.shift();
    draw(); tone(d);
  }
  function draw() {
    const [g, w, h] = fitCanvas($('magChart'));
    g.clearRect(0, 0, w, h);
    const max = Math.max(80, ...hist);
    g.strokeStyle = '#1f2a36'; [20, 60].forEach(y => { const yy = h - y / max * h; g.beginPath(); g.moveTo(0, yy); g.lineTo(w, yy); g.stroke(); });
    g.strokeStyle = '#22d3ee'; g.lineWidth = 2; g.beginPath();
    hist.forEach((v, i) => { const x = i / 199 * w, y = h - v / max * h; i ? g.lineTo(x, y) : g.moveTo(x, y); }); g.stroke();
  }
  function tone(d) {
    if (!$('magSound').checked || d < 8) { if (gain) gain.gain.value = 0; return; }
    if (!ac) ac = new (window.AudioContext || window.webkitAudioContext)();
    if (!osc) { osc = ac.createOscillator(); gain = ac.createGain(); osc.connect(gain).connect(ac.destination); osc.start(); }
    osc.frequency.value = 300 + Math.min(d, 200) * 8; gain.gain.value = 0.08;
  }
})();

// ---------- Glint detector (shared by lens + IR) ----------
// Finds small, isolated, very bright spots that persist across frames.
function glintDetector({ video, overlay, status, sensitivity, preferPurple }) {
  const work = document.createElement('canvas'), wg = work.getContext('2d', { willReadFrequently: true });
  let heat = null, raf, W = 0, H = 0;
  function frame() {
    raf = requestAnimationFrame(frame);
    if (video.readyState < 2) return;
    const vw = video.videoWidth, vh = video.videoHeight; if (!vw) return;
    // Sample at 576px wide, then max-pool 3x3 down to 192px so tiny glints survive.
    const SW = 576, SH = Math.round(576 * vh / vw) - (Math.round(576 * vh / vw) % 3);
    W = SW / 3; H = SH / 3;
    if (work.width !== SW || work.height !== SH) { work.width = SW; work.height = SH; heat = new Float32Array(W * H); }
    wg.drawImage(video, 0, 0, SW, SH);
    const src = wg.getImageData(0, 0, SW, SH).data;
    const px = new Uint8ClampedArray(W * H * 4), lum = new Float32Array(W * H);
    let mean = 0;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      let best = -1, bo = 0;
      for (let dy = 0; dy < 3; dy++) for (let dx = 0; dx < 3; dx++) {
        const o = ((y * 3 + dy) * SW + x * 3 + dx) * 4, l = 0.299 * src[o] + 0.587 * src[o + 1] + 0.114 * src[o + 2];
        if (l > best) { best = l; bo = o; }
      }
      const i = y * W + x; lum[i] = best; mean += best;
      px[i * 4] = src[bo]; px[i * 4 + 1] = src[bo + 1]; px[i * 4 + 2] = src[bo + 2];
    }
    mean /= W * H;
    const thr = sensitivity();
    const seen = new Uint8Array(W * H), blobs = [];
    for (let y = 2; y < H - 2; y++) for (let x = 2; x < W - 2; x++) {
      const i = y * W + x; if (seen[i] || lum[i] < thr) continue;
      // flood fill this bright region
      const stack = [i]; seen[i] = 1; let n = 0, sx = 0, sy = 0, sr = 0, sg = 0, sb = 0;
      while (stack.length) {
        const j = stack.pop(), jx = j % W, jy = (j / W) | 0; n++; sx += jx; sy += jy;
        sr += px[j * 4]; sg += px[j * 4 + 1]; sb += px[j * 4 + 2];
        for (const k of [j - 1, j + 1, j - W, j + W]) if (k >= 0 && k < W * H && !seen[k] && lum[k] >= thr) { seen[k] = 1; stack.push(k); }
        if (n > 60) break;
      }
      if (n > 40) continue; // too big: a lamp, window or white surface, not a lens
      const cx = Math.round(sx / n), cy = Math.round(sy / n);
      // isolation: the ring around the spot must be much darker
      let ring = 0, rc = 0; const R = Math.max(4, Math.ceil(Math.sqrt(n)) + 3);
      for (let a = 0; a < 16; a++) { const rx = cx + Math.round(R * Math.cos(a * Math.PI / 8)), ry = cy + Math.round(R * Math.sin(a * Math.PI / 8)); if (rx >= 0 && ry >= 0 && rx < W && ry < H) { ring += lum[ry * W + rx]; rc++; } }
      ring /= rc || 1;
      if (ring > thr - 70) continue;
      const purple = (sb / n) > (sg / n) + 15;
      blobs.push({ cx, cy, n, purple });
    }
    for (let i = 0; i < heat.length; i++) heat[i] *= 0.85;
    for (const b of blobs) heat[b.cy * W + b.cx] += preferPurple && !b.purple ? 0.5 : 1;
    // draw
    overlay.width = video.clientWidth; overlay.height = video.clientHeight;
    const og = overlay.getContext('2d'), s = overlay.width / W;
    og.clearRect(0, 0, overlay.width, overlay.height);
    let hits = 0;
    for (const b of blobs) {
      // accumulate heat in a 3x3 neighbourhood to tolerate hand shake
      let hsum = 0; for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) { const k = (b.cy + dy) * W + b.cx + dx; if (k >= 0 && k < heat.length) hsum += heat[k]; }
      if (hsum < 2.2) continue; hits++;
      og.strokeStyle = b.purple ? '#d946ef' : '#f43f5e'; og.lineWidth = 3;
      og.beginPath(); og.arc((b.cx + 0.5) * s, (b.cy + 0.5) * s, Math.max(14, Math.sqrt(b.n) * s * 1.5), 0, 7); og.stroke();
    }
    status.innerHTML = hits ? `<span class="pill bad">${hits} candidate${hits > 1 ? 's' : ''}</span> Move closer and change angle: a lens keeps glinting.` :
      (mean > 90 ? 'Too bright. Dim the room lights for best results.' : 'Scanning… no steady glints yet.');
  }
  frame();
  return () => cancelAnimationFrame(raf);
}

async function openCamera(facing) {
  return navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: facing }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
}

// ---------- Lens finder ----------
(function lens() {
  let stream, torchOn = false;
  const status = $('lensStatus'), video = $('lensVid');
  $('lensStart').onclick = async () => {
    if (stops.lens) { stops.lens(); delete stops.lens; return; }
    try {
      stream = await openCamera('environment');
      video.srcObject = stream; await video.play();
      const track = stream.getVideoTracks()[0];
      const caps = track.getCapabilities ? track.getCapabilities() : {};
      $('lensTorch').disabled = !caps.torch;
      if (caps.torch) { await track.applyConstraints({ advanced: [{ torch: true }] }).catch(() => {}); torchOn = true; }
      else status.textContent = 'No flashlight control in this browser. Hold another light right next to the camera.';
      const stopDet = glintDetector({ video, overlay: $('lensOv'), status, sensitivity: () => +$('lensSens').value });
      $('lensStart').textContent = 'Stop';
      stops.lens = () => { stopDet(); stream.getTracks().forEach(t => t.stop()); video.srcObject = null; $('lensStart').textContent = 'Start scan'; $('lensTorch').disabled = true; $('lensOv').getContext('2d').clearRect(0, 0, 9999, 9999); };
    } catch (e) { status.textContent = 'Camera unavailable: ' + e.message; }
  };
  $('lensTorch').onclick = () => {
    const t = stream && stream.getVideoTracks()[0]; if (!t) return;
    torchOn = !torchOn; t.applyConstraints({ advanced: [{ torch: torchOn }] }).catch(() => {});
  };
})();

// ---------- IR check ----------
(function ir() {
  const status = $('irStatus'), video = $('irVid');
  async function start(facing) {
    if (stops.ir) { stops.ir(); delete stops.ir; }
    try {
      const stream = await openCamera(facing);
      video.srcObject = stream; await video.play();
      const stopDet = glintDetector({ video, overlay: $('irOv'), status, sensitivity: () => 225, preferPurple: true });
      stops.ir = () => { stopDet(); stream.getTracks().forEach(t => t.stop()); video.srcObject = null; };
    } catch (e) { status.textContent = 'Camera unavailable: ' + e.message; }
  }
  $('irFront').onclick = () => start('user');
  $('irBack').onclick = () => start('environment');
})();

// ---------- Bluetooth ----------
(function ble() {
  const status = $('bleStatus'), list = $('bleList'), devs = new Map();
  let scan = null, handler = null;
  const u16 = s => (typeof s === 'string' && /^0000([0-9a-f]{4})-0000-1000-8000-00805f9b34fb$/i.test(s)) ? s.slice(4, 8).toLowerCase() : String(s).toLowerCase();
  const COMPANY = { 0x004c: 'Apple', 0x0075: 'Samsung', 0x00e0: 'Google', 0x0006: 'Microsoft', 0x0157: 'Huami', 0x038f: 'Xiaomi', 0x02e5: 'Espressif (ESP32 chip)', 0x0059: 'Nordic Semiconductor' };

  function classify(d) {
    const svc = [...d.uuids].map(u16);
    if (d.mfr.has(0x004c)) {
      const first = d.mfr.get(0x004c)[0];
      if (first === 0x12) return ['bad', 'Apple Find My item (AirTag or tracker)'];
      return ['', 'Apple device'];
    }
    if (svc.includes('fd5a')) return ['bad', 'Samsung SmartTag'];
    if (svc.includes('feed') || svc.includes('feec')) return ['bad', 'Tile tracker'];
    if (svc.includes('fe33') || svc.includes('fe65')) return ['bad', 'Chipolo tracker'];
    if (svc.includes('feaa')) return ['warn', 'Beacon / Google Find My Device network'];
    if (svc.includes('fe2c')) return ['', 'Google Fast Pair device'];
    if (d.mfr.has(0x02e5) || d.mfr.has(0x0059)) return ['warn', 'DIY/dev-board chip (common in homemade bugs)'];
    for (const id of d.mfr.keys()) if (COMPANY[id]) return ['', COMPANY[id] + ' device'];
    if (!d.name) return ['warn', 'Unnamed device'];
    return ['', 'Bluetooth device'];
  }
  function render() {
    const arr = [...devs.values()].sort((a, b) => (b.rssi ?? -999) - (a.rssi ?? -999));
    list.innerHTML = arr.map(d => {
      const [lvl, kind] = classify(d), r = d.rssi;
      const dist = r == null ? '' : r > -55 ? 'very close' : r > -70 ? 'in this room' : r > -85 ? 'nearby' : 'far';
      return `<div class="dev"><div><b>${esc(d.name || '(no name)')}</b><small>${kind} · seen ${d.count}×</small></div><div style="text-align:right"><span class="pill ${lvl}">${r == null ? '--' : r + ' dBm'}</span><br><small>${dist}</small></div></div>`;
    }).join('') || '<p class="unit">No devices yet…</p>';
    const flagged = arr.filter(d => classify(d)[0] === 'bad').length;
    status.innerHTML = `${arr.length} devices` + (flagged ? ` · <span class="pill bad">${flagged} tracker${flagged > 1 ? 's' : ''}</span>` : '');
  }
  const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  $('bleScan').onclick = async () => {
    if (!navigator.bluetooth) { status.textContent = 'Web Bluetooth isn’t available here (iPhone browsers and Firefox don’t have it). Use the built-in tracker scans listed below.'; return; }
    if (!navigator.bluetooth.requestLEScan) { status.innerHTML = 'Live scan needs Chrome with <code>chrome://flags/#enable-experimental-web-platform-features</code> turned on. Or use <b>Pick a device</b>: the picker itself lists every nearby device.'; return; }
    try {
      scan = await navigator.bluetooth.requestLEScan({ acceptAllAdvertisements: true, keepRepeatedDevices: true });
      handler = ev => {
        const id = ev.device.id;
        const d = devs.get(id) || { name: '', uuids: new Set(), mfr: new Map(), count: 0 };
        d.name = ev.device.name || ev.name || d.name; d.rssi = ev.rssi; d.count++;
        (ev.uuids || []).forEach(u => d.uuids.add(u));
        if (ev.serviceData) ev.serviceData.forEach((_, k) => d.uuids.add(k));
        if (ev.manufacturerData) ev.manufacturerData.forEach((dv, k) => d.mfr.set(k, new Uint8Array(dv.buffer, dv.byteOffset, dv.byteLength)));
        devs.set(id, d);
      };
      navigator.bluetooth.addEventListener('advertisementreceived', handler);
      $('bleStop').disabled = false; $('bleScan').disabled = true;
      const t = setInterval(render, 700);
      $('bleStop').onclick = () => { scan.stop(); navigator.bluetooth.removeEventListener('advertisementreceived', handler); clearInterval(t); $('bleStop').disabled = true; $('bleScan').disabled = false; render(); };
      render();
    } catch (e) { status.textContent = 'Scan failed: ' + e.message; }
  };
  $('blePick').onclick = async () => {
    if (!navigator.bluetooth) { status.textContent = 'Web Bluetooth isn’t available in this browser.'; return; }
    try {
      status.textContent = 'The picker lists every nearby device. Look for names you don’t recognise.';
      const dev = await navigator.bluetooth.requestDevice({ acceptAllDevices: true });
      devs.set(dev.id, { name: dev.name || '', uuids: new Set(), mfr: new Map(), count: 1, rssi: null });
      render();
    } catch (e) { if (e.name !== 'NotFoundError') status.textContent = e.message; }
  };
})();

// ---------- RF buzz / ultrasonic ----------
(function audio() {
  let ac, an, buf, raf, stream, gsmHits = 0, usHits = 0;
  const status = $('audStatus');
  $('audStart').onclick = async () => {
    if (ac) { stop(); return; }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
      ac = new (window.AudioContext || window.webkitAudioContext)();
      an = ac.createAnalyser(); an.fftSize = 16384; an.smoothingTimeConstant = 0.5;
      ac.createMediaStreamSource(stream).connect(an);
      buf = new Float32Array(an.frequencyBinCount);
      $('audStart').textContent = 'Stop';
      status.textContent = `Listening at ${ac.sampleRate} Hz. Keep the room quiet.`;
      loop();
    } catch (e) { status.textContent = 'Microphone unavailable: ' + e.message; ac = null; }
  };
  function stop() { cancelAnimationFrame(raf); stream.getTracks().forEach(t => t.stop()); ac.close(); ac = null; $('audStart').textContent = 'Start listening'; }
  const bin = f => Math.round(f / (ac.sampleRate / an.fftSize));
  function peakAbove(f, halfWin = 40) {
    // dB of the peak near f minus the median of the surrounding band
    const c = bin(f), w = bin(halfWin), pk = Math.max(buf[c - 1], buf[c], buf[c + 1]);
    const side = []; for (let i = c - w; i <= c + w; i++) if (Math.abs(i - c) > 3) side.push(buf[i]);
    side.sort((a, b) => a - b); return pk - side[side.length >> 1];
  }
  function loop() {
    raf = requestAnimationFrame(loop);
    an.getFloatFrequencyData(buf);
    // GSM TDMA burst: 217 Hz fundamental with strong harmonics
    const h = [217, 434, 651, 868].map(f => peakAbove(f));
    const gsm = h.filter(x => x > 10).length >= 3;
    gsmHits = Math.max(0, Math.min(60, gsmHits + (gsm ? 2 : -1)));
    // Ultrasonic: narrow peak 18–21.5 kHz well above the band median
    let us = false, usFreq = 0;
    if (ac.sampleRate >= 44100) {
      const a = bin(18000), b = Math.min(buf.length - 2, bin(21500)), band = [];
      let best = -Infinity, bi = a;
      for (let i = a; i <= b; i++) { band.push(buf[i]); if (buf[i] > best) { best = buf[i]; bi = i; } }
      band.sort((x, y) => x - y);
      us = best - band[band.length >> 1] > 25 && best > -90; usFreq = bi * ac.sampleRate / an.fftSize;
    }
    usHits = Math.max(0, Math.min(60, usHits + (us ? 2 : -1)));
    const gf = $('gsmFlag'), uf = $('usFlag');
    gf.className = 'pill ' + (gsmHits > 20 ? 'bad' : gsmHits > 6 ? 'warn' : 'ok'); gf.textContent = gsmHits > 20 ? 'DETECTED' : gsmHits > 6 ? 'possible' : 'none';
    uf.className = 'pill ' + (usHits > 20 ? 'bad' : usHits > 6 ? 'warn' : 'ok'); uf.textContent = usHits > 20 ? (usFreq / 1000).toFixed(1) + ' kHz' : usHits > 6 ? 'possible' : 'none';
    draw();
  }
  function draw() {
    const [g, w, h] = fitCanvas($('audChart')); g.clearRect(0, 0, w, h);
    const panes = [[0, 1000, 'Low band 0–1 kHz (217 Hz markers)', [217, 434, 651, 868]], [15000, Math.min(22000, ac.sampleRate / 2), 'Ultrasonic 15–22 kHz', [18000]]];
    panes.forEach(([f0, f1, label, marks], p) => {
      const top = p * h / 2, ph = h / 2 - 14;
      g.fillStyle = '#8b9bb0'; g.font = '11px system-ui'; g.fillText(label, 4, top + 11);
      g.strokeStyle = 'rgba(244,63,94,.5)'; marks.forEach(m => { const x = (m - f0) / (f1 - f0) * w; g.beginPath(); g.moveTo(x, top + 14); g.lineTo(x, top + 14 + ph); g.stroke(); });
      g.strokeStyle = '#22d3ee'; g.lineWidth = 1.5; g.beginPath();
      const a = bin(f0), b = bin(f1);
      for (let i = a; i <= b; i++) { const x = (i - a) / (b - a) * w, v = Math.max(0, Math.min(1, (buf[i] + 120) / 90)), y = top + 14 + ph - v * ph; i === a ? g.moveTo(x, y) : g.lineTo(x, y); }
      g.stroke();
    });
  }
})();

// ---------- Checklist ----------
(function checklist() {
  const items = [
    'Smoke detectors and CO alarms: look for a lens hole or a power cable that shouldn’t be there',
    'USB chargers, power strips and extension leads: compare their weight and look with a known-good one',
    'Wall sockets, light switches and face plates: loose screws, scratches, fresh paint',
    'Alarm clocks, digital photo frames, speakers and routers',
    'TV, set-top box, Wi-Fi extenders and anything plugged in that you didn’t bring',
    'Air vents, ceiling tiles, light fittings and lamp shades',
    'Mirrors: put a fingernail on the glass. No gap between nail and reflection may mean a two-way mirror',
    'Picture frames, shelves, books, plant pots and decor facing the bed, shower or desk',
    'Under tables, desks, chairs and the bed frame: feel for tape, velcro or small boxes',
    'Car: OBD port under the dashboard, under seats, wheel arches, bumpers (trackers)',
    'Bags, coat pockets, jacket linings and gifts you’ve been given recently (trackers)',
    'Unknown Wi-Fi networks or Bluetooth names appearing only in this location',
    'Phone: check for unknown apps, battery drain, Device Admin apps, and run Safety Check (iPhone)',
  ];
  const key = 'sweepguard-checklist', saved = JSON.parse(localStorage.getItem(key) || '{}');
  $('ckList').innerHTML = items.map((t, i) => `<label class="ck"><input type="checkbox" data-i="${i}" ${saved[i] ? 'checked' : ''}><span>${t}</span></label>`).join('');
  const prog = () => { const n = Object.values(saved).filter(Boolean).length; $('ckProg').textContent = Math.round(n / items.length * 100) + '% done'; };
  $('ckList').onchange = e => { saved[e.target.dataset.i] = e.target.checked; localStorage.setItem(key, JSON.stringify(saved)); prog(); };
  $('ckReset').onclick = () => { for (const k in saved) delete saved[k]; localStorage.removeItem(key); document.querySelectorAll('#ckList input').forEach(c => c.checked = false); prog(); };
  prog();
})();
