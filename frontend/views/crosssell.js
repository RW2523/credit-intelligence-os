import { api, icon, esc, money, tag, toast, drawer, closeDrawer, $, $$ } from '/lib.js';
import { t, tt, lang } from '/i18n.js';
import { state } from '/app.js';

const KIND = {
  takaful: ['Potential takaful offer', 'Tawaran takaful berpotensi', 'shield', 'gold'],
  financing: ['Potential financing offer', 'Tawaran pembiayaan berpotensi', 'coins', 'brand'],
  retention: ['Retention intervention', 'Intervensi pengekalan', 'users', 'amber'],
  rahnu: ['Short-term liquidity', 'Kecairan jangka pendek', 'coins', 'purple'],
  advice: ['Retirement planning', 'Perancangan persaraan', 'flag', 'blue'],
};
let filter = '';

export async function crosssell(el) {
  const d = await api('/crosssell');
  const rows = d.rows.filter(r => !filter || r.kind === filter);
  const count = k => d.rows.filter(r => r.kind === k).length;
  const ms = lang() === 'ms';
  el.innerHTML = `
  <div class="page-head"><div><h1>${t('Cross-selling options')}</h1>
    <p>${tt('AI-ranked next-best offers for members, each with the reason chain behind it. Responsible-lending rules are built in: no financing offers to members in financial distress or near the 60% deduction cap, and members without marketing consent cannot be contacted.',
            'Tawaran terbaik seterusnya yang disusun AI untuk ahli, setiap satu dengan rantaian sebab. Peraturan pembiayaan bertanggungjawab terbina dalam: tiada tawaran pembiayaan kepada ahli dalam tekanan kewangan atau hampir had potongan 60%, dan ahli tanpa persetujuan pemasaran tidak boleh dihubungi.')}</p></div>
    <div class="spacer"></div>
    <span class="tag t-amber" title="${esc(d.external.note)}">${icon('layers', 11)} ${tt('External data: simulated', 'Data luaran: simulasi')}</span>
    <a class="btn" href="/api/crosssell.csv">${icon('download', 14)} CSV</a>
  </div>

  <div class="grid g3" style="margin-bottom:14px">
    ${['takaful', 'financing', 'retention'].map((k, i) => `<button class="kpi ${filter === k ? 'accent' : ''}" data-k="${k}" style="text-align:left">
      <div class="lbl">${icon(KIND[k][2], 13)} ${tt('Member', 'Ahli')} ${'ABC'[i]} → ${esc(ms ? KIND[k][1] : KIND[k][0])}</div>
      <div class="val">${count(k)}</div>
      <div class="sub">${esc([tt('existing financing → good repayment history → no takaful', 'pembiayaan sedia ada → sejarah bayaran baik → tiada takaful'),
        tt('salary + savings → no personal financing → high repayment capacity', 'gaji + simpanan → tiada pembiayaan peribadi → kemampuan bayar tinggi'),
        tt('declining engagement', 'penglibatan menurun')][i])}</div></button>`).join('')}
  </div>

  <div class="card" style="margin-bottom:14px"><div class="card-b row wrap" style="gap:8px">
    <span class="up">${tt('Show', 'Tunjuk')}</span>
    <button class="chip ${!filter ? 'on' : ''}" data-f="">${tt('All', 'Semua')} · ${d.rows.length}</button>
    ${Object.keys(KIND).map(k => `<button class="chip ${filter === k ? 'on' : ''}" data-f="${k}">${esc(ms ? KIND[k][1] : KIND[k][0])} · ${count(k)}</button>`).join('')}
    <div class="spacer" style="flex:1"></div>
    <span class="tiny dim">${esc(d.external.ccris)} · ${esc(d.external.sola)}</span>
  </div></div>

  <div class="card"><div class="tw"><table>
    <thead><tr><th>${tt('Member', 'Ahli')}</th><th>${tt('Suggestion', 'Cadangan')}</th><th>${tt('Why — reason chain', 'Kenapa — rantaian sebab')}</th>
      <th class="r">${tt('Score', 'Skor')}</th><th>${tt('Consent', 'Persetujuan')}</th><th>${tt('Action', 'Tindakan')}</th></tr></thead>
    <tbody>${rows.map(r => `<tr>
      <td><div class="row"><div class="avatar sm">${esc(r.initials)}</div><div><div class="linkish" data-m="${r.member_id}" style="font-weight:560">${esc(r.name)}</div>
        <div class="tiny dim">${esc(r.branch)} · ${esc(r.service || '')}${r.distress ? ` · ${tt('distress', 'tekanan')} ${esc(r.distress)}` : ''}</div></div></div></td>
      <td>${tag(r.product, KIND[r.kind][3])}<div class="tiny dim" style="margin-top:3px">${esc(ms ? KIND[r.kind][1] : r.identifies)}</div></td>
      <td><div class="chain">${r.chain.map(c => `<span>${esc(c)}</span>`).join('<i>→</i>')}</div>
        <div class="tiny muted" style="margin-top:4px">${esc(r.pitch)}</div></td>
      <td class="r num">${r.score}</td>
      <td>${r.contactable ? tag(tt('Yes', 'Ya'), 'green') : tag(tt('No contact', 'Jangan hubungi'), 'red')}</td>
      <td>${r.feedback ? tag(r.feedback.outcome, 'grey') : `<div class="row" style="gap:4px">
        <button class="btn sm" data-draft="${r.member_id}" data-p="${esc(r.product)}" ${r.contactable && r.kind !== 'advice' ? '' : 'disabled'}>${icon('msg', 11)} ${tt('Draft', 'Draf')}</button>
        <button class="btn sm good" data-fb="Accepted" data-m2="${r.member_id}" data-p="${esc(r.product)}" title="Accepted">${icon('check', 11)}</button>
        <button class="btn sm" data-fb="Declined" data-m2="${r.member_id}" data-p="${esc(r.product)}" title="Declined">${icon('x', 11)}</button></div>`}</td></tr>`).join('')}
    </tbody></table></div>
    ${rows.length ? '' : `<div class="empty">${tt('No suggestions in this group.', 'Tiada cadangan dalam kumpulan ini.')}</div>`}
  </div>
  <div class="note small" style="margin-top:12px">${icon('info', 12)} ${esc(d.external.note)}</div>`;

  $$('[data-k]', el).forEach(b => b.onclick = () => { filter = filter === b.dataset.k ? '' : b.dataset.k; crosssell(el); });
  $$('[data-f]', el).forEach(b => b.onclick = () => { filter = b.dataset.f; crosssell(el); });
  $$('[data-m]', el).forEach(b => b.onclick = () => window.go('members', b.dataset.m));
  $$('[data-fb]', el).forEach(b => b.onclick = async () => {
    await api('/crosssell/feedback', { method: 'POST', body: { member_id: b.dataset.m2, product: b.dataset.p, outcome: b.dataset.fb } });
    toast(tt('Feedback recorded', 'Maklum balas direkod'), `${b.dataset.p}: ${b.dataset.fb}`, 'good'); crosssell(el);
  });
  $$('[data-draft]', el).forEach(b => b.onclick = () => draft(b.dataset.draft, b.dataset.p, el));
}

async function draft(mid, product, el) {
  drawer(`<h3>${tt('Drafting…', 'Menyediakan draf…')}</h3>`, `<div class="center" style="height:200px"><div class="spin"></div></div>`);
  let out;
  try {
    out = await api('/crosssell/draft', { method: 'POST', body: { member_id: mid, product, channel: 'SMS/Email', lang: lang() === 'ms' ? 'ms' : 'en' } });
  } catch (e) { closeDrawer(); return toast(tt('Cannot draft', 'Tidak boleh draf'), e.message, 'bad'); }
  drawer(`<div class="row">${icon('msg', 16)}<h3>${tt('Offer draft', 'Draf tawaran')} — ${esc(product)}</h3></div>`, `
    <div class="col" style="gap:12px">
      <div class="note amber"><b>${tt('Draft only.', 'Draf sahaja.')}</b> <span class="small">${esc(out.policy_note)}</span></div>
      <div class="field"><label>${tt('Subject', 'Subjek')}</label><input class="inp" id="sub" value="${esc(out.subject)}"/></div>
      <div class="field"><label>${tt('Message', 'Mesej')}</label><textarea class="inp" id="body" rows="10">${esc(out.body)}</textarea></div>
      <div class="tiny dim">${out._source === 'llm' ? tt('Written by the on-device model.', 'Ditulis oleh model tempatan.') : tt('From the approved template.', 'Daripada templat yang diluluskan.')}</div>
    </div>`, { footer: `<button class="btn primary" id="ok">${icon('check')} ${tt('Approve & mark contacted', 'Lulus & tanda dihubungi')}</button>`,
      onMount: dr => dr.querySelector('#ok').onclick = async () => {
        await api('/crosssell/feedback', { method: 'POST', body: { member_id: mid, product, outcome: 'Contacted' } });
        await api('/collections/outreach', { method: 'POST', body: { member_id: mid, channel: 'Email', outcome: 'Offer sent', note: dr.querySelector('#sub').value } });
        closeDrawer(); toast(tt('Queued for sending', 'Dalam baris gilir untuk dihantar'), tt('Logged to the ledger.', 'Direkod dalam lejar.'), 'good'); crosssell(el);
      } });
}
