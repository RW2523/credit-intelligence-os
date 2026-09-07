// ---------------------------------------------------------------- helpers
export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];

export function h(html) { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; }
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export const money = (n, d = 0) => '$' + Number(n || 0).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
export const pct = (n, d = 1) => `${(Number(n) * 100).toFixed(d)}%`;
export const num = (n, d = 0) => Number(n || 0).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
export const date = s => s ? new Date(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—';
export const dtime = s => s ? new Date(s).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
export const ago = s => { if (!s) return '—'; const d = (Date.now() - new Date(s)) / 864e5; return d < 1 ? 'today' : d < 2 ? 'yesterday' : `${Math.floor(d)}d ago`; };

export const toneFor = v => ({
  Low: 'green', Moderate: 'amber', Elevated: 'amber', High: 'red',
  PASS: 'green', FAIL: 'red', Match: 'green', Review: 'amber', Mismatch: 'red', Insufficient: 'grey',
  Support: 'green', Caution: 'amber', Concern: 'amber', Oppose: 'red',
  Clear: 'green', Watch: 'amber', Critical: 'red',
  STABLE: 'green', WATCH: 'cyan', ELEVATED: 'amber', AT_RISK: 'red', RECOVERY: 'purple',
  APPROVE: 'green', DECLINE: 'red', 'OFFICER REVIEW': 'amber', 'REQUEST INFORMATION': 'blue', INVESTIGATE: 'red',
  Verified: 'green', 'Needs Review': 'amber', Rejected: 'red',
  Approved: 'green', Declined: 'red', P1: 'red', P2: 'amber', P3: 'blue',
  AUTONOMOUS: 'purple', HUMAN: 'blue',
}[v] || 'grey');

export const tag = (v, tone) => `<span class="tag t-${tone || toneFor(v)}">${esc(v)}</span>`;

// ------------------------------------------------------------------- api
export async function api(path, opts = {}) {
  const r = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json' }, ...opts,
    body: opts.body && typeof opts.body !== 'string' ? JSON.stringify(opts.body) : opts.body,
  });
  if (!r.ok) { let m; try { m = (await r.json()).detail; } catch { m = r.statusText; } throw new Error(m || 'request failed'); }
  return r.json();
}

export function sse(path, handlers, opts = {}) {
  const ctrl = new AbortController();
  (async () => {
    const r = await fetch('/api' + path, { signal: ctrl.signal, method: opts.method || 'GET', ...opts,
      headers: { 'Content-Type': 'application/json' },
      body: opts.body ? JSON.stringify(opts.body) : undefined });
    const reader = r.body.getReader(); const dec = new TextDecoder(); let buf = '';
    while (true) {
      const { done, value } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split('\n\n'); buf = parts.pop();
      for (const p of parts) {
        const ev = (p.match(/^event: (.+)$/m) || [])[1];
        const dl = (p.match(/^data: ([\s\S]+)$/m) || [])[1];
        if (ev && dl) { try { handlers[ev]?.(JSON.parse(dl)); } catch (e) { console.warn(e); } }
      }
    }
    handlers.close?.();
  })().catch(e => { if (e.name !== 'AbortError') handlers.error?.({ message: e.message }); });
  return ctrl;
}

// ---------------------------------------------------------------- toasts
export function toast(title, sub = '', kind = '') {
  let w = $('.toast-wrap'); if (!w) { w = h('<div class="toast-wrap"></div>'); document.body.appendChild(w); }
  const t = h(`<div class="toast ${kind}"><b>${esc(title)}</b>${sub ? `<span>${esc(sub)}</span>` : ''}</div>`);
  w.appendChild(t);
  setTimeout(() => { t.style.transition = '.3s'; t.style.opacity = '0'; t.style.transform = 'translateX(12px)'; setTimeout(() => t.remove(), 320); }, 3600);
}

// --------------------------------------------------------------- drawer
export function drawer(title, bodyHTML, { footer = '', wide = false, onMount } = {}) {
  closeDrawer();
  const scrim = h('<div class="scrim"></div>');
  const d = h(`<aside class="drawer ${wide ? 'wide' : ''}">
    <div class="drawer-h">${title}<div class="spacer" style="flex:1"></div>
      <button class="btn-icon" data-x>${icon('x')}</button></div>
    <div class="drawer-b">${bodyHTML}</div>
    ${footer ? `<div class="drawer-f">${footer}</div>` : ''}</aside>`);
  document.body.append(scrim, d);
  scrim.onclick = closeDrawer; d.querySelector('[data-x]').onclick = closeDrawer;
  onMount?.(d);
  return d;
}
export function closeDrawer() { $$('.scrim,.drawer').forEach(e => e.remove()); }
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });

// ---------------------------------------------------------------- icons
const P = {
  grid: 'M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z',
  list: 'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
  plus: 'M12 5v14M5 12h14',
  file: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6',
  users: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
  activity: 'M22 12h-4l-3 9L9 3l-3 9H2',
  phone: 'M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.9.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z',
  sliders: 'M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6',
  shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  book: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z',
  chart: 'M18 20V10M12 20V4M6 20v-6',
  cpu: 'M4 4h16v16H4zM9 9h6v6H9zM9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3',
  search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.35-4.35',
  bell: 'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0',
  x: 'M18 6 6 18M6 6l12 12',
  chevron: 'M9 18l6-6-6-6',
  down: 'M6 9l6 6 6-6',
  check: 'M20 6 9 17l-5-5',
  alert: 'M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01',
  scale: 'M12 3v18M5 7h14M7 7l-3 7h6zM17 7l-3 7h6zM7 21h10',
  power: 'M18.36 6.64a9 9 0 1 1-12.73 0M12 2v10',
  msg: 'M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8z',
  up: 'M23 6l-9.5 9.5-5-5L1 18',
  clock: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2',
  target: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12zM12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4z',
  layers: 'M12 2 2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5',
  refresh: 'M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15',
  send: 'M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z',
  download: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3',
  eye: 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  home: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10',
  user: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8',
};
export const icon = (n, s = 16, cls = '') =>
  `<svg class="ico ${cls}" width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${P[n] || P.grid}"/></svg>`;

// --------------------------------------------------------------- charts
export function lineChart(series, { w = 640, h = 170, keys = [], colors = ['#4d7cfe', '#2ecc8f', '#f5a623'], labels = [], area = true } = {}) {
  const pad = { l: 30, r: 8, t: 10, b: 20 };
  const max = Math.max(1, ...series.flatMap(d => keys.map(k => d[k])));
  const X = i => pad.l + i * (w - pad.l - pad.r) / Math.max(1, series.length - 1);
  const Y = v => h - pad.b - (v / max) * (h - pad.t - pad.b);
  let out = `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px;overflow:visible">`;
  for (let g = 0; g <= 4; g++) { const y = pad.t + g * (h - pad.t - pad.b) / 4;
    out += `<line x1="${pad.l}" x2="${w - pad.r}" y1="${y}" y2="${y}" stroke="#1e2a3d" stroke-dasharray="2 4"/>
            <text x="${pad.l - 6}" y="${y + 3}" fill="#495a75" font-size="9" text-anchor="end">${Math.round(max - g * max / 4)}</text>`; }
  keys.forEach((k, ki) => {
    const pts = series.map((d, i) => `${X(i)},${Y(d[k])}`).join(' ');
    if (area) out += `<polygon points="${pad.l},${h - pad.b} ${pts} ${X(series.length - 1)},${h - pad.b}" fill="${colors[ki]}" opacity=".08"/>`;
    out += `<polyline points="${pts}" fill="none" stroke="${colors[ki]}" stroke-width="2" stroke-linejoin="round"/>`;
    series.forEach((d, i) => { out += `<circle cx="${X(i)}" cy="${Y(d[k])}" r="2.4" fill="${colors[ki]}"><title>${labels[ki] || k}: ${d[k]}</title></circle>`; });
  });
  series.forEach((d, i) => { if (i % Math.ceil(series.length / 8) === 0)
    out += `<text x="${X(i)}" y="${h - 5}" fill="#495a75" font-size="9" text-anchor="middle">${d.d || d.month?.slice(5) || i}</text>`; });
  return out + '</svg>';
}

export function barChart(data, { w = 620, h = 160, color = '#4d7cfe', threshold = null, thresholdLabel = '' } = {}) {
  const pad = { l: 28, r: 8, t: 12, b: 22 };
  const max = Math.max(1, ...data.map(d => d.v), threshold || 0);
  const bw = (w - pad.l - pad.r) / data.length;
  let out = `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px;overflow:visible">`;
  data.forEach((d, i) => {
    const bh = (d.v / max) * (h - pad.t - pad.b);
    const x = pad.l + i * bw + bw * .16, y = h - pad.b - bh;
    out += `<rect x="${x}" y="${y}" width="${bw * .68}" height="${Math.max(1, bh)}" rx="3"
      fill="${d.color || color}" opacity="${d.dim ? .35 : .9}"><title>${d.l}: ${d.v}</title></rect>`;
    out += `<text x="${x + bw * .34}" y="${h - 7}" fill="#495a75" font-size="9" text-anchor="middle">${d.l}</text>`;
  });
  if (threshold != null) { const y = h - pad.b - (threshold / max) * (h - pad.t - pad.b);
    out += `<line x1="${pad.l}" x2="${w - pad.r}" y1="${y}" y2="${y}" stroke="#f2545b" stroke-width="1.2" stroke-dasharray="4 3"/>
            <text x="${w - pad.r}" y="${y - 4}" fill="#f2545b" font-size="9" text-anchor="end">${thresholdLabel}</text>`; }
  return out + '</svg>';
}

export function gauge(value, { size = 132, color = '#4d7cfe', label = '', sub = '' } = {}) {
  const r = size / 2 - 12, c = 2 * Math.PI * r, off = c * (1 - Math.min(1, Math.max(0, value)));
  return `<div class="gauge" style="height:${size}px">
    <svg width="${size}" height="${size}" style="transform:rotate(-90deg)">
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="#1b2436" stroke-width="9"/>
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${color}" stroke-width="9"
        stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}"
        style="transition:stroke-dashoffset .8s cubic-bezier(.4,0,.2,1)"/></svg>
    <div class="lbl"><b>${label}</b><span>${sub}</span></div></div>`;
}

export function donut(entries, { size = 128, colors = {} } = {}) {
  const total = entries.reduce((a, e) => a + e.v, 0) || 1;
  const r = size / 2 - 10, c = 2 * Math.PI * r; let acc = 0;
  let out = `<svg width="${size}" height="${size}" style="transform:rotate(-90deg)">`;
  entries.forEach(e => {
    const frac = e.v / total;
    out += `<circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${colors[e.k] || e.color || '#4d7cfe'}"
      stroke-width="11" stroke-dasharray="${frac * c} ${c}" stroke-dashoffset="${-acc * c}"><title>${e.k}: ${e.v}</title></circle>`;
    acc += frac;
  });
  return out + '</svg>';
}

export function spark(values, { w = 90, h = 30, color = '#4d7cfe' } = {}) {
  if (!values.length) return '';
  const max = Math.max(...values), min = Math.min(...values), rng = max - min || 1;
  const pts = values.map((v, i) => `${i * w / (values.length - 1)},${h - ((v - min) / rng) * (h - 4) - 2}`).join(' ');
  return `<svg class="spark" width="${w}" height="${h}"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.6"/></svg>`;
}

export function stepChart(series, { w = 620, h = 150, threshold = null } = {}) {
  const pad = { l: 28, r: 10, t: 12, b: 22 };
  const max = Math.max(3, ...series.map(d => d.days_late));
  const X = i => pad.l + i * (w - pad.l - pad.r) / Math.max(1, series.length - 1);
  const Y = v => h - pad.b - (v / max) * (h - pad.t - pad.b);
  let out = `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px;overflow:visible">`;
  out += `<line x1="${pad.l}" x2="${w - pad.r}" y1="${Y(0)}" y2="${Y(0)}" stroke="#2ecc8f" stroke-dasharray="3 3" opacity=".5"/>`;
  if (threshold != null && threshold > 0) out += `<line x1="${pad.l}" x2="${w - pad.r}" y1="${Y(threshold)}" y2="${Y(threshold)}" stroke="#f5a623" stroke-dasharray="4 3" opacity=".7"/>`;
  const pts = series.map((d, i) => `${X(i)},${Y(d.days_late)}`).join(' ');
  out += `<polygon points="${pad.l},${Y(0)} ${pts} ${X(series.length - 1)},${Y(0)}" fill="#f5a623" opacity=".1"/>`;
  out += `<polyline points="${pts}" fill="none" stroke="#f5a623" stroke-width="2"/>`;
  series.forEach((d, i) => {
    const col = d.days_late === 0 ? '#2ecc8f' : d.days_late <= 5 ? '#f5a623' : '#f2545b';
    out += `<circle cx="${X(i)}" cy="${Y(d.days_late)}" r="3" fill="${col}"><title>${d.month}: ${d.days_late} days late</title></circle>`;
    if (i % 3 === 0) out += `<text x="${X(i)}" y="${h - 6}" fill="#495a75" font-size="8.5" text-anchor="middle">${d.month.slice(2, 7)}</text>`;
  });
  return out + '</svg>';
}
