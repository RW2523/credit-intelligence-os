import { api, icon, esc, money, pct, tag, date, dtime, drawer, closeDrawer, toast, $, $$, h } from '/lib.js';
import { logOutreach } from '/views/members.js';

export async function collections(el) {
  const d = await api('/collections');
  el.innerHTML = `
  <div class="page-head"><div><h1>Collections Intelligence</h1>
    <p>A daily expected-value priority list. Reactive for past-due accounts and predictive for members whose
       behaviour says trouble is coming before any payment is missed.</p></div>
    <div class="spacer"></div>
    <span class="tag t-grey">portfolio at risk ${money(d.total_balance)}</span>
    <span class="tag t-green">expected recovery ${money(d.total_ev)}</span></div>

  <div class="col" style="gap:12px">
    ${d.rows.map(r => `<div class="card">
      <div class="card-h">
        <div class="avatar sm">${r.initials}</div>
        <h3>${esc(r.name)}</h3>${tag(r.priority)}${tag(r.state)}
        <span class="sub">${r.dpd ? r.dpd + ' days past due' : 'no arrears — predicted risk'} · ${esc(r.stage)}</span>
        <div class="spacer"></div>
        <span class="tag t-grey">balance ${money(r.balance)}</span>
        <span class="tag t-blue">expected ${money(r.expected_value)}</span>
        <button class="btn sm" data-m="${r.member_id}">Member 360</button></div>
      <div class="card-b grid g-2-1">
        <div class="col" style="gap:10px">
          <div class="note ${r.dpd >= 90 ? 'red' : r.dpd === 0 ? 'green' : 'amber'}">
            <b>Why now</b><div class="small">${esc(r.why_now)}</div></div>
          <div class="row wrap small muted" style="gap:16px">
            <span>Response probability <b style="color:var(--ink)">${r.response}%</b></span>
            <span>30-day late risk <b style="color:var(--ink)">${pct(r.p30, 0)}</b></span>
            <span>Recovery likelihood <b style="color:var(--ink)">${pct(r.recovery, 0)}</b></span>
            <span>Last payment <b style="color:var(--ink)">${date(r.last_payment)}</b></span>
            ${r.promise ? `<span>Promise to pay <b style="color:var(--amber)">${date(r.promise)}</b></span>` : ''}</div>
          <div class="up">Communication history</div>
          <div class="timeline">${r.comms.map(c => `<div class="tl-item ${c.type === 'promise' ? 'hot' : ''}">
            <div class="row"><b style="font-size:12px">${esc(c.title)}</b><span class="tiny dim">${dtime(c.at)}</span>
              <span class="tag t-grey">${esc(c.outcome)}</span></div>
            <div class="small muted">${esc(c.text)}</div></div>`).join('') || '<div class="small dim">No contact recorded.</div>'}</div>
        </div>
        <div class="col" style="gap:9px">
          <div class="up">Next best action</div>
          <div class="card" style="background:var(--panel-2)"><div class="card-b col" style="gap:7px">
            <div style="font-size:14.5px;font-weight:640">${esc(r.next_best_action.action)}</div>
            <div class="row wrap"><span class="tag t-blue">${esc(r.next_best_action.channel)}</span>
              <span class="tag t-grey">${icon('clock', 11)} ${esc(r.next_best_action.window)}</span></div>
            <div class="small muted"><b>Objective.</b> ${esc(r.next_best_action.objective)}</div>
            <div class="small muted"><b>Reason.</b> ${esc(r.next_best_action.reason)}</div>
          </div></div>
          <div class="row wrap" style="gap:7px">
            <button class="btn primary sm" data-draft="${r.member_id}">${icon('msg', 12)} Draft message</button>
            <button class="btn sm" data-log="${r.member_id}" data-name="${esc(r.name)}">${icon('phone', 12)} Log outreach</button>
            <button class="btn sm" data-restructure="${r.member_id}">${icon('sliders', 12)} Restructure</button>
          </div>
        </div>
      </div></div>`).join('')}
  </div>`;

  $$('[data-m]', el).forEach(b => b.onclick = () => window.go('members', b.dataset.m));
  $$('[data-log]', el).forEach(b => b.onclick = () => logOutreach(b.dataset.log, b.dataset.name));
  $$('[data-draft]', el).forEach(b => b.onclick = () => draftMessage(b.dataset.draft));
  $$('[data-restructure]', el).forEach(b => b.onclick = () => restructure(b.dataset.restructure, d.rows));
}

async function draftMessage(mid) {
  drawer(`<h3>Drafting outreach…</h3>`, `<div class="center" style="height:200px"><div class="spin"></div></div>`);
  const out = await api('/collections/draft', { method: 'POST', body: { member_id: mid, channel: 'Email' } });
  drawer(`<div class="row">${icon('msg', 16)}<h3>Draft outreach</h3></div>`, `
    <div class="col" style="gap:12px">
      <div class="note amber"><b>Draft only.</b> <span class="small">${esc(out.policy_note)}</span></div>
      <div class="field"><label>Subject</label><input class="inp" id="sub" value="${esc(out.subject)}"/></div>
      <div class="field"><label>Message</label><textarea class="inp" id="body" rows="12">${esc(out.body)}</textarea></div>
      <div class="tiny dim">Generated locally${out._source === 'llm' ? ' by the on-device model' : ' from the approved template'}.</div>
    </div>`, {
    footer: `<button class="btn primary" id="approve">${icon('check')} Approve & queue send</button>
             <button class="btn ghost" id="cancel">Discard</button>`,
    onMount: dr => {
      dr.querySelector('#cancel').onclick = closeDrawer;
      dr.querySelector('#approve').onclick = async () => {
        await api('/collections/outreach', { method: 'POST', body: {
          member_id: mid, channel: 'Email', outcome: 'Queued',
          note: dr.querySelector('#sub').value } });
        closeDrawer(); toast('Queued for sending', 'Officer-approved. Logged to the ledger.', 'good'); window.render();
      };
    }
  });
}

function restructure(mid, rows) {
  const r = rows.find(x => x.member_id === mid);
  const calc = (term, rate) => {
    const i = rate / 100 / 12;
    return r.balance * i / (1 - Math.pow(1 + i, -term));
  };
  drawer(`<h3>Restructure — ${esc(r.name)}</h3>`, `
    <div class="col" style="gap:14px">
      <div class="note"><b>Balance ${money(r.balance)}</b>
        <div class="small muted">Deterministic calculation. Any offer requires officer approval and a hardship record.</div></div>
      <div class="field"><label>New term (months) — <b id="tv">36</b></label>
        <input type="range" id="term" min="12" max="72" step="6" value="36"/></div>
      <div class="field"><label>Rate (%) — <b id="rv">9.5</b></label>
        <input type="range" id="rate" min="4" max="16" step="0.5" value="9.5"/></div>
      <div class="card"><div class="card-b">
        <dl class="kv"><dt>New monthly instalment</dt><dd><b id="pay">—</b></dd>
        <dt>Total repayable</dt><dd id="tot">—</dd>
        <dt>Versus current arrears</dt><dd id="delta">—</dd></dl></div></div>
    </div>`, {
    footer: `<button class="btn primary" id="offer">Record hardship offer</button>`,
    onMount: dr => {
      const upd = () => {
        const t = +dr.querySelector('#term').value, rt = +dr.querySelector('#rate').value;
        dr.querySelector('#tv').textContent = t; dr.querySelector('#rv').textContent = rt;
        const p = calc(t, rt);
        dr.querySelector('#pay').textContent = money(p, 2);
        dr.querySelector('#tot').textContent = money(p * t, 2);
        dr.querySelector('#delta').textContent = `${money(r.balance)} over ${t} months`;
      };
      dr.querySelector('#term').oninput = upd; dr.querySelector('#rate').oninput = upd; upd();
      dr.querySelector('#offer').onclick = async () => {
        await api('/collections/outreach', { method: 'POST', body: {
          member_id: mid, channel: 'Restructure', outcome: 'Arrangement Agreed',
          note: `Hardship restructure offered: ${dr.querySelector('#pay').textContent} per month.` } });
        closeDrawer(); toast('Offer recorded', 'Sealed to the decision ledger.', 'good'); window.render();
      };
    }
  });
}
