import { $, $$, api, icon, esc, toast, closeDrawer, drawer, dtime, setServerNow } from '/lib.js';
import { t, tt, lang, setLang, hasLang } from '/i18n.js';
import { mark } from '/brand.js';
import * as views from '/views/index.js';

export const state = { view: null, param: null, boot: null, user: null, notifications: [], badge: {} };

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
  { g: 'Growth', items: [
    { id: 'crosssell', name: 'Cross-selling options', icon: 'gift' },
  ]},
  { g: 'Governance', items: [
    { id: 'cockpit', name: 'Management Cockpit', icon: 'chart' },
    { id: 'sandbox', name: 'Policy Sandbox', icon: 'sliders' },
    { id: 'governance', name: 'Model Governance', icon: 'cpu' },
    { id: 'ledger', name: 'Decision Ledger', icon: 'book' },
  ]},
  { g: 'Assistants', items: [
    { id: 'assistant', name: 'KT Assistant', icon: 'msg' },
  ]},
  { g: 'My account', items: [
    { id: 'member-portal', name: 'My Account', icon: 'home' },
    { id: 'check', name: 'Check Before You Borrow', icon: 'calc' },
  ]},
];
// each role opens on the surface that answers "what needs me today?"
const LANDING = { officer: 'overview', senior: 'applications', collections: 'collections', risk: 'overview',
  compliance: 'ledger', manager: 'cockpit', board: 'cockpit', marketing: 'crosssell', member: 'member-portal' };
const DETAIL_OF = { workbench: 'applications' };

// Guided demo — a short, role-specific walk through what KT asked to see
const GUIDE = {
  member: [['member-portal', null, 'Your balance and next ANGKASA deduction', 'Baki dan potongan ANGKASA seterusnya'],
    ['member-portal', null, 'Ask the assistant in Malay: "Berapa baki pinjaman saya dan bila bayaran seterusnya?"', 'Tanya pembantu: "Berapa baki pinjaman saya dan bila bayaran seterusnya?"'],
    ['check', null, 'Check Before You Borrow — the same rules the officer uses', 'Semak Sebelum Memohon — peraturan sama seperti pegawai']],
  officer: [['overview', null, 'What needs attention today', 'Perkara yang perlu perhatian hari ini'],
    ['workbench', 'APP-104310', 'Kpl Mohd Ridzuan — maximum RM0 with the reasons (was "−200")', 'Kpl Mohd Ridzuan — maksimum RM0 dengan sebabnya'],
    ['workbench', 'APP-104355', 'Kpl Jeffrey — passes DSR, breaches the 60% deduction cap', 'Kpl Jeffrey — lulus DSR, melebihi had potongan 60%'],
    ['documents', null, 'Document Intelligence — click a field, the box lands on the value', 'Klik medan, kotak tepat pada nilai'],
    ['assistant', null, 'KT Assistant — ask about cases in BM or English', 'Pembantu KT — tanya dalam BM atau English']],
  senior: [['applications', null, 'The queue with DSR and the 60% deduction check', 'Baris gilir dengan DSR dan semakan 60%'],
    ['members', '104436', 'Possible bankruptcy — Mej (B) Ramasamy', 'Kemungkinan bankrap — Mej (B) Ramasamy'],
    ['crosssell', null, 'Cross-selling options — takaful, financing, retention', 'Pilihan jualan silang']],
  manager: [['cockpit', null, 'Cockpit — hover the trend; click the legend', 'Kokpit — halakan trend; klik petunjuk'],
    ['crosssell', null, 'Cross-selling options with reason chains', 'Pilihan jualan silang dengan rantaian sebab'],
    ['assistant', null, 'Ask: "Financing requested by branch"', 'Tanya: "Jumlah pembiayaan mengikut cawangan"']],
  board: [['cockpit', null, 'Cockpit — aggregates, distress outlook, growth', 'Kokpit — agregat, tinjauan tekanan, pertumbuhan'],
    ['sandbox', null, 'Policy Sandbox — move a control, replay, propose', 'Kotak Pasir — gerak kawalan, main semula, cadang'],
    ['ledger', null, 'Decision Ledger — plain-language records', 'Lejar Keputusan — rekod bahasa biasa'],
    ['governance', null, 'Model cards and the Autonomy Dial', 'Kad model dan Dail Autonomi']],
};
GUIDE.collections = [['collections', null, 'Expected-value priority list', 'Senarai keutamaan'], ['early-warning', null, 'Early warning against each member\'s own baseline', 'Amaran awal'], ['members', '104436', 'Possible bankruptcy and recommended support', 'Kemungkinan bankrap dan sokongan']];
GUIDE.risk = GUIDE.board.filter(x => x[0] !== 'cockpit' && x[0] !== 'ledger').concat([['members', '104310', 'Distress outlook for an at-risk member', 'Tinjauan tekanan ahli berisiko']]);
GUIDE.compliance = [['ledger', null, 'Ledger and case reconstruction', 'Lejar dan pembinaan semula kes'], ['governance', null, 'Model cards, fairness, overrides', 'Kad model, keadilan, pembatalan']];
GUIDE.marketing = [['crosssell', null, 'Cross-selling options — consent respected', 'Pilihan jualan silang — persetujuan dihormati'], ['assistant', null, 'Ask: "List the takaful opportunities"', 'Tanya: "Senaraikan peluang takaful"']];

function showGuide() {
  const steps = (GUIDE[state.user.role] || []).filter(([v]) => canSee(v));
  drawer(`<div class="row">${icon('flag', 16)}<h3>${tt('Demo guide', 'Panduan demo')} — ${esc(lang() === 'ms' ? state.user.role_ms : state.user.role_label)}</h3></div>`,
    `<div class="col" style="gap:8px">${steps.map(([v, p, en, ms], i) => `<button class="quick" data-gv="${v}" data-gp="${p || ''}" style="flex-direction:row;align-items:center;gap:10px">
      <span class="qi">${i + 1}</span><span><b>${esc(navName(v))}${p ? ` · ${esc(p)}` : ''}</b><br/><span>${esc(lang() === 'ms' ? ms : en)}</span></span></button>`).join('')}
      <div class="tiny dim">${tt('Synthetic demonstration data. Sign in as another role for its own guide.', 'Data demonstrasi sintetik. Log masuk sebagai peranan lain untuk panduannya.')}</div></div>`,
    { onMount: d => d.querySelectorAll('[data-gv]').forEach(b => b.onclick = () => go(b.dataset.gv, b.dataset.gp || null)) });
}

const allowed = () => new Set(state.user?.views || []);
export function canSee(view) {
  const a = allowed();
  return a.has(view) || (DETAIL_OF[view] ? a.has(DETAIL_OF[view]) || a.has(view) : false);
}
const landingView = () => LANDING[state.user?.role] || NAV.flatMap(g => g.items).find(i => allowed().has(i.id))?.id;
const navName = id => t(NAV.flatMap(g => g.items).find(i => i.id === id)?.name || { workbench: 'Case Workbench' }[id] || id);

// -------------------------------------------------------------- routing
export function go(view, param = null) {
  if (state.user && !canSee(view)) {
    toast(t('Not available for this role'), `${state.user.role_label} · ${navName(view)}`, 'warn');
    view = landingView(); param = null;
  }
  state.view = view; state.param = param;
  closeDrawer(); document.body.classList.remove('nav-open');
  const h = param ? `#${view}/${encodeURIComponent(param)}` : `#${view}`;
  if (location.hash !== h) history.pushState(null, '', h);
  render();
}
window.addEventListener('popstate', () => routeFromHash());
function routeFromHash() {
  const [v, p] = location.hash.slice(1).split('/');
  if (!state.user) return;
  if (!v) return go(landingView());
  if (!canSee(v)) return go(landingView());
  state.view = v; state.param = p ? decodeURIComponent(p) : null; render();
}
window.go = go;

// ---------------------------------------------------------------- theme
export const theme = () => document.documentElement.dataset.theme || 'dark';
export function applyTheme(x) {
  document.documentElement.dataset.theme = x;
  try { localStorage.setItem('cios-theme', x); } catch (e) { /* private mode */ }
}

// ---------------------------------------------------------------- shell
function shell() {
  const u = state.user;
  const llmOk = state.boot.llm?.available;
  return `
  <aside class="sidebar" aria-label="Navigation">
    <div class="brand">
      <div class="brand-mark">${mark('sb')}</div>
      <div class="brand-txt"><b>KT Credit Intelligence</b><span>Koperasi Tentera</span></div>
    </div>
    <nav class="nav">
      ${NAV.map(g => {
        const items = g.items.filter(i => canSee(i.id));
        if (!items.length) return '';
        return `<div class="nav-group">${t(g.g)}</div>` + items.map(i => `
        <button class="nav-item ${state.view === i.id || (i.id === 'applications' && state.view === 'workbench') ? 'on' : ''}" data-go="${i.id}">
          ${icon(i.icon)} <span>${t(i.name)}</span>
          ${state.badge[i.badge] ? `<span class="pill">${state.badge[i.badge]}</span>` : ''}
        </button>`).join('');
      }).join('')}
    </nav>
    <div class="sidebar-foot">
      <div class="row" style="gap:9px">
        <div class="avatar">${esc(u.initials)}</div>
        <div style="min-width:0;flex:1">
          <div style="font-size:12px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(u.name)}</div>
          <div class="tiny muted">${esc(lang() === 'ms' ? u.role_ms : u.role_label)}</div>
        </div>
        <button class="btn-icon" id="logout" title="${t('Sign out')}" aria-label="${t('Sign out')}"
          style="background:transparent;border-color:#ffffff22;color:var(--sidebar-ink)">${icon('logout', 15)}</button>
      </div>
    </div>
  </aside>
  <div class="main">
    <header class="topbar">
      <button class="btn-icon menu-btn" id="menu" aria-label="Menu">${icon('list')}</button>
      <div class="crumbs">${icon('layers', 14)}<b>${esc(navName(state.view))}</b>${state.param ? `<span>/</span><span class="mono">${esc(state.param)}</span>` : ''}</div>
      ${u.role !== 'member' ? `<div class="search">
        <span class="si">${icon('search', 15)}</span>
        <input id="gsearch" placeholder="${t('Search members, applications, documents, policies…')}" autocomplete="off" aria-label="Search"/>
        <div id="sresults"></div>
      </div>` : '<div style="flex:1"></div>'}
      <div class="top-actions">
        ${u.role !== 'member' ? `<span class="tag t-${llmOk ? 'green' : 'amber'}" title="${tt('Local AI model on this machine', 'Model AI tempatan')}">
          ${icon('cpu', 12)} ${llmOk ? esc(shortModel(state.boot.llm.model)) : 'deterministic mode'}</span>
        <span class="tag t-${state.boot.autonomy?.kill_switch ? 'red' : 'purple'}" title="Autonomy Dial">${icon('power', 12)} ${state.boot.autonomy?.kill_switch ? 'STOPPED' : esc(state.boot.autonomy?.mode || '')}</span>` : ''}
        <span class="tag t-grey" title="${tt('Demo day — Malaysia time (UTC+8)', 'Hari demo — waktu Malaysia (UTC+8)')}">${icon('clock', 12)} ${esc(dtime(state.boot.now).replace(/,? \d\d:\d\d.*/, ''))} · MYT</span>
        <div class="lang-sw" role="group" aria-label="${t('Language')}">
          <button data-lang="ms" class="${lang() === 'ms' ? 'on' : ''}">BM</button><button data-lang="en" class="${lang() === 'en' ? 'on' : ''}">EN</button></div>
        <button class="btn-icon" id="theme" title="${theme() === 'light' ? 'Dark' : 'Light'} mode" aria-label="Toggle theme">${icon(theme() === 'light' ? 'moon' : 'sun')}</button>
        ${u.role !== 'member' ? `<button class="btn-icon" id="bell" aria-label="${t('Notifications')}">${icon('bell')}${state.notifications.length ? '<i class="dot-badge"></i>' : ''}</button>` : ''}
        <button class="btn-icon" id="guide" title="${tt('Demo guide', 'Panduan demo')}" aria-label="${tt('Demo guide', 'Panduan demo')}">${icon('flag')}</button>
        <button class="btn-icon" id="refresh" title="${t('Refresh')}" aria-label="${t('Refresh')}">${icon('refresh')}</button>
      </div>
    </header>
    <main class="content" id="content"><div class="center"><div class="spin"></div></div></main>
  </div>`;
}
const shortModel = m => String(m || '').replace(/-a3b-instruct-2507-q4_K_M$/, '').replace(/-instruct.*$/, '');

// ---------------------------------------------------------------- render
export async function render() {
  closeDrawer();
  if (!state.user) return;
  const app = $('#app');
  if (!app.querySelector('.sidebar')) { app.className = ''; app.innerHTML = shell(); }
  else {
    const tpl = document.createElement('template');
    tpl.innerHTML = shell().trim();
    app.querySelector('.sidebar').replaceWith(tpl.content.querySelector('.sidebar'));
    app.querySelector('.topbar').replaceWith(tpl.content.querySelector('.topbar'));
  }
  bindShell();
  const el = $('#content');
  el.innerHTML = '<div class="center" style="height:200px"><div class="spin"></div></div>';
  el.scrollTop = 0;
  const alias = { 'early-warning': 'earlyWarning', 'member-portal': 'memberPortal', check: 'checkBorrow', assistant: 'assistantPage' };
  const fn = views[alias[state.view] || state.view] || views[alias[landingView()] || landingView()];
  try { await fn(el, state.param); } catch (e) {
    console.error(e);
    if (e.status === 401) return;
    el.innerHTML = `<div class="empty">${icon('alert', 28)}<b>${esc(e.message)}</b>
      <span class="small">${t('Something went wrong rendering this view.')}</span></div>`;
  }
}
window.render = render;

function bindShell() {
  $$('[data-go]').forEach(b => b.onclick = () => go(b.dataset.go));
  $('#theme').onclick = () => { applyTheme(theme() === 'light' ? 'dark' : 'light'); render(); };
  $('#refresh').onclick = async () => { await refreshMeta(); render(); toast(tt('Refreshed', 'Dimuat semula')); };
  $('#bell') && ($('#bell').onclick = showNotifications);
  $('#menu').onclick = () => document.body.classList.toggle('nav-open');
  $('#guide').onclick = showGuide;
  $('#logout').onclick = async () => { await api('/auth/logout', { method: 'POST' }).catch(() => {}); signedOut(); };
  $$('[data-lang]').forEach(b => b.onclick = () => { setLang(b.dataset.lang); render(); });
  bindSearch();
}

let searchTimer;
function bindSearch() {
  const inp = $('#gsearch'), box = $('#sresults');
  if (!inp) return;
  inp.oninput = () => {
    clearTimeout(searchTimer);
    const q = inp.value.trim();
    if (q.length < 2) { box.innerHTML = ''; return; }
    searchTimer = setTimeout(async () => {
      const { rows } = await api('/search?q=' + encodeURIComponent(q));
      box.innerHTML = rows.length ? `<div class="search-results">${rows.map(r => `
        <button class="sr-item" data-link="${esc(r.link)}">
          <span class="sr-kind">${esc(r.kind)}</span>
          <span style="flex:1;min-width:0"><div style="font-size:12.5px">${esc(r.title)}</div>
          <div class="tiny muted">${esc(r.sub)}</div></span>${icon('chevron', 13)}</button>`).join('')}</div>`
        : `<div class="search-results"><div class="empty small">${tt('No matches for', 'Tiada padanan untuk')} “${esc(q)}”</div></div>`;
      box.querySelectorAll('[data-link]').forEach(b => b.onclick = () => {
        const [v, p] = b.dataset.link.split(':'); box.innerHTML = ''; inp.value = '';
        if (v) go(v, p || null);
      });
    }, 180);
  };
  document.addEventListener('click', e => { if (!e.target.closest('.search')) box.innerHTML = ''; });
}

async function showNotifications() {
  const { rows, support } = await api('/notifications');
  drawer(`<h3>${t('Notifications')}</h3>`, `
    <div class="col" style="gap:10px">
      ${support.length ? `<div class="up">${tt('Support tasks', 'Tugasan sokongan')}</div>` + support.map(s => `
        <div class="note amber"><b>${esc(s.kind)} — ${esc(s.member)}</b><div class="small">${esc(s.detail)}</div>
        <div class="tiny dim">${esc(s.queue)} · SLA ${esc(s.sla)} · ${dtime(s.at)}</div></div>`).join('') : ''}
      <div class="up" style="margin-top:6px">${tt('Activity', 'Aktiviti')}</div>
      ${rows.map(n => `<div class="note ${n.tone === 'blue' ? '' : n.tone}" ${n.link ? `data-link="${esc(n.link)}" style="cursor:pointer"` : ''}>
        <b>${esc(n.title)}</b><div class="small muted">${esc(n.detail || '')}</div>
        <div class="tiny dim">${dtime(n.at)}</div></div>`).join('')}
    </div>`, { onMount: d => d.querySelectorAll('[data-link]').forEach(x => x.onclick = () => {
      const [v, p] = x.dataset.link.split(':'); if (canSee(v)) go(v, p || null); }) });
}

export async function refreshMeta() {
  state.boot = await api('/bootstrap');
  state.user = state.boot.user;
  setServerNow(state.boot.now);
  if (state.user.role === 'member') { state.notifications = []; return; }
  const jobs = [api('/notifications').catch(() => ({ rows: [] }))];
  if (canSee('overview') || canSee('cockpit')) jobs.push(api('/portfolio').catch(() => null));
  const [n, p] = await Promise.all(jobs);
  state.notifications = n.rows;
  state.badge = p ? { apps: p.kpis.pipeline - p.kpis.decided, ew: p.kpis.early_warnings, coll: 8 } : {};
}

// ----------------------------------------------------------------- auth
function signedOut() {
  state.user = null; state.boot = null;
  document.body.classList.remove('nav-open');
  const app = $('#app'); app.className = '';
  views.login(app, async user => {
    if (!hasLang()) setLang(user.role === 'member' ? 'ms' : 'en');
    await refreshMeta();
    app.innerHTML = '';
    const [v, p] = location.hash.slice(1).split('/');
    if (v && canSee(v)) { state.view = v; state.param = p ? decodeURIComponent(p) : null; render(); }
    else go(landingView());
  });
}
window.addEventListener('kt:signed-out', () => { if (state.user) { toast(tt('Session ended', 'Sesi tamat'), tt('Please sign in again.', 'Sila log masuk semula.'), 'warn'); } signedOut(); });

// ----------------------------------------------------------------- boot
(async function boot() {
  try {
    await api('/auth/me');
    await refreshMeta();
    routeFromHash();
  } catch (e) {
    signedOut();
  }
})();
