import { api, icon, esc, money, pct, tag, toneFor, date, dtime, stepChart, lineChart, gauge,
         drawer, toast, $, $$ } from '/lib.js';

// ---------------------------------------------------------- member list
export async function members(el, param) {
  if (param) return member360(el, param);
  const { rows } = await api('/members');
  el.innerHTML = `
  <div class="page-head"><div><h1>Member 360</h1>
    <p>One unified intelligence profile per member — core data, derived timeline features and longitudinal state,
       shared by underwriting, servicing, collections and every assistant.</p></div></div>
  <div class="card"><div class="tw"><table>
    <thead><tr><th>Member</th><th>Since</th><th>Branch</th><th class="r">Savings</th><th class="r">Share capital</th>
      <th class="r">Outstanding</th><th>Reliability</th><th>State</th><th>30-day late risk</th><th></th></tr></thead>
    <tbody>${rows.map(m => `<tr class="clickable" data-m="${m.id}">
      <td><div class="row"><div class="avatar sm">${m.initials}</div>
        <div><div style="font-weight:560">${esc(m.name)}</div><div class="tiny dim mono">${m.id}</div></div></div></td>
      <td class="small">${date(m.since)}</td><td class="small">${esc(m.branch)}</td>
      <td class="r num">${money(m.savings)}</td><td class="r num">${money(m.share_capital)}</td>
      <td class="r num">${money(m.outstanding)}</td>
      <td style="width:110px"><div class="meter"><div class="bar thin"><i style="width:${m.reliability}%;background:var(--green)"></i></div>
        <span class="mono">${m.reliability}%</span></div></td>
      <td>${tag(m.lmi_state)}</td>
      <td class="num small">${pct(m.p30, 0)}</td><td>${icon('chevron', 14)}</td></tr>`).join('')}
    </tbody></table></div></div>`;
  $$('[data-m]', el).forEach(r => r.onclick = () => window.go('members', r.dataset.m));
}

// ------------------------------------------------------------ member 360
async function member360(el, mid) {
  const d = await api('/members/' + mid);
  const m = d.member, l = d.lmi;
  el.innerHTML = `
  <div class="page-head">
    <button class="btn-icon" id="back">${icon('chevron', 16)}</button>
    <div class="row" style="gap:12px"><div class="avatar lg">${m.initials}</div>
      <div><h1>${esc(m.name)}</h1><p class="tiny mono">member ${m.id} · ${esc(m.branch)} · since ${date(m.since)}</p></div></div>
    <div class="spacer"></div>
    ${tag(l.state.state)}
    <button class="btn" id="outreach">${icon('phone')} Log outreach</button>
  </div>

  <div class="grid g5" style="margin-bottom:14px">
    ${k('Savings', money(m.savings))}${k('Share capital', money(m.share_capital))}
    ${k('Current financing', money(m.outstanding))}${k('Payment reliability', m.reliability + '%')}
    ${k('Prior facilities', m.prior_loans)}
  </div>

  <div class="grid g-2-1" style="margin-bottom:14px">
    <div class="card"><div class="card-h"><h3>Longitudinal payment behaviour</h3>
      <span class="sub">days late per cycle against this member's own baseline</span>
      <div class="spacer"></div>${l.change_point.detected ? `<span class="tag t-amber">change point ${l.change_point.days_ago} days ago</span>` : '<span class="tag t-green">no change point</span>'}</div>
      <div class="card-b">
        ${stepChart(l.series, { threshold: Math.max(3, l.baseline.mean_days_late + 2 * l.baseline.sd) })}
        <div class="note ${l.state.state === 'STABLE' ? 'green' : l.state.state === 'AT_RISK' ? 'red' : 'amber'}" style="margin-top:10px">
          <b>Why now</b><div class="small">${esc(l.why_now)}</div></div>
      </div></div>
    <div class="card"><div class="card-h"><h3>Forecast</h3></div><div class="card-b col" style="gap:10px">
      <div class="row" style="gap:12px;justify-content:center">
        <div style="width:118px">${gauge(l.forecast.p_late_30d, { size: 112, label: pct(l.forecast.p_late_30d, 0), sub: '30-day late',
          color: l.forecast.p_late_30d > .5 ? '#f2545b' : '#f5a623' })}</div>
        <div style="width:118px">${gauge(l.forecast.recovery_likelihood, { size: 112, label: pct(l.forecast.recovery_likelihood, 0), sub: 'recovery', color: '#2ecc8f' })}</div>
      </div>
      <dl class="kv">
        <dt>Personal baseline</dt><dd>${l.baseline.mean_days_late} days late (sd ${l.baseline.sd})</dd>
        <dt>On-time rate</dt><dd>${l.baseline.on_time_rate}%</dd>
        <dt>90-day late risk</dt><dd>${pct(l.forecast.p_late_90d, 0)}</dd>
        <dt>Savings vs baseline</dt><dd>${l.forecast.savings_drop_pct > 0 ? '−' + l.forecast.savings_drop_pct + '%' : 'stable'}</dd>
        <dt>Trend</dt><dd>${l.forecast.trend_days_per_cycle > 0 ? '+' : ''}${l.forecast.trend_days_per_cycle} days / cycle</dd>
      </dl>
      <div class="tiny dim">${esc(l.state.hysteresis)}</div>
    </div></div>
  </div>

  <div class="grid g3" style="margin-bottom:14px">
    <div class="card"><div class="card-h"><h3>Cross-data investigation</h3></div><div class="card-b col" style="gap:9px">
      <div class="note ${l.corroboration.suppressed ? '' : l.corroboration.supporting.length > 1 ? 'amber' : 'green'}">
        <b>${esc(l.corroboration.verdict)}</b>
        <div class="small muted">corroboration strength ${l.corroboration.strength}</div></div>
      ${l.corroboration.supporting.map(s => `<div class="row" style="gap:8px">
        ${icon('alert', 13)}<div style="flex:1"><b class="small">${esc(s.source)}</b>
        <div class="tiny muted">${esc(s.detail)}</div></div><span class="mono tiny dim">+${s.weight}</span></div>`).join('')}
      ${l.corroboration.mitigating.map(s => `<div class="row" style="gap:8px">
        ${icon('check', 13)}<div style="flex:1"><b class="small">${esc(s.source)}</b>
        <div class="tiny muted">${esc(s.detail)}</div></div><span class="mono tiny dim">${s.weight}</span></div>`).join('')}
      ${l.corroboration.supporting.length || l.corroboration.mitigating.length ? '' : '<div class="small dim">No corroborating or mitigating evidence found.</div>'}
    </div></div>
    <div class="card"><div class="card-h"><h3>Recommended intervention</h3></div><div class="card-b col" style="gap:9px">
      <div class="row wrap">${tag(l.intervention.urgency === 'None' ? 'Clear' : l.intervention.urgency === 'High' ? 'Critical' : 'Watch')}
        <span class="tag t-grey">${esc(l.intervention.channel)}</span></div>
      <div style="font-size:15px;font-weight:600">${esc(l.intervention.action)}</div>
      <div class="small muted"><b>Objective.</b> ${esc(l.intervention.objective)}</div>
      <div class="small muted"><b>Rationale.</b> ${esc(l.intervention.rationale)}</div>
      ${l.state.state === 'RECOVERY' ? `<div class="note purple"><b>Recovery ${l.state.recovery_progress}/${l.state.recovery_target}</b>
        <div class="small">Alert closes automatically when criteria are met; the history is retained.</div></div>` : ''}
    </div></div>
    <div class="card"><div class="card-h"><h3>Savings trajectory</h3></div><div class="card-b">
      ${lineChart(l.savings_trend.map((v, i) => ({ d: '', v })), { keys: ['v'], h: 120, colors: ['#22d3ee'] })}
      <div class="tiny dim">Monthly savings contribution — an independent corroborating source.</div>
    </div></div>
  </div>

  <div class="grid g2">
    <div class="card"><div class="card-h"><h3>Applications & facilities</h3></div><div class="tw"><table>
      <thead><tr><th>Case</th><th>Product</th><th class="r">Amount</th><th>Status</th><th>Risk</th><th></th></tr></thead>
      <tbody>${d.applications.map(a => `<tr class="clickable" data-c="${a.id}"><td class="mono tiny">${a.id}</td>
        <td class="small">${esc(a.product)}</td><td class="r num">${money(a.amount)}</td>
        <td>${tag(a.status)}</td><td>${tag(a.risk)}</td><td>${icon('chevron', 13)}</td></tr>`).join('')
        || '<tr><td colspan="6" class="dim small">No applications on record.</td></tr>'}</tbody></table></div></div>
    <div class="card"><div class="card-h"><h3>Communication history</h3></div><div class="card-b">
      <div class="timeline">${d.comms.map(cm => `<div class="tl-item ${cm.type === 'promise' ? 'hot' : ''}">
        <div class="row"><b style="font-size:12.5px">${esc(cm.title)}</b><span class="tiny dim">${dtime(cm.at)}</span></div>
        <div class="small muted">${esc(cm.text)}</div></div>`).join('')
        || '<div class="small dim">No recorded contact.</div>'}</div></div></div>
  </div>`;

  $('#back', el).onclick = () => window.go('members');
  $$('[data-c]', el).forEach(r => r.onclick = () => window.go('workbench', r.dataset.c));
  $('#outreach', el).onclick = () => logOutreach(mid, m.name);
}

const k = (l, v) => `<div class="kpi"><div class="lbl">${l}</div><div class="val" style="font-size:19px">${v}</div></div>`;

export function logOutreach(mid, name) {
  drawer(`<h3>Log outreach — ${esc(name)}</h3>`, `
    <div class="col" style="gap:12px">
      <div class="field"><label>Channel</label><select class="inp" id="ch">
        <option>Phone</option><option>SMS</option><option>Email</option><option>Branch visit</option></select></div>
      <div class="field"><label>Outcome</label><select class="inp" id="oc">
        <option>Contacted</option><option>No Answer</option><option>Promise to Pay</option>
        <option>Arrangement Agreed</option><option>Hardship Identified</option></select></div>
      <div class="field"><label>Note</label><textarea class="inp" id="nt" rows="4"
        placeholder="What was discussed and agreed."></textarea></div>
    </div>`, {
    footer: `<button class="btn primary" id="save">Save to ledger</button>`,
    onMount: dr => dr.querySelector('#save').onclick = async () => {
      await api('/collections/outreach', { method: 'POST', body: {
        member_id: mid, channel: dr.querySelector('#ch').value,
        outcome: dr.querySelector('#oc').value, note: dr.querySelector('#nt').value } });
      toast('Outreach logged', 'Recorded in the decision ledger.', 'good');
      const { closeDrawer } = await import('/lib.js'); closeDrawer(); window.render();
    }
  });
}

// ------------------------------------------------------------ early warning
export async function earlyWarning(el) {
  const { rows } = await api('/early-warning');
  const buckets = {};
  rows.forEach(r => (buckets[r.state.state] ||= []).push(r));
  el.innerHTML = `
  <div class="page-head"><div><h1>Early Warning</h1>
    <p>Members are compared against their <b>own</b> historical baseline, not against a generic borrower.
       Signals must be corroborated by an independent source before an alert escalates.</p></div>
    <div class="spacer"></div>
    ${['AT_RISK', 'ELEVATED', 'WATCH', 'RECOVERY', 'STABLE'].map(s =>
      `<span class="tag t-${toneFor(s)}">${s.replace('_', ' ')} ${(buckets[s] || []).length}</span>`).join('')}
  </div>
  <div class="col" style="gap:12px">
    ${rows.filter(r => r.state.state !== 'STABLE').map(card).join('') ||
      '<div class="empty">Every member is inside their own baseline.</div>'}
    <div class="card"><div class="card-h"><h3>Stable members</h3><span class="sub">monitored, no action</span></div>
      <div class="card-b row wrap" style="gap:8px">
        ${(buckets.STABLE || []).map(r => `<button class="chip" data-m="${r.member_id}">${esc(r.name)}</button>`).join('')}
      </div></div>
  </div>`;
  $$('[data-m]', el).forEach(b => b.onclick = () => window.go('members', b.dataset.m));

  function card(r) {
    return `<div class="card"><div class="card-h">
      <div class="avatar sm">${esc(r.name.split(' ').map(x => x[0]).join(''))}</div>
      <h3>${esc(r.name)}</h3>${tag(r.state.state)}
      <span class="sub">${r.change_point.days_ago ? `change point ${r.change_point.days_ago} days ago` : 'no change point'}</span>
      <div class="spacer"></div>
      <span class="tag t-grey">30-day late ${pct(r.forecast.p_late_30d, 0)}</span>
      <span class="tag t-grey">recovery ${pct(r.forecast.recovery_likelihood, 0)}</span>
      <button class="btn sm" data-m="${r.member_id}">Open ${icon('chevron', 12)}</button></div>
      <div class="card-b grid g-2-1">
        <div>${stepChart(r.series, { h: 130, threshold: Math.max(3, r.baseline.mean_days_late + 2 * r.baseline.sd) })}</div>
        <div class="col" style="gap:8px">
          <div class="note ${r.state.state === 'AT_RISK' ? 'red' : r.state.state === 'RECOVERY' ? 'purple' : 'amber'}">
            <b>Why now</b><div class="small">${esc(r.why_now)}</div></div>
          <div class="small muted"><b>${esc(r.corroboration.verdict)}</b></div>
          ${r.corroboration.supporting.map(s => `<div class="tiny muted">• ${esc(s.source)}: ${esc(s.detail)}</div>`).join('')}
          ${r.corroboration.mitigating.map(s => `<div class="tiny" style="color:var(--green)">• suppressed by ${esc(s.source)}: ${esc(s.detail)}</div>`).join('')}
          <div class="sep" style="margin:6px 0"></div>
          <div class="row"><span class="tag t-blue">${esc(r.intervention.action)}</span></div>
          <div class="tiny muted">${esc(r.intervention.rationale)}</div>
        </div></div></div>`;
  }
}
