import { api, icon, esc, money, num, pct, tag, toneFor, lineChart, donut, h, date, ago } from '/lib.js';
import { openWorkbench } from '/views/applications.js';

export async function overview(el) {
  const p = await api('/portfolio');
  const k = p.kpis;
  const riskColors = { Low: '#2ecc8f', Moderate: '#f5a623', Elevated: '#f59e0b', High: '#f2545b' };

  el.innerHTML = `
  <div class="page-head">
    <div><h1>Portfolio Overview</h1>
      <p>Every application, member and facility on one intelligence backbone — from origination through
         servicing, early warning and collections.</p></div>
    <div class="spacer"></div>
    <button class="btn" data-go="early-warning">${icon('activity')} Early warnings</button>
    <button class="btn" data-go="sandbox">${icon('sliders')} Policy sandbox</button>
    <button class="btn primary" data-go="intake">${icon('plus')} New application</button>
  </div>

  ${p.autonomy.kill_switch ? `<div class="kill-banner">${icon('power', 18)}
    <div><b style="color:var(--red)">Autonomous execution is stopped</b>
    <div class="small muted">The kill switch is engaged. AI recommendations continue; every action routes to a person.</div></div></div>` : ''}

  <div class="grid g4" style="margin-bottom:14px">
    ${kpi('Applications in pipeline', num(k.pipeline), `${k.decided} decided · ${k.applications_today} today`, 'accent', 'list')}
    ${kpi('Approval rate', k.approval_rate + '%', 'approved vs submitted, 16-day window', 'accent-green', 'check')}
    ${kpi('Predicted delinquency', k.predicted_delinquency + '%', 'exposure-weighted probability of default', 'accent-amber', 'activity')}
    ${kpi('Members in early warning', num(k.early_warnings), 'behavioural drift from personal baseline', k.early_warnings ? 'accent-red' : '', 'alert')}
  </div>

  <div class="grid g-3-2" style="margin-bottom:14px">
    <div class="card">
      <div class="card-h"><h3>Application flow</h3><span class="sub">submitted · approved · declined</span>
        <div class="spacer"></div>
        <span class="tag t-blue">Exposure ${money(k.exposure)}</span></div>
      <div class="card-b">${lineChart(p.trend, { keys: ['a', 'ap', 'de'], labels: ['Submitted', 'Approved', 'Declined'], h: 186 })}
        <div class="row wrap small muted" style="margin-top:8px;gap:14px">
          ${['Submitted #4d7cfe', 'Approved #2ecc8f', 'Declined #f5a623'].map(s => {
            const [n, c] = s.split(' ');
            return `<span class="row" style="gap:6px"><i style="width:9px;height:3px;border-radius:3px;background:${c};display:inline-block"></i>${n}</span>`;
          }).join('')}
        </div></div>
    </div>
    <div class="card">
      <div class="card-h"><h3>Risk mix</h3><span class="sub">live pipeline</span></div>
      <div class="card-b row" style="gap:18px">
        ${donut(Object.entries(p.risk_mix).map(([kk, v]) => ({ k: kk, v })), { colors: riskColors })}
        <div class="col" style="flex:1;gap:7px">
          ${Object.entries(p.risk_mix).map(([kk, v]) => `<div class="row small">
            <i style="width:8px;height:8px;border-radius:3px;background:${riskColors[kk] || '#4d7cfe'}"></i>
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
      <div class="card-h"><h3>Priority queue</h3><span class="sub">what needs a person today</span>
        <div class="spacer"></div><button class="btn sm" data-go="applications">Open queue ${icon('chevron', 12)}</button></div>
      <div class="tw"><table>
        <thead><tr><th>Applicant</th><th>Product</th><th class="r">Amount</th><th>Risk</th><th>DSR</th>
          <th>Docs</th><th>Integrity</th><th>Next action</th></tr></thead>
        <tbody>${p.queue.map(r => `<tr class="clickable" data-case="${r.id}">
          <td><div class="row"><div class="avatar sm">${r.initials}</div>
            <div><div style="font-weight:560">${esc(r.name)}</div><div class="tiny dim mono">${r.id}</div></div></div></td>
          <td class="small">${esc(r.product)}</td>
          <td class="r num">${money(r.amount)}</td>
          <td>${tag(r.risk)}</td>
          <td class="num small">${r.dsr}%</td>
          <td class="small"><span class="${r.docs.v < r.docs.t ? 'tag t-amber' : 'tag t-green'}">${r.docs.v}/${r.docs.t}</span></td>
          <td>${tag(r.fraud)}</td>
          <td class="small">${esc(r.next)}</td></tr>`).join('')}</tbody></table></div>
    </div>
    <div class="col" style="gap:14px">
      <div class="card"><div class="card-h"><h3>AI highlights</h3><span class="sub">surfaced automatically</span></div>
        <div class="card-b col" style="gap:9px">
          ${p.highlights.map(x => `<div class="note ${x.tone === 'red' ? 'red' : x.tone === 'amber' ? 'amber' : x.tone === 'green' ? 'green' : ''}"
            style="cursor:pointer" data-go="${x.action}">
            <b>${esc(x.title)}</b><div class="small muted">${esc(x.detail)}</div></div>`).join('')
            || '<div class="empty small">Nothing needs attention.</div>'}
        </div></div>
      <div class="card"><div class="card-h"><h3>Latest evidence</h3></div>
        <div class="card-b col" style="gap:2px">
          ${p.recent_documents.map(d => `<div class="field-row" data-doc="${d.id}">
            ${icon('file', 15)}<span class="k" style="color:var(--ink-2)">${esc(d.label)}</span>
            ${tag(d.status)}<span class="conf">${d.confidence}%</span></div>`).join('')}
        </div></div>
    </div>
  </div>

  <div class="card">
    <div class="card-h"><h3>Members drifting from their own baseline</h3>
      <span class="sub">longitudinal intelligence — predicted before any arrears</span>
      <div class="spacer"></div><button class="btn sm" data-go="early-warning">All early warnings ${icon('chevron', 12)}</button></div>
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

  el.querySelectorAll('[data-go]').forEach(b => b.onclick = () => window.go(b.dataset.go));
  el.querySelectorAll('[data-case]').forEach(r => r.onclick = () => openWorkbench(r.dataset.case));
  el.querySelectorAll('[data-member]').forEach(r => r.onclick = () => window.go('members', r.dataset.member));
  el.querySelectorAll('[data-doc]').forEach(r => r.onclick = () => window.go('documents', r.dataset.doc));
}

function kpi(label, val, sub, accent = '', ic = 'grid') {
  return `<div class="kpi ${accent}">
    <div class="lbl">${icon(ic, 13)} ${label}</div>
    <div class="val">${val}</div><div class="sub">${sub}</div></div>`;
}
