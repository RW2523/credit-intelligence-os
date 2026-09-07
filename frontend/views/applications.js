import { api, sse, icon, esc, money, num, pct, tag, toneFor, drawer, closeDrawer, toast,
         date, dtime, gauge, barChart, stepChart, h, $, $$ } from '/lib.js';

let filters = { q: '', product: '', branch: '', risk: '', status: '', officer: '' };

export function openWorkbench(id) { window.go('workbench', id); }

// ============================================================== QUEUE
export async function applications(el, param) {
  if (param) return openWorkbench(param);
  const qs = new URLSearchParams(Object.fromEntries(Object.entries(filters).filter(([, v]) => v))).toString();
  const { rows, facets } = await api('/applications?' + qs);

  el.innerHTML = `
  <div class="page-head">
    <div><h1>Applications</h1><p>${rows.length} case${rows.length === 1 ? '' : 's'} in the queue.
      Every row carries its own deterministic policy result, calibrated risk and evidence completeness.</p></div>
    <div class="spacer"></div>
    <button class="btn" id="bulkDocs">${icon('send')} Request documents</button>
    <button class="btn primary" data-go="intake">${icon('plus')} New application</button>
  </div>

  <div class="card" style="margin-bottom:14px"><div class="card-b row wrap" style="gap:10px">
    <div class="search" style="max-width:280px;margin:0">
      <span class="si">${icon('search', 15)}</span>
      <input id="q" placeholder="Search name, id, product…" value="${esc(filters.q)}"/></div>
    ${sel('product', 'All products', facets.product)}
    ${sel('branch', 'All branches', facets.branch)}
    ${sel('risk', 'All risk', facets.risk)}
    ${sel('status', 'All states', facets.status)}
    ${sel('officer', 'All officers', facets.officer)}
    <button class="btn ghost sm" id="clearF">Clear</button>
    <div class="spacer" style="flex:1"></div>
    <span class="small muted">${rows.filter(r => !r.decided).length} open · ${rows.filter(r => r.decided).length} decided</span>
  </div></div>

  <div class="card"><div class="tw"><table>
    <thead><tr>
      <th style="width:26px"><input type="checkbox" id="all"/></th>
      <th>Applicant</th><th>Product</th><th class="r">Amount</th><th>Policy</th><th>DSR</th>
      <th>Risk</th><th>Integrity</th><th>Docs</th><th>AI recommendation</th><th>Route</th><th>Next</th><th></th>
    </tr></thead>
    <tbody>${rows.map(r => `<tr class="clickable" data-id="${r.id}">
      <td onclick="event.stopPropagation()"><input type="checkbox" class="sel" value="${r.id}"/></td>
      <td><div class="row"><div class="avatar sm">${r.initials}</div>
        <div><div style="font-weight:560">${esc(r.name)}</div>
        <div class="tiny dim mono">${r.id} · ${esc(r.branch)}</div></div></div></td>
      <td class="small">${esc(r.product)}<div class="tiny dim">${esc(r.officer)}</div></td>
      <td class="r num" style="font-weight:600">${money(r.amount)}</td>
      <td>${tag(r.policy)}</td>
      <td class="num small">${r.dsr}%</td>
      <td>${tag(r.risk)}<div class="tiny dim num">PD ${pct(r.pd, 1)}</div></td>
      <td>${tag(r.fraud)}</td>
      <td><span class="tag ${r.docs.v < r.docs.t ? 't-amber' : 't-green'}">${r.docs.v}/${r.docs.t}</span></td>
      <td>${r.recommendation === 'Not run' ? '<span class="tiny dim">not run</span>'
            : `${tag(r.recommendation)}<div class="tiny dim num">conf ${r.confidence} · dis ${r.disagreement}</div>`}</td>
      <td>${tag(r.route)}</td>
      <td class="small">${r.decided ? tag(r.decision) : esc(r.next)}</td>
      <td>${icon('chevron', 14)}</td></tr>`).join('')}</tbody></table></div>
    ${rows.length ? '' : '<div class="empty">No cases match these filters.</div>'}
  </div>`;

  const rerender = () => applications(el);
  $('#q', el).oninput = e => { filters.q = e.target.value; clearTimeout(window._qt); window._qt = setTimeout(rerender, 260); };
  $$('select[data-f]', el).forEach(s => s.onchange = () => { filters[s.dataset.f] = s.value; rerender(); });
  $('#clearF', el).onclick = () => { filters = { q: '', product: '', branch: '', risk: '', status: '', officer: '' }; rerender(); };
  $('#all', el).onclick = e => $$('.sel', el).forEach(c => c.checked = e.target.checked);
  $('#bulkDocs', el).onclick = () => {
    const n = $$('.sel:checked', el).length;
    toast(n ? `Document request queued for ${n} case(s)` : 'Select cases first',
          n ? 'Notification service will send the policy-approved template.' : '', n ? 'good' : 'warn');
  };
  $$('tr[data-id]', el).forEach(r => r.onclick = () => quickLook(r.dataset.id));
  el.querySelectorAll('[data-go]').forEach(b => b.onclick = () => window.go(b.dataset.go));
}

const sel = (k, ph, opts) => `<select class="inp" data-f="${k}" style="max-width:160px">
  <option value="">${ph}</option>${opts.map(o => `<option ${filters[k] === o ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select>`;

// ------------------------------------------------------------ quick look
async function quickLook(id) {
  const c = await api('/applications/' + id);
  const p = c.policy, r = c.risk, d = c.documents_summary;
  drawer(`<div class="row"><div class="avatar">${c.member.initials}</div>
      <div><h3>${esc(c.member.name)}</h3><div class="tiny dim mono">${c.application.id}</div></div></div>`, `
    <div class="col" style="gap:14px">
      <div class="row wrap">${tag(p.result)}${tag(r.grade)}${tag(c.fraud.level)}
        <span class="tag t-grey">${esc(c.application.product)}</span>
        <span class="tag t-blue">${money(c.application.amount)}</span></div>
      <dl class="kv">
        <dt>Instalment</dt><dd>${money(p.instalment)} / month</dd>
        <dt>Debt service ratio</dt><dd>${p.dsr}% <span class="dim">of ${p.dsr_ceiling}%</span></dd>
        <dt>Verified income</dt><dd>${money(p.income.verified_annual)}</dd>
        <dt>Probability of default</dt><dd>${pct(r.pd, 1)}</dd>
        <dt>Evidence</dt><dd>${d.verified} / ${d.required} verified</dd>
        <dt>Authority required</dt><dd>${esc(p.authority_required)}</dd>
      </dl>
      ${d.missing.length ? `<div class="note amber"><b>Missing evidence</b>
        <div class="small">${d.missing.map(esc).join(' · ')}</div></div>` : ''}
      ${c.reconciliation.exceptions.map(x => `<div class="note ${x.severity === 'high' ? 'red' : 'amber'}">
        <b>${esc(x.title)}</b><div class="small">${esc(x.detail)}</div>
        <div class="tiny dim">${esc(x.classification)}</div></div>`).join('')}
      ${c.council ? `<div class="note ${c.council.summary.recommendation === 'APPROVE' ? 'green' : ''}">
        <b>Council: ${esc(c.council.summary.recommendation)}</b>
        <div class="small">${esc(c.council.summary.rationale)}</div>
        <div class="tiny dim">confidence ${c.council.summary.confidence} · disagreement ${c.council.summary.disagreement}</div></div>`
      : `<div class="note"><b>The Council has not deliberated on this case yet.</b>
        <div class="small muted">Open the workbench to run it.</div></div>`}
    </div>`, {
    footer: `<button class="btn primary" id="ow">${icon('eye')} Open Workbench</button>
             <button class="btn" id="rd">${icon('send')} Request documents</button>
             <button class="btn ghost" id="esc">Escalate</button>`,
    onMount: dr => {
      dr.querySelector('#ow').onclick = () => { closeDrawer(); openWorkbench(id); };
      dr.querySelector('#rd').onclick = async () => {
        await api(`/applications/${id}/decision`, { method: 'POST',
          body: { action: 'Request Information', reason: 'Outstanding mandatory evidence requested from member.' } });
        closeDrawer(); toast('Documents requested', 'Logged to the decision ledger.', 'good'); window.render();
      };
      dr.querySelector('#esc').onclick = async () => {
        await api(`/applications/${id}/decision`, { method: 'POST',
          body: { action: 'Escalate', reason: 'Escalated to senior officer from the queue.' } });
        closeDrawer(); toast('Escalated', 'Routed to Senior Officer.', 'warn'); window.render();
      };
    }
  });
}

// ========================================================== WORKBENCH
let tab = 'overview';
export async function workbench(el, id) {
  if (!id) return window.go('applications');
  const c = await api('/applications/' + id);
  const p = c.policy, r = c.risk, f = c.fraud, d = c.documents_summary;
  const s = c.council?.summary;

  el.innerHTML = `
  <div class="page-head">
    <button class="btn-icon" id="back">${icon('chevron', 16, 'flip')}</button>
    <div class="row" style="gap:12px">
      <div class="avatar lg">${c.member.initials}</div>
      <div><h1>${esc(c.member.name)}</h1>
        <p class="mono tiny">${c.application.id} · member ${c.member.id} · ${esc(c.application.branch)} ·
           submitted ${dtime(c.application.submitted)}</p></div>
    </div>
    <div class="spacer"></div>
    <div class="col" style="align-items:flex-end;gap:4px">
      <div style="font-size:20px;font-weight:700">${money(c.application.amount)}</div>
      <div class="tiny dim">${esc(c.application.product)} · ${c.application.term} months · ${esc(c.application.purpose)}</div>
    </div>
  </div>

  <div class="grid g5" style="margin-bottom:14px">
    ${stat('Affordability', p.affordability, `DSR ${p.dsr}% of ${p.dsr_ceiling}%`, toneFor(p.affordability))}
    ${stat('Credit risk', r.grade, `PD ${pct(r.pd, 1)} · score ${r.score}`, toneFor(r.grade))}
    ${stat('Integrity', f.level, f.headline.slice(0, 42), toneFor(f.level))}
    ${stat('Evidence', `${d.verified} / ${d.required}`, d.missing.length ? `missing ${d.missing.length}` : 'complete', d.complete ? 'green' : 'amber')}
    ${stat('Member state', c.lmi.state.state, `${pct(c.lmi.forecast.p_late_30d, 0)} 30-day late risk`, toneFor(c.lmi.state.state))}
  </div>

  <div class="grid g-2-1" style="margin-bottom:14px">
    <div class="card" id="councilCard">${councilPanel(c)}</div>
    <div class="col" style="gap:14px">
      <div class="card"><div class="card-h"><h3>Autonomy routing</h3></div><div class="card-b col" style="gap:9px">
        <div class="row">${tag(c.routing.path)}<span class="tag t-grey">mode ${esc(c.routing.mode)}</span>
          <span class="tag t-grey">${esc(p.authority_required)}</span></div>
        <ul class="small muted" style="padding-left:16px;line-height:1.7">
          ${c.routing.reasons.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
        <div class="tiny dim">The Board-set Autonomy Dial is the only path to autonomous execution.</div>
      </div></div>
      <div class="card"><div class="card-h"><h3>What changes the outcome?</h3></div>
        <div class="card-b col" style="gap:10px">
          <div><div class="up" style="color:var(--green)">Improves if</div>
            <ul class="small muted" style="padding-left:16px;line-height:1.75">
              ${c.counterfactuals.improves.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>
          <div><div class="up" style="color:var(--red)">Deteriorates if</div>
            <ul class="small muted" style="padding-left:16px;line-height:1.75">
              ${c.counterfactuals.deteriorates.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>
        </div></div>
    </div>
  </div>

  <div class="card" style="margin-bottom:14px">
    <div class="tabs" id="tabs">
      ${['overview', 'documents', 'financials', 'risk', 'member', 'activity']
        .map(t => `<button class="tab ${tab === t ? 'on' : ''}" data-tab="${t}">${
          { overview: 'Overview', documents: 'Documents & evidence', financials: 'Policy & affordability',
            risk: 'Risk & integrity', member: 'Member profile', activity: 'Activity & ledger' }[t]}</button>`).join('')}
    </div>
    <div class="card-b" id="tabBody"></div>
  </div>

  <div class="card">
    <div class="card-h"><h3>Officer decision</h3>
      <span class="sub">${s ? `AI recommends ${s.recommendation}` : 'Council has not run'}</span>
      <div class="spacer"></div>
      ${c.decision ? tag(c.decision.action) : '<span class="tag t-grey">pending</span>'}</div>
    <div class="card-b">${decisionPanel(c)}</div>
  </div>`;

  $('#back', el).onclick = () => window.go('applications');
  $$('[data-tab]', el).forEach(b => b.onclick = () => { tab = b.dataset.tab; workbench(el, id); });
  renderTab($('#tabBody', el), c);
  bindCouncil(el, c);
  bindDecision(el, c);
}

const stat = (l, v, sub, tone) => `<div class="kpi accent-${tone === 'green' ? 'green' : tone === 'red' ? 'red' : tone === 'amber' ? 'amber' : ''}">
  <div class="lbl">${l}</div><div class="val" style="font-size:19px;color:var(--${tone === 'grey' ? 'ink' : tone})">${esc(v)}</div>
  <div class="sub">${esc(sub)}</div></div>`;

// ------------------------------------------------------------- council
function councilPanel(c) {
  const s = c.council?.summary;
  return `<div class="card-h">${icon('cpu', 15)}<h3>AI Credit Council</h3>
      <span class="sub">bounded deliberation over registered evidence</span>
      <div class="spacer"></div>
      <button class="btn ${s ? '' : 'primary'} sm" id="runCouncil">${icon('refresh', 13)} ${s ? 'Re-run' : 'Run Council'}</button></div>
    <div class="card-b" id="councilBody">
      ${s ? summaryBlock(c) : `<div class="empty">${icon('cpu', 26)}
        <b>The Council has not deliberated on this case</b>
        <span class="small">Five specialist agents plus a Challenger will reason over the registered evidence,
        then a Synthesizer produces a governed recommendation. Nothing is decided without a person.</span></div>`}
    </div>`;
}

function summaryBlock(c) {
  const s = c.council.summary, pos = c.council.positions, ch = c.council.challenger;
  const conf = s.confidence;
  return `
  <div class="row wrap" style="gap:18px;align-items:flex-start">
    <div style="width:150px">${gauge(conf, { label: Math.round(conf * 100) + '%', sub: 'confidence',
      color: conf > .85 ? '#2ecc8f' : conf > .7 ? '#f5a623' : '#f2545b' })}</div>
    <div style="flex:1;min-width:220px" class="col">
      <div class="row wrap">${tag(s.recommendation)}
        <span class="tag t-grey">disagreement ${s.disagreement}</span>
        <span class="tag t-grey">${esc(s.dissent_count)} dissenting</span>
        ${c.council.grounding.llm_positions ? `<span class="tag t-purple">${c.council.grounding.llm_positions}/${c.council.grounding.total_positions} model-authored</span>` : ''}
        ${c.council.grounding.unsupported ? `<span class="tag t-red">${c.council.grounding.unsupported} unsupported citation(s)</span>`
          : '<span class="tag t-green">all claims cited</span>'}</div>
      <div style="font-size:13px">${esc(s.rationale)}</div>
      <div class="note"><b>Decisive factor — ${esc(s.decisive_factor)}</b>
        <div class="small muted">${esc(s.decisive_detail)}</div></div>
      ${s.unresolved.length ? `<div class="note amber"><b>Unresolved reservations</b>
        <ul class="small" style="padding-left:16px;margin-top:3px">${s.unresolved.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>` : ''}
      ${s.conditions.length ? `<div class="note green"><b>Conditions attached</b>
        <ul class="small" style="padding-left:16px;margin-top:3px">${s.conditions.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>` : ''}
    </div>
  </div>
  <div class="sep"></div>
  <div class="col" style="gap:8px" id="positions">
    ${pos.map(agentCard).join('')}
    ${agentCard(ch, true)}
  </div>
  <div class="sep"></div>
  <div class="row wrap" style="gap:6px">
    <span class="up" style="margin-right:4px">Evidence register</span>
    ${c.council.evidence.map(e => `<span class="ev-chip" title="${esc(e.text)}">${e.id}</span>`).join('')}
  </div>`;
}

function agentCard(a, isChallenger = false) {
  const tone = toneFor(a.stance);
  return `<div class="agent" data-agent="${a.id}">
    <div class="ah">
      ${icon(a.icon || 'cpu', 15)}
      <div style="flex:1;min-width:0">
        <div class="an">${esc(a.name)} ${a.revised ? '<span class="tag t-purple">revised</span>' : ''}
          ${a.escalated ? '<span class="tag t-amber">escalated</span>' : ''}
          ${a._source === 'llm' ? '' : '<span class="tag t-grey" title="The local model was unavailable; this position comes from the deterministic engine">rule-based</span>'}</div>
        <div class="small muted">${esc(a.headline || '')}</div>
      </div>
      <span class="tag t-${tone}">${esc(a.stance)}</span>
      <span class="mono dim">${a.confidence ?? ''}</span>
      ${icon('down', 14)}
    </div>
    <div class="ab" style="display:none">
      <div>${esc(a.reasoning || '')}</div>
      ${a.numeric_rewrite ? `<div class="note amber" style="margin-top:8px">
        <b>Grounding rule applied.</b> <span class="small">The model restated figures, so its reasoning was
        replaced with the engine's own wording. Its draft is kept for audit.</span>
        <details style="margin-top:5px"><summary class="small linkish">Show the model's draft</summary>
        <div class="small dim" style="margin-top:5px">${esc(a.reasoning_model || '')}</div></details></div>` : ''}
      ${a.ask ? `<div class="note amber" style="margin-top:8px"><b>Requests</b> ${esc(a.ask)}</div>` : ''}
      ${a.revision_note ? `<div class="note purple" style="margin-top:8px"><b>Revised after challenge</b> ${esc(a.revision_note)}</div>` : ''}
      <div class="row wrap" style="margin-top:8px;gap:5px">
        <span class="up">cites</span>${(a.evidence || []).map(e => `<span class="ev-chip">${esc(e)}</span>`).join('')}</div>
    </div></div>`;
}

function bindCouncil(el, c) {
  const body = () => $('#councilBody', el);
  const bindToggles = () => $$('.agent .ah', el).forEach(a => a.onclick = () => {
    const b = a.nextElementSibling; b.style.display = b.style.display === 'none' ? 'block' : 'none';
  });
  bindToggles();

  $('#runCouncil', el).onclick = () => {
    const btn = $('#runCouncil', el);
    btn.disabled = true; btn.innerHTML = `${icon('refresh', 13)} Deliberating…`;
    const seen = new Map();
    body().innerHTML = `<div class="col" style="gap:8px" id="live"></div>`;
    const live = $('#live', el);
    const placeholder = (id, name) => `<div class="agent thinking" id="ag-${id}"><div class="ah">
        <span class="pulse"></span><div style="flex:1"><div class="an">${esc(name)}</div>
        <div class="shimmer" style="width:70%;margin-top:6px"></div></div>
        <span class="tiny dim">reasoning…</span></div></div>`;

    sse(`/applications/${c.application.id}/council/stream`, {
      start: d => {
        live.innerHTML = `<div class="note"><b>Deliberation started</b>
          <div class="small muted">${d.evidence.length} pieces of evidence registered ·
          model ${esc(d.model.available ? d.model.model : 'deterministic fallback')}</div></div>`;
      },
      agent_start: d => { live.insertAdjacentHTML('beforeend', placeholder(d.id, d.name)); },
      agent: d => {
        seen.set(d.id, d);
        const ph = $('#ag-' + d.id, el);
        const card = h(agentCard(d, d.id === 'challenger'));
        if (ph) ph.replaceWith(card); else live.appendChild(card);
        card.classList.add('rise');
        bindToggles();
      },
      challenge: d => {
        live.insertAdjacentHTML('beforeend', `<div class="note purple rise">
          <b>${esc(d.from)} → ${esc(d.to)}</b><div class="small">${esc(d.question)}</div>
          <div class="tiny dim" style="margin-top:3px">Requests: ${esc(d.ask || '')}</div></div>`);
      },
      revision: d => {
        live.insertAdjacentHTML('beforeend', `<div class="note green rise"><b>${esc(d.name)} revised its position</b>
          <div class="small">${esc(d.headline)}</div></div>`);
      },
      summary: async () => { toast('Council complete', 'Recommendation synthesized and sealed to the ledger.', 'good'); },
      routing: () => {},
      error: d => { toast('Council failed', d.message, 'bad'); btn.disabled = false; },
      close: async () => { await workbench(el, c.application.id); },
    });
  };
}

// ------------------------------------------------------------- decision
function decisionPanel(c) {
  if (c.decision) {
    const dd = c.decision;
    return `<div class="col" style="gap:12px">
      <div class="row wrap">${tag(dd.action)}
        ${dd.override ? '<span class="tag t-purple">override of AI recommendation</span>' : ''}
        <span class="tag t-grey">${esc(dd.actor)} · ${esc(dd.role)}</span>
        <span class="tag t-grey">${dtime(dd.at)}</span></div>
      ${dd.override ? `<div class="note purple"><b>AI recommended ${esc(dd.ai_recommendation)} · officer chose ${esc(dd.action)}</b>
        <div class="small">${esc(dd.reason)}</div></div>`
        : dd.reason ? `<div class="note"><b>Reason</b> ${esc(dd.reason)}</div>` : ''}
      ${dd.conditions?.length ? `<div class="note green"><b>Conditions</b>
        <ul class="small" style="padding-left:16px">${dd.conditions.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>` : ''}
      <div id="execBlock"></div>
    </div>`;
  }
  const rec = c.council?.summary?.recommendation;
  return `<div class="col" style="gap:12px">
    ${rec ? `<div class="note"><b>AI recommendation: ${esc(rec)}</b>
      <div class="small muted">Choosing a different outcome is an override and requires a written reason,
      which is recorded in the decision ledger.</div></div>` : ''}
    <div class="field"><label>Reason / note (required for an override)</label>
      <textarea class="inp" id="reason" rows="2" placeholder="e.g. Secondary income confirmed directly with the employer."></textarea></div>
    <div class="row wrap" style="gap:8px">
      <button class="btn good lg" data-act="Approve">${icon('check')} Approve</button>
      <button class="btn bad lg" data-act="Decline">${icon('x')} Decline</button>
      <button class="btn warn lg" data-act="Request Information">${icon('send')} Request information</button>
      <button class="btn lg" data-act="Escalate">${icon('up')} Escalate</button>
      <div class="spacer" style="flex:1"></div>
      <button class="btn lg" id="askAI">${icon('msg')} Ask Credit AI</button>
    </div>
    <div class="tiny dim">Approving issues a governed approval token; the execution service is the only component
      permitted to write to the core financing system.</div>
  </div>`;
}

function bindDecision(el, c) {
  const ask = $('#askAI', el);
  if (ask) ask.onclick = () => askDrawer(c.application.id, c.member.name);
  $$('[data-act]', el).forEach(b => b.onclick = async () => {
    const action = b.dataset.act, reason = $('#reason', el)?.value || '';
    b.disabled = true;
    try {
      const res = await api(`/applications/${c.application.id}/decision`, {
        method: 'POST', body: { action, reason, actor: 'Sarah Kim', role: 'Credit Officer' } });
      toast(`${action} recorded`, res.decision.override ? 'Override reason sealed to the ledger.' : 'Sealed to the decision ledger.', 'good');
      await workbench(el, c.application.id);
      if (res.execution) showExecution(res.execution);
    } catch (e) { toast('Not recorded', e.message, 'bad'); b.disabled = false; }
  });
  if (c.decision) api(`/applications/${c.application.id}/execution`).then(x => {
    if (x && x.account) $('#execBlock', el).innerHTML = execHTML(x);
  });
}

const execHTML = x => `<div class="card"><div class="card-h">${icon('layers', 15)}<h3>Core execution</h3>
    <span class="sub">facility ${esc(x.account)}</span></div><div class="card-b">
  <div class="stepper">${x.steps.map((s, i) => `<div class="step done"><span class="n">${icon('check', 10)}</span>${esc(s.name)}</div>`).join('')}</div>
  <div class="sep"></div>
  <div class="row wrap small muted" style="gap:16px">
    <span>Instalment <b class="num" style="color:var(--ink)">${money(x.instalment)}</b></span>
    <span>Rate <b style="color:var(--ink)">${x.rate}%</b></span>
    <span>Term <b style="color:var(--ink)">${x.term} months</b></span>
    <span>First due <b style="color:var(--ink)">${date(x.first_due)}</b></span>
    <span class="mono dim">token ${esc(String(x.token).slice(0, 16))}…</span></div>
  <div class="tw" style="margin-top:10px"><table><thead><tr><th>#</th><th>Due</th><th class="r">Amount</th>
    <th class="r">Principal</th><th class="r">Interest</th><th class="r">Balance</th></tr></thead>
    <tbody>${x.schedule.map(s => `<tr><td>${s.n}</td><td class="small">${date(s.due)}</td>
      <td class="r num">${money(s.amount, 2)}</td><td class="r num">${money(s.principal, 2)}</td>
      <td class="r num">${money(s.interest, 2)}</td><td class="r num">${money(s.balance, 2)}</td></tr>`).join('')}</tbody></table></div>
  </div></div>`;

function showExecution(x) {
  drawer(`<h3>Facility activated</h3>`, `<div class="col" style="gap:12px">
    <div class="note green"><b>${esc(x.account)} created in the core system</b>
      <div class="small">Approval token validated, idempotency key ${esc(x.idempotency_key)}.</div></div>
    ${execHTML(x)}</div>`, { wide: true });
}

// ------------------------------------------------------------- ask AI
export function askDrawer(appId, who) {
  drawer(`<div class="row">${icon('msg', 16)}<h3>Ask Credit AI${who ? ` — ${esc(who)}` : ''}</h3></div>`, `
    <div class="col" style="gap:12px">
      <div class="note"><b>Grounded assistant.</b> <span class="small">It answers only from this case's frozen
        snapshot, its registered evidence and the policy library. It will not state a credit decision.</span></div>
      <div class="chips" id="suggest">
        ${['Why is this applicant at this risk grade?', 'Which policies apply to this case?',
           'Compare the payslip with the bank statement.', 'What evidence is missing?',
           'What would change the recommendation?'].map(q => `<button class="chip">${esc(q)}</button>`).join('')}
      </div>
      <div class="chat" id="chat"></div>
      <div class="row"><input class="inp" id="qin" placeholder="Ask about this case…"/>
        <button class="btn primary" id="send">${icon('send')}</button></div>
    </div>`, {
    wide: false,
    onMount: dr => {
      const chat = dr.querySelector('#chat'), input = dr.querySelector('#qin');
      const send = async () => {
        const q = input.value.trim(); if (!q) return;
        input.value = '';
        chat.insertAdjacentHTML('beforeend', `<div class="msg me">${esc(q)}</div>`);
        const bubble = h(`<div class="msg ai"><span class="pulse"></span></div>`);
        chat.appendChild(bubble); chat.scrollTop = chat.scrollHeight;
        let text = '';
        sse('/ask', {
          meta: m => bubble.innerHTML = '',
          token: t => { text += t.t; bubble.textContent = text; chat.scrollTop = chat.scrollHeight; },
          done: () => { chat.scrollTop = chat.scrollHeight; },
          error: e => bubble.textContent = 'Assistant unavailable: ' + e.message,
        }, { method: 'POST', body: { question: q, application_id: appId } });
      };
      dr.querySelector('#send').onclick = send;
      input.onkeydown = e => { if (e.key === 'Enter') send(); };
      dr.querySelectorAll('#suggest .chip').forEach(b => b.onclick = () => { input.value = b.textContent; send(); });
    }
  });
}

// ---------------------------------------------------------------- tabs
function renderTab(el, c) {
  const p = c.policy, r = c.risk, f = c.fraud;
  if (tab === 'overview') {
    el.innerHTML = `<div class="grid g2">
      <div class="col" style="gap:12px">
        <div class="up">Decision factors</div>
        ${c.decision_factors.map(x => `<div>
          <div class="row small"><span style="flex:1">${esc(x.name)}</span>
            <span class="tag t-${x.direction === 'positive' ? 'green' : 'amber'}">${esc(x.direction)}</span></div>
          <div class="meter" style="margin-top:5px"><div class="bar"><i style="width:${Math.min(100, Math.abs(x.weight) * 100)}%;
            background:${x.direction === 'positive' ? 'var(--green)' : 'var(--amber)'}"></i></div>
            <span class="mono dim">${x.weight}</span></div>
          <div class="tiny dim" style="margin-top:3px">${esc(x.detail)}</div></div>`).join('')}
      </div>
      <div class="col" style="gap:12px">
        <div class="up">Case snapshot</div>
        <dl class="kv">
          <dt>Snapshot hash</dt><dd class="mono">${esc(c.snapshot.hash)}</dd>
          <dt>Frozen at</dt><dd>${dtime(c.snapshot.frozen_at)}</dd>
          <dt>Policy version</dt><dd>${esc(c.snapshot.policy_version)}</dd>
          <dt>Model version</dt><dd class="mono">${esc(c.snapshot.model_version)}</dd>
          <dt>Documents</dt><dd class="mono tiny">${c.snapshot.documents.join(', ') || '—'}</dd>
          <dt>Channel</dt><dd>${esc(c.application.channel)}</dd>
          <dt>Guarantor</dt><dd>${esc(c.application.guarantor || '—')}</dd>
        </dl>
        <div class="note"><b>Why this matters.</b> <span class="small">Every recommendation is reproducible
          against the exact information that existed at decision time.</span></div>
      </div></div>`;
  }
  if (tab === 'documents') {
    el.innerHTML = `
      <div class="row wrap" style="gap:8px;margin-bottom:12px">
        ${c.documents_summary.required_list.map(t => {
          const has = c.documents.find(d => d.doc_type === t);
          return `<span class="tag t-${has ? (has.status === 'Verified' ? 'green' : 'amber') : 'red'}">
            ${has ? icon('check', 11) : icon('x', 11)} ${esc(t)}</span>`; }).join('')}
      </div>
      <div class="tw"><table><thead><tr><th>Document</th><th>Type</th><th>Status</th><th>Confidence</th>
        <th>Forensics</th><th>Uploaded</th><th></th></tr></thead><tbody>
        ${c.documents.map(d => {
          const fx = c.forensics.find(x => x.doc_id === d.id) || {};
          return `<tr class="clickable" data-doc="${d.id}"><td>${icon('file', 14)} ${esc(d.label)}</td>
            <td class="small">${esc(d.doc_type)}</td><td>${tag(d.status)}</td>
            <td style="width:120px"><div class="meter"><div class="bar thin"><i style="width:${d.confidence}%"></i></div>
              <span class="mono">${d.confidence}%</span></div></td>
            <td>${tag(fx.verdict || 'Clean')}${fx.flags?.length ? `<div class="tiny dim">${esc(fx.flags[0])}</div>` : ''}</td>
            <td class="small dim">${dtime(d.uploaded)}</td><td>${icon('eye', 14)}</td></tr>`; }).join('')}
      </tbody></table></div>
      <div class="sep"></div>
      <div class="up" style="margin-bottom:8px">Cross-source reconciliation</div>
      ${reconTable(c.reconciliation)}
      ${c.reconciliation.exceptions.map(x => `<div class="note ${x.severity === 'high' ? 'red' : 'amber'}" style="margin-top:9px">
        <b>${esc(x.title)}</b> <span class="tag t-grey">${esc(x.policy)}</span>
        <div class="small">${esc(x.detail)}</div>
        <div class="tiny dim">Resolution: ${esc(x.resolution)} · ${esc(x.classification)}</div></div>`).join('')}
      <div class="sep"></div>
      <div class="drop" id="drop">${icon('download', 20)}<div style="margin-top:6px">Drop a document here, or click to browse</div>
        <div class="tiny dim">It is scanned, classified, extracted and registered as evidence on this case.</div></div>`;
    el.querySelectorAll('[data-doc]').forEach(t => t.onclick = () => window.go('documents', t.dataset.doc));
    bindUpload(el, c.application.id);
  }
  if (tab === 'financials') {
    el.innerHTML = `<div class="grid g2">
      <div class="col" style="gap:12px">
        <div class="up">Affordability calculation</div>
        <dl class="kv">
          <dt>Declared annual income</dt><dd>${money(p.income.declared_annual)}</dd>
          <dt>Payslip (annualised)</dt><dd>${money(p.income.payslip_annual)}</dd>
          <dt>Bank deposits (annualised)</dt><dd>${money(p.income.bank_annual)}</dd>
          <dt><b>Verified income used</b></dt><dd><b>${money(p.income.verified_annual)}</b></dd>
          <dt>Verified monthly net</dt><dd>${money(p.income.verified_monthly, 2)}</dd>
          <dt>Existing commitments</dt><dd>${money(p.existing_commitments)}</dd>
          <dt>New instalment</dt><dd>${money(p.instalment, 2)}</dd>
          <dt><b>Total obligations</b></dt><dd><b>${money(p.total_obligations, 2)}</b></dd>
          <dt>Debt service ratio</dt><dd><b style="color:var(--${p.dsr <= p.dsr_ceiling ? 'green' : 'red'})">${p.dsr}%</b> of ${p.dsr_ceiling}%</dd>
          <dt>Maximum supportable financing</dt><dd>${money(p.max_financing)}</dd>
        </dl>
        <div class="note ${p.income.material_variance ? 'amber' : ''}"><b>Income basis</b>
          <div class="small">${esc(p.income.basis)} — ${p.income.variance_pct}% variance.</div></div>
      </div>
      <div class="col" style="gap:12px">
        <div class="up">Policy gates · ${esc(p.policy_version)}</div>
        ${p.gates.map(g => `<div class="row" style="gap:10px;padding:7px 0;border-bottom:1px solid var(--line-soft)">
          <span class="tag t-${g.passed ? 'green' : 'red'}">${g.passed ? icon('check', 11) : icon('x', 11)}</span>
          <div style="flex:1"><div style="font-size:12.5px">${esc(g.name)}</div>
            <div class="tiny dim">${esc(g.id)} · requires ${esc(g.required)}</div></div>
          <span class="mono small">${esc(g.actual)}</span></div>`).join('')}
        <div class="note ${p.result === 'PASS' ? 'green' : 'red'}"><b>Policy result: ${esc(p.result)}</b>
          <div class="small">Authority required: ${esc(p.authority_required)}. Exposure ${money(p.exposure)} against a
            ${money(p.exposure_cap)} cap.</div></div>
      </div></div>`;
  }
  if (tab === 'risk') {
    el.innerHTML = `<div class="grid g2">
      <div class="col" style="gap:12px">
        <div class="row" style="gap:16px">
          <div style="width:140px">${gauge(Math.min(1, r.pd * 5), { label: pct(r.pd, 1), sub: 'prob. of default',
            color: r.pd < .07 ? '#2ecc8f' : r.pd < .13 ? '#f5a623' : '#f2545b' })}</div>
          <div class="col" style="flex:1">
            <div class="row wrap">${tag(r.grade)}<span class="tag t-grey">band ${r.band}</span>
              <span class="tag t-grey">score ${r.score}</span></div>
            <div class="tiny dim">${esc(r.model_version)} · calibration ${esc(r.calibration)} ·
              population base rate ${pct(r.base_rate, 1)}</div>
            <div class="small muted">Ensemble: logistic regression ${pct(r.pd_lr, 1)} · gradient boosting ${pct(r.pd_gb, 1)}</div>
          </div></div>
        <div class="up">Reason codes</div>
        ${r.reason_codes.length ? r.reason_codes.map(x => `<div class="note amber small">${esc(x)}</div>`).join('')
          : '<div class="note green small">No adverse reason codes generated.</div>'}
        <div class="up" style="margin-top:6px">Model drivers</div>
        ${r.drivers.slice(0, 7).map(dv => `<div class="row" style="gap:9px">
          <span style="flex:1;font-size:12px">${esc(dv.label)} <span class="dim mono">${dv.value}</span></span>
          <div class="bar thin" style="width:120px"><i style="width:${Math.min(100, Math.abs(dv.contribution) * 55)}%;
            background:${dv.contribution > 0 ? 'var(--red)' : 'var(--green)'}"></i></div>
          <span class="mono tiny dim" style="width:44px;text-align:right">${dv.contribution > 0 ? '+' : ''}${dv.contribution}</span>
        </div>`).join('')}
      </div>
      <div class="col" style="gap:12px">
        <div class="row">${tag(f.level)}<span class="small muted">${esc(f.headline)}</span></div>
        <div class="note ${f.level === 'Clear' ? 'green' : 'amber'}"><b>${esc(f.disclaimer)}</b></div>
        <div class="up">Integrity checks</div>
        ${f.checks.map(x => `<div class="row" style="gap:9px;padding:6px 0;border-bottom:1px solid var(--line-soft)">
          <span class="tag t-${x.passed ? 'green' : 'red'}">${x.passed ? icon('check', 11) : icon('alert', 11)}</span>
          <div style="flex:1"><div style="font-size:12.5px">${esc(x.name)}</div>
            <div class="tiny dim">${esc(x.detail)}</div></div></div>`).join('')}
        ${f.graph.length ? `<div class="up" style="margin-top:6px">Relationship graph</div>
          ${f.graph.map(g => `<div class="small muted">${esc(g.a)} ↔ ${esc(g.b)} — ${esc(g.kind)}</div>`).join('')}` : ''}
        <div class="up" style="margin-top:6px">Document hashes</div>
        ${f.doc_hashes.map(x => `<div class="row small"><span style="flex:1">${esc(x.doc)}</span>
          <span class="mono dim">${esc(x.hash)}</span></div>`).join('')}
      </div></div>`;
  }
  if (tab === 'member') {
    const m = c.member, l = c.lmi;
    el.innerHTML = `<div class="grid g2">
      <div class="col" style="gap:12px">
        <dl class="kv">
          <dt>Member since</dt><dd>${date(m.since)} (${p.tenure_months} months)</dd>
          <dt>Branch</dt><dd>${esc(m.branch)}</dd>
          <dt>Savings</dt><dd>${money(m.savings)}</dd>
          <dt>Share capital</dt><dd>${money(m.share_capital)}</dd>
          <dt>Current financing</dt><dd>${money(m.outstanding)}</dd>
          <dt>Prior facilities</dt><dd>${m.prior_loans}</dd>
          <dt>Payment reliability</dt><dd>${m.reliability}%</dd>
          <dt>Employer</dt><dd>${esc(m.employer)}</dd>
          <dt>Employment</dt><dd>${esc(m.employment)}</dd>
        </dl>
        <button class="btn" data-member="${m.id}">${icon('user')} Open full Member 360</button>
      </div>
      <div class="col" style="gap:10px">
        <div class="row">${tag(l.state.state)}<span class="small muted">${esc(l.why_now)}</span></div>
        ${stepChart(l.series, { threshold: 5 })}
        <div class="row wrap small muted" style="gap:14px">
          <span>Baseline <b style="color:var(--ink)">${l.baseline.mean_days_late} days late</b></span>
          <span>On-time <b style="color:var(--ink)">${l.baseline.on_time_rate}%</b></span>
          <span>30-day risk <b style="color:var(--ink)">${pct(l.forecast.p_late_30d, 0)}</b></span>
          <span>Recovery <b style="color:var(--ink)">${pct(l.forecast.recovery_likelihood, 0)}</b></span></div>
      </div></div>`;
    el.querySelectorAll('[data-member]').forEach(b => b.onclick = () => window.go('members', b.dataset.member));
  }
  if (tab === 'activity') {
    el.innerHTML = `<div class="timeline">
      ${c.ledger.map(x => `<div class="tl-item ${x.stage.includes('Human') ? 'hot' : x.stage.includes('Execution') ? 'ok' : 'blue'}">
        <div class="row"><b style="font-size:12.5px">${esc(x.stage)}</b>
          <span class="tag t-grey">${esc(x.actor)}</span>
          <span class="tiny dim">${dtime(x.at)}</span></div>
        <div class="small muted">${esc(x.summary)}</div>
        <div class="tiny dim mono">#${x.seq} · ${esc(String(x.hash).slice(0, 20))}…</div></div>`).join('')}
      ${c.comms.map(x => `<div class="tl-item"><div class="row"><b style="font-size:12.5px">${esc(x.title)}</b>
        <span class="tiny dim">${dtime(x.at)}</span></div>
        <div class="small muted">${esc(x.text)}</div></div>`).join('')}
    </div>`;
  }
}

export function reconTable(rec) {
  const cols = [...new Set(rec.rows.flatMap(r => Object.keys(r.values)))];
  return `<div class="tw"><table><thead><tr><th>Attribute</th>
    ${cols.map(c => `<th>${esc(c)}</th>`).join('')}<th>Result</th></tr></thead><tbody>
    ${rec.rows.map(r => `<tr><td style="font-weight:560">${esc(r.attribute)}</td>
      ${cols.map(c => { const v = r.values[c];
        return `<td class="small ${r.result !== 'Match' && v ? 'hl' : ''}">${v === null || v === undefined || v === '' ? '<span class="dim">—</span>' : esc(typeof v === 'number' ? v.toLocaleString() : v)}</td>`; }).join('')}
      <td>${tag(r.result)}<div class="tiny dim">${esc(r.detail)}</div></td></tr>`).join('')}
  </tbody></table></div>`;
}

export function bindUpload(el, appId) {
  const drop = el.querySelector('#drop'); if (!drop) return;
  const input = document.querySelector('#uploader');
  const send = async files => {
    for (const f of files) {
      const fd = new FormData(); fd.append('file', f);
      drop.innerHTML = `<div class="row" style="justify-content:center"><span class="pulse"></span>
        Processing ${esc(f.name)}…</div>`;
      const r = await fetch(`/api/applications/${appId}/documents`, { method: 'POST', body: fd }).then(x => x.json());
      toast('Document registered', `${r.document.doc_type} · ${r.document.confidence}% confidence`, 'good');
    }
    window.render();
  };
  drop.onclick = () => { input.value = ''; input.onchange = () => send(input.files); input.click(); };
  drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); };
  drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); send(e.dataTransfer.files); };
}
