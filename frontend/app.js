import { $, h, api, icon, esc, toast, closeDrawer } from '/lib.js';
import * as views from '/views/index.js';

export const state = {
  view: 'overview', param: null, boot: null, role: 'officer', notifications: [], badge: {},
};

const NAV = [
  { g: 'Origination', items: [
    { id: 'overview', name: 'Portfolio Overview', icon: 'grid' },
    { id: 'applications', name: 'Applications', icon: 'list', badge: 'apps' },
    { id: 'intake', name: 'New Application', icon: 'plus' },
    { id: 'documents', name: 'Document Intelligence', icon: 'file' },
  ]},
  { g: 'Members & Servicing', items: [
    { id: 'members', name: 'Member 360', icon: 'users' },
    { id: 'early-warning', name: 'Early Warning', icon: 'activity', badge: 'ew' },
    { id: 'collections', name: 'Collections', icon: 'phone', badge: 'coll' },
  ]},
  { g: 'Governance', items: [
    { id: 'cockpit', name: 'Management Cockpit', icon: 'chart' },
    { id: 'sandbox', name: 'Policy Sandbox', icon: 'sliders' },
    { id: 'governance', name: 'Model Governance', icon: 'cpu' },
    { id: 'ledger', name: 'Decision Ledger', icon: 'book' },
  ]},
  { g: 'Assistants', items: [
    { id: 'member-portal', name: 'Member Assistant', icon: 'msg' },
  ]},
];

// -------------------------------------------------------------- routing
export function go(view, param = null) {
  state.view = view; state.param = param;
  closeDrawer();
  location.hash = param ? `#${view}/${param}` : `#${view}`;
  render();
}
window.addEventListener('hashchange', () => {
  const [v, p] = location.hash.slice(1).split('/');
  if (v && (v !== state.view || (p || null) !== state.param)) { state.view = v; state.param = p || null; render(); }
});
window.go = go;

// ---------------------------------------------------------------- shell
function shell() {
  const u = state.boot.roles[state.role];
  return `
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">CI</div>
      <div class="brand-txt"><b>Credit Intelligence</b><span>Operating System</span></div>
    </div>
    <nav class="nav">
      ${NAV.map(g => `<div class="nav-group">${g.g}</div>` + g.items.map(i => `
        <button class="nav-item ${state.view === i.id ? 'on' : ''}" data-go="${i.id}">
          ${icon(i.icon)} <span>${i.name}</span>
          ${state.badge[i.badge] ? `<span class="pill ${i.badge === 'ew' ? 'hot' : ''}">${state.badge[i.badge]}</span>` : ''}
        </button>`).join('')).join('')}
    </nav>
    <div class="sidebar-foot">
      <div class="row" style="gap:9px">
        <div class="avatar">${u.initials}</div>
        <div style="min-width:0;flex:1">
          <div style="font-size:12px;font-weight:600" class="truncate">${u.name}</div>
          <div class="tiny muted">${u.role}</div>
        </div>
      </div>
      <select class="inp" id="roleSel" style="margin-top:8px;height:30px;font-size:12px">
        ${Object.entries(state.boot.roles).map(([k, r]) =>
          `<option value="${k}" ${k === state.role ? 'selected' : ''}>${r.role}</option>`).join('')}
      </select>
    </div>
  </aside>
  <div class="main">
    <header class="topbar">
      <div class="crumbs">${icon('layers', 14)}<b>${navName(state.view)}</b>${state.param ? `<span>/</span><span class="mono">${esc(state.param)}</span>` : ''}</div>
      <div class="search">
        <span class="si">${icon('search', 15)}</span>
        <input id="gsearch" placeholder="Search members, applications, documents, policies…" autocomplete="off"/>
        <div id="sresults"></div>
      </div>
      <div class="top-actions">
        <span class="tag t-${state.boot.llm.available ? 'green' : 'amber'}" title="Local model">
          ${icon('cpu', 12)} ${state.boot.llm.available ? esc(state.boot.llm.model) : 'deterministic mode'}</span>
        <span class="tag t-${state.boot.autonomy.kill_switch ? 'red' : 'purple'}">${icon('power', 12)} ${state.boot.autonomy.kill_switch ? 'STOPPED' : esc(state.boot.autonomy.mode)}</span>
        <button class="btn-icon" id="bell">${icon('bell')}${state.notifications.length ? '<i class="dot-badge"></i>' : ''}</button>
        <button class="btn-icon" id="refresh" title="Refresh">${icon('refresh')}</button>
      </div>
    </header>
    <main class="content" id="content"><div class="center"><div class="spin"></div></div></main>
  </div>`;
}
const navName = id => NAV.flatMap(g => g.items).find(i => i.id === id)?.name || id;

// ---------------------------------------------------------------- render
export async function render() {
  closeDrawer();
  const app = $('#app');
  if (!app.querySelector('.sidebar')) app.innerHTML = shell();
  else {
    app.querySelector('.sidebar').outerHTML = h(shell()).outerHTML;
    $('.crumbs').innerHTML = `${icon('layers', 14)}<b>${navName(state.view)}</b>${state.param ? `<span>/</span><span class="mono">${esc(state.param)}</span>` : ''}`;
  }
  bindShell();
  const el = $('#content');
  el.innerHTML = '<div class="center"><div class="spin"></div></div>';
  const alias = { 'early-warning': 'earlyWarning', 'member-portal': 'memberPortal' };
  const fn = views[alias[state.view] || state.view] || views.overview;
  try { await fn(el, state.param); } catch (e) {
    console.error(e);
    el.innerHTML = `<div class="empty">${icon('alert', 28)}<b>${esc(e.message)}</b>
      <span class="small">Something went wrong rendering this view.</span></div>`;
  }
}
window.render = render;

function bindShell() {
  document.querySelectorAll('[data-go]').forEach(b => b.onclick = () => go(b.dataset.go));
  const sel = $('#roleSel');
  if (sel) sel.onchange = e => {
    state.role = e.target.value;
    const allowed = state.boot.roles[state.role].views;
    toast('Role switched', state.boot.roles[state.role].name);
    go(allowed.includes(state.view) ? state.view : allowed[0]);
  };
  $('#refresh').onclick = async () => { await refreshMeta(); render(); toast('Refreshed'); };
  $('#bell').onclick = showNotifications;
  bindSearch();
}

let searchTimer;
function bindSearch() {
  const inp = $('#gsearch'), box = $('#sresults');
  inp.oninput = () => {
    clearTimeout(searchTimer);
    const q = inp.value.trim();
    if (q.length < 2) { box.innerHTML = ''; return; }
    searchTimer = setTimeout(async () => {
      const { rows } = await api('/search?q=' + encodeURIComponent(q));
      box.innerHTML = rows.length ? `<div class="search-results">${rows.map(r => `
        <button class="sr-item" data-link="${r.link}">
          <span class="sr-kind">${r.kind}</span>
          <span style="flex:1;min-width:0"><div style="font-size:12.5px">${esc(r.title)}</div>
          <div class="tiny muted">${esc(r.sub)}</div></span>${icon('chevron', 13)}</button>`).join('')}</div>`
        : `<div class="search-results"><div class="empty small">No matches for “${esc(q)}”</div></div>`;
      box.querySelectorAll('[data-link]').forEach(b => b.onclick = () => {
        const [v, p] = b.dataset.link.split(':'); box.innerHTML = ''; inp.value = '';
        go(v === 'workbench' ? 'applications' : v, p || null);
        if (v === 'workbench') views.openWorkbench(p);
      });
    }, 180);
  };
  document.addEventListener('click', e => { if (!e.target.closest('.search')) box.innerHTML = ''; });
}

async function showNotifications() {
  const { rows, support } = await api('/notifications');
  const { drawer } = await import('/lib.js');
  drawer(`<h3>Notifications</h3>`, `
    <div class="col" style="gap:10px">
      ${support.length ? `<div class="up">Support tasks</div>` + support.map(s => `
        <div class="note amber"><b>${esc(s.kind)} — ${esc(s.member)}</b><div class="small">${esc(s.detail)}</div>
        <div class="tiny dim">Queue ${esc(s.queue)} · SLA ${esc(s.sla)}</div></div>`).join('') : ''}
      <div class="up" style="margin-top:6px">Activity</div>
      ${rows.map(n => `<div class="note ${n.tone === 'blue' ? '' : n.tone}">
        <b>${esc(n.title)}</b><div class="small muted">${esc(n.detail || '')}</div>
        <div class="tiny dim">${new Date(n.at).toLocaleString()}</div></div>`).join('')}
    </div>`);
}

export async function refreshMeta() {
  state.boot = await api('/bootstrap');
  const [p, n] = await Promise.all([api('/portfolio'), api('/notifications')]);
  state.notifications = n.rows;
  state.badge = { apps: p.kpis.pipeline, ew: p.kpis.early_warnings, coll: 6 };
  state.portfolio = p;
}

// ----------------------------------------------------------------- boot
(async function boot() {
  await refreshMeta();
  const [v, p] = location.hash.slice(1).split('/');
  if (v) { state.view = v; state.param = p || null; }
  render();
})();
