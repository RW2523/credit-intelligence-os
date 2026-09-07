import { api, icon, esc, money, tag, toast, $, $$, sse, h } from '/lib.js';

export async function intake(el) {
  const boot = await api('/bootstrap');
  const { rows: members } = await api('/members');
  el.innerHTML = `
  <div class="page-head"><div><h1>New Application</h1>
    <p>On submission the case is created and its snapshot is frozen, so every downstream assessment can later be
       reproduced against exactly the information that existed at decision time.</p></div></div>

  <div class="grid g-2-1" style="align-items:start">
    <div class="card"><div class="card-h"><h3>Application intake</h3></div><div class="card-b col" style="gap:14px">
      <div class="grid g2">
        <div class="field"><label>Member</label><select class="inp" id="member">
          ${members.map(m => `<option value="${m.id}" data-inc="${m.declared_income}" data-emp="${esc(m.employer)}">
            ${esc(m.name)} — ${m.id}</option>`).join('')}
          <option value="">＋ New applicant</option></select></div>
        <div class="field"><label>Branch</label><select class="inp" id="branch">
          ${boot.branches.map(b => `<option>${b}</option>`).join('')}</select></div>
      </div>
      <div class="grid g2" id="newFields" style="display:none">
        <div class="field"><label>Applicant name</label><input class="inp" id="name" placeholder="Full name"/></div>
        <div class="field"><label>Employer</label><input class="inp" id="employer" placeholder="Employer"/></div>
      </div>
      <div class="grid g2">
        <div class="field"><label>Product</label><select class="inp" id="product">
          ${Object.keys(boot.products).map(p => `<option>${p}</option>`).join('')}</select></div>
        <div class="field"><label>Employment</label><select class="inp" id="employment">
          <option>Employed</option><option>Self-Employed</option><option>Contract</option></select></div>
      </div>
      <div class="grid g3">
        <div class="field"><label>Amount requested</label><input class="inp num" id="amount" type="number" value="25000"/></div>
        <div class="field"><label>Term (months)</label><input class="inp num" id="term" type="number" value="36"/></div>
        <div class="field"><label>Declared annual income</label><input class="inp num" id="income" type="number" value="52000"/></div>
      </div>
      <div class="grid g2">
        <div class="field"><label>Existing monthly commitments</label><input class="inp num" id="commit" type="number" value="450"/></div>
        <div class="field"><label>Guarantor (optional)</label><input class="inp" id="guarantor" placeholder="—"/></div>
      </div>
      <div class="field"><label>Purpose</label><input class="inp" id="purpose" value="Home improvement"/></div>
      <div class="sep"></div>
      <div class="row wrap">
        <button class="btn primary lg" id="submit">${icon('check')} Create case & freeze snapshot</button>
        <button class="btn lg" id="reset">Reset</button>
      </div>
    </div></div>

    <div class="col" style="gap:14px">
      <div class="card"><div class="card-h"><h3>Live affordability preview</h3><span class="sub">deterministic</span></div>
        <div class="card-b" id="preview"></div></div>
      <div class="card"><div class="card-h"><h3>What happens on submit</h3></div><div class="card-b">
        <div class="timeline">${['Application created', 'Case created', 'Snapshot frozen',
          'Document processing starts', 'Feature calculation starts', 'Policy assessment starts',
          'Risk & fraud scoring', 'Ready for the AI Credit Council'].map(s =>
          `<div class="tl-item blue"><b style="font-size:12.5px">${s}</b></div>`).join('')}</div></div></div>
      <div class="card"><div class="card-h"><h3>Required evidence</h3></div>
        <div class="card-b row wrap" style="gap:7px" id="reqdocs"></div></div>
    </div>
  </div>`;

  const g = id => $('#' + id, el);
  const upd = () => {
    const prod = boot.products[g('product').value];
    const amount = +g('amount').value || 0, term = +g('term').value || 1;
    const inc = +g('income').value || 0, commit = +g('commit').value || 0;
    const r = prod.rate / 100 / 12;
    const pay = r ? amount * r / (1 - Math.pow(1 + r, -term)) : amount / term;
    const monthly = inc / 12;
    const dsr = monthly ? (commit + pay) / monthly * 100 : 999;
    const ok = dsr <= prod.max_dti && amount <= prod.max && term <= prod.max_term;
    g('preview').innerHTML = `
      <dl class="kv">
        <dt>Monthly instalment</dt><dd><b>${money(pay, 2)}</b></dd>
        <dt>Interest rate</dt><dd>${prod.rate}%</dd>
        <dt>Verified monthly income</dt><dd>${money(monthly, 2)}</dd>
        <dt>Existing commitments</dt><dd>${money(commit)}</dd>
        <dt>Total obligations</dt><dd>${money(commit + pay, 2)}</dd>
        <dt>Debt service ratio</dt><dd><b style="color:var(--${dsr <= prod.max_dti ? 'green' : 'red'})">${dsr.toFixed(2)}%</b>
          <span class="dim">of ${prod.max_dti}%</span></dd>
        <dt>Product ceiling</dt><dd>${money(prod.max)}</dd>
      </dl>
      <div class="bar" style="margin-top:10px"><i style="width:${Math.min(100, dsr / prod.max_dti * 100)}%;
        background:var(--${dsr <= prod.max_dti ? 'green' : 'red'})"></i></div>
      <div class="note ${ok ? 'green' : 'red'}" style="margin-top:10px">
        <b>${ok ? 'Within policy' : 'Outside policy'}</b>
        <div class="small">${ok ? 'This request passes the deterministic gates before any model runs.'
          : 'Adjust the amount or term — a hard gate fails at these values.'}</div></div>`;
    g('reqdocs').innerHTML = prod.docs.map(d => `<span class="tag t-grey">${esc(d)}</span>`).join('');
  };
  ['product', 'amount', 'term', 'income', 'commit'].forEach(id => { g(id).oninput = upd; g(id).onchange = upd; });
  g('member').onchange = () => {
    const o = g('member').selectedOptions[0];
    $('#newFields', el).style.display = g('member').value ? 'none' : 'grid';
    if (o.dataset.inc) { g('income').value = o.dataset.inc; g('employer') && (g('employer').value = o.dataset.emp || ''); }
    upd();
  };
  g('reset').onclick = () => intake(el);
  g('submit').onclick = async () => {
    const btn = g('submit'); btn.disabled = true;
    try {
      const body = {
        member_id: g('member').value, applicant_name: g('name')?.value || '',
        product: g('product').value, amount: +g('amount').value, term: +g('term').value,
        purpose: g('purpose').value, branch: g('branch').value,
        existing_commitments: +g('commit').value, declared_income: +g('income').value,
        employer: g('employer')?.value || '', employment: g('employment').value,
        guarantor: g('guarantor').value || null,
      };
      const r = await api('/applications', { method: 'POST', body });
      toast('Case created', `${r.id} — snapshot ${r.case.snapshot.hash} frozen`, 'good');
      window.go('workbench', r.id);
    } catch (e) { toast('Not created', e.message, 'bad'); btn.disabled = false; }
  };
  g('member').onchange();
  upd();
}
