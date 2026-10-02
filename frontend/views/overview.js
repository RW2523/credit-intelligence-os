import { api, icon, esc, money, num, pct, tag, toneFor, lineChart, donut, h, date, ago } from '/lib.js';
import { openWorkbench } from '/views/applications.js';
import { t, tt, lang } from '/i18n.js';
import { state } from '/app.js';

export async function overview(el) {
  const p = await api('/portfolio');
  const k = p.kpis;
  const riskColors = { Low: 'var(--green)', Moderate: 'var(--amber)', Elevated: 'var(--amber-2)', High: 'var(--red)' };

  el.innerHTML = `
  <div class="page-head">
    <div><h1>${t('Portfolio Overview')}</h1>
      <p>${tt(`What needs attention today, ${state.user.name.split(' ')[0]} — every application, member and facility across KT's ${p.kpis.members} members and six branches.`,
              `Perkara yang perlu perhatian hari ini — setiap permohonan, ahli dan kemudahan merentasi ${p.kpis.members} ahli dan enam cawangan KT.`)}</p></div>
    <div class="spacer"></div>
    ${state.user.views.includes('early-warning') ? `<button class="btn" data-go="early-warning">${icon('activity')} ${t('Early Warning')}</button>` : ''}
    ${state.user.views.includes('assistant') ? `<button class="btn" data-go="assistant">${icon('msg')} ${t('KT Assistant')}</button>` : ''}
    ${state.user.views.includes('intake') ? `<button class="btn primary" data-go="intake">${icon('plus')} ${t('New Application')}</button>` : ''}
  </div>

  ${p.autonomy.kill_switch ? `<div class="kill-banner">${icon('power', 18)}
    <div><b style="color:var(--red)">Autonomous execution is stopped</b>
    <div class="small muted">The kill switch is engaged. AI recommendations continue; every action routes to a person.</div></div></div>` : ''}

  <div class="grid g4" style="margin-bottom:14px">
    ${kpi(tt('Applications in pipeline', 'Permohonan dalam proses'), num(k.pipeline), `${k.decided} ${tt('decided', 'diputuskan')} · ${k.applications_today} ${tt('today', 'hari ini')}`, 'accent', 'list')}
    ${kpi(tt('Approval rate', 'Kadar kelulusan'), k.approval_rate + '%', tt('approved vs received, last 16 days', 'diluluskan berbanding diterima, 16 hari'), 'accent-green', 'check')}
    ${kpi(tt('Predicted delinquency', 'Jangkaan tunggakan'), k.predicted_delinquency + '%', tt('exposure-weighted probability of default', 'kebarangkalian mungkir berwajaran'), 'accent-amber', 'activity')}
    ${kpi(tt('Members in early warning', 'Ahli dalam amaran awal'), num(k.early_warnings), tt('drift from their own deduction baseline', 'hanyut daripada asas potongan sendiri'), k.early_warnings ? 'accent-red' : '', 'alert')}
  </div>

  <div class="grid g-3-2" style="margin-bottom:14px">
    <div class="card">
      <div class="card-h"><h3>${tt('Application flow', 'Aliran permohonan')}</h3><span class="sub">${tt('last 16 days · Malaysia time', '16 hari lalu · waktu Malaysia')}</span>
        <div class="spacer"></div>
        <span class="tag t-blue">${tt('Requested', 'Dipohon')} ${money(k.exposure)}</span></div>
      <div class="card-b">${lineChart(p.trend, { keys: ['a', 'ap', 'de'], labels: [tt('Received', 'Diterima'), tt('Approved', 'Diluluskan'), tt('Declined', 'Ditolak')],
        colors: ['var(--info)', 'var(--green)', 'var(--red)'], h: 186 })}</div>
    </div>
    <div class="card">
      <div class="card-h"><h3>${tt('Risk mix', 'Campuran risiko')}</h3><span class="sub">${tt('live pipeline', 'saluran aktif')}</span></div>
      <div class="card-b row" style="gap:18px">
        ${donut(Object.entries(p.risk_mix).map(([kk, v]) => ({ k: kk, v })), { colors: riskColors })}
        <div class="col" style="flex:1;gap:7px">
          ${Object.entries(p.risk_mix).map(([kk, v]) => `<div class="row small">
            <i style="width:8px;height:8px;border-radius:3px;background:${riskColors[kk] || 'var(--brand)'}"></i>
            <span style="flex:1">${kk}</span><b class="num">${v}</b></div>`).join('')}
          <div class="sep"></div>
          <div class="small muted">Ledger ${p.ledger.intact ? '<span class="tag t-green">intact</span>' : '<span class="tag t-red">broken</span>'}
            <span class="dim">· ${p.ledger.records} records</span></div>
        </div>
      </div>
    </div>
  </div>

  <div class="grid g-2-1" style="margin-bottom:14px">
    <div class="card">
      <div class="card-h"><h3>${tt('Priority queue', 'Baris gilir keutamaan')}</h3><span class="sub">${tt('what needs a person today', 'yang perlu tindakan hari ini')}</span>
        <div class="spacer"></div>${state.user.views.includes('applications') ? `<button class="btn sm" data-go="applications">${tt('Open queue', 'Buka baris gilir')} ${icon('chevron', 12)}</button>` : ''}</div>
      <div class="tw"><table>
        <thead><tr><th>${tt('Applicant', 'Pemohon')}</th><th>${t('Product')}</th><th class="r">${t('Amount')}</th><th>${tt('Risk', 'Risiko')}</th><th>DSR</th>
          <th>${t('Documents')}</th><th>${tt('Integrity', 'Integriti')}</th><th>${tt('Next action', 'Tindakan seterusnya')}</th></tr></thead>
        <tbody>${p.queue.map(r => `<tr class="clickable" data-case="${r.id}">
          <td><div class="row"><div class="avatar sm">${r.initials}</div>
            <div><div style="font-weight:560">${esc(r.name)}</div><div class="tiny dim mono">${r.id}</div></div></div></td>
          <td class="small">${esc(lang() === 'ms' ? (state.boot.products[r.product]?.ms || r.product) : r.product)}<div class="tiny dim">${esc(r.branch)}</div></td>
          <td class="r num">${money(r.amount)}</td>
          <td>${tag(r.risk)}</td>
          <td class="num small">${r.dsr}%</td>
          <td class="small"><span class="${r.docs.v < r.docs.t ? 'tag t-amber' : 'tag t-green'}">${r.docs.v}/${r.docs.t}</span></td>
          <td>${tag(r.fraud)}</td>
          <td class="small">${esc(r.next)}</td></tr>`).join('')}</tbody></table></div>
    </div>
    <div class="col" style="gap:14px">
      <div class="card"><div class="card-h"><h3>${tt('AI highlights', 'Sorotan AI')}</h3><span class="sub">${tt('surfaced automatically', 'dikesan secara automatik')}</span></div>
        <div class="card-b col" style="gap:9px">
          ${p.highlights.map(x => `<div class="note ${x.tone === 'red' ? 'red' : x.tone === 'amber' ? 'amber' : x.tone === 'green' ? 'green' : ''}"
            style="cursor:pointer" data-go="${x.action}">
            <b>${esc(x.title)}</b><div class="small muted">${esc(x.detail)}</div></div>`).join('')
            || '<div class="empty small">Nothing needs attention.</div>'}
        </div></div>
      <div class="card"><div class="card-h"><h3>${tt('Latest evidence', 'Bukti terkini')}</h3></div>
        <div class="card-b col" style="gap:2px">
          ${p.recent_documents.map(d => `<div class="field-row" data-doc="${d.id}">
            ${icon('file', 15)}<span class="k" style="color:var(--ink-2)">${esc(d.label)}</span>
            ${tag(d.status)}<span class="conf">${d.confidence}%</span></div>`).join('')}
        </div></div>
    </div>
  </div>

  <div class="card">
    <div class="card-h"><h3>${tt('Members drifting from their own baseline', 'Ahli yang hanyut daripada asas sendiri')}</h3>
      <span class="sub">${tt('predicted before any arrears', 'diramal sebelum sebarang tunggakan')}</span>
      <div class="spacer"></div>${state.user.views.includes('early-warning') ? `<button class="btn sm" data-go="early-warning">${tt('All early warnings', 'Semua amaran awal')} ${icon('chevron', 12)}</button>` : ''}</div>
    <div class="tw"><table>
      <thead><tr><th>Member</th><th>State</th><th>Change point</th><th>30-day late risk</th>
        <th>Recovery likelihood</th><th>Why now</th><th></th></tr></thead>
      <tbody>${p.early_warning.map(a => `<tr class="clickable" data-member="${a.member_id}">
        <td><div class="row"><div class="avatar sm">${esc(a.name.split(' ').map(x => x[0]).join(''))}</div>
          <span style="font-weight:560">${esc(a.name)}</span></div></td>
        <td>${tag(a.state.state)}</td>
        <td class="small">${a.change_point.days_ago ? a.change_point.days_ago + ' days ago' : '—'}</td>
        <td style="width:130px"><div class="meter"><div class="bar"><i style="width:${a.forecast.p_late_30d * 100}%;
          background:${a.forecast.p_late_30d > .5 ? 'var(--red)' : 'var(--amber)'}"></i></div>
          <span class="mono">${pct(a.forecast.p_late_30d, 0)}</span></div></td>
        <td style="width:130px"><div class="meter"><div class="bar"><i style="width:${a.forecast.recovery_likelihood * 100}%;background:var(--green)"></i></div>
          <span class="mono">${pct(a.forecast.recovery_likelihood, 0)}</span></div></td>
        <td class="small muted" style="max-width:340px">${esc(a.why_now.slice(0, 120))}</td>
        <td>${icon('chevron', 14)}</td></tr>`).join('')}</tbody></table></div>
  </div>`;

  const can = v => state.user.views.includes(v);
  el.querySelectorAll('[data-go]').forEach(b => b.onclick = () => window.go(b.dataset.go));
  el.querySelectorAll('[data-case]').forEach(r => r.onclick = () => can('applications') && openWorkbench(r.dataset.case));
  el.querySelectorAll('[data-member]').forEach(r => r.onclick = () => can('members') && window.go('members', r.dataset.member));
  el.querySelectorAll('[data-doc]').forEach(r => r.onclick = () => can('documents') && window.go('documents', r.dataset.doc));
}

function kpi(label, val, sub, accent = '', ic = 'grid') {
  return `<div class="kpi ${accent}">
    <div class="lbl">${icon(ic, 13)} ${label}</div>
    <div class="val">${val}</div><div class="sub">${sub}</div></div>`;
}
