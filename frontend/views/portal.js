import { api, icon, esc, money, date, month, tag, h, $, $$, toast, drawer, closeDrawer, md, gauge } from '/lib.js';
import { t, tt, lang } from '/i18n.js';
import { state } from '/app.js';
import { mark } from '/brand.js';

const ms = () => lang() === 'ms';
const prodName = (k, p) => ms() ? (p?.ms || k) : k;

// ============================================================ MY ACCOUNT
export async function memberPortal(el) {
  const d = await api('/me');
  const m = d.member;
  const nextAmt = m.deduction;
  const statusTone = s => ({ 'Officer Review': 'blue', 'Documents Pending': 'amber', Approved: 'green', Declined: 'red' }[s] || 'grey');
  el.innerHTML = `
  <div class="page-head">
    <div class="row" style="gap:12px"><div class="avatar lg">${esc(m.initials)}</div>
      <div><h1>${t('Welcome back')}, ${esc(m.given_name)}</h1>
        <p>${esc(m.display_rank)} · ${esc(m.service_label)} · ${esc(m.camp)} · ${tt('member no.', 'no. anggota')} <span class="mono">${esc(m.id)}</span></p></div></div>
    <div class="spacer"></div><span class="tag t-gold">${icon('shield', 11)} KT Online</span>
  </div>

  <div class="grid g-2-1" style="margin-bottom:14px">
    <div class="hero-card">
      <div class="row" style="align-items:flex-start;gap:20px;flex-wrap:wrap;position:relative;z-index:1">
        <div style="flex:1;min-width:220px">
          <div class="lbl">${t('Outstanding balance')}</div>
          <div class="big">${money(m.outstanding)}</div>
          <div class="sub">${m.outstanding ? tt('Existing KT financing — the amount still owed', 'Pembiayaan KT sedia ada — jumlah yang masih terhutang') : tt('No KT financing', 'Tiada pembiayaan KT')}</div>
        </div>
        ${nextAmt ? `<div style="min-width:200px">
          <div class="lbl">${t('Next deduction')}</div>
          <div class="big" style="font-size:26px">${money(nextAmt)}</div>
          <div class="sub">${date(d.next_deduction)} · ${esc(m.repayment_channel)}</div></div>` : ''}
      </div>
    </div>
    <div class="grid g2">
      ${kpi(t('Savings'), money(m.savings), 'Simpanan')}
      ${kpi(t('Share capital'), money(m.share_capital), 'Modal Syer')}
      ${kpi(t('Monthly instalment'), money(m.deduction), t('by salary deduction'))}
      ${kpi(t('Your branch'), esc(d.branch.name.replace('Cawangan ', '')), esc(d.branch.state))}
    </div>
  </div>

  <div class="grid g4" style="margin-bottom:14px">
    ${quick('check', 'calc', t('Check Before You Borrow'), tt('See your indicative limit before you apply', 'Lihat anggaran had anda sebelum memohon'))}
    ${quick('statement', 'print', t('Statement'), tt('Deductions and balance, ready to print', 'Potongan dan baki, sedia untuk dicetak'))}
    ${quick('upload', 'upload', t('Upload a document'), tt('Send what your application still needs', 'Hantar dokumen yang masih diperlukan'))}
    ${quick('ask', 'msg', t('Member Assistant'), tt('Ask in Bahasa Malaysia or English', 'Tanya dalam Bahasa Malaysia atau English'))}
  </div>

  <div class="grid g-1-2" style="align-items:start">
    <div class="col" style="gap:14px">
      <div class="card"><div class="card-h"><h3>${t('My applications')}</h3></div><div class="card-b col" style="gap:9px">
        ${d.applications.map(a => `<div class="note ${a.missing.length ? 'amber' : ''}">
          <div class="row"><b style="flex:1">${esc(prodName(a.product, { ms: a.product_ms }))} — ${money(a.amount)}</b>${tag(ms() ? a.status_ms : a.status, statusTone(a.status))}</div>
          <div class="tiny dim mono">${esc(a.id)} · ${a.term} ${t('months')} · ${t('Submitted')} ${date(a.submitted)}</div>
          <div class="small" style="margin-top:4px">${a.missing.length ? `${t('Documents still needed')}: <b>${esc((ms() ? a.missing_ms : a.missing).join(', '))}</b>`
            : `${icon('check', 11)} ${t('All documents received')}`}</div></div>`).join('')
          || `<div class="small dim">${t('No applications in progress.')}</div>`}
      </div></div>
      <div class="card"><div class="card-h"><h3>${t('Recent deductions')}</h3></div><div class="card-b col" style="gap:5px">
        ${d.payments.slice(-6).reverse().map(p => `<div class="row small">
          <span style="flex:1">${month(p.month)}</span>
          <span class="tag t-${p.days_late <= 2 ? 'green' : p.days_late < 10 ? 'amber' : 'red'}">
            ${p.days_late <= 2 ? t('on time') : p.days_late + ' ' + t('days late')}</span>
          <b class="num" style="width:80px;text-align:right">${money(p.amount_paid)}</b></div>`).join('')
          || `<div class="small dim">${tt('No KT financing deductions.', 'Tiada potongan pembiayaan KT.')}</div>`}
      </div></div>
      <div class="card"><div class="card-h"><h3>${t('Takaful & Ar-Rahnu')}</h3></div><div class="card-b col" style="gap:8px">
        <div class="small"><b>${t('Your cover')}:</b> ${d.takaful.length ? d.takaful.map(x => esc(prodName(x, d.products[x]))).join(', ') : t('No takaful cover with KT yet.')}</div>
        ${['Motor Takaful', 'General Takaful', 'Ar-Rahnu KT'].filter(x => !d.takaful.includes(x)).map(x => `
          <div class="row small" style="gap:8px">${icon(x.startsWith('Ar') ? 'coins' : 'shield', 14)}
            <span style="flex:1"><b>${esc(prodName(x, d.products[x]))}</b><div class="tiny muted">${esc(d.products[x].desc)}</div></span></div>`).join('')}
      </div></div>
    </div>

    <div class="card" id="assistantCard" style="display:flex;flex-direction:column;height:620px">
      <div class="card-h">${icon('msg', 15)}<h3>${t('Member Assistant')}</h3>
        <span class="sub">${t('it answers about your account — it never makes a financing decision')}</span></div>
      <div class="card-b chat" id="chat" style="flex:1;overflow-y:auto">
        <div class="msg ai">${ms()
          ? `Salam sejahtera ${esc(m.given_name)}. Saya boleh membantu tentang baki pembiayaan, ansuran seterusnya, status permohonan, dokumen yang diperlukan dan simpanan anda — dalam Bahasa Malaysia atau English.`
          : `Hello ${esc(m.given_name)}. I can help with your financing balance, next instalment, application status, documents still needed and your savings — in English or Bahasa Malaysia.`}</div>
      </div>
      <div class="card-b" style="border-top:1px solid var(--line)">
        <div class="chips" style="margin-bottom:9px" id="sug">
          ${(ms() ? ['Berapa baki pembiayaan saya dan bila bayaran seterusnya?', 'Apa status permohonan saya?', 'Dokumen apa yang masih diperlukan?', 'Berapa simpanan dan modal syer saya?', 'Saya hilang kerja dan risau tentang bayaran bulan depan']
                 : ["What's my outstanding balance?", 'When is my next deduction?', "What's happening with my application?", 'Which documents do you still need?', "I lost my job and I'm worried about next month's payment"])
            .map(q => `<button class="chip">${esc(q)}</button>`).join('')}
        </div>
        <form class="row" id="f"><input class="inp" id="q" placeholder="${t('Ask about your account…')}" aria-label="Question"/>
          <button class="btn primary" id="send" type="submit" aria-label="${t('Send')}">${icon('send')}</button></form>
      </div>
    </div>
  </div>`;

  const chat = $('#chat', el), input = $('#q', el);
  const history = [];
  const send = async q => {
    if (!q) return;
    input.value = '';
    chat.insertAdjacentHTML('beforeend', `<div class="msg me">${esc(q)}</div>`);
    const b = h('<div class="msg ai"><span class="pulse"></span></div>');
    chat.appendChild(b); chat.scrollTop = chat.scrollHeight;
    try {
      const r = await api('/member-assistant', { method: 'POST', body: { question: q, lang: lang(), history: history.slice(-6) } });
      b.innerHTML = md(r.answer);
      history.push({ role: 'user', content: q }, { role: 'assistant', content: r.answer });
      if (r.handoff) {
        chat.insertAdjacentHTML('beforeend', `<div class="msg sys">${icon('alert', 11)} ${r.lang === 'ms'
          ? `Tugasan sokongan dibuka — ${esc(r.handoff.queue)}, SLA 1 hari bekerja` : `Support task opened — ${esc(r.handoff.queue)}, SLA ${esc(r.handoff.sla)}`}</div>`);
      }
      if ((r.intents || []).includes('borrow'))
        chat.insertAdjacentHTML('beforeend', `<button class="chip on" style="align-self:flex-start" data-go="check">${icon('calc', 12)} ${t('Check Before You Borrow')}</button>`);
      chat.querySelectorAll('[data-go]').forEach(x => x.onclick = () => window.go(x.dataset.go));
    } catch (e) { b.textContent = tt('Assistant unavailable: ', 'Pembantu tidak tersedia: ') + e.message; }
    chat.scrollTop = chat.scrollHeight;
  };
  $('#f', el).onsubmit = e => { e.preventDefault(); send(input.value.trim()); };
  $$('#sug .chip', el).forEach(b => b.onclick = () => send(b.textContent));
  $$('[data-q]', el).forEach(b => b.onclick = () => {
    const k = b.dataset.q;
    if (k === 'check') window.go('check');
    if (k === 'ask') { $('#assistantCard', el).scrollIntoView({ behavior: 'smooth' }); input.focus(); }
    if (k === 'statement') statement(d);
    if (k === 'upload') uploadDoc(d);
  });
}

const kpi = (l, v, sub) => `<div class="kpi"><div class="lbl">${l}</div><div class="val" style="font-size:20px">${v}</div>
  ${sub ? `<div class="sub">${sub}</div>` : ''}</div>`;
const quick = (k, ic, title, sub) => `<button class="quick" data-q="${k}"><span class="qi">${icon(ic, 16)}</span><b>${title}</b><span>${sub}</span></button>`;

function statement(d) {
  const m = d.member;
  const rows = d.payments.slice().reverse();
  drawer(`<h3>${t('Statement')}</h3>`, `
    <div class="col" style="gap:12px" id="stmt">
      <div class="row" style="gap:10px"><div style="width:40px;height:40px">${mark('st')}</div>
        <div><b>Koperasi Angkatan Tentera Malaysia Berhad</b><div class="tiny muted">${tt('Member statement', 'Penyata ahli')} · ${date(state.boot.today)} · MYT</div></div></div>
      <dl class="kv">
        <dt>${tt('Member', 'Ahli')}</dt><dd>${esc(m.name)} (${esc(m.id)})</dd>
        <dt>MyKad</dt><dd class="mono">${esc(m.mykad.replace(/\d{4}$/, '****'))}</dd>
        <dt>${t('Outstanding balance')}</dt><dd><b>${money(m.outstanding)}</b></dd>
        <dt>${t('Monthly instalment')}</dt><dd>${money(m.deduction)} · ${esc(m.repayment_channel)}</dd>
        <dt>${t('Savings')} / ${t('Share capital')}</dt><dd>${money(m.savings)} / ${money(m.share_capital)}</dd>
      </dl>
      <div class="tw"><table><thead><tr><th>${tt('Cycle', 'Kitaran')}</th><th class="r">${tt('Due', 'Perlu')}</th><th class="r">${tt('Paid', 'Dibayar')}</th><th>${t('Status')}</th></tr></thead>
        <tbody>${rows.map(p => `<tr><td class="small">${date(p.month)}</td><td class="r num">${money(p.amount_due, 2)}</td>
          <td class="r num">${money(p.amount_paid, 2)}</td><td class="small">${p.days_late <= 2 ? t('on time') : p.days_late + ' ' + t('days late')}</td></tr>`).join('')}
        </tbody></table></div>
      <div class="tiny dim">${tt('Synthetic demonstration statement.', 'Penyata demonstrasi sintetik.')}</div>
    </div>`, { wide: true, footer: `<button class="btn primary" id="pr">${icon('print', 14)} ${t('Print')}</button>`,
      onMount: dr => dr.querySelector('#pr').onclick = () => {
        const w = window.open('', '_blank', 'width=800,height=900');
        w.document.write(`<html><head><title>KT statement ${m.id}</title><link rel="stylesheet" href="/styles.css"></head>
          <body data-theme="light" style="overflow:auto;padding:24px;background:#fff">${dr.querySelector('#stmt').outerHTML}</body></html>`);
        w.document.close(); w.onload = () => w.print();
      } });
}

function uploadDoc(d) {
  const open = d.applications.filter(a => !['Approved', 'Declined'].includes(a.status));
  if (!open.length) return toast(tt('No application needs documents', 'Tiada permohonan memerlukan dokumen'));
  const a = open[0];
  drawer(`<h3>${t('Upload a document')}</h3>`, `
    <div class="col" style="gap:12px">
      <div class="note ${a.missing.length ? 'amber' : 'green'}"><b>${esc(a.id)} — ${esc(prodName(a.product, { ms: a.product_ms }))}</b>
        <div class="small">${a.missing.length ? `${t('Documents still needed')}: ${esc((ms() ? a.missing_ms : a.missing).join(', '))}` : t('All documents received')}</div></div>
      <div class="drop" id="drop">${icon('upload', 20)}<div style="margin-top:6px">${tt('Drop a file here, or click to choose', 'Letak fail di sini, atau klik untuk memilih')}</div>
        <div class="tiny dim">PDF, PNG, JPG, CSV · ${tt('max 10 MB', 'maksimum 10 MB')}</div></div>
    </div>`, { onMount: dr => {
      const drop = dr.querySelector('#drop'), inp = document.querySelector('#uploader');
      const send = async files => {
        for (const f of files) {
          const fd = new FormData(); fd.append('file', f);
          drop.innerHTML = `<div class="row" style="justify-content:center"><span class="pulse"></span> ${esc(f.name)}…</div>`;
          const r = await fetch(`/api/applications/${a.id}/documents`, { method: 'POST', body: fd, credentials: 'same-origin' });
          const j = await r.json();
          if (!r.ok) { toast(tt('Upload failed', 'Muat naik gagal'), j.detail || '', 'bad'); continue; }
          toast(tt('Document received', 'Dokumen diterima'), `${ms() ? j.document.doc_type_ms : j.document.doc_type}`, 'good');
        }
        closeDrawer(); window.render();
      };
      drop.onclick = () => { inp.value = ''; inp.onchange = () => send(inp.files); inp.click(); };
      drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); };
      drop.ondragleave = () => drop.classList.remove('over');
      drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); send(e.dataTransfer.files); };
    } });
}

// ================================================== CHECK BEFORE YOU BORROW
export async function checkBorrow(el) {
  const d = await api('/me');
  const products = Object.entries(d.products).filter(([, p]) => p.kind === 'financing');
  let sel = { product: 'Personal Financing-i', amount: 20000, term: 60 };
  el.innerHTML = `
  <div class="page-head"><div><h1>${t('Check Before You Borrow')}</h1>
    <p>${tt('See an indicative maximum before you apply. It uses exactly the same affordability rules a KT credit officer uses — the debt service ratio on your verified pay, the 60% salary-deduction cap, KT exposure and product limits — on your own record.',
            'Lihat anggaran maksimum sebelum memohon. Ia menggunakan peraturan kemampuan yang sama seperti pegawai kredit KT — nisbah khidmat hutang ke atas gaji yang disahkan, had potongan gaji 60%, pendedahan KT dan had produk — ke atas rekod anda sendiri.')}</p></div></div>
  <div class="grid g-1-2" style="align-items:start">
    <div class="card"><div class="card-h"><h3>${tt('Your request', 'Permintaan anda')}</h3></div><div class="card-b col" style="gap:14px">
      <div class="field"><label for="prod">${t('Product')}</label><select class="inp" id="prod">
        ${products.map(([k, p]) => `<option value="${esc(k)}" ${k === sel.product ? 'selected' : ''}>${esc(prodName(k, p))}</option>`).join('')}</select></div>
      <div class="field"><label for="amt">${t('Amount')} — <b id="amtv"></b></label>
        <input type="range" id="amt" step="500"/><input class="inp num" id="amtn" type="number" step="500" style="margin-top:6px"/></div>
      <div class="field"><label for="term">${t('Tenure')} — <b id="termv"></b></label><input type="range" id="term" step="6"/></div>
      <div class="note small" id="pinfo"></div>
      <div class="tiny dim">${tt('Your pay and existing deductions are taken from your KT record and latest payslip.', 'Gaji dan potongan sedia ada diambil daripada rekod KT dan slip gaji terkini anda.')}</div>
    </div></div>
    <div class="col" style="gap:14px" id="out"><div class="card"><div class="card-b center" style="height:200px"><div class="spin"></div></div></div></div>
  </div>`;

  const P = () => d.products[sel.product];
  const setBounds = () => {
    const p = P();
    const a = $('#amt', el), n = $('#amtn', el), tm = $('#term', el);
    a.min = n.min = p.min; a.max = n.max = Math.min(p.max, 150000);
    sel.amount = Math.min(Math.max(sel.amount, p.min), +a.max);
    a.value = n.value = sel.amount;
    tm.min = p.min_term; tm.max = p.max_term; tm.step = p.max_term - p.min_term >= 24 ? 6 : 3;
    sel.term = Math.min(Math.max(sel.term, p.min_term), p.max_term); tm.value = sel.term;
    $('#pinfo', el).innerHTML = `<b>${esc(prodName(sel.product, p))}</b> · ${esc(p.contract)} · ${t('Profit rate')} ${p.rate}% ${t('flat, per year')}
      <div class="tiny muted">${esc(p.desc)} ${money(p.min)} – ${money(p.max)}, ${p.min_term}–${p.max_term} ${t('months')}.</div>`;
    labels();
  };
  const labels = () => { $('#amtv', el).textContent = money(sel.amount); $('#termv', el).textContent = `${sel.term} ${t('months')}`; };
  let timer;
  const run = () => { clearTimeout(timer); timer = setTimeout(async () => {
    const r = await api('/me/affordability', { method: 'POST', body: sel });
    $('#out', el).innerHTML = result(r);
    $('#apply', el) && ($('#apply', el).onclick = () => apply(r));
  }, 220); };
  $('#prod', el).onchange = e => { sel.product = e.target.value; setBounds(); run(); };
  $('#amt', el).oninput = e => { sel.amount = +e.target.value; $('#amtn', el).value = sel.amount; labels(); run(); };
  $('#amtn', el).onchange = e => { sel.amount = +e.target.value || P().min; $('#amt', el).value = sel.amount; labels(); run(); };
  $('#term', el).oninput = e => { sel.term = +e.target.value; labels(); run(); };
  setBounds(); run();
}

function result(r) {
  const x = r.result, ok = r.within_policy && r.amount <= x.max_financing;
  const dsrPct = Math.min(1, x.dsr / Math.max(1, x.dsr_ceiling * 1.5));
  const bar = (v, cap, lbl) => `<div><div class="row small"><span style="flex:1">${lbl}</span><b>${v == null ? '—' : v + '%'}</b>
      <span class="dim">/ ${cap}%</span></div><div class="meterbar" style="margin-top:5px"><i style="width:${Math.min(100, (v || 0) / (cap * 1.5) * 100)}%;
      background:var(--${(v || 0) <= cap ? 'green' : 'red'})"></i><em style="left:${100 / 1.5}%"></em></div></div>`;
  return `
  <div class="card ${ok ? '' : ''}"><div class="card-b">
    <div class="row wrap" style="gap:18px;align-items:center">
      <div style="flex:1;min-width:220px"><div class="up">${t('Indicative maximum')}</div>
        <div style="font-size:34px;font-weight:750;letter-spacing:-.03em">${money(x.max_financing)}</div>
        <div class="small muted">${esc(prodName(r.product, { ms: x.product_ms }))} · ${r.term} ${t('months')} · ${tt('binding limit', 'had pengikat')}: <b>${esc(x.max_financing_binding_label)}</b></div>
        <div class="tiny dim" style="margin-top:3px">${money(r.max_at_longest_term)} ${t('at the longest tenure')} (${r.longest_term} ${t('months')})</div></div>
      <div style="width:150px">${gauge(dsrPct, { label: x.dsr + '%', sub: 'DSR', color: x.dsr <= x.dsr_ceiling ? 'var(--green)' : 'var(--red)' })}</div>
    </div>
    <div class="note ${ok ? 'green' : 'amber'}" style="margin-top:12px"><b>${ok ? tt('Your request fits within policy', 'Permintaan anda dalam had dasar')
      : tt('Your request is above what policy supports today', 'Permintaan anda melebihi had dasar hari ini')}</b>
      <div class="small">${esc(r.explanation)}</div></div>
  </div></div>
  <div class="grid g2">
    <div class="card"><div class="card-h"><h3>${tt('At the amount you entered', 'Pada amaun yang dimasukkan')}</h3></div><div class="card-b col" style="gap:10px">
      <dl class="kv">
        <dt>${t('Monthly instalment')}</dt><dd><b>${money(x.instalment, 2)}</b></dd>
        <dt>${t('Profit rate')}</dt><dd>${x.rate}% ${t('flat, per year')}</dd>
        <dt>${tt('Total profit', 'Jumlah keuntungan')}</dt><dd>${money(x.total_profit, 2)}</dd>
        <dt>${tt('Total payable', 'Jumlah perlu dibayar')}</dt><dd>${money(x.total_payable, 2)}</dd>
        <dt>${tt('Existing financing deductions', 'Potongan pembiayaan sedia ada')}</dt><dd>${money(x.existing_commitments)}</dd>
      </dl>
      ${bar(x.dsr, x.dsr_ceiling, t('Debt service ratio'))}
      ${x.by_salary_deduction ? bar(x.deduction_ratio, x.deduction_cap, t('Salary deduction cap')) : ''}
    </div></div>
    <div class="card"><div class="card-h"><h3>${tt('Eligibility checks', 'Semakan kelayakan')}</h3></div><div class="card-b col" style="gap:4px">
      ${r.gates.map(g => `<div class="row small" style="gap:8px;padding:4px 0;border-bottom:1px solid var(--line-soft)">
        <span class="tag t-${g.passed ? 'green' : g.hard ? 'red' : 'amber'}">${icon(g.passed ? 'check' : 'x', 11)}</span>
        <span style="flex:1">${esc(g.name)}<div class="tiny dim">${esc(g.required)}</div></span><span class="mono tiny">${esc(g.actual)}</span></div>`).join('')}
    </div></div>
  </div>
  <div class="card"><div class="card-h"><h3>${t('Documents you will need')}</h3></div><div class="card-b row wrap" style="gap:6px">
    ${r.documents.map(x => `<span class="tag t-grey">${esc(ms() ? x.ms : x.en)}</span>`).join('')}</div></div>
  <div class="note gold small">${icon('info', 12)} ${esc(r.disclaimer[ms() ? 'ms' : 'en'])}</div>
  <div class="row"><button class="btn primary lg" id="apply" ${r.amount > x.max_financing || !r.within_policy ? 'disabled' : ''}>${icon('send', 14)} ${t('Proceed to apply')}</button>
    ${r.amount > x.max_financing && x.max_financing > 0 ? `<span class="small muted">${tt('Lower the amount to', 'Kurangkan amaun kepada')} ${money(x.max_financing)} ${tt('or less to apply.', 'atau kurang untuk memohon.')}</span>` : ''}</div>`;
}

function apply(r) {
  drawer(`<h3>${t('Proceed to apply')}</h3>`, `
    <div class="col" style="gap:12px">
      <dl class="kv"><dt>${t('Product')}</dt><dd>${esc(prodName(r.product, { ms: r.result.product_ms }))}</dd>
        <dt>${t('Amount')}</dt><dd>${money(r.amount)}</dd><dt>${t('Tenure')}</dt><dd>${r.term} ${t('months')}</dd>
        <dt>${t('Monthly instalment')}</dt><dd>${money(r.result.instalment, 2)}</dd></dl>
      <div class="field"><label for="purp">${t('Purpose')}</label><input class="inp" id="purp" placeholder="${tt('e.g. home renovation', 'cth. ubah suai rumah')}"/></div>
      <div class="note small">${esc(r.disclaimer[ms() ? 'ms' : 'en'])}</div>
    </div>`, { footer: `<button class="btn primary" id="ok">${t('Apply')}</button>`, onMount: dr => dr.querySelector('#ok').onclick = async () => {
      try {
        const x = await api('/me/applications', { method: 'POST', body: { product: r.product, amount: r.amount, term: r.term,
          purpose: dr.querySelector('#purp').value || '—' } });
        closeDrawer();
        toast(tt('Application submitted', 'Permohonan dihantar'), `${x.id} — ${tt('a KT officer will review it', 'pegawai KT akan menyemaknya')}`, 'good');
        window.go('member-portal');
      } catch (e) { toast(tt('Not submitted', 'Tidak dihantar'), e.message, 'bad'); }
    } });
}
