import { api, icon, esc, money, tag, toast, $, $$, sse, h } from '/lib.js';
import { t, tt, lang } from '/i18n.js';

export async function intake(el) {
  const boot = await api('/bootstrap');
  const { rows: members } = await api('/members');
  el.innerHTML = `
  <div class="page-head"><div><h1>${t('New Application')}</h1>
    <p>${tt('On submission the case is created and its snapshot frozen, so every assessment can later be reproduced against exactly the information that existed at decision time.',
            'Apabila dihantar, kes dicipta dan snapshot dibekukan supaya setiap penilaian boleh dihasilkan semula.')}</p></div></div>

  <div class="grid g-2-1" style="align-items:start">
    <div class="card"><div class="card-h"><h3>Application intake</h3></div><div class="card-b col" style="gap:14px">
      <div class="grid g2">
        <div class="field"><label>Member</label><select class="inp" id="member">
          ${members.map(m => `<option value="${m.id}" data-inc="${m.declared_income}" data-emp="${esc(m.employer)}"
            data-commit="${m.financing_deductions}" data-branch="${esc(m.branch)}">
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
        <div class="field"><label>${t('Product')}</label><select class="inp" id="product">
          ${boot.financing.map(p => `<option value="${esc(p)}">${esc(lang() === 'ms' ? boot.products[p].ms : p)}</option>`).join('')}</select></div>
        <div class="field"><label>${tt('Service status', 'Taraf perkhidmatan')}</label><select class="inp" id="employment">
          <option>Serving — permanent & confirmed</option><option>Civil service — permanent</option>
          <option>Retired (pension)</option><option>Self-employed (business owner)</option></select></div>
      </div>
      <div class="grid g3">
        <div class="field"><label>${tt('Amount requested (RM)', 'Amaun dipohon (RM)')}</label><input class="inp num" id="amount" type="number" value="25000"/></div>
        <div class="field"><label>${tt('Tenure (months)', 'Tempoh (bulan)')}</label><input class="inp num" id="term" type="number" value="48"/></div>
        <div class="field"><label>${tt('Declared annual income, before financing (RM)', 'Pendapatan tahunan diisytihar, sebelum pembiayaan (RM)')}</label><input class="inp num" id="income" type="number" value="52000"/></div>
      </div>
      <div class="grid g2">
        <div class="field"><label>${tt('Existing monthly financing deductions (RM)', 'Potongan pembiayaan bulanan sedia ada (RM)')}</label><input class="inp num" id="commit" type="number" value="650"/></div>
        <div class="field"><label>Guarantor (optional)</label><input class="inp" id="guarantor" placeholder="—"/></div>
      </div>
      <div class="field"><label>${t('Purpose')}</label><input class="inp" id="purpose" value="Home renovation"/></div>
      <div class="sep"></div>
      <div class="row wrap">
        <button class="btn primary lg" id="submit">${icon('check')} Create case & freeze snapshot</button>
        <button class="btn lg" id="reset">Reset</button>
      </div>
    </div></div>

    <div class="col" style="gap:14px">
      <div class="card"><div class="card-h"><h3>${tt('Live affordability preview', 'Pratonton kemampuan')}</h3><span class="sub">${tt('flat profit rate · indicative', 'kadar keuntungan rata · anggaran')}</span></div>
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
    // flat profit rate, as on KT's financing: amount × (1 + rate × years) ÷ months
    const pay = amount * (1 + prod.rate / 100 * term / 12) / term;
    const monthly = inc / 12;
    const dsr = monthly ? (commit + pay) / monthly * 100 : 999;
    const ok = dsr <= prod.max_dti && amount <= prod.max && amount >= prod.min && term <= prod.max_term && term >= prod.min_term;
    g('preview').innerHTML = `
      <dl class="kv">
        <dt>${t('Monthly instalment')}</dt><dd><b>${money(pay, 2)}</b></dd>
        <dt>${t('Profit rate')}</dt><dd>${prod.rate}% ${t('flat, per year')} · ${esc(prod.contract)}</dd>
        <dt>${tt('Declared monthly income', 'Pendapatan bulanan diisytihar')}</dt><dd>${money(monthly, 2)}</dd>
        <dt>${tt('Existing financing deductions', 'Potongan pembiayaan sedia ada')}</dt><dd>${money(commit)}</dd>
        <dt>${tt('Total financing obligations', 'Jumlah obligasi pembiayaan')}</dt><dd>${money(commit + pay, 2)}</dd>
        <dt>${t('Debt service ratio')}</dt><dd><b style="color:var(--${dsr <= prod.max_dti ? 'green' : 'red'})">${dsr.toFixed(2)}%</b>
          <span class="dim">of ${prod.max_dti}%</span></dd>
        <dt>${tt('Product range', 'Julat produk')}</dt><dd>${money(prod.min)} – ${money(prod.max)} · ${prod.min_term}–${prod.max_term} ${t('months')}</dd>
      </dl>
      <div class="bar" style="margin-top:10px"><i style="width:${Math.min(100, dsr / prod.max_dti * 100)}%;
        background:var(--${dsr <= prod.max_dti ? 'green' : 'red'})"></i></div>
      <div class="note ${ok ? 'green' : 'red'}" style="margin-top:10px">
        <b>${ok ? t('Within policy') : t('Outside policy')}</b>
        <div class="small">${ok ? tt('Passes the declared-income checks; the case file adds the 60% deduction cap, exposure and verified income.', 'Lulus semakan pendapatan diisytihar; fail kes menambah had potongan 60%, pendedahan dan pendapatan disahkan.')
          : tt('Adjust the amount or tenure — a hard gate fails at these values.', 'Laraskan amaun atau tempoh — had wajib gagal pada nilai ini.')}</div></div>`;
    g('reqdocs').innerHTML = prod.docs.map(d => `<span class="tag t-grey">${esc(lang() === 'ms' ? (boot.doc_ms[d] || d) : d)}</span>`).join('');
  };
  ['product', 'amount', 'term', 'income', 'commit'].forEach(id => { g(id).oninput = upd; g(id).onchange = upd; });
  g('member').onchange = () => {
    const o = g('member').selectedOptions[0];
    $('#newFields', el).style.display = g('member').value ? 'none' : 'grid';
    if (o.dataset.inc) { g('income').value = o.dataset.inc; g('employer') && (g('employer').value = o.dataset.emp || '');
      g('commit').value = o.dataset.commit || 0; if (o.dataset.branch) g('branch').value = o.dataset.branch; }
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
        existing_commitments: +g('commit').value, declared_income: g('member').value ? null : +g('income').value,
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
