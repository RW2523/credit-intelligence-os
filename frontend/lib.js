import { lang } from '/i18n.js';

// ---------------------------------------------------------------- helpers
export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];

export function h(html) { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; }
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// Ringgit, Malaysia time, en-MY / ms-MY
const TZ = 'Asia/Kuala_Lumpur';
const loc = () => (lang() === 'ms' ? 'ms-MY' : 'en-MY');
export const money = (n, d = 0) => {
  const v = Number(n || 0);
  return (v < 0 ? '-RM' : 'RM') + Math.abs(v).toLocaleString('en-MY', { minimumFractionDigits: d, maximumFractionDigits: d });
};
export const pct = (n, d = 1) => `${(Number(n) * 100).toFixed(d)}%`;
export const num = (n, d = 0) => Number(n || 0).toLocaleString('en-MY', { minimumFractionDigits: d, maximumFractionDigits: d });
const asDate = s => new Date(/^\d{4}-\d{2}-\d{2}$/.test(s) ? `${s}T00:00:00+08:00` : s);
export const date = s => s ? asDate(s).toLocaleDateString(loc(), { timeZone: TZ, day: 'numeric', month: 'short', year: 'numeric' }) : '—';
export const month = s => s ? asDate(s).toLocaleDateString(loc(), { timeZone: TZ, month: 'short', year: 'numeric' }) : '—';
export const dtime = s => s ? asDate(s).toLocaleString(loc(), { timeZone: TZ, day: 'numeric', month: 'short', year: 'numeric',
  hour: '2-digit', minute: '2-digit', hour12: false }) : '—';
export const time = s => s ? asDate(s).toLocaleTimeString(loc(), { timeZone: TZ, hour: '2-digit', minute: '2-digit', hour12: false }) : '';
let clockOffset = 0;                          // server "now" minus browser now — keeps "today" right on a frozen demo day
export function setServerNow(iso) { if (iso) clockOffset = new Date(iso) - Date.now(); }
export const nowMs = () => Date.now() + clockOffset;
export const ago = s => {
  if (!s) return '—';
  const d = (nowMs() - asDate(s)) / 864e5;
  const ms = lang() === 'ms';
  return d < 1 ? (ms ? 'hari ini' : 'today') : d < 2 ? (ms ? 'semalam' : 'yesterday') : ms ? `${Math.floor(d)} hari lalu` : `${Math.floor(d)}d ago`;
};

export const toneFor = v => ({
  Low: 'green', Moderate: 'amber', Elevated: 'amber', High: 'red', Watch: 'amber',
  PASS: 'green', FAIL: 'red', Match: 'green', Review: 'amber', Mismatch: 'red', Insufficient: 'grey',
  Support: 'green', Caution: 'amber', Concern: 'amber', Oppose: 'red',
  Clear: 'green', Critical: 'red',
  STABLE: 'green', WATCH: 'cyan', ELEVATED: 'amber', AT_RISK: 'red', RECOVERY: 'purple',
  APPROVE: 'green', DECLINE: 'red', 'OFFICER REVIEW': 'amber', 'REQUEST INFORMATION': 'blue', INVESTIGATE: 'red',
  Verified: 'green', 'Needs Review': 'amber', Rejected: 'red',
  Approved: 'green', Declined: 'red', Escalated: 'purple', P1: 'red', P2: 'amber', P3: 'blue',
  AUTONOMOUS: 'purple', HUMAN: 'blue', Approve: 'green', Decline: 'red', 'Refer to officer': 'amber',
  'Request info': 'blue', 'Request Information': 'blue', Escalate: 'purple',
}[v] || 'grey');

export const tag = (v, tone) => `<span class="tag t-${tone || toneFor(v)}">${esc(v)}</span>`;

// ------------------------------------------------------------------- api
export async function api(path, opts = {}) {
  const r = await fetch('/api' + path, {
    credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, ...opts,
    body: opts.body && typeof opts.body !== 'string' ? JSON.stringify(opts.body) : opts.body,
  });
  if (r.status === 401 && !path.startsWith('/auth/')) { window.dispatchEvent(new Event('kt:signed-out')); }
  if (!r.ok) { let m; try { m = (await r.json()).detail; } catch { m = r.statusText; } const e = new Error(m || 'request failed'); e.status = r.status; throw e; }
  return r.json();
}

export function sse(path, handlers, opts = {}) {
  const ctrl = new AbortController();
  (async () => {
    const r = await fetch('/api' + path, { signal: ctrl.signal, method: opts.method || 'GET', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: opts.body ? JSON.stringify(opts.body) : undefined });
    if (r.status === 401) { window.dispatchEvent(new Event('kt:signed-out')); return; }
    if (!r.ok) { let m; try { m = (await r.json()).detail; } catch { m = r.statusText; } handlers.error?.({ message: m }); return; }
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
  let w = $('.toast-wrap'); if (!w) { w = h('<div class="toast-wrap" role="status" aria-live="polite"></div>'); document.body.appendChild(w); }
  const t = h(`<div class="toast ${kind}"><b>${esc(title)}</b>${sub ? `<span>${esc(sub)}</span>` : ''}</div>`);
  w.appendChild(t);
  setTimeout(() => { t.style.transition = '.3s'; t.style.opacity = '0'; t.style.transform = 'translateX(12px)'; setTimeout(() => t.remove(), 320); }, 4200);
}

// --------------------------------------------------------------- drawer
export function drawer(title, bodyHTML, { footer = '', wide = false, onMount } = {}) {
  closeDrawer();
  const scrim = h('<div class="scrim"></div>');
  const d = h(`<aside class="drawer ${wide ? 'wide' : ''}" role="dialog" aria-modal="true">
    <div class="drawer-h">${title}<div class="spacer" style="flex:1"></div>
      <button class="btn-icon" data-x aria-label="Close">${icon('x')}</button></div>
    <div class="drawer-b">${bodyHTML}</div>
    ${footer ? `<div class="drawer-f">${footer}</div>` : ''}</aside>`);
  document.body.append(scrim, d);
  scrim.onclick = closeDrawer; d.querySelector('[data-x]').onclick = closeDrawer;
  onMount?.(d);
  return d;
}
export function closeDrawer() { $$('.scrim,.drawer').forEach(e => e.remove()); }
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });

// ---------------------------------------------------------------- markdown
// A deliberately small renderer for assistant answers: escaped first, then bold, code, lists and tables.
export function md(text) {
  const lines = esc(text || '').split('\n');
  const out = []; let list = null, table = null;
  const inline = s => s.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>');
  const flush = () => {
    if (list) { out.push(`<${list.t}>${list.items.map(i => `<li>${inline(i)}</li>`).join('')}</${list.t}>`); list = null; }
    if (table) {
      const rows = table.filter(r => !/^\s*\|?\s*:?-{2,}/.test(r));
      const cells = r => r.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map(c => inline(c.trim()));
      const [head, ...body] = rows;
      out.push(`<div class="tw md-table"><table><thead><tr>${cells(head).map(c => `<th>${c}</th>`).join('')}</tr></thead>
        <tbody>${body.map(r => `<tr>${cells(r).map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
      table = null;
    }
  };
  for (const raw of lines) {
    const l = raw.trimEnd();
    if (/^\s*\|.*\|\s*$/.test(l)) { if (list) flush(); (table ||= []).push(l); continue; }
    if (table) flush();
    let m;
    if ((m = l.match(/^\s*[-*•]\s+(.*)$/))) { if (!list || list.t !== 'ul') { flush(); list = { t: 'ul', items: [] }; } list.items.push(m[1]); continue; }
    if ((m = l.match(/^\s*\d+[.)]\s+(.*)$/))) { if (!list || list.t !== 'ol') { flush(); list = { t: 'ol', items: [] }; } list.items.push(m[1]); continue; }
    flush();
    if ((m = l.match(/^#{1,4}\s+(.*)$/))) { out.push(`<div class="md-h">${inline(m[1])}</div>`); continue; }
    if (l.trim()) out.push(`<p>${inline(l)}</p>`);
  }
  flush();
  return out.join('');
}

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
  back: 'M15 18l-6-6 6-6',
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
  upload: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12',
  eye: 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  home: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10',
  user: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8',
  sun: 'M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4',
  moon: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8',
  logout: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9',
  globe: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z',
  lock: 'M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4',
  gift: 'M20 12v10H4V12M2 7h20v5H2zM12 22V7M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7zM12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z',
  coins: 'M8 12a6 6 0 1 0 0-12 6 6 0 0 0 0 12zM18.09 10.37A6 6 0 1 1 10.34 18M7 6h1v4M16.71 13.88l.7.71-2.82 2.82',
  calc: 'M4 2h16v20H4zM8 6h8M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01M16 18h.01',
  flag: 'M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7',
  info: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 16v-4M12 8h.01',
  print: 'M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2M6 14h12v8H6z',
};
export const icon = (n, s = 16, cls = '') =>
  `<svg class="ico ${cls}" width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"
    stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${P[n] || P.grid}"/></svg>`;

// --------------------------------------------------------------- charts
// Every chart carries a legend and a hover tooltip. Line charts snap a crosshair to the nearest day and
// list every visible series; legend items toggle a series on and off.
const PALETTE = ['var(--brand)', 'var(--green)', 'var(--amber)', 'var(--violet)', 'var(--cyan)', 'var(--red)'];
const enc = o => esc(JSON.stringify(o));

export function lineChart(series, { w = 640, h = 170, keys = [], colors = PALETTE, labels = [], area = true,
                                   xKey = 'd', unit = '', legend = true, yFmt = null } = {}) {
  const pad = { l: 36, r: 10, t: 12, b: 22 };
  const max = Math.max(1, ...series.flatMap(d => keys.map(k => d[k])));
  const n = series.length;
  const X = i => pad.l + i * (w - pad.l - pad.r) / Math.max(1, n - 1);
  const Y = v => h - pad.b - (v / max) * (h - pad.t - pad.b);
  const yf = yFmt || (v => unit === 'RM' ? money(v) : num(v));
  let svg = `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px;overflow:visible" role="img">`;
  for (let g = 0; g <= 4; g++) {
    const y = pad.t + g * (h - pad.t - pad.b) / 4;
    svg += `<line x1="${pad.l}" x2="${w - pad.r}" y1="${y}" y2="${y}" style="stroke:var(--line-2)" stroke-dasharray="2 4"/>
            <text x="${pad.l - 6}" y="${y + 3}" style="fill:var(--ink-4)" font-size="9" text-anchor="end">${esc(yf(Math.round(max - g * max / 4)))}</text>`;
  }
  keys.forEach((k, ki) => {
    const pts = series.map((d, i) => `${X(i)},${Y(d[k])}`).join(' ');
    svg += `<g class="ser" data-k="${ki}">`;
    if (area) svg += `<polygon points="${pad.l},${h - pad.b} ${pts} ${X(n - 1)},${h - pad.b}" style="fill:${colors[ki]}" opacity=".07"/>`;
    svg += `<polyline points="${pts}" fill="none" style="stroke:${colors[ki]}" stroke-width="2" stroke-linejoin="round"/>`;
    series.forEach((d, i) => { svg += `<circle class="pt" data-i="${i}" cx="${X(i)}" cy="${Y(d[k])}" r="2.6" style="fill:${colors[ki]}"/>`; });
    svg += '</g>';
  });
  const step = Math.ceil(n / 8);
  series.forEach((d, i) => { if (i % step === 0 || i === n - 1)
    svg += `<text x="${X(i)}" y="${h - 5}" style="fill:var(--ink-4)" font-size="9" text-anchor="middle">${esc(d[xKey] ?? d.month?.slice(5) ?? i)}</text>`; });
  svg += `<line class="xhair" x1="0" x2="0" y1="${pad.t}" y2="${h - pad.b}" style="stroke:var(--ink-3);display:none" stroke-dasharray="3 3"/></svg>`;
  const meta = { x0: pad.l, dx: (w - pad.l - pad.r) / Math.max(1, n - 1), w, n, unit,
    labels: keys.map((k, i) => labels[i] || k), colors: keys.map((_, i) => colors[i]),
    rows: series.map(d => ({ x: d[xKey] ?? d.month ?? '', v: keys.map(k => d[k]) })) };
  return `<div class="chart" data-kind="line" data-meta="${enc(meta)}">${svg}<div class="ch-tip"></div>
    ${legend ? legendHTML(meta.labels, meta.colors, true) : ''}</div>`;
}

function legendHTML(labels, colors, toggle) {
  return `<div class="legend">${labels.map((l, i) => `<button class="lgd" data-k="${i}" ${toggle ? '' : 'disabled'}
    aria-pressed="true"><i style="background:${colors[i]}"></i>${esc(l)}</button>`).join('')}</div>`;
}

export function barChart(data, { w = 620, h = 160, color = 'var(--brand)', threshold = null, thresholdLabel = '',
                                 unit = '', legend = null } = {}) {
  const pad = { l: 36, r: 8, t: 12, b: 24 };
  const max = Math.max(1, ...data.map(d => d.v), threshold || 0);
  const bw = (w - pad.l - pad.r) / Math.max(1, data.length);
  const vf = v => unit === 'RM' ? money(v) : unit === '%' ? `${num(v, 1)}%` : num(v);
  let svg = `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px;overflow:visible" role="img">`;
  for (let g = 0; g <= 3; g++) {
    const y = pad.t + g * (h - pad.t - pad.b) / 3;
    svg += `<line x1="${pad.l}" x2="${w - pad.r}" y1="${y}" y2="${y}" style="stroke:var(--line-2)" stroke-dasharray="2 4"/>
      <text x="${pad.l - 6}" y="${y + 3}" style="fill:var(--ink-4)" font-size="9" text-anchor="end">${esc(vf(Math.round(max - g * max / 3)))}</text>`;
  }
  data.forEach((d, i) => {
    const bh = (d.v / max) * (h - pad.t - pad.b);
    const x = pad.l + i * bw + bw * .16, y = h - pad.b - bh;
    svg += `<rect x="${x}" y="${y}" width="${bw * .68}" height="${Math.max(1, bh)}" rx="3" class="bar-r"
      data-tip="${esc(`${d.l}: ${vf(d.v)}${d.note ? ' · ' + d.note : ''}`)}" style="fill:${d.color || color}" opacity="${d.dim ? .35 : .9}"/>`;
    svg += `<text x="${x + bw * .34}" y="${h - 8}" style="fill:var(--ink-4)" font-size="9" text-anchor="middle">${esc(String(d.l).slice(0, 18))}</text>`;
  });
  if (threshold != null) { const y = h - pad.b - (threshold / max) * (h - pad.t - pad.b);
    svg += `<line x1="${pad.l}" x2="${w - pad.r}" y1="${y}" y2="${y}" style="stroke:var(--red)" stroke-width="1.2" stroke-dasharray="4 3"/>
            <text x="${w - pad.r}" y="${y - 4}" style="fill:var(--red)" font-size="9" text-anchor="end">${esc(thresholdLabel)}</text>`; }
  svg += '</svg>';
  return `<div class="chart" data-kind="bar">${svg}<div class="ch-tip"></div>${legend ? legendHTML(legend.labels, legend.colors, false) : ''}</div>`;
}

export function gauge(value, { size = 132, color = 'var(--brand)', label = '', sub = '' } = {}) {
  const r = size / 2 - 12, c = 2 * Math.PI * r, off = c * (1 - Math.min(1, Math.max(0, value)));
  return `<div class="gauge" style="height:${size}px">
    <svg width="${size}" height="${size}" style="transform:rotate(-90deg)" aria-hidden="true">
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" style="stroke:var(--track)" stroke-width="9"/>
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" style="stroke:${color}" stroke-width="9"
        stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}"
        style="transition:stroke-dashoffset .8s cubic-bezier(.4,0,.2,1)"/></svg>
    <div class="lbl"><b>${label}</b><span>${sub}</span></div></div>`;
}

export function donut(entries, { size = 128, colors = {} } = {}) {
  const total = entries.reduce((a, e) => a + e.v, 0) || 1;
  const r = size / 2 - 10, c = 2 * Math.PI * r; let acc = 0;
  let out = `<div class="chart" data-kind="donut" style="width:${size}px"><svg width="${size}" height="${size}" style="transform:rotate(-90deg)">`;
  entries.forEach(e => {
    const frac = e.v / total;
    out += `<circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" style="stroke:${colors[e.k] || e.color || 'var(--brand)'}"
      stroke-width="12" stroke-dasharray="${frac * c} ${c}" stroke-dashoffset="${-acc * c}"
      data-tip="${esc(`${e.k}: ${e.v} (${Math.round(frac * 100)}%)`)}"/>`;
    acc += frac;
  });
  return out + '</svg><div class="ch-tip"></div></div>';
}

export function spark(values, { w = 90, h = 30, color = 'var(--brand)' } = {}) {
  if (!values.length) return '';
  const max = Math.max(...values), min = Math.min(...values), rng = max - min || 1;
  const pts = values.map((v, i) => `${i * w / (values.length - 1)},${h - ((v - min) / rng) * (h - 4) - 2}`).join(' ');
  return `<svg class="spark" width="${w}" height="${h}" aria-hidden="true"><polyline points="${pts}" fill="none" style="stroke:${color}" stroke-width="1.6"/></svg>`;
}

export function stepChart(series, { w = 620, h = 150, threshold = null } = {}) {
  if (!series.length) return `<div class="empty small">${lang() === 'ms' ? 'Tiada sejarah potongan untuk dipantau.' : 'No deduction history to monitor.'}</div>`;
  const pad = { l: 30, r: 10, t: 12, b: 22 };
  const max = Math.max(3, ...series.map(d => d.days_late));
  const X = i => pad.l + i * (w - pad.l - pad.r) / Math.max(1, series.length - 1);
  const Y = v => h - pad.b - (v / max) * (h - pad.t - pad.b);
  let out = `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px;overflow:visible" role="img">`;
  out += `<line x1="${pad.l}" x2="${w - pad.r}" y1="${Y(0)}" y2="${Y(0)}" style="stroke:var(--green)" stroke-dasharray="3 3" opacity=".5"/>`;
  if (threshold != null && threshold > 0) out += `<line x1="${pad.l}" x2="${w - pad.r}" y1="${Y(threshold)}" y2="${Y(threshold)}" style="stroke:var(--amber)" stroke-dasharray="4 3" opacity=".7"/>`;
  for (let g = 0; g <= 2; g++) { const v = Math.round(max * g / 2);
    out += `<text x="${pad.l - 6}" y="${Y(v) + 3}" style="fill:var(--ink-4)" font-size="9" text-anchor="end">${v}</text>`; }
  const pts = series.map((d, i) => `${X(i)},${Y(d.days_late)}`).join(' ');
  out += `<polygon points="${pad.l},${Y(0)} ${pts} ${X(series.length - 1)},${Y(0)}" style="fill:var(--amber)" opacity=".1"/>`;
  out += `<polyline points="${pts}" fill="none" style="stroke:var(--amber)" stroke-width="2"/>`;
  const ms = lang() === 'ms';
  series.forEach((d, i) => {
    const col = d.days_late === 0 ? 'var(--green)' : d.days_late <= 5 ? 'var(--amber)' : 'var(--red)';
    out += `<circle cx="${X(i)}" cy="${Y(d.days_late)}" r="3.4" style="fill:${col}"
      data-tip="${esc(`${month(d.month)}: ${d.days_late === 0 ? (ms ? 'tepat masa' : 'on time') : d.days_late + (ms ? ' hari lewat' : ' days late')}`)}"/>`;
    if (i % 3 === 0) out += `<text x="${X(i)}" y="${h - 6}" style="fill:var(--ink-4)" font-size="8.5" text-anchor="middle">${esc(month(d.month))}</text>`;
  });
  out += '</svg>';
  const leg = ms ? ['Tepat masa', 'Lewat ≤ 5 hari', 'Lewat > 5 hari', 'Ambang peribadi'] : ['On time', 'Late ≤ 5 days', 'Late > 5 days', 'Personal threshold'];
  return `<div class="chart" data-kind="step">${out}<div class="ch-tip"></div>${legendHTML(leg, ['var(--green)', 'var(--amber)', 'var(--red)', 'var(--amber)'], false)}</div>`;
}

// ---- chart interactivity (delegated, so every chart on every view gets it)
function tipAt(chart, html, e) {
  const tip = chart.querySelector('.ch-tip'); if (!tip) return;
  tip.innerHTML = html; tip.style.display = 'block';
  const r = chart.getBoundingClientRect();
  let x = e.clientX - r.left + 14, y = e.clientY - r.top + 12;
  if (x + tip.offsetWidth > r.width) x = e.clientX - r.left - tip.offsetWidth - 14;
  tip.style.left = Math.max(0, x) + 'px'; tip.style.top = Math.max(0, y) + 'px';
}
document.addEventListener('mousemove', e => {
  const chart = e.target.closest?.('.chart');
  $$('.chart .ch-tip').forEach(t => { if (!chart || !chart.contains(t)) t.style.display = 'none'; });
  if (!chart) return;
  if (chart.dataset.kind === 'line') {
    const svg = chart.querySelector('svg'); const m = JSON.parse(chart.dataset.meta);
    const r = svg.getBoundingClientRect();
    const vb = svg.viewBox.baseVal, scale = Math.min(r.width / vb.width, r.height / vb.height);
    const xv = (e.clientX - r.left - (r.width - vb.width * scale) / 2) / scale;
    const i = Math.max(0, Math.min(m.n - 1, Math.round((xv - m.x0) / m.dx)));
    const xh = svg.querySelector('.xhair'); const X = m.x0 + i * m.dx;
    xh.setAttribute('x1', X); xh.setAttribute('x2', X); xh.style.display = '';
    svg.querySelectorAll('.pt').forEach(c => c.classList.toggle('on', +c.dataset.i === i));
    const row = m.rows[i];
    const hidden = new Set([...chart.querySelectorAll('.lgd[aria-pressed=false]')].map(b => +b.dataset.k));
    const fv = v => m.unit === 'RM' ? money(v) : num(v);
    tipAt(chart, `<b>${esc(row.x)}</b>` + m.labels.map((l, k) => hidden.has(k) ? '' :
      `<div class="row" style="gap:6px"><i class="sw" style="background:${m.colors[k]}"></i><span style="flex:1">${esc(l)}</span><b>${esc(fv(row.v[k]))}</b></div>`).join(''), e);
    return;
  }
  const t = e.target.closest?.('[data-tip]');
  if (t && chart.contains(t)) tipAt(chart, esc(t.dataset.tip), e);
  else { const tip = chart.querySelector('.ch-tip'); if (tip) tip.style.display = 'none'; }
});
document.addEventListener('mouseleave', e => {
  if (!e.target.closest) return;
  const chart = e.target.closest('.chart'); if (!chart || e.target !== chart) return;
  chart.querySelectorAll('.ch-tip').forEach(t => t.style.display = 'none');
  chart.querySelector('.xhair')?.style.setProperty('display', 'none');
  chart.querySelectorAll('.pt.on').forEach(c => c.classList.remove('on'));
}, true);
document.addEventListener('click', e => {
  const b = e.target.closest?.('.chart .lgd'); if (!b || b.disabled) return;
  const on = b.getAttribute('aria-pressed') !== 'false';
  b.setAttribute('aria-pressed', on ? 'false' : 'true');
  b.closest('.chart').querySelectorAll(`.ser[data-k="${b.dataset.k}"]`).forEach(s => s.style.display = on ? 'none' : '');
});
