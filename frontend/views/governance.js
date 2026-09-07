import { api, icon, esc, money, num, pct, tag, toneFor, date, dtime, barChart, lineChart, donut,
         drawer, closeDrawer, toast, $, $$ } from '/lib.js';

// ============================================================= SANDBOX
export async function sandbox(el) {
  const boot = await api('/bootstrap');
  el.innerHTML = `
  <div class="page-head"><div><h1>Policy Sandbox</h1>
    <p>Replay every frozen case snapshot under candidate thresholds before anything reaches production.
       Nothing changes until a governed approval is recorded.</p></div></div>

  <div class="grid g-1-2" style="align-items:start">
    <div class="col" style="gap:14px">
      <div class="card"><div class="card-h"><h3>Candidate thresholds</h3></div><div class="card-b col" style="gap:16px">
        ${slider('dsr', 'Debt service ratio ceiling', 25, 50, 1, 40, '%')}
        ${slider('exp', 'Exposure multiple of equity', 2, 8, 0.5, 4, '×')}
        ${slider('conf', 'Minimum council confidence', 0.6, 0.99, 0.01, 0.88, '')}
        ${slider('pd', 'Maximum probability of default', 0.01, 0.2, 0.01, 0.05, '')}
        <button class="btn primary lg" id="run">${icon('activity')} Run simulation</button>
      </div></div>
      <div class="card" id="autonomyCard"></div>
    </div>
    <div class="col" style="gap:14px" id="simOut">
      <div class="card"><div class="card-b empty">${icon('sliders', 26)}
        <b>No simulation run yet</b><span class="small">Adjust the thresholds and replay the portfolio.</span></div></div>
    </div>
  </div>`;

  const vals = () => ({
    dsr_ceiling: +$('#dsr', el).value, exposure_multiple: +$('#exp', el).value,
    min_confidence: +$('#conf', el).value, max_pd: +$('#pd', el).value });
  $$('input[type=range]', el).forEach(s => s.oninput = () => {
    $('#' + s.id + 'v', el).textContent = s.value + (s.dataset.unit || ''); });
  $('#run', el).onclick = async () => {
    const out = $('#simOut', el);
    out.innerHTML = `<div class="card"><div class="card-b center" style="height:200px"><div class="spin"></div></div></div>`;
    const s = await api('/sandbox/simulate', { method: 'POST', body: vals() });
    out.innerHTML = simResult(s);
    out.querySelector('#promote').onclick = () => promote(vals());
  };
  renderAutonomy($('#autonomyCard', el), boot.autonomy);
}

const slider = (id, label, min, max, step, val, unit) => `
  <div class="field"><label>${label} — <b id="${id}v">${val}${unit}</b></label>
    <input type="range" id="${id}" min="${min}" max="${max}" step="${step}" value="${val}" data-unit="${unit}"/></div>`;

function simResult(s) {
  const b = s.baseline, c = s.candidate;
  const d = (a, bb) => { const x = bb - a; return `<span style="color:var(--${x > 0 ? 'green' : x < 0 ? 'red' : 'ink-3'})">${x > 0 ? '+' : ''}${x.toFixed(1)}</span>`; };
  return `
  <div class="grid g3">
    ${sk('Approvals', `${c.approve}`, `was ${b.approve}`, c.approve >= b.approve ? 'green' : 'red')}
    ${sk('Approval rate', c.approval_rate + '%', `was ${b.approval_rate}% (${d(b.approval_rate, c.approval_rate)})`, '')}
    ${sk('Predicted delinquency', c.predicted_delinquency + '%', `was ${b.predicted_delinquency}%`, c.predicted_delinquency <= b.predicted_delinquency ? 'green' : 'red')}
  </div>
  <div class="card"><div class="card-h"><h3>Portfolio impact</h3>
    <span class="sub">replayed against ${b.approve + b.decline + b.request} frozen snapshots</span></div>
    <div class="card-b">
      ${barChart([
        { l: 'Approve', v: c.approve, color: '#2ecc8f' }, { l: 'Approve (base)', v: b.approve, color: '#2ecc8f', dim: true },
        { l: 'Request', v: c.request, color: '#4d7cfe' }, { l: 'Request (base)', v: b.request, color: '#4d7cfe', dim: true },
        { l: 'Decline', v: c.decline, color: '#f2545b' }, { l: 'Decline (base)', v: b.decline, color: '#f2545b', dim: true },
      ], { h: 150 })}
      <div class="row wrap small muted" style="gap:18px;margin-top:8px">
        <span>Exposure <b style="color:var(--ink)">${money(c.exposure)}</b> <span class="dim">(was ${money(b.exposure)})</span></span>
      </div></div></div>
  <div class="card"><div class="card-h"><h3>Cases that change outcome</h3>
    <span class="sub">${s.changed.length} of ${b.outcomes.length}</span></div>
    ${s.changed.length ? `<div class="tw"><table><thead><tr><th>Case</th><th>Member</th><th>Product</th>
      <th class="r">Amount</th><th>DSR</th><th>Before</th><th>After</th></tr></thead><tbody>
      ${s.changed.map(x => `<tr><td class="mono tiny">${x.id}</td><td>${esc(x.name)}</td>
        <td class="small">${esc(x.product)}</td><td class="r num">${money(x.amount)}</td>
        <td class="num small">${x.dsr}%</td><td>${tag(x.before)}</td><td>${tag(x.after)}</td></tr>`).join('')}
      </tbody></table></div>` : '<div class="card-b empty small">No case changes outcome under these thresholds.</div>'}
    ${Object.keys(s.segments).length ? `<div class="card-b"><div class="up">Affected segments</div>
      <div class="row wrap" style="gap:8px;margin-top:6px">
        ${Object.entries(s.segments).map(([k, v]) => `<span class="tag t-amber">${esc(k)} · ${v}</span>`).join('')}</div></div>` : ''}
  </div>
  <div class="note amber">${esc(s.note)}</div>
  <button class="btn primary lg" id="promote">${icon('up')} Propose for board approval</button>`;
}

const sk = (l, v, sub, tone) => `<div class="kpi ${tone ? 'accent-' + tone : ''}">
  <div class="lbl">${l}</div><div class="val" style="font-size:22px">${v}</div><div class="sub">${sub}</div></div>`;

function promote(thresholds) {
  drawer(`<h3>Propose policy change</h3>`, `
    <div class="col" style="gap:12px">
      <div class="note amber"><b>This does not change production.</b>
        <div class="small">It records a proposal for board approval and seals it to the ledger.</div></div>
      <pre class="mono" style="background:var(--bg-2);padding:12px;border-radius:9px;border:1px solid var(--line)">${esc(JSON.stringify(thresholds, null, 2))}</pre>
      <div class="field"><label>Justification (required)</label>
        <textarea class="inp" id="j" rows="4" placeholder="Why this change, and what it is expected to achieve."></textarea></div>
    </div>`, {
    footer: `<button class="btn primary" id="ok">Record proposal</button>`,
    onMount: dr => dr.querySelector('#ok').onclick = async () => {
      try {
        await api('/sandbox/promote', { method: 'POST', body: { thresholds, justification: dr.querySelector('#j').value } });
        closeDrawer(); toast('Proposal recorded', 'Pending board approval.', 'good');
      } catch (e) { toast('Not recorded', e.message, 'bad'); }
    }
  });
}

// --------------------------------------------------------- autonomy dial
function renderAutonomy(host, a) {
  const modes = a.modes;
  host.innerHTML = `<div class="card-h">${icon('power', 15)}<h3>Autonomy Dial</h3>
      <span class="sub">board-controlled</span><div class="spacer"></div>
      ${tag(a.kill_switch ? 'STOPPED' : a.mode, a.kill_switch ? 'red' : 'purple')}</div>
    <div class="card-b col" style="gap:12px">
      <div class="col" style="gap:5px">
        ${modes.map((m, i) => `<button class="field-row ${a.mode === m ? 'on' : ''}" data-mode="${m}">
          <span class="k" style="text-align:left;color:var(--ink-2)">
            <b>${m.replace(/_/g, ' ')}</b>
            <div class="tiny dim">${['System observes only; no output reaches the officer.',
              'System advises; the officer sees the recommendation.',
              'System assists with drafting and evidence; the officer acts.',
              'System may prepare an action for one-click human approval.',
              'System may execute inside the board-set limits.'][i]}</div></span>
          ${a.mode === m ? tag('active', 'purple') : ''}</button>`).join('')}
      </div>
      <div class="sep"></div>
      <div class="up">Limits on autonomous execution</div>
      <dl class="kv">
        <dt>Maximum amount</dt><dd>${money(a.limits.max_amount)}</dd>
        <dt>Maximum probability of default</dt><dd>${pct(a.limits.max_pd, 1)}</dd>
        <dt>Minimum confidence</dt><dd>${a.limits.min_confidence}</dd>
        <dt>Maximum disagreement</dt><dd>${a.limits.max_disagreement}</dd>
        <dt>Products</dt><dd class="small">${a.limits.products.join(', ')}</dd>
        <dt>Evidence must be complete</dt><dd>${a.limits.require_complete_docs ? 'Yes' : 'No'}</dd>
      </dl>
      <div class="tiny dim">${esc(a.approved_by)} · last changed ${dtime(a.changed_at)}</div>
      <div class="sep"></div>
      <div class="row" style="gap:10px;padding:10px;border:1px solid ${a.kill_switch ? '#f2545b55' : 'var(--line)'};
        border-radius:10px;background:${a.kill_switch ? 'var(--red-dim)' : 'transparent'}">
        ${icon('power', 18)}
        <div style="flex:1"><b style="font-size:12.5px">Stop autonomous actions</b>
          <div class="tiny dim">AI recommendations, policy and models keep running. Every action routes to a person.</div></div>
        <button class="switch danger ${a.kill_switch ? 'on' : ''}" id="kill"><i></i></button>
      </div>
    </div>`;
  host.querySelectorAll('[data-mode]').forEach(b => b.onclick = async () => {
    const r = await api('/governance/autonomy', { method: 'POST', body: { mode: b.dataset.mode } });
    toast('Autonomy mode set', b.dataset.mode.replace(/_/g, ' '), 'warn');
    renderAutonomy(host, r); (await import('/app.js')).refreshMeta().then(() => {});
  });
  host.querySelector('#kill').onclick = async () => {
    const r = await api('/governance/autonomy', { method: 'POST', body: { kill_switch: !a.kill_switch } });
    toast(r.kill_switch ? 'Autonomous execution stopped' : 'Autonomous execution resumed',
          'Change sealed to the ledger.', r.kill_switch ? 'bad' : 'good');
    renderAutonomy(host, r);
    const app = await import('/app.js'); await app.refreshMeta(); app.render();
  };
}

// ========================================================== GOVERNANCE
export async function governance(el) {
  const g = await api('/governance');
  el.innerHTML = `
  <div class="page-head"><div><h1>Model & AI Governance</h1>
    <p>Model health, grounding discipline, override behaviour and fairness monitoring — the evidence that the
       platform is behaving the way the board approved.</p></div></div>

  <div class="grid g4" style="margin-bottom:14px">
    ${kpi('Council runs', g.council_runs, `avg confidence ${g.avg_confidence}`)}
    ${kpi('Officer overrides', `${g.overrides}`, `${g.override_rate}% of ${g.decisions} decisions`, g.override_rate > 30 ? 'accent-amber' : '')}
    ${kpi('Grounding interventions', (g.grounding.unsupported_citations || 0) + (g.grounding.numeric_rewrites || 0),
      `${g.grounding.numeric_rewrites || 0} figure rewrites · ${g.grounding.unsupported_citations} bad citations ·
       ${g.grounding.llm_positions}/${g.grounding.total_positions} model-authored`,
      g.grounding.unsupported_citations ? 'accent-red' : 'accent-amber')}
    ${kpi('Ledger integrity', g.ledger.intact ? 'Intact' : 'BROKEN', `${g.ledger.records} hash-chained records`,
      g.ledger.intact ? 'accent-green' : 'accent-red')}
  </div>

  <div class="grid g-2-1" style="margin-bottom:14px">
    <div class="card"><div class="card-h"><h3>Model registry & health</h3></div><div class="tw"><table>
      <thead><tr><th>Model</th><th>Version</th><th>Status</th><th>Calibration</th><th>Drift</th><th>Note</th></tr></thead>
      <tbody>${g.models.map(m => `<tr><td style="font-weight:560">${esc(m.name)}</td>
        <td class="mono tiny">${esc(m.version)}</td><td>${tag(m.status, m.status === 'Healthy' ? 'green' : 'blue')}</td>
        <td class="small">${esc(m.calibration)}</td>
        <td style="width:110px">${m.drift != null ? `<div class="meter"><div class="bar thin">
          <i style="width:${m.drift * 400}%;background:${m.drift > .1 ? 'var(--red)' : 'var(--green)'}"></i></div>
          <span class="mono tiny">${m.drift}</span></div>` : '<span class="dim">—</span>'}</td>
        <td class="small muted">${esc(m.note)}</td></tr>`).join('')}</tbody></table></div></div>
    <div class="card"><div class="card-h"><h3>Fairness monitoring</h3><span class="sub">approval rate by segment</span></div>
      <div class="card-b col" style="gap:9px">
        ${g.fairness.map(f => `<div>
          <div class="row small"><span style="flex:1">${esc(f.segment)}</span>
            <b class="num">${f.approval}%</b>
            <span class="tag t-${f.flag ? 'amber' : 'grey'}">${f.delta > 0 ? '+' : ''}${f.delta}</span></div>
          <div class="bar thin" style="margin-top:4px"><i style="width:${f.approval}%;
            background:${f.flag ? 'var(--amber)' : 'var(--brand)'}"></i></div></div>`).join('')}
        <div class="tiny dim">Flagged segments are surfaced for human review; the platform does not act on them.</div>
      </div></div>
  </div>

  <div class="grid g2">
    <div class="card"><div class="card-h"><h3>Override analytics</h3></div>
      ${g.override_detail.length ? `<div class="tw"><table><thead><tr><th>Case</th><th>AI</th><th>Officer</th>
        <th>Reason</th><th>By</th></tr></thead><tbody>
        ${g.override_detail.map(o => `<tr><td class="mono tiny">${esc(o.case)}</td>
          <td>${tag(o.ai_recommendation)}</td><td>${tag(o.action)}</td>
          <td class="small muted">${esc(o.reason)}</td><td class="small">${esc(o.actor)}</td></tr>`).join('')}
        </tbody></table></div>` : '<div class="card-b empty small">No overrides recorded yet.</div>'}</div>
    <div class="card" id="autonomyCard2"></div>
  </div>

  ${g.policy_changes.length ? `<div class="card" style="margin-top:14px">
    <div class="card-h"><h3>Pending policy changes</h3></div><div class="card-b col" style="gap:9px">
    ${g.policy_changes.map(p => `<div class="note amber"><b>${esc(p.status)}</b>
      <div class="small">${esc(p.justification)}</div>
      <div class="tiny dim mono">${esc(JSON.stringify(p.thresholds))} · ${esc(p.actor)} · ${dtime(p.at)}</div></div>`).join('')}
    </div></div>` : ''}`;
  renderAutonomy($('#autonomyCard2', el), g.autonomy);
}

const kpi = (l, v, sub, accent = '') => `<div class="kpi ${accent}"><div class="lbl">${l}</div>
  <div class="val">${v}</div><div class="sub">${sub}</div></div>`;

// ============================================================== LEDGER
export async function ledger(el, param) {
  const { rows, verification } = await api('/ledger' + (param ? '?case_id=' + encodeURIComponent(param) : ''));
  el.innerHTML = `
  <div class="page-head"><div><h1>Decision Ledger</h1>
    <p>Append-only and hash-chained. Any case can be reconstructed exactly as it was decided —
       snapshot, evidence, policy, models, agent opinions, challenge, recommendation, human decision, execution and outcome.</p></div>
    <div class="spacer"></div>
    ${tag(verification.intact ? 'Chain intact' : 'Chain broken', verification.intact ? 'green' : 'red')}
    <span class="tag t-grey">${verification.records} records</span>
    ${param ? `<button class="btn sm" id="clear">Show all</button>` : ''}</div>

  <div class="card" style="margin-bottom:14px"><div class="card-b row wrap" style="gap:8px">
    <span class="up">Reconstruct a case</span>
    <input class="inp" id="cid" placeholder="APP-104328" value="${esc(param || '')}" style="max-width:200px"/>
    <button class="btn primary sm" id="rec">${icon('layers', 12)} Reconstruct</button>
    <div class="spacer" style="flex:1"></div>
    <span class="tiny dim mono">head ${esc(String(verification.head).slice(0, 28))}…</span></div></div>

  <div class="card"><div class="tw"><table>
    <thead><tr><th>#</th><th>Time</th><th>Case</th><th>Stage</th><th>Actor</th><th>Summary</th><th>Hash</th></tr></thead>
    <tbody>${rows.map(r => `<tr class="clickable" data-seq="${r.seq}"><td class="mono tiny dim">${r.seq}</td>
      <td class="small">${dtime(r.at)}</td><td class="mono tiny">${esc(r.case_id)}</td>
      <td><span class="tag t-${stageTone(r.stage)}">${esc(r.stage)}</span></td>
      <td class="small">${esc(r.actor)}</td><td class="small muted">${esc(r.summary)}</td>
      <td class="mono tiny dim">${esc(String(r.hash).slice(0, 12))}…</td></tr>`).join('')}</tbody></table></div></div>`;

  $('#rec', el).onclick = () => reconstruct($('#cid', el).value.trim());
  if ($('#clear', el)) $('#clear', el).onclick = () => window.go('ledger');
  $$('[data-seq]', el).forEach(r => r.onclick = () => {
    const rec = rows.find(x => x.seq == r.dataset.seq);
    drawer(`<h3>Ledger record #${rec.seq}</h3>`, `<div class="col" style="gap:12px">
      <dl class="kv"><dt>Time</dt><dd>${dtime(rec.at)}</dd><dt>Case</dt><dd class="mono">${esc(rec.case_id)}</dd>
        <dt>Stage</dt><dd>${esc(rec.stage)}</dd><dt>Actor</dt><dd>${esc(rec.actor)}</dd></dl>
      <div class="note">${esc(rec.summary)}</div>
      <div class="up">Payload</div>
      <pre class="mono" style="background:var(--bg-2);padding:12px;border-radius:9px;border:1px solid var(--line);
        overflow:auto;max-height:400px">${esc(JSON.stringify(rec.payload, null, 2))}</pre>
      <div class="up">Chain</div>
      <div class="small mono dim">prev ${esc(rec.prev_hash)}</div>
      <div class="small mono">this ${esc(rec.hash)}</div></div>`, { wide: true });
  });
}

const stageTone = s => s.includes('Human') ? 'purple' : s.includes('Execution') || s.includes('Token') ? 'green'
  : s.includes('Autonomy') || s.includes('Policy Change') ? 'amber'
  : s.includes('Hardship') || s.includes('Complaint') ? 'red' : 'grey';

async function reconstruct(aid) {
  if (!aid) return toast('Enter a case id', '', 'warn');
  let r; try { r = await api('/ledger/reconstruct/' + encodeURIComponent(aid)); }
  catch (e) { return toast('Not found', e.message, 'bad'); }
  drawer(`<h3>Reconstruction — <span class="mono">${esc(aid)}</span></h3>`, `
    <div class="col" style="gap:10px">
      <div class="note ${r.verification.intact ? 'green' : 'red'}">
        <b>Hash chain ${r.verification.intact ? 'verified' : 'BROKEN'}</b>
        <div class="small">${r.verification.records} records in the ledger.</div></div>
      ${r.steps.map(s => `<div class="card"><div class="card-h">
        <span class="tag t-blue">${s.n}</span><h3>${esc(s.title)}</h3>
        <div class="spacer"></div><span class="small muted">${esc(String(s.summary))}</span></div>
        <div class="card-b"><pre class="mono" style="overflow:auto;max-height:260px;color:var(--ink-2)">${
          esc(JSON.stringify(s.detail, null, 2) || 'null')}</pre></div></div>`).join('')}
    </div>`, { wide: true });
}

// ============================================================= COCKPIT
export async function cockpit(el) {
  const c = await api('/cockpit');
  const p = c.portfolio, k = p.kpis, g = c.governance;
  el.innerHTML = `
  <div class="page-head"><div><h1>Management Cockpit</h1>
    <p>The institution rather than the individual case — volume, exposure, risk, recovery, model behaviour and
       the questions worth asking this month.</p></div>
    <div class="spacer"></div><button class="btn" id="ask">${icon('msg')} Ask the cockpit</button></div>

  <div class="grid g5" style="margin-bottom:14px">
    ${kpi('Pipeline', k.pipeline, `${k.decided} decided`, 'accent')}
    ${kpi('Exposure', money(k.exposure), 'requested across live cases')}
    ${kpi('Predicted delinquency', k.predicted_delinquency + '%', 'exposure-weighted', 'accent-amber')}
    ${kpi('Collections at risk', money(c.collections.balance), `${c.collections.cases} cases`, 'accent-red')}
    ${kpi('Expected recovery', money(c.collections.expected), 'modelled', 'accent-green')}
  </div>

  <div class="grid g-2-1" style="margin-bottom:14px">
    <div class="card"><div class="card-h"><h3>Volume and outcome trend</h3></div>
      <div class="card-b">${lineChart(p.trend, { keys: ['a', 'ap', 'de'], h: 200 })}</div></div>
    <div class="card"><div class="card-h"><h3>AI behaviour</h3></div><div class="card-b col" style="gap:10px">
      <dl class="kv">
        <dt>Council runs</dt><dd>${g.council_runs}</dd>
        <dt>Average confidence</dt><dd>${g.avg_confidence}</dd>
        <dt>Average disagreement</dt><dd>${g.avg_disagreement}</dd>
        <dt>Override rate</dt><dd>${g.override_rate}%</dd>
        <dt>Unsupported claims</dt><dd>${g.grounding.unsupported_citations}</dd>
        <dt>Autonomy mode</dt><dd>${esc(g.autonomy.mode)}</dd>
        <dt>Kill switch</dt><dd>${g.autonomy.kill_switch ? tag('ENGAGED', 'red') : tag('off', 'green')}</dd>
      </dl></div></div>
  </div>

  <div class="grid g3">
    ${breakdown('By product', c.products)}
    ${breakdown('By branch', c.branches)}
    ${breakdown('By officer', c.officers)}
  </div>`;
  $('#ask', el).onclick = async () => {
    const { askDrawer } = await import('/views/applications.js');
    askDrawer(null, 'Portfolio');
  };
}

const breakdown = (title, obj) => `<div class="card"><div class="card-h"><h3>${title}</h3></div>
  <div class="tw"><table><thead><tr><th>Segment</th><th class="r">Cases</th><th class="r">Amount</th><th class="r">PD</th></tr></thead>
  <tbody>${Object.entries(obj).sort((a, b) => b[1].amount - a[1].amount).map(([k, v]) =>
    `<tr><td class="small">${esc(k)}</td><td class="r num">${v.count}</td>
     <td class="r num">${money(v.amount)}</td><td class="r num">${v.pd}%</td></tr>`).join('')}
  </tbody></table></div></div>`;
