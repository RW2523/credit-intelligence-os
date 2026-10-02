import { api, icon, esc, money, pct, tag, toneFor, date, dtime, stepChart, lineChart, barChart, gauge,
         drawer, toast, $, $$ } from '/lib.js';
import { t, tt, lang } from '/i18n.js';
import { state } from '/app.js';

let mfilter = { q: '', branch: '' };

// ---------------------------------------------------------- member list
export async function members(el, param) {
  if (param) return member360(el, param);
  const qs = new URLSearchParams(Object.fromEntries(Object.entries(mfilter).filter(([, v]) => v))).toString();
  const { rows } = await api('/members?' + qs);
  el.innerHTML = `
  <div class="page-head"><div><h1>${t('Member 360')}</h1>
    <p>${tt('One profile per KT member — service record, savings and share capital, KT financing, salary-deduction behaviour and longitudinal state, shared by underwriting, servicing, collections and every assistant.',
            'Satu profil bagi setiap ahli KT — rekod perkhidmatan, simpanan dan modal syer, pembiayaan KT, tingkah laku potongan gaji dan keadaan longitudinal.')}</p></div></div>
  <div class="card" style="margin-bottom:14px"><div class="card-b row wrap" style="gap:10px">
    <div class="search" style="max-width:300px;margin:0"><span class="si">${icon('search', 15)}</span>
      <input id="mq" placeholder="${tt('Name, member no. or service no.…', 'Nama, no. anggota atau no. tentera…')}" value="${esc(mfilter.q)}"/></div>
    <select class="inp" id="mb" style="max-width:200px"><option value="">${tt('All branches', 'Semua cawangan')}</option>
      ${state.boot.branches.map(b => `<option ${mfilter.branch === b ? 'selected' : ''}>${esc(b)}</option>`).join('')}</select>
    <div class="spacer" style="flex:1"></div><span class="small muted">${rows.length} ${tt('members', 'ahli')}</span></div></div>
  <div class="card"><div class="tw"><table>
    <thead><tr><th>${tt('Member', 'Ahli')}</th><th>${tt('Service', 'Perkhidmatan')}</th><th>${t('Branch')}</th><th class="r">${t('Savings')}</th><th class="r">${t('Share capital')}</th>
      <th class="r">${tt('KT outstanding', 'Baki KT')}</th><th>${tt('Reliability', 'Kebolehpercayaan')}</th><th>${tt('State', 'Keadaan')}</th><th>${tt('30-day late risk', 'Risiko lewat 30 hari')}</th><th></th></tr></thead>
    <tbody>${rows.map(m => `<tr class="clickable" data-m="${m.id}">
      <td><div class="row"><div class="avatar sm">${m.initials}</div>
        <div><div style="font-weight:560">${esc(m.name)}</div><div class="tiny dim mono">${m.id} · ${esc(m.service_no)}</div></div></div></td>
      <td class="small">${esc(m.service_label)}<div class="tiny dim">${esc(m.camp)}</div></td><td class="small">${esc(m.branch)}</td>
      <td class="r num">${money(m.savings)}</td><td class="r num">${money(m.share_capital)}</td>
      <td class="r num">${money(m.outstanding)}</td>
      <td style="width:110px"><div class="meter"><div class="bar thin"><i style="width:${m.reliability}%;background:var(--green)"></i></div>
        <span class="mono">${m.reliability}%</span></div></td>
      <td>${tag(m.lmi_state)}</td>
      <td class="num small">${pct(m.p30, 0)}</td><td>${icon('chevron', 14)}</td></tr>`).join('')}
    </tbody></table></div></div>`;
  $$('[data-m]', el).forEach(r => r.onclick = () => window.go('members', r.dataset.m));
  $('#mq', el).oninput = e => { mfilter.q = e.target.value; clearTimeout(window._mq); window._mq = setTimeout(() => members(el), 280); };
  $('#mb', el).onchange = e => { mfilter.branch = e.target.value; members(el); };
}

// ------------------------------------------------------------ member 360
async function member360(el, mid) {
  const d = await api('/members/' + mid);
  const m = d.member, l = d.lmi;
  el.innerHTML = `
  <div class="page-head">
    <button class="btn-icon" id="back" aria-label="${t('Back')}">${icon('back', 16)}</button>
    <div class="row" style="gap:12px"><div class="avatar lg">${m.initials}</div>
      <div><h1>${esc(m.name)}</h1><p class="tiny">${esc(m.service_label)} · ${esc(m.unit)} · ${esc(m.camp)}</p>
        <p class="tiny mono">${tt('member', 'ahli')} ${m.id} · ${esc(m.service_no)} · MyKad ${esc(m.mykad)} · ${esc(m.branch)} · ${tt('since', 'sejak')} ${date(m.since)}</p></div></div>
    <div class="spacer"></div>
    ${tag(l.state.state)}
    ${state.user.views.includes('collections') || state.user.views.includes('members') ? `<button class="btn" id="outreach">${icon('phone')} ${tt('Log outreach', 'Rekod hubungan')}</button>` : ''}
  </div>

  <div class="grid g5" style="margin-bottom:14px">
    ${k(t('Savings') + ' · Simpanan', money(m.savings))}${k(t('Share capital') + ' · Modal Syer', money(m.share_capital))}
    ${k(tt('KT financing outstanding', 'Baki pembiayaan KT'), money(m.outstanding), `${money(m.deduction)}/${tt('month', 'bulan')} · ${esc(m.repayment_channel)}`)}
    ${k(tt('Salary deductions vs gross', 'Potongan gaji berbanding kasar'), d.external ? (d.external.sola.deduction_ratio ?? '—') + '%' : '—', `${tt('cap', 'had')} 60% · ${tt('headroom', 'ruang')} ${d.external ? money(d.external.sola.monthly_headroom) : '—'}`)}
    ${k(tt('Compulsory retirement', 'Bersara wajib'), m.retirement_date ? date(m.retirement_date) : tt('Pensioner', 'Pesara'), m.months_to_retirement != null ? `${m.months_to_retirement} ${t('months')}` : '')}
  </div>

  ${d.distress ? distressSection(d.distress, d.distress_context) : ''}

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
          color: l.forecast.p_late_30d > .5 ? 'var(--red)' : 'var(--amber)' })}</div>
        <div style="width:118px">${gauge(l.forecast.recovery_likelihood, { size: 112, label: pct(l.forecast.recovery_likelihood, 0), sub: 'recovery', color: 'var(--green)' })}</div>
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
    <div class="card"><div class="card-h"><h3>${tt('Savings contributions', 'Caruman simpanan')}</h3></div><div class="card-b">
      ${lineChart(l.savings_trend.map((v, i) => ({ d: `M-${l.savings_trend.length - 1 - i}`, v })), { keys: ['v'], labels: [tt('Monthly savings (RM)', 'Simpanan bulanan (RM)')], h: 120, colors: ['var(--cyan)'], unit: 'RM' })}
      <div class="tiny dim">${tt('Monthly savings contribution — an independent corroborating source.', 'Caruman simpanan bulanan — sumber pengesahan bebas.')}</div>
    </div></div>
  </div>

  ${d.external ? `<div class="card" style="margin-bottom:14px"><div class="card-h"><h3>${tt('External data', 'Data luaran')}</h3>
    <span class="tag t-amber">${tt('simulated until KT provides sandbox access', 'simulasi sehingga KT memberi akses kotak pasir')}</span></div>
    <div class="card-b grid g3">
      <div><div class="up">Experian CCRIS</div><dl class="kv" style="margin-top:6px">
        <dt>${tt('Facilities', 'Kemudahan')}</dt><dd>${d.external.ccris.facility_count}</dd><dt>${tt('Total outstanding', 'Jumlah tertunggak')}</dt><dd>${money(d.external.ccris.total_outstanding)}</dd>
        <dt>${tt('Worst arrears (12m)', 'Tunggakan terburuk (12b)')}</dt><dd>${d.external.ccris.max_dpd_12m} ${tt('days', 'hari')}</dd><dt>${tt('Legal', 'Undang-undang')}</dt><dd>${esc(d.external.ccris.legal_status)}</dd></dl></div>
      <div><div class="up">SOLA</div><dl class="kv" style="margin-top:6px">
        <dt>${tt('Gross pay', 'Gaji kasar')}</dt><dd>${money(d.external.sola.gross_monthly)}</dd><dt>${tt('Deductions used', 'Potongan digunakan')}</dt><dd>${money(d.external.sola.deductions_used)}</dd>
        <dt>${tt('Headroom to 60%', 'Ruang hingga 60%')}</dt><dd>${money(d.external.sola.monthly_headroom)}</dd><dt>${tt('Channel', 'Saluran')}</dt><dd>${esc(d.external.sola.channel)}</dd></dl></div>
      <div><div class="up">eKYC</div><dl class="kv" style="margin-top:6px">
        <dt>${tt('Status', 'Status')}</dt><dd>${tag(d.external.ekyc.status, d.external.ekyc.status === 'Verified' ? 'green' : 'amber')}</dd>
        <dt>${tt('Face match', 'Padanan wajah')}</dt><dd>${d.external.ekyc.face_match}</dd><dt>${tt('Liveness', 'Kehidupan')}</dt><dd>${esc(d.external.ekyc.liveness)}</dd></dl>
        ${d.external.ekyc.note ? `<div class="tiny" style="color:var(--amber)">${esc(d.external.ekyc.note)}</div>` : ''}</div>
    </div></div>` : ''}

  ${d.crosssell?.length ? `<div class="card" style="margin-bottom:14px"><div class="card-h"><h3>${t('Cross-selling options')}</h3>
    <span class="sub">${tt('the two best next actions for this member', 'dua tindakan terbaik untuk ahli ini')}</span></div><div class="card-b col" style="gap:8px">
    ${d.crosssell.slice(0, 3).map(o => `<div class="row wrap" style="gap:10px">${tag(o.product, 'gold')}
      <div class="chain" style="flex:1">${o.chain.map(c => `<span>${esc(c)}</span>`).join('<i>→</i>')}</div>
      ${o.contactable ? '' : tag(tt('No contact', 'Jangan hubungi'), 'red')}</div>`).join('')}</div></div>` : ''}

  <div class="grid g2">
    <div class="card"><div class="card-h"><h3>${tt('Applications & facilities', 'Permohonan & kemudahan')}</h3></div><div class="tw"><table>
      <thead><tr><th>Case</th><th>Product</th><th class="r">Amount</th><th>Status</th><th>Risk</th><th></th></tr></thead>
      <tbody>${d.applications.map(a => `<tr class="clickable" data-c="${a.id}"><td class="mono tiny">${a.id}</td>
        <td class="small">${esc(a.product)}</td><td class="r num">${money(a.amount)}</td>
        <td>${tag(a.status)}</td><td>${tag(a.risk)}</td><td>${icon('chevron', 13)}</td></tr>`).join('')
        || '<tr><td colspan="6" class="dim small">No applications on record.</td></tr>'}</tbody></table></div></div>
    <div class="card"><div class="card-h"><h3>${tt('Communication history', 'Sejarah komunikasi')}</h3></div><div class="card-b">
      <div class="timeline">${d.comms.map(cm => `<div class="tl-item ${cm.type === 'promise' ? 'hot' : ''}">
        <div class="row"><b style="font-size:12.5px">${esc(cm.title)}</b><span class="tiny dim">${dtime(cm.at)}</span></div>
        <div class="small muted">${esc(cm.text)}</div></div>`).join('')
        || '<div class="small dim">No recorded contact.</div>'}</div></div></div>
  </div>`;

  $('#back', el).onclick = () => window.go('members');
  $$('[data-c]', el).forEach(r => r.onclick = () => window.go('workbench', r.dataset.c));
  $('#outreach', el) && ($('#outreach', el).onclick = () => logOutreach(mid, m.name));
}

const k = (l, v, sub = '') => `<div class="kpi"><div class="lbl">${l}</div><div class="val" style="font-size:19px">${v}</div>${sub ? `<div class="sub">${sub}</div>` : ''}</div>`;

// "Possible Bankruptcy" — restricted to Senior Officer, Collections, Risk, Compliance and Branch Manager (POL-013)
function distressSection(s, ctx) {
  const tone = { Low: 'green', Watch: 'amber', Elevated: 'amber', High: 'red' }[s.band];
  const ms = lang() === 'ms';
  const bandMs = { Low: 'Rendah', Watch: 'Pantau', Elevated: 'Meningkat', High: 'Tinggi' }[s.band];
  return `<div class="card sens" style="margin-bottom:14px">
    <div class="card-h">${icon('alert', 15)}<h3>${tt('Possible bankruptcy — financial-distress outlook', 'Kemungkinan bankrap — tinjauan tekanan kewangan')}</h3>
      <span class="tag t-gold">${icon('lock', 10)} ${tt('restricted · access logged', 'terhad · akses direkod')}</span>
      <div class="spacer"></div>${tag(ms ? bandMs : s.band, tone)}</div>
    <div class="card-b grid g3" style="align-items:start">
      <div class="col" style="gap:10px">
        <div class="row" style="gap:14px">
          <div style="width:118px">${gauge(Math.min(1, Math.sqrt(s.probability_12m / 0.25)), { size: 112, label: (s.probability_12m * 100).toFixed(s.probability_12m < 0.01 ? 2 : 1) + '%',
            sub: tt('12-month', '12 bulan'), color: `var(--${tone})` })}</div>
          <div class="col" style="gap:3px"><div class="small"><b>${s.multiple_of_base}×</b> ${tt('the ~0.3% national rate for civil servants', 'kadar nasional ~0.3% untuk penjawat awam')}</div>
            <div class="small muted">${tt('Total debt incl. other lenders', 'Jumlah hutang termasuk pemberi pinjaman lain')}: <b>${money(s.total_debt)}</b></div>
            <div class="tiny dim">${esc(s.model_version)} · ${tt('trained on', 'dilatih pada')} ${s.trained_on.toLocaleString()} · ${tt('cohort rate', 'kadar kohort')} ${(s.cohort_base_rate * 100).toFixed(2)}%</div></div>
        </div>
        <div class="note gold small">${esc(s.guardrail)}</div>
      </div>
      <div class="col" style="gap:7px">
        <div class="up">${tt('What drives it', 'Pemacu utama')}</div>
        ${s.drivers.length ? s.drivers.map(dv => `<div class="row small" style="gap:8px"><span style="flex:1">${esc(dv.label)}
          <span class="dim mono">${esc(dv.value)}</span></span><div class="bar thin" style="width:90px"><i style="width:${Math.min(100, dv.contribution * 30)}%;background:var(--red)"></i></div></div>`).join('')
          : `<div class="small muted">${tt('No material driver — inside normal ranges.', 'Tiada pemacu ketara — dalam julat biasa.')}</div>`}
        <div class="up" style="margin-top:6px">${tt('Recommended support', 'Sokongan disyorkan')}</div>
        <ul class="small" style="padding-left:16px;line-height:1.7">${s.actions.map(a => `<li>${esc(a)}</li>`).join('')}</ul>
      </div>
      <div class="col" style="gap:7px">
        <div class="up">${tt('National context', 'Konteks nasional')}</div>
        <div class="small">${esc(ctx.headline)}</div>
        ${barChart(ctx.series.map(x => ({ l: x.year, v: x.n })), { h: 110, color: 'var(--gold)' })}
        <div class="tiny dim">${ctx.sources.map(esc).join('<br/>')}</div>
        <div class="tiny dim">${esc(ctx.threshold)}</div>
      </div>
    </div></div>`;
}

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
  <div class="page-head"><div><h1>${t('Early Warning')}</h1>
    <p>${tt('Members are compared against their <b>own</b> salary-deduction history, not against a generic borrower. Signals must be corroborated by an independent source — the ANGKASA feed, savings contributions — before an alert escalates.',
            'Ahli dibandingkan dengan sejarah potongan gaji <b>mereka sendiri</b>. Isyarat mesti disahkan oleh sumber bebas — suapan ANGKASA, caruman simpanan — sebelum amaran ditingkatkan.')}</p></div>
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
