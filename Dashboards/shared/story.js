/* Story engine shared by every dashboard.
 *
 *   Story.start({ steps, render })
 *     steps  : [{ kicker, title, body, change, stats:[{v,l,c}], note }]
 *     render : (index, step, direction) => void   // must fully draw the chart state for that step
 *
 * Next / Previous / Play buttons, the progress bar and ←/→/space keys all move between steps.
 * The step is kept in the URL hash (#3), so a presenter can jump straight to a slide.
 */
(function () {
  // ?still in the URL turns animation off (used for screenshots / printing)
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches || /[?&]still\b/.test(location.search);
  const $ = (s) => document.querySelector(s);

  const Story = {
    T: reduced ? 0 : 900,                       // standard transition length (ms)
    ease: (window.d3 && d3.easeCubicInOut) || ((t) => t),
    css: (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim(),
    money: (v, d = 0) => "$" + Number(v).toLocaleString("en-CA", { maximumFractionDigits: d, minimumFractionDigits: d }),
    pct: (v, d = 1) => (v * 100).toFixed(d) + "%",
    current: 0,
  };

  /* ---------- tooltip ---------- */
  const tip = document.createElement("div");
  tip.className = "tip";
  document.addEventListener("DOMContentLoaded", () => document.body.appendChild(tip));
  Story.tip = {
    show(html, ev) {
      tip.innerHTML = html;
      tip.classList.add("on");
      const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
      let x = ev.clientX + pad, y = ev.clientY + pad;
      if (x + w > window.innerWidth - 8) x = ev.clientX - w - pad;
      if (y + h > window.innerHeight - 8) y = ev.clientY - h - pad;
      tip.style.left = x + "px"; tip.style.top = y + "px";
    },
    hide() { tip.classList.remove("on"); },
  };

  /* ---------- theme toggle (follows OS by default) ---------- */
  Story.initTheme = function (onChange) {
    const btn = $("#theme");
    let saved = null;
    try { saved = localStorage.getItem("rr-theme"); } catch (e) {}
    if (saved) document.documentElement.dataset.theme = saved;
    const label = () => {
      const dark = document.documentElement.dataset.theme
        ? document.documentElement.dataset.theme === "dark"
        : window.matchMedia("(prefers-color-scheme: dark)").matches;
      if (btn) btn.textContent = dark ? "☀ Light" : "☾ Dark";
      return dark;
    };
    label();
    if (btn) btn.onclick = () => {
      const next = label() ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem("rr-theme", next); } catch (e) {}
      label();
      onChange && onChange();
    };
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { label(); onChange && onChange(); });
  };

  /* ---------- the stepper ---------- */
  Story.start = function ({ steps, render }) {
    const n = steps.length;
    const box = $("#narrative-content");
    const dots = $("#dots");
    let timer = null;

    steps.forEach((s, i) => {
      const b = document.createElement("button");
      b.title = `Step ${i + 1}: ${s.title.replace(/<[^>]+>/g, "")}`;
      b.setAttribute("aria-label", b.title);
      b.onclick = () => { stop(); go(i); };
      dots.appendChild(b);
    });

    function fill(s) {
      const stats = (s.stats || []).map((x) =>
        `<div class="stat"><div class="v">${x.c ? `<span class="sw" style="background:var(${x.c})"></span>` : ""}${x.v}</div><div class="l">${x.l}</div></div>`).join("");
      box.innerHTML = `
        <div class="kicker">${s.kicker || ""}</div>
        <h2>${s.title}</h2>
        <div class="body">${s.body || ""}</div>
        ${stats ? `<div class="stats">${stats}</div>` : ""}
        ${s.change ? `<div class="change"><span class="h">↻ What just moved</span>${s.change}</div>` : ""}
        ${s.note ? `<div class="note">${s.note}</div>` : ""}`;
    }

    function go(i, first) {
      i = Math.max(0, Math.min(n - 1, i));
      const dir = i >= Story.current ? 1 : -1;
      Story.current = i;
      const s = steps[i];
      if (first || Story.T === 0) fill(s);
      else {
        box.classList.add("out");
        setTimeout(() => { fill(s); box.classList.remove("out"); }, 220);
      }
      [...dots.children].forEach((d, k) => { d.className = k === i ? "on" : k < i ? "done" : ""; });
      $("#prev").disabled = i === 0;
      $("#next").disabled = i === n - 1;
      $("#counter").textContent = `Step ${i + 1} / ${n}`;
      history.replaceState(null, "", "#" + (i + 1));
      render(i, s, dir);
    }

    function stop() { clearInterval(timer); timer = null; $("#play").textContent = "▶ Play"; }
    function play() {
      if (timer) return stop();
      if (Story.current === n - 1) go(0);
      $("#play").textContent = "❚❚ Pause";
      timer = setInterval(() => { if (Story.current >= n - 1) stop(); else go(Story.current + 1); }, 7000);
    }

    $("#prev").onclick = () => { stop(); go(Story.current - 1); };
    $("#next").onclick = () => { stop(); go(Story.current + 1); };
    $("#play").onclick = play;
    document.addEventListener("keydown", (e) => {
      if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;
      if (e.key === "ArrowRight" || e.key === "PageDown") { stop(); go(Story.current + 1); }
      else if (e.key === "ArrowLeft" || e.key === "PageUp") { stop(); go(Story.current - 1); }
      else if (e.key === " ") { e.preventDefault(); play(); }
    });

    const start = parseInt(location.hash.slice(1), 10);
    go(Number.isFinite(start) ? start - 1 : 0, true);
    Story.redraw = () => render(Story.current, steps[Story.current], 0);
    return { go };
  };

  /* ---------- small helpers for charts ---------- */
  Story.legend = function (items) {   // items: [[cssVar, label], ...]
    document.querySelector("#legend").innerHTML =
      items.map(([c, l]) => `<span><i style="background:var(${c})"></i>${l}</span>`).join("");
  };
  Story.chartTitle = (t) => { document.querySelector("#chart-title").textContent = t; };
  Story.widget = (id) => {
    document.querySelectorAll(".widget").forEach((w) => w.classList.toggle("show", w.id === id));
  };

  window.Story = Story;
})();
