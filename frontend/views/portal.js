import { api, icon, esc, money, date, tag, h, $, toast } from '/lib.js';

export async function memberPortal(el) {
  const mid = '104328';
  const d = await api('/members/' + mid);
  const m = d.member;
  el.innerHTML = `
  <div class="page-head"><div class="row" style="gap:12px">
    <div class="avatar lg">${m.initials}</div>
    <div><h1>${esc(m.name)}</h1><p class="tiny">Member portal · authenticated as member ${m.id}</p></div></div>
    <div class="spacer"></div><span class="tag t-blue">Member view</span></div>

  <div class="grid g4" style="margin-bottom:14px">
    ${k('Outstanding balance', money(m.outstanding))}
    ${k('Savings', money(m.savings))}
    ${k('Share capital', money(m.share_capital))}
    ${k('Next payment', money(650), 'due 5th of next month')}
  </div>

  <div class="grid g-1-2" style="align-items:start">
    <div class="col" style="gap:14px">
      <div class="card"><div class="card-h"><h3>My applications</h3></div><div class="card-b col" style="gap:9px">
        ${d.applications.map(a => `<div class="note"><b>${esc(a.product)} — ${money(a.amount)}</b>
          <div class="small muted">${esc(a.status)}</div>
          <div class="tiny dim mono">${a.id}</div></div>`).join('') || '<div class="small dim">No open applications.</div>'}
      </div></div>
      <div class="card"><div class="card-h"><h3>Recent payments</h3></div><div class="card-b col" style="gap:5px">
        ${d.payments.slice(-6).reverse().map(p => `<div class="row small">
          <span style="flex:1">${date(p.month)}</span>
          <span class="tag t-${p.days_late === 0 ? 'green' : p.days_late < 10 ? 'amber' : 'red'}">
            ${p.days_late === 0 ? 'on time' : p.days_late + 'd late'}</span>
          <b class="num">${money(p.amount_paid)}</b></div>`).join('')}
      </div></div>
    </div>

    <div class="card" style="display:flex;flex-direction:column;height:560px">
      <div class="card-h">${icon('msg', 15)}<h3>Member Assistant</h3>
        <span class="sub">it can answer about your account — it never makes a credit decision</span></div>
      <div class="card-b chat" id="chat" style="flex:1;overflow-y:auto">
        <div class="msg ai">Hi ${esc(m.name.split(' ')[0])}. I can help with your balance, next payment,
application status, required documents, or arrange a callback from member support.</div>
      </div>
      <div class="card-b" style="border-top:1px solid var(--line)">
        <div class="chips" style="margin-bottom:9px" id="sug">
          ${["What's my outstanding balance?", 'When is my next payment?', 'Which documents do you still need?',
             "What's happening with my application?", "I lost my job and I'm worried about next month's payment"]
            .map(q => `<button class="chip">${esc(q)}</button>`).join('')}
        </div>
        <div class="row"><input class="inp" id="q" placeholder="Ask about your account…"/>
          <button class="btn primary" id="send">${icon('send')}</button></div>
      </div>
    </div>
  </div>`;

  const chat = $('#chat', el), input = $('#q', el);
  const send = async () => {
    const q = input.value.trim(); if (!q) return;
    input.value = '';
    chat.insertAdjacentHTML('beforeend', `<div class="msg me">${esc(q)}</div>`);
    const b = h('<div class="msg ai"><span class="pulse"></span></div>');
    chat.appendChild(b); chat.scrollTop = chat.scrollHeight;
    try {
      const r = await api('/member-assistant', { method: 'POST', body: { question: q, member_id: mid } });
      b.textContent = r.answer;
      if (r.handoff) {
        chat.insertAdjacentHTML('beforeend',
          `<div class="msg sys">${icon('alert', 11)} ${esc(r.handoff.kind)} signal detected — support task created,
           routed to ${esc(r.handoff.queue)}, SLA ${esc(r.handoff.sla)}</div>`);
        toast('Handed off to a person', `${r.handoff.kind} routed to Member Support`, 'warn');
      }
    } catch (e) { b.textContent = 'Assistant unavailable: ' + e.message; }
    chat.scrollTop = chat.scrollHeight;
  };
  $('#send', el).onclick = send;
  input.onkeydown = e => { if (e.key === 'Enter') send(); };
  el.querySelectorAll('#sug .chip').forEach(b => b.onclick = () => { input.value = b.textContent; send(); });
}

const k = (l, v, sub = '') => `<div class="kpi"><div class="lbl">${l}</div>
  <div class="val" style="font-size:20px">${v}</div>${sub ? `<div class="sub">${sub}</div>` : ''}</div>`;
