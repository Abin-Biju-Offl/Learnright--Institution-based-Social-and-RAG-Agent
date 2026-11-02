// ─────────────────────────────────────────────────────────────────────────────
//  NCERT Textbook Assistant  –  app.js
//  Self-contained: BotAvatar (canvas) + ThinkingOrb (canvas) + full chat logic
// ─────────────────────────────────────────────────────────────────────────────

"use strict";

const $ = (id) => document.getElementById(id);

// ═══════════════════════════════════════════════════════════════════════════════
//  1.  BOT AVATAR  (bot-avatars inspired — pure canvas, no deps)
//      Renders a friendly rounded blob that looks around and bobs gently.
// ═══════════════════════════════════════════════════════════════════════════════

class BotAvatar {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {object} opts
   * @param {string}  opts.type   – "clover"|"star"|"blob"|"flower"|"circle"
   * @param {string}  opts.state  – "default"|"working"|"sleeping"
   * @param {number}  opts.size   – canvas logical size in px (canvas must match)
   * @param {string}  opts.color  – CSS colour override
   * @param {number}  opts.seed   – 0-1, phase offset for row desync
   */
  constructor(canvas, opts = {}) {
    this.canvas = canvas;
    this.ctx    = canvas.getContext("2d");
    this.type   = opts.type  || "clover";
    this.state  = opts.state || "default";
    this.size   = opts.size  || canvas.width;
    this.seed   = (opts.seed || 0) * Math.PI * 2;
    this.color  = opts.color || BotAvatar.PALETTE[this.type] || "#007aff";
    this._t     = this.seed;
    this._raf   = null;
    this._eyeTargetX = 0;
    this._eyeTargetY = 0;
    this._eyeX  = 0;
    this._eyeY  = 0;
    this._blink = 0;
    this._nextBlink = this._randomBlinkDelay();
    this._bobY  = 0;
    this._jumped = false;
    this._jumpT  = 0;
    this._jumpV  = 0;
    this._lastPointer = null;
    this._setupPointer();
    this._loop();
  }

  static PALETTE = {
    clover:   "#30d158",
    star:     "#ffd60a",
    flower:   "#ff9f0a",
    blob:     "#007aff",
    circle:   "#5e5ce6",
    ghost:    "#8e8e93",
    drop:     "#64d2ff",
    hexagon:  "#bf5af2",
    cat:      "#ff6b6b",
    cloud:    "#aeaeb2",
    droid:    "#34c759",
    mech:     "#636366",
    alien:    "#30d158",
    triangle: "#ff9f0a",
    square:   "#007aff",
    pill:     "#ff375f",
    pebble:   "#a2845e",
    puddle:   "#5ac8fa",
  };

  _randomBlinkDelay() { return 2.5 + Math.random() * 3.5; }

  _setupPointer() {
    const handler = (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const cx   = rect.left + rect.width  / 2;
      const cy   = rect.top  + rect.height / 2;
      const r    = rect.width * 1.8;
      const dx   = (e.clientX - cx) / r;
      const dy   = (e.clientY - cy) / r;
      this._eyeTargetX = Math.max(-1, Math.min(1, dx));
      this._eyeTargetY = Math.max(-1, Math.min(1, dy));
    };
    document.addEventListener("pointermove", handler, { passive: true });

    this.canvas.addEventListener("click", () => {
      if (!this._jumped) { this._jumped = true; this._jumpT = 0; this._jumpV = 8; }
    });
  }

  setState(state) { this.state = state; }

  _loop() {
    const step = (ts) => {
      const dt = 1 / 60;
      this._t += dt;

      // Eye lerp
      const lerpSpeed = this.state === "sleeping" ? 0.02 : 0.08;
      this._eyeX += (this._eyeTargetX - this._eyeX) * lerpSpeed;
      this._eyeY += (this._eyeTargetY - this._eyeY) * lerpSpeed;

      // Blink
      this._nextBlink -= dt;
      if (this._nextBlink <= 0) { this._blink = 0.18; this._nextBlink = this._randomBlinkDelay(); }
      if (this._blink > 0) this._blink = Math.max(0, this._blink - dt);

      // Bob
      const bobFreq  = this.state === "working" ? 3.2 : this.state === "sleeping" ? 0.6 : 1.4;
      const bobAmp   = this.state === "sleeping" ? 1.5 : this.state === "working"  ? 4   : 2.5;
      this._bobY = Math.sin(this._t * bobFreq + this.seed) * bobAmp;

      // Jump
      if (this._jumped) {
        this._jumpT += dt;
        this._bobY   += this._jumpV * this._jumpT - 18 * this._jumpT * this._jumpT;
        if (this._jumpT > this._jumpV / 18) { this._jumped = false; this._jumpT = 0; this._jumpV = 0; }
      }

      this._draw();
      this._raf = requestAnimationFrame(step);
    };
    this._raf = requestAnimationFrame(step);
  }

  _draw() {
    const { ctx, size } = this;
    const S = size;
    const cx = S / 2, cy = S / 2;
    ctx.clearRect(0, 0, S, S);

    const bobOffset = Math.min(6, Math.max(-6, this._bobY));
    ctx.save();
    ctx.translate(0, bobOffset * (S / 96));

    // ── Body ──
    const R = S * 0.38;
    ctx.save();
    const bodyPath = this._bodyPath(cx, cy, R);
    // Shadow
    ctx.shadowColor = "rgba(0,0,0,0.18)";
    ctx.shadowBlur  = S * 0.18;
    ctx.shadowOffsetY = S * 0.06;
    ctx.fillStyle = this.color;
    ctx.fill(bodyPath);
    ctx.shadowColor = "transparent";

    // Sheen highlight
    const grad = ctx.createRadialGradient(cx - R * 0.25, cy - R * 0.35, 0, cx, cy, R * 1.1);
    grad.addColorStop(0, "rgba(255,255,255,0.35)");
    grad.addColorStop(0.5, "rgba(255,255,255,0.08)");
    grad.addColorStop(1,   "rgba(0,0,0,0.10)");
    ctx.fillStyle = grad;
    ctx.fill(bodyPath);
    ctx.restore();

    // ── Face ──
    const sleeping = this.state === "sleeping";
    const working  = this.state === "working";
    const eyeR = S * 0.072;
    const eyeOffX = S * 0.115;
    const eyeOffY = S * 0.04;
    const eyeMoveR = eyeR * 0.55;

    const eyeLX = cx - eyeOffX;
    const eyeLY = cy + eyeOffY;
    const eyeRX = cx + eyeOffX;
    const eyeRY = cy + eyeOffY;

    const blinkPct = this._blink > 0 ? 1 - Math.abs(this._blink - 0.09) / 0.09 : 0;

    // Pupil offset clamped to eye boundary
    const px = this._eyeX * eyeMoveR;
    const py = this._eyeY * eyeMoveR;

    [eyeLX, eyeRX].forEach((ex) => {
      const ey = ex === eyeLX ? eyeLY : eyeRY;
      if (sleeping) {
        // Closed arc
        ctx.beginPath();
        ctx.arc(ex, ey, eyeR * 0.7, Math.PI, 0, false);
        ctx.closePath();
        ctx.fillStyle = "rgba(0,0,0,0.55)";
        ctx.fill();
      } else {
        // Eye white
        ctx.save();
        ctx.beginPath();
        ctx.ellipse(ex, ey, eyeR, eyeR * (1 - blinkPct * 0.85), 0, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255,255,255,0.92)";
        ctx.fill();
        // Pupil
        ctx.clip();
        ctx.beginPath();
        ctx.arc(ex + px, ey + py, eyeR * 0.48, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(10,10,20,0.90)";
        ctx.fill();
        // Glint
        ctx.beginPath();
        ctx.arc(ex + px - eyeR * 0.14, ey + py - eyeR * 0.14, eyeR * 0.13, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255,255,255,0.9)";
        ctx.fill();
        ctx.restore();
      }
    });

    // Mouth (face="mouth" equivalent when working)
    if (working) {
      const mouthW = S * 0.18;
      const mouthY = cy + S * 0.20;
      const smile  = Math.sin(this._t * 4) * 0.5 + 0.5;
      ctx.beginPath();
      ctx.moveTo(cx - mouthW / 2, mouthY);
      ctx.quadraticCurveTo(cx, mouthY + smile * S * 0.08, cx + mouthW / 2, mouthY);
      ctx.strokeStyle = "rgba(0,0,0,0.55)";
      ctx.lineWidth   = S * 0.028;
      ctx.lineCap     = "round";
      ctx.stroke();
    } else if (sleeping) {
      // Zzz
      ctx.font = `bold ${S * 0.18}px Inter, sans-serif`;
      ctx.fillStyle = "rgba(0,0,0,0.35)";
      ctx.textAlign = "center";
      ctx.fillText("z", cx + S * 0.25, cy - S * 0.18);
    }

    ctx.restore();
  }

  /** Returns a Path2D for the body shape based on this.type */
  _bodyPath(cx, cy, R) {
    const p = new Path2D();
    switch (this.type) {
      case "star": {
        const n = 5, inner = R * 0.42;
        for (let i = 0; i < n * 2; i++) {
          const a = (Math.PI / n) * i - Math.PI / 2;
          const r = i % 2 === 0 ? R : inner;
          i === 0 ? p.moveTo(cx + r * Math.cos(a), cy + r * Math.sin(a))
                  : p.lineTo(cx + r * Math.cos(a), cy + r * Math.sin(a));
        }
        p.closePath(); break;
      }
      case "triangle": {
        for (let i = 0; i < 3; i++) {
          const a = (Math.PI * 2 / 3) * i - Math.PI / 2;
          i === 0 ? p.moveTo(cx + R * Math.cos(a), cy + R * Math.sin(a))
                  : p.lineTo(cx + R * Math.cos(a), cy + R * Math.sin(a));
        }
        p.closePath(); break;
      }
      case "hexagon": {
        for (let i = 0; i < 6; i++) {
          const a = (Math.PI / 3) * i - Math.PI / 6;
          i === 0 ? p.moveTo(cx + R * Math.cos(a), cy + R * Math.sin(a))
                  : p.lineTo(cx + R * Math.cos(a), cy + R * Math.sin(a));
        }
        p.closePath(); break;
      }
      case "square": {
        const s = R * 1.35;
        p.roundRect(cx - s / 2, cy - s / 2, s, s, s * 0.22);
        break;
      }
      case "drop": {
        p.moveTo(cx, cy - R * 1.1);
        p.bezierCurveTo(cx + R * 0.8, cy - R * 0.3, cx + R, cy + R * 0.5, cx, cy + R);
        p.bezierCurveTo(cx - R, cy + R * 0.5, cx - R * 0.8, cy - R * 0.3, cx, cy - R * 1.1);
        break;
      }
      case "clover": {
        // 4-leaf clover: 4 overlapping circles
        const r2 = R * 0.62, off = R * 0.38;
        [[0, -off], [off, 0], [0, off], [-off, 0]].forEach(([ox, oy]) => {
          p.arc(cx + ox, cy + oy, r2, 0, Math.PI * 2); p.closePath();
        });
        break;
      }
      case "flower": {
        const petals = 5;
        for (let i = 0; i < petals; i++) {
          const a  = (Math.PI * 2 / petals) * i;
          const bx = cx + Math.cos(a) * R * 0.5;
          const by = cy + Math.sin(a) * R * 0.5;
          p.arc(bx, by, R * 0.48, 0, Math.PI * 2); p.closePath();
        }
        break;
      }
      case "ghost": {
        p.moveTo(cx - R, cy + R * 0.3);
        p.arc(cx, cy - R * 0.05, R, Math.PI, 0);
        const waves = 3;
        for (let i = 0; i < waves; i++) {
          const wx = cx + R - (2 * R / waves) * i;
          const dir = i % 2 === 0 ? 1 : -1;
          p.quadraticCurveTo(wx - R / waves, cy + R * 0.55 + dir * R * 0.22, wx - 2 * R / waves, cy + R * 0.3);
        }
        p.closePath(); break;
      }
      default: // blob / circle etc.
        p.arc(cx, cy, R, 0, Math.PI * 2);
    }
    return p;
  }

  destroy() { if (this._raf) cancelAnimationFrame(this._raf); }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  2.  THINKING ORB  (thinking-orbs inspired — canvas, no deps)
//      Nine hand-tuned animated states, drawn as a glowing fluid orb.
// ═══════════════════════════════════════════════════════════════════════════════

class ThinkingOrb {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {object} opts
   * @param {"working"|"searching"|"solving"|"listening"|"connecting"|"weaving"|"composing"|"breathing"|"shaping"} opts.state
   * @param {number} opts.size
   * @param {number} opts.speed   – clock multiplier
   * @param {boolean} opts.dark
   * @param {boolean} opts.paused
   */
  constructor(canvas, opts = {}) {
    this.canvas = canvas;
    this.ctx    = canvas.getContext("2d");
    this.state  = opts.state  || "searching";
    this.size   = opts.size   || canvas.width;
    this.speed  = opts.speed  || 1;
    this.dark   = opts.dark   ?? this._prefersDark();
    this.paused = opts.paused || false;
    this._t     = 0;
    this._raf   = null;
    this._loop();
  }

  _prefersDark() {
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  }

  setState(state) { this.state = state; }
  setPaused(v)   { this.paused = v; }

  // Per-state palette & behaviour
  static STATES = {
    working:    { hue: 220, sat: 90,  speed: 1.6,  blobs: 4, pulse: 0.9 },
    searching:  { hue: 260, sat: 85,  speed: 1.1,  blobs: 3, pulse: 0.6 },
    solving:    { hue: 280, sat: 80,  speed: 1.3,  blobs: 5, pulse: 1.0 },
    listening:  { hue: 180, sat: 75,  speed: 0.7,  blobs: 3, pulse: 0.5 },
    connecting: { hue: 200, sat: 80,  speed: 2.0,  blobs: 4, pulse: 1.2 },
    weaving:    { hue: 320, sat: 90,  speed: 1.4,  blobs: 6, pulse: 0.8 },
    composing:  { hue: 45,  sat: 90,  speed: 0.9,  blobs: 3, pulse: 0.7 },
    breathing:  { hue: 160, sat: 65,  speed: 0.5,  blobs: 2, pulse: 0.4 },
    shaping:    { hue: 30,  sat: 85,  speed: 1.2,  blobs: 4, pulse: 0.9 },
  };

  _loop() {
    const step = () => {
      if (!this.paused) {
        const cfg = ThinkingOrb.STATES[this.state] || ThinkingOrb.STATES.searching;
        this._t += (1 / 60) * this.speed * cfg.speed;
        this._draw(cfg);
      }
      this._raf = requestAnimationFrame(step);
    };
    this._raf = requestAnimationFrame(step);
  }

  _draw(cfg) {
    const { ctx, size: S } = this;
    const cx = S / 2, cy = S / 2;
    ctx.clearRect(0, 0, S, S);

    const t    = this._t;
    const R    = S * 0.42;
    const H    = cfg.hue;
    const sat  = cfg.sat;
    const n    = cfg.blobs;
    const pulse = 1 + Math.sin(t * 2.1) * 0.07 * cfg.pulse;

    // Outer glow
    const glow = ctx.createRadialGradient(cx, cy, R * 0.2, cx, cy, R * pulse * 1.5);
    glow.addColorStop(0,   `hsla(${H},${sat}%,65%,0.28)`);
    glow.addColorStop(0.5, `hsla(${H},${sat}%,55%,0.10)`);
    glow.addColorStop(1,   `hsla(${H},${sat}%,45%,0)`);
    ctx.beginPath();
    ctx.arc(cx, cy, R * pulse * 1.5, 0, Math.PI * 2);
    ctx.fillStyle = glow;
    ctx.fill();

    // Core fluid blobs
    for (let i = 0; i < n; i++) {
      const phase = (Math.PI * 2 / n) * i;
      const wobble = 0.25 + 0.12 * Math.sin(t * 0.7 + phase * 1.3);
      const bx  = cx + Math.cos(t * 0.9 + phase) * R * wobble * pulse;
      const by  = cy + Math.sin(t * 1.1 + phase * 1.2) * R * wobble * pulse;
      const br  = R * (0.55 + 0.15 * Math.sin(t * 1.5 + phase));
      const hShift = (i * 28 + t * 15) % 360;
      const bGrad  = ctx.createRadialGradient(bx - br * 0.2, by - br * 0.2, 0, bx, by, br);
      bGrad.addColorStop(0,   `hsla(${(H + hShift) % 360},${sat}%,72%,0.70)`);
      bGrad.addColorStop(0.6, `hsla(${H},${sat}%,55%,0.45)`);
      bGrad.addColorStop(1,   `hsla(${H},${sat}%,45%,0)`);
      ctx.beginPath();
      ctx.arc(bx, by, br, 0, Math.PI * 2);
      ctx.fillStyle = bGrad;
      ctx.fill();
    }

    // Core sphere
    const cGrad = ctx.createRadialGradient(cx - R * 0.22, cy - R * 0.22, 0, cx, cy, R * pulse);
    cGrad.addColorStop(0,    `hsla(${H},${sat}%,82%,0.90)`);
    cGrad.addColorStop(0.45, `hsla(${H},${sat}%,62%,0.80)`);
    cGrad.addColorStop(1,    `hsla(${H},${sat}%,38%,0.60)`);
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.72 * pulse, 0, Math.PI * 2);
    ctx.fillStyle = cGrad;
    ctx.fill();

    // Glint
    ctx.beginPath();
    ctx.arc(cx - R * 0.22, cy - R * 0.22, R * 0.14, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255,255,255,0.55)";
    ctx.fill();
  }

  destroy() { if (this._raf) cancelAnimationFrame(this._raf); }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  3.  APP LOGIC
// ═══════════════════════════════════════════════════════════════════════════════

const STORAGE_KEY = "ncert-tutor-sessions-v2";
const EXAMPLES = {
  // Class 10 — NCERT books (real content)
  "10|English":        ["Why did Lencho write a letter to God?", "What did Mandela learn about courage?"],
  "10|Science":        ["What is a balanced chemical equation?", "Why does the sky appear blue?"],
  "10|Social Science": ["What are the different types of soil in India?", "What is Project Tiger?"],
  // Class 5 — Sunshine Reader / Science Around Us / Our Land and People (demo)
  "5|English":         ["What happened to the thirsty crow?", "What did Meena do with her kite?"],
  "5|Science":         ["How do plants make their food?", "What is a shadow?"],
  "5|Social Science":  ["Why is water important for us?", "What kind of animals live in forests?"],
};

let sessions = loadSessions();
let activeSessionId = sessions[0]?.id || null;
let lastQuestion = null;
let currentSources = [];

// ── Avatar & Orb instances ──────────────────────────────────────────────────
let welcomeAvatar  = null;
let brandAvatar    = null;
let thinkingOrb    = null;

function initAvatars() {
  // Welcome hero avatar (large, "default" state, clover shape)
  const wCanvas = $("welcome-avatar");
  if (wCanvas) {
    welcomeAvatar = new BotAvatar(wCanvas, {
      type: "clover", state: "default", size: 96, seed: 0.12,
    });
  }

  // Sidebar brand avatar (small, matches clover)
  const bCanvas = $("brand-avatar");
  if (bCanvas) {
    brandAvatar = new BotAvatar(bCanvas, {
      type: "clover", state: "default", size: 36, seed: 0.55,
    });
  }

  // Thinking orb (hidden until a query is in flight)
  const orbCanvas = $("orb-canvas");
  if (orbCanvas) {
    thinkingOrb = new ThinkingOrb(orbCanvas, {
      state: "searching", size: 28, speed: 1, paused: true,
    });
  }
}

// ── Session management ──────────────────────────────────────────────────────
function loadSessions() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); }
  catch { return []; }
}
function saveSessions() { localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.slice(0, 30))); }

function createSession() {
  const s = {
    id: crypto.randomUUID(), title: "New conversation",
    createdAt: Date.now(), updatedAt: Date.now(), messages: [],
  };
  sessions.unshift(s); activeSessionId = s.id;
  saveSessions(); renderHistory(); return s.id;
}
function activeSession() { return sessions.find((s) => s.id === activeSessionId); }

function renderHistory() {
  $("history").replaceChildren(...sessions.map((s) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "history-item" + (s.id === activeSessionId ? " active" : "");
    const title = document.createElement("span");
    title.className = "history-item-title";
    title.textContent = s.title;
    const date = document.createElement("span");
    date.className = "history-item-date";
    date.textContent = new Date(s.updatedAt).toLocaleDateString(undefined, { month: "short", day: "numeric" });
    btn.append(title, date);
    btn.onclick = () => selectSession(s.id);
    return btn;
  }));
}

function selectSession(id) {
  activeSessionId = id;
  const s = activeSession();
  $("conversation").replaceChildren(...s.messages.flatMap(renderMessage));
  $("welcome").hidden = s.messages.length > 0;
  if (welcomeAvatar) welcomeAvatar.setState(s.messages.length > 0 ? "working" : "default");
  $("result").hidden = true; $("question").value = "";
  renderHistory();
  closeSidebar();
}

// ── Message rendering ───────────────────────────────────────────────────────
function renderMessage(msg, idx) {
  const art = document.createElement("article");
  art.className = `message ${msg.role}`;
  art.style.setProperty("--delay", `${Math.min(idx ?? 0, 6) * 40}ms`);

  if (msg.role === "user") {
    art.innerHTML = `
      <div class="avatar" aria-label="You">Y</div>
      <div class="message-body">${escapeHtml(msg.text)}</div>`;
  } else {
    // Assistant: canvas bot avatar
    const canvas = document.createElement("canvas");
    canvas.width = 32; canvas.height = 32; canvas.className = "avatar";
    canvas.setAttribute("aria-label", "NCERT Tutor");
    art.appendChild(canvas);
    const body = document.createElement("div");
    body.className = "message-body";
    body.innerHTML = formatAnswer(msg.text);
    art.appendChild(body);
    // Init tiny avatar
    requestAnimationFrame(() => {
      new BotAvatar(canvas, { type: "clover", state: "default", size: 32, seed: Math.random() });
    });
  }
  return [art];
}

function addMessage(role, text) {
  const s = activeSession();
  s.messages.push({ role, text }); s.updatedAt = Date.now();
  if (role === "user" && s.title === "New conversation") s.title = text.slice(0, 48);
  saveSessions();
  $("welcome").hidden = true;
  if (welcomeAvatar) welcomeAvatar.setState("working");
  const nodes = renderMessage({ role, text }, s.messages.length - 1);
  $("conversation").append(...nodes);
  scrollToBottom();
}

function scrollToBottom() {
  const c = $("conversation");
  c.scrollTo({ top: c.scrollHeight, behavior: "smooth" });
}

// ── Health check ────────────────────────────────────────────────────────────
async function checkHealth() {
  const el = $("status");
  try {
    const h = await (await fetch("/api/health")).json();
    const ok = h.status === "ok";
    el.textContent = ok ? "Ready" : "Problem";
    el.className = "status " + (ok ? "ok" : "error");
    const svcs = ["ollama", "embedding server", "llm server", "qdrant"].filter((n) => n in h);
    el.title = [`Index: ${h.index}`, ...svcs.map((n) => `${n}: ${h[n]}`)].join("\n");
  } catch {
    el.textContent = "Server offline";
    el.className = "status error";
  }
}

// ── Subjects ────────────────────────────────────────────────────────────────
async function loadSubjects() {
  const sel = $("subject");
  try {
    const r = await fetch("/api/subjects");
    if (!r.ok) throw new Error((await r.json()).detail);
    const subjects = await r.json();
    sel.innerHTML = subjects.map(
      (s) => `<option value="${s.grade}|${escapeHtml(s.subject)}">Class ${s.grade} · ${escapeHtml(s.subject)} (${escapeHtml(s.book)})</option>`
    ).join("");
    sel.disabled = false;
    showExamples();
  } catch (err) {
    sel.innerHTML = "<option>Textbooks unavailable</option>";
    showError(err.message || "Could not reach the server.");
  }
}

function selected() {
  const [grade, subject] = $("subject").value.split("|");
  return { grade: Number(grade), subject };
}
function showExamples() {
  const qs = EXAMPLES[$("subject").value] || [];
  $("examples").replaceChildren(...qs.map((q) => {
    const chip = document.createElement("button");
    chip.type = "button"; chip.textContent = q;
    chip.onclick = () => { $("question").value = q; $("question").focus(); };
    return chip;
  }));
}
function changeTextbook() { $("result").hidden = true; lastQuestion = null; showExamples(); }

// ── Ask ──────────────────────────────────────────────────────────────────────
async function ask(event) {
  event.preventDefault();
  const q = $("question").value.trim();
  if (q.length < 3 || $("ask-button").disabled) return;

  lastQuestion = { question: q, ...selected(), language: $("language").value };
  addMessage("user", q);
  $("question").value = "";

  $("ask-button").disabled = true;
  $("subject").disabled = true;
  $("result").hidden = false;
  $("answer").className = "answer";
  $("answer").innerHTML = "";
  $("sources-block").hidden = true;
  $("feedback").hidden = true;

  // Show orb + "Searching…"
  setProgress("searching", "Searching your textbook…");

  try {
    const res = await fetch("/api/ask/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(lastQuestion),
    });
    if (!res.ok) {
      const { detail } = await res.json();
      throw new Error(typeof detail === "string" ? detail : "Please check your question and try again.");
    }
    await readEvents(res);
  } catch (err) {
    showError(err.message);
  } finally {
    hideProgress();
    $("ask-button").disabled = false;
    $("subject").disabled = false;
    if (welcomeAvatar) welcomeAvatar.setState("default");
  }
}

function setProgress(orbState, text) {
  if (thinkingOrb) { thinkingOrb.setState(orbState); thinkingOrb.setPaused(false); }
  $("progress-text").textContent = text;
  $("progress-wrap").hidden = false;
}
function hideProgress() {
  if (thinkingOrb) thinkingOrb.setPaused(true);
  $("progress-wrap").hidden = true;
}

async function readEvents(res) {
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "", answer = "";
  setProgress("working", "Writing the answer…");

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const lines = buffer.split("\n"); buffer = lines.pop();
    for (const line of lines.filter(Boolean)) {
      const ev = JSON.parse(line);
      if (ev.type === "token") {
        hideProgress();
        answer += ev.text;
        $("answer").innerHTML = formatAnswer(answer);
      } else if (ev.type === "done") {
        currentSources = ev.sources;
        showSources(ev.sources);
        lastQuestion.answer = answer;
        showFeedback();
        const s = activeSession();
        s.messages.push({ role: "assistant", text: answer });
        s.updatedAt = Date.now();
        saveSessions(); renderHistory();
        scrollToBottom();
      } else if (ev.type === "error") {
        throw new Error(ev.message);
      }
    }
  }
}

// ── Sources ──────────────────────────────────────────────────────────────────
function showSources(sources) {
  $("sources").innerHTML = sources.map((s) => `
    <li><details>
      <summary class="source-row">
        <span>Chapter ${s.chapter}: ${escapeHtml(s.chapter_title)}, page ${s.page}</span>
        <button type="button" class="preview-source"
          data-file="${escapeHtml(s.file)}" data-page="${s.page}" data-title="${escapeHtml(s.chapter_title)}">
          Preview PDF
        </button>
      </summary>
      <blockquote>${escapeHtml(s.text)}</blockquote>
    </details></li>`).join("");
  $("sources-block").hidden = sources.length === 0;
  $("sources").querySelectorAll(".preview-source").forEach((btn) =>
    btn.addEventListener("click", () => openPreview(btn.dataset.file, btn.dataset.page, btn.dataset.title))
  );
}

function openPreview(file, page, title) {
  if (!file || !page) return;
  $("preview-panel").hidden = false;
  $("workspace-grid").classList.add("with-preview");
  $("preview-toggle").hidden = false;
  $("preview-title").textContent = title || "PDF preview";
  $("preview-page").textContent  = `Page ${page}`;
  $("pdf-frame").src = `/pdfs/${file.split("/").map(encodeURIComponent).join("/")}#page=${encodeURIComponent(page)}`;
}
function closePreview() {
  $("preview-panel").hidden = true;
  $("workspace-grid").classList.remove("with-preview");
  $("pdf-frame").src = "about:blank";
}

// ── Feedback ─────────────────────────────────────────────────────────────────
function showFeedback() {
  $("feedback").hidden = false;
  $("feedback-thanks").hidden = true;
  $("feedback").querySelectorAll("button").forEach((b) => (b.disabled = false));
}
async function sendFeedback(helpful) {
  $("feedback").querySelectorAll("button").forEach((b) => (b.disabled = true));
  $("feedback-thanks").hidden = false;
  const { question, answer, grade, subject } = lastQuestion;
  await fetch("/api/feedback", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, answer, grade, subject, helpful }),
  }).catch(() => {});
}

// ── Error ────────────────────────────────────────────────────────────────────
function showError(msg) {
  $("result").hidden = false;
  $("answer").className = "answer error";
  $("answer").textContent = msg;
  $("sources-block").hidden = true;
  $("feedback").hidden = true;
}

// ── Formatters ───────────────────────────────────────────────────────────────
function formatAnswer(text) {
  return escapeHtml(text.trim()).split(/\n\s*\n/).map((block) => {
    const lines = block.split("\n").filter((l) => l.trim());
    const isList = lines.length > 0 && lines.every((l) => /^\s*([-*•]|\d+\.)\s/.test(l));
    if (isList) {
      const items = lines.map((l) => `<li>${inline(l.replace(/^\s*([-*•]|\d+\.)\s+/, ""))}</li>`);
      return /^\s*\d+\./.test(lines[0]) ? `<ol>${items.join("")}</ol>` : `<ul>${items.join("")}</ul>`;
    }
    return `<p>${lines.map((l) => inline(l.replace(/^#+\s*/, ""))).join("<br>")}</p>`;
  }).join("");
}
function inline(line) {
  return line
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[(\d[\d,\s]*)\]/g, '<span class="cite">[$1]</span>');
}
function escapeHtml(t) { const d = document.createElement("div"); d.textContent = t; return d.innerHTML; }

// ── Sidebar mobile ───────────────────────────────────────────────────────────
function closeSidebar() {
  $("sidebar").classList.remove("open");
}
function toggleSidebar() {
  $("sidebar").classList.toggle("open");
}

// ── Event listeners ──────────────────────────────────────────────────────────
$("ask-form").addEventListener("submit", ask);
$("subject").addEventListener("change", changeTextbook);
$("question").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("ask-form").requestSubmit(); }
});
$("feedback").querySelectorAll("button").forEach((b) =>
  b.addEventListener("click", () => sendFeedback(b.dataset.helpful === "true"))
);
$("new-chat").addEventListener("click", () => {
  createSession(); selectSession(activeSessionId); $("question").focus();
});
$("clear-history").addEventListener("click", () => {
  if (!confirm("Clear all saved conversations on this device?")) return;
  sessions = []; createSession(); selectSession(activeSessionId);
});
$("close-preview").addEventListener("click", closePreview);
$("preview-toggle").addEventListener("click", () =>
  $("preview-panel").hidden
    ? openPreview(currentSources[0]?.file, currentSources[0]?.page, currentSources[0]?.chapter_title)
    : closePreview()
);
$("menu-button").addEventListener("click", toggleSidebar);
$("sidebar-overlay").addEventListener("click", closeSidebar);

// Reflect dark/light on orb
window.matchMedia?.("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
  if (thinkingOrb) thinkingOrb.dark = e.matches;
});

// ── Boot ─────────────────────────────────────────────────────────────────────
if (!activeSessionId) createSession();
renderHistory();
selectSession(activeSessionId);
initAvatars();
checkHealth();
loadSubjects();
