import { api, icon, esc, money, num, pct, tag, toneFor, date, dtime, barChart, lineChart, donut,
         drawer, closeDrawer, toast, $, $$ } from '/lib.js';
import { t, tt, lang } from '/i18n.js';
import { state, refreshMeta, render } from '/app.js';
import { askDrawer } from '/views/assistant.js';

const PNAME = p => (lang() === 'ms' ? state.boot.products?.[p]?.ms : null) || p;

// ============================================================= SANDBOX
const CONTROLS = [
  { k: 'dsr_ceiling', label: ['Debt service ratio ceiling', 'Siling nisbah khidmat hutang'], min: 30, max: 70, step: 1, unit: '%',
    help: ['Lower = fewer approvals and less risk; higher = more members qualify but repayments take more of their net pay. Applies to every product.',
           'Lebih rendah = kurang kelulusan, risiko lebih rendah; lebih tinggi = lebih ramai layak tetapi ansuran mengambil lebih banyak gaji bersih.'],
    prodLabel: ['product ceilings (40% salary products, 45% business)', 'siling produk (40% produk gaji, 45% perniagaan)'] },
  { k: 'deduction_cap', label: ['Salary deduction cap (% of gross)', 'Had potongan gaji (% kasar)'], min: 40, max: 70, step: 1, unit: '%',
    help: ['The government rule is 60% of gross pay through Biro ANGKASA. Tightening it protects take-home pay.',
           'Peraturan kerajaan ialah 60% gaji kasar melalui Biro ANGKASA. Mengetatkannya melindungi gaji bawa pulang.'] },
  { k: 'exposure_multiple', label: ['Exposure multiple of savings + share capital', 'Gandaan pendedahan simpanan + modal syer'], min: 2, max: 8, step: 0.5, unit: '×',
    help: ['How many times a member\'s own savings and share capital KT will lend in total.', 'Berapa kali ganda simpanan dan modal syer ahli yang KT akan biayai.'] },
  { k: 'min_gross', label: ['Minimum gross salary', 'Gaji kasar minimum'], min: 1500, max: 3500, step: 100, unit: 'RM',
    help: ['Eligibility floor for Personal and Express Financing-i.', 'Had kelayakan untuk Pembiayaan Peribadi dan Ekspres-i.'] },
  { k: 'min_confidence', label: ['Minimum Council confidence for straight-through', 'Keyakinan Majlis minimum untuk terus lulus'], min: 0.6, max: 0.99, step: 0.01, unit: '',
    help: ['Below this, a case that passes policy is referred to an officer instead of being eligible for autonomous approval.',
           'Di bawah paras ini, kes yang lulus dasar dirujuk kepada pegawai.'] },
  { k: 'max_pd', label: ['Maximum probability of default for straight-through', 'Kebarangkalian mungkir maksimum untuk terus lulus'], min: 0.01, max: 0.2, step: 0.01, unit: '',
    help: ['Cases with a higher calibrated default probability always go to a person.', 'Kes dengan kebarangkalian mungkir lebih tinggi sentiasa kepada manusia.'] },
];

export async function sandbox(el) {
  const [boot, gov] = await Promise.all([api('/bootstrap'), api('/governance')]);
  const prod = gov.production;
  const ms = lang() === 'ms';
  const val = c => (prod[c.k] ?? (c.k === 'dsr_ceiling' ? 40 : null));
  el.innerHTML = `
  <div class="page-head"><div><h1>${t('Policy Sandbox')}</h1>
    <p>${tt('Test a policy change on the whole frozen portfolio before adopting it. Move a control, replay every open case, and see what changes — approvals, exposure, expected delinquency and exactly which members are affected. Production changes only after a second Board member approves.',
            'Uji perubahan dasar ke atas seluruh portfolio sebelum menerimanya. Gerakkan kawalan, main semula setiap kes, dan lihat perubahannya. Pengeluaran hanya berubah selepas kelulusan ahli Lembaga kedua.')}</p></div>
    <div class="spacer"></div><span class="tag t-gold">${tt('Policy', 'Dasar')} ${esc(gov.policy_version)}</span></div>

  <div class="note gold" style="margin-bottom:14px"><b>${tt('Why this matters to the Board', 'Mengapa ini penting kepada Lembaga')}</b>
    <div class="small">${tt('The Board owns credit policy and decides how much the AI may do. The sandbox turns a policy debate into evidence: the effect of a resolution on real cases is visible before it is passed. The Autonomy Dial sets the AI\'s authority and the kill switch stops it at once. Every proposal, approval and dial change is sealed to the Decision Ledger.',
      'Lembaga memiliki dasar kredit dan menentukan sejauh mana AI boleh bertindak. Kotak pasir menukar perbahasan dasar kepada bukti: kesan resolusi ke atas kes sebenar boleh dilihat sebelum diluluskan. Dail Autonomi menetapkan kuasa AI dan suis henti menghentikannya serta-merta. Setiap cadangan, kelulusan dan perubahan direkod dalam Lejar Keputusan.')}</div></div>

  <div class="grid g-1-2" style="align-items:start">
    <div class="col" style="gap:14px">
      <div class="card"><div class="card-h"><h3>${tt('Candidate policy', 'Dasar calon')}</h3><div class="spacer"></div>
        <button class="btn ghost sm" id="reset">${tt('Reset to production', 'Set semula ke pengeluaran')}</button></div>
        <div class="card-b col" style="gap:16px">
        ${CONTROLS.map(c => `<div class="field" data-ctl="${c.k}">
          <label for="${c.k}">${esc(ms ? c.label[1] : c.label[0])} — <b id="${c.k}v"></b> <span class="tag t-grey" id="${c.k}d" style="display:none"></span></label>
          <input type="range" id="${c.k}" min="${c.min}" max="${c.max}" step="${c.step}" value="${val(c) ?? c.min}" data-unit="${c.unit}"/>
          <div class="tiny dim">${esc(ms ? c.help[1] : c.help[0])} ${tt('Production', 'Pengeluaran')}: <b>${val(c) == null ? esc(ms ? c.prodLabel[1] : c.prodLabel[0]) : fmtv(c, val(c))}</b></div>
        </div>`).join('')}
        <button class="btn primary lg" id="run">${icon('activity')} ${tt('Replay the portfolio', 'Main semula portfolio')}</button>
      </div></div>
      <div class="card" id="autonomyCard"></div>
    </div>
    <div class="col" style="gap:14px">
      <div id="simOut"><div class="card"><div class="card-b empty">${icon('sliders', 26)}
        <b>${tt('No simulation run yet', 'Belum ada simulasi')}</b><span class="small">${tt('Move a control and replay the portfolio.', 'Gerakkan kawalan dan main semula portfolio.')}</span></div></div></div>
      <div id="proposals">${proposals(gov.policy_changes)}</div>
    </div>
  </div>`;

  const changed = () => Object.fromEntries(CONTROLS.map(c => [c.k, +$('#' + c.k, el).value])
    .filter(([k, v]) => { const c = CONTROLS.find(x => x.k === k); const p = val(c); return p == null ? v !== (k === 'dsr_ceiling' ? 40 : null) : Math.abs(v - p) > 1e-9; }));
  const refresh = () => CONTROLS.forEach(c => {
    const s = $('#' + c.k, el), d = $('#' + c.k + 'd', el);
    $('#' + c.k + 'v', el).textContent = fmtv(c, +s.value);
    const ch = changed()[c.k] !== undefined;
    d.style.display = ch ? '' : 'none'; d.textContent = tt('changed', 'diubah');
    s.closest('.field').style.opacity = ch ? 1 : .85;
  });
  $$('input[type=range]', el).forEach(s => s.oninput = refresh);
  refresh();
  $('#reset', el).onclick = () => sandbox(el);
  $('#run', el).onclick = async () => {
    const out = $('#simOut', el);
    out.innerHTML = `<div class="card"><div class="card-b center" style="height:200px"><div class="spin"></div></div></div>`;
    const s = await api('/sandbox/simulate', { method: 'POST', body: changed() });
    out.innerHTML = simResult(s);
    out.querySelector('#promote') && (out.querySelector('#promote').onclick = () => promote(changed(), s, el));
  };
  renderAutonomy($('#autonomyCard', el), boot.autonomy);
  bindProposals(el);
}

const fmtv = (c, v) => c.unit === '%' ? `${v}%` : c.unit === '×' ? `${v}×` : c.unit === 'RM' ? money(v) : `${v}`;

function simResult(s) {
  const b = s.baseline, c = s.candidate_result;
  const delta = (a, x, inv = false) => { const d = x - a; const good = inv ? d < 0 : d > 0;
    return d ? `<span style="color:var(--${good ? 'green' : 'red'})">${d > 0 ? '+' : ''}${Number.isInteger(d) ? d : d.toFixed(1)}</span>` : '<span class="dim">±0</span>'; };
  const changedKeys = Object.keys(s.candidate).filter(k => s.candidate[k] !== s.production[k]);
  return `
  <div class="card"><div class="card-h"><h3>${tt('Current policy vs candidate', 'Dasar semasa vs calon')}</h3>
    <span class="sub">${s.cases} ${tt('open cases replayed', 'kes terbuka dimain semula')}</span></div>
    <div class="tw"><table><thead><tr><th></th><th class="r">${tt('Current', 'Semasa')}</th><th class="r">${tt('Candidate', 'Calon')}</th><th class="r">${tt('Change', 'Perubahan')}</th></tr></thead><tbody>
      <tr><td>${tt('Straight-through eligible', 'Layak terus lulus')}</td><td class="r num">${b.approve}</td><td class="r num">${c.approve}</td><td class="r">${delta(b.approve, c.approve)}</td></tr>
      <tr><td>${tt('Referred to an officer', 'Dirujuk kepada pegawai')}</td><td class="r num">${b.refer}</td><td class="r num">${c.refer}</td><td class="r">${delta(b.refer, c.refer, true)}</td></tr>
      <tr><td>${tt('Waiting on documents', 'Menunggu dokumen')}</td><td class="r num">${b.request}</td><td class="r num">${c.request}</td><td class="r">${delta(b.request, c.request, true)}</td></tr>
      <tr><td>${tt('Declined by policy', 'Ditolak oleh dasar')}</td><td class="r num">${b.decline}</td><td class="r num">${c.decline}</td><td class="r">${delta(b.decline, c.decline, true)}</td></tr>
      <tr><td>${tt('Approved exposure', 'Pendedahan diluluskan')}</td><td class="r num">${money(b.exposure)}</td><td class="r num">${money(c.exposure)}</td><td class="r">${delta(b.exposure / 1000, c.exposure / 1000)}k</td></tr>
      <tr><td>${tt('Expected delinquency of approvals', 'Jangkaan tunggakan kelulusan')}</td><td class="r num">${b.predicted_delinquency}%</td><td class="r num">${c.predicted_delinquency}%</td><td class="r">${delta(b.predicted_delinquency, c.predicted_delinquency, true)}</td></tr>
      <tr><td>${tt('Total supportable financing (capacity)', 'Jumlah pembiayaan disokong (kapasiti)')}</td><td class="r num">${money(b.capacity)}</td><td class="r num">${money(c.capacity)}</td><td class="r">${delta(b.capacity / 1000, c.capacity / 1000)}k</td></tr>
    </tbody></table></div>
    <div class="card-b">${barChart([
      { l: tt('Approve', 'Lulus'), v: b.approve, color: 'var(--green)', dim: true, note: tt('current', 'semasa') }, { l: tt('Approve*', 'Lulus*'), v: c.approve, color: 'var(--green)', note: tt('candidate', 'calon') },
      { l: tt('Refer', 'Rujuk'), v: b.refer, color: 'var(--amber)', dim: true, note: tt('current', 'semasa') }, { l: tt('Refer*', 'Rujuk*'), v: c.refer, color: 'var(--amber)', note: tt('candidate', 'calon') },
      { l: tt('Docs', 'Dokumen'), v: b.request, color: 'var(--info)', dim: true, note: tt('current', 'semasa') }, { l: tt('Docs*', 'Dokumen*'), v: c.request, color: 'var(--info)', note: tt('candidate', 'calon') },
      { l: tt('Decline', 'Tolak'), v: b.decline, color: 'var(--red)', dim: true, note: tt('current', 'semasa') }, { l: tt('Decline*', 'Tolak*'), v: c.decline, color: 'var(--red)', note: tt('candidate', 'calon') },
    ], { h: 150, legend: { labels: [tt('Current (faded)', 'Semasa (pudar)'), tt('Candidate (*)', 'Calon (*)')], colors: ['var(--line-3)', 'var(--brand)'] } })}</div></div>
  <div class="card"><div class="card-h"><h3>${tt('Members whose outcome changes', 'Ahli yang keputusannya berubah')}</h3>
    <span class="sub">${s.changed.length} ${tt('of', 'daripada')} ${s.cases}</span></div>
    ${s.changed.length ? `<div class="tw"><table><thead><tr><th>${tt('Member', 'Ahli')}</th><th>${t('Branch')}</th><th>${t('Product')}</th>
      <th class="r">${t('Amount')}</th><th>DSR</th><th>${tt('Deductions', 'Potongan')}</th><th>${tt('Before', 'Sebelum')}</th><th>${tt('After', 'Selepas')}</th></tr></thead><tbody>
      ${s.changed.map(x => `<tr><td><div style="font-weight:560">${esc(x.name)}</div><div class="tiny dim mono">${x.id}</div></td><td class="small">${esc(x.branch)}</td>
        <td class="small">${esc(PNAME(x.product))}</td><td class="r num">${money(x.amount)}</td>
        <td class="num small">${x.dsr}%</td><td class="num small">${x.deduction == null ? '—' : x.deduction + '%'}</td><td>${tag(x.before)}</td><td>${tag(x.after)}</td></tr>`).join('')}
      </tbody></table></div>` : `<div class="card-b empty small">${tt('No case changes outcome under this candidate.', 'Tiada kes berubah keputusan di bawah calon ini.')}</div>`}
    ${Object.keys(s.segments).length ? `<div class="card-b"><div class="up">${tt('Affected segments', 'Segmen terjejas')}</div>
      <div class="row wrap" style="gap:6px;margin-top:6px">${Object.entries(s.segments).flatMap(([dim, o]) => Object.entries(o).map(([k, v]) =>
        `<span class="tag t-amber">${esc(dim)}: ${esc(PNAME(k))} · ${v}</span>`)).join('')}</div></div>` : ''}
    <div class="card-b"><div class="up">${tt('Which limit binds each case under the candidate', 'Had yang mengikat setiap kes di bawah calon')}</div>
      <div class="row wrap" style="gap:6px;margin-top:6px">${Object.entries(s.binding).map(([k, v]) =>
        `<span class="tag t-grey">${esc({ dsr: 'DSR', deduction_cap: tt('60% deduction cap', 'had potongan 60%'), exposure: tt('exposure', 'pendedahan'), product_ceiling: tt('product max', 'had produk') }[k] || k)} · ${v}</span>`).join('')}</div></div>
  </div>
  <div class="note amber small">${esc(s.note)}</div>
  ${changedKeys.length && state.user.views.includes('sandbox') ? `<button class="btn primary lg" id="promote">${icon('up')} ${tt('Propose this change for Board approval', 'Cadangkan perubahan ini untuk kelulusan Lembaga')}</button>` : ''}`;
}

function promote(thresholds, sim, el) {
  const rows = Object.entries(thresholds).map(([k, v]) => {
    const c = CONTROLS.find(x => x.k === k);
    return `<tr><td>${esc(lang() === 'ms' ? c.label[1] : c.label[0])}</td><td class="r">${sim.production[k] == null ? '—' : fmtv(c, sim.production[k])}</td><td class="r"><b>${fmtv(c, v)}</b></td></tr>`;
  }).join('');
  drawer(`<h3>${tt('Propose policy change', 'Cadang perubahan dasar')}</h3>`, `
    <div class="col" style="gap:12px">
      <div class="note amber"><b>${tt('This does not change production.', 'Ini tidak mengubah pengeluaran.')}</b>
        <div class="small">${tt('It records a proposal. A Board member other than the proposer must approve it before it takes effect, and the policy version is then incremented.',
          'Ia merekod cadangan. Ahli Lembaga selain pencadang mesti meluluskannya sebelum berkuat kuasa.')}</div></div>
      <div class="tw"><table><thead><tr><th>${tt('Control', 'Kawalan')}</th><th class="r">${tt('Current', 'Semasa')}</th><th class="r">${tt('Proposed', 'Dicadang')}</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="small muted">${tt('Expected effect', 'Kesan dijangka')}: ${sim.changed.length} ${tt('case(s) change outcome; approved exposure', 'kes berubah; pendedahan diluluskan')} ${money(sim.baseline.exposure)} → ${money(sim.candidate_result.exposure)}.</div>
      <div class="field"><label for="j">${tt('Justification (required)', 'Justifikasi (wajib)')}</label>
        <textarea class="inp" id="j" rows="4" placeholder="${tt('Why this change, and what it is expected to achieve.', 'Mengapa perubahan ini, dan apa yang dijangka dicapai.')}"></textarea></div>
    </div>`, {
    footer: `<button class="btn primary" id="ok">${tt('Record proposal', 'Rekod cadangan')}</button>`,
    onMount: dr => dr.querySelector('#ok').onclick = async () => {
      try {
        await api('/sandbox/promote', { method: 'POST', body: { thresholds, justification: dr.querySelector('#j').value } });
        closeDrawer(); toast(tt('Proposal recorded', 'Cadangan direkod'), tt('Pending a second Board approval.', 'Menunggu kelulusan ahli Lembaga kedua.'), 'good');
        sandbox(el);
      } catch (e) { toast(tt('Not recorded', 'Tidak direkod'), e.message, 'bad'); }
    }
  });
}

function proposals(list) {
  if (!list?.length) return '';
  const canReview = state.user.role === 'board';
  return `<div class="card"><div class="card-h"><h3>${tt('Policy change proposals', 'Cadangan perubahan dasar')}</h3></div><div class="card-b col" style="gap:9px">
    ${list.map(p => `<div class="note ${p.status.startsWith('Approved') ? 'green' : p.status === 'Rejected' ? 'red' : 'amber'}">
      <div class="row"><b style="flex:1">${esc(p.id)} — ${esc(p.status)}${p.policy_version ? ` (${esc(p.policy_version)})` : ''}</b>
        ${canReview && p.status === 'Pending Board approval' && p.actor_username !== state.user.username ? `
          <button class="btn sm good" data-rv="${p.id}" data-ok="1">${icon('check', 11)} ${tt('Approve', 'Lulus')}</button>
          <button class="btn sm bad" data-rv="${p.id}" data-ok="0">${icon('x', 11)} ${tt('Reject', 'Tolak')}</button>` : ''}</div>
      <div class="small">${Object.entries(p.thresholds).map(([k, v]) => { const c = CONTROLS.find(x => x.k === k);
        return `${esc(c ? (lang() === 'ms' ? c.label[1] : c.label[0]) : k)}: ${p.before?.[k] == null ? '—' : esc(fmtv(c, p.before[k]))} → <b>${esc(fmtv(c, v))}</b>`; }).join(' · ')}</div>
      <div class="small muted">“${esc(p.justification)}”</div>
      <div class="tiny dim">${tt('Proposed by', 'Dicadang oleh')} ${esc(p.actor)} · ${dtime(p.at)}${p.reviewed_by ? ` · ${tt('reviewed by', 'disemak oleh')} ${esc(p.reviewed_by)} ${dtime(p.reviewed_at)}` : ''}
        ${p.status === 'Pending Board approval' && p.actor_username === state.user.username ? ` · ${tt('awaiting a second Board member', 'menunggu ahli Lembaga kedua')}` : ''}</div></div>`).join('')}
  </div></div>`;
}

function bindProposals(el) {
  $$('[data-rv]', el).forEach(b => b.onclick = async () => {
    try {
      const r = await api('/sandbox/proposals/' + b.dataset.rv, { method: 'POST', body: { approve: b.dataset.ok === '1' } });
      toast(r.status, r.policy_version ? `${tt('Now in force as', 'Kini berkuat kuasa sebagai')} ${r.policy_version}` : '', b.dataset.ok === '1' ? 'good' : 'warn');
      await refreshMeta(); render();
    } catch (e) { toast(tt('Not recorded', 'Tidak direkod'), e.message, 'bad'); }
  });
}

// --------------------------------------------------------- autonomy dial
function renderAutonomy(host, a) {
  const modes = a.modes;
  const board = state.user.role === 'board';
  const ms = lang() === 'ms';
  const desc = ms ? ['Sistem memerhati sahaja; tiada output kepada pegawai.', 'Sistem menasihati; pegawai melihat cadangan.',
    'Sistem membantu menyediakan draf dan bukti; pegawai bertindak.', 'Sistem boleh menyediakan tindakan untuk kelulusan satu klik.',
    'Sistem boleh melaksana dalam had yang ditetapkan Lembaga.'] : ['System observes only; no output reaches the officer.',
    'System advises; the officer sees the recommendation.', 'System assists with drafting and evidence; the officer acts.',
    'System may prepare an action for one-click human approval.', 'System may execute inside the Board-set limits.'];
  host.innerHTML = `<div class="card-h">${icon('power', 15)}<h3>${tt('Autonomy Dial', 'Dail Autonomi')}</h3>
      <span class="sub">${board ? tt('Board-controlled', 'dikawal Lembaga') : tt('read-only — Board-controlled', 'baca sahaja — dikawal Lembaga')}</span><div class="spacer"></div>
      ${tag(a.kill_switch ? 'STOPPED' : a.mode, a.kill_switch ? 'red' : 'purple')}</div>
    <div class="card-b col" style="gap:12px">
      <div class="col" style="gap:5px">
        ${modes.map((m, i) => `<button class="field-row ${a.mode === m ? 'on' : ''}" data-mode="${m}" ${board ? '' : 'disabled'}>
          <span class="k" style="text-align:left;color:var(--ink-2)"><b>${m.replace(/_/g, ' ')}</b><div class="tiny dim">${desc[i]}</div></span>
          ${a.mode === m ? tag('active', 'purple') : ''}</button>`).join('')}
      </div>
      <div class="sep"></div>
      <div class="up">${tt('Limits on autonomous execution', 'Had pelaksanaan autonomi')}</div>
      <dl class="kv">
        <dt>${tt('Maximum amount', 'Amaun maksimum')}</dt><dd>${money(a.limits.max_amount)}</dd>
        <dt>${tt('Maximum probability of default', 'Kebarangkalian mungkir maksimum')}</dt><dd>${pct(a.limits.max_pd, 1)}</dd>
        <dt>${tt('Minimum confidence', 'Keyakinan minimum')}</dt><dd>${a.limits.min_confidence}</dd>
        <dt>${tt('Maximum disagreement', 'Percanggahan maksimum')}</dt><dd>${a.limits.max_disagreement}</dd>
        <dt>${t('Product')}</dt><dd class="small">${a.limits.products.map(PNAME).map(esc).join(', ')}</dd>
        <dt>${tt('Evidence must be complete', 'Bukti mesti lengkap')}</dt><dd>${a.limits.require_complete_docs ? tt('Yes', 'Ya') : tt('No', 'Tidak')}</dd>
      </dl>
      <div class="tiny dim">${esc(a.approved_by)} · ${tt('last changed', 'kali terakhir diubah')} ${dtime(a.changed_at)}${a.changed_by ? ' · ' + esc(a.changed_by) : ''}</div>
      <div class="sep"></div>
      <div class="row" style="gap:10px;padding:10px;border:1px solid ${a.kill_switch ? 'var(--red-line)' : 'var(--line)'};
        border-radius:10px;background:${a.kill_switch ? 'var(--red-dim)' : 'transparent'}">
        ${icon('power', 18)}
        <div style="flex:1"><b style="font-size:12.5px">${tt('Stop autonomous actions', 'Hentikan tindakan autonomi')}</b>
          <div class="tiny dim">${tt('Recommendations, policy and models keep running. Every action routes to a person.', 'Cadangan, dasar dan model terus berjalan. Setiap tindakan kepada manusia.')}</div></div>
        <button class="switch danger ${a.kill_switch ? 'on' : ''}" id="kill" ${board ? '' : 'disabled'} aria-label="Kill switch"><i></i></button>
      </div>
    </div>`;
  if (!board) return;
  host.querySelectorAll('[data-mode]').forEach(b => b.onclick = async () => {
    const r = await api('/governance/autonomy', { method: 'POST', body: { mode: b.dataset.mode } });
    toast(tt('Autonomy mode set', 'Mod autonomi ditetapkan'), b.dataset.mode.replace(/_/g, ' '), 'warn');
    renderAutonomy(host, r); await refreshMeta();
  });
  host.querySelector('#kill').onclick = async () => {
    const r = await api('/governance/autonomy', { method: 'POST', body: { kill_switch: !a.kill_switch } });
    toast(r.kill_switch ? tt('Autonomous execution stopped', 'Pelaksanaan autonomi dihentikan') : tt('Autonomous execution resumed', 'Pelaksanaan autonomi disambung'),
      tt('Change sealed to the ledger.', 'Perubahan direkod dalam lejar.'), r.kill_switch ? 'bad' : 'good');
    await refreshMeta(); render();
  };
}

// ========================================================== GOVERNANCE
export async function governance(el) {
  const g = await api('/governance');
  el.innerHTML = `
  <div class="page-head"><div><h1>${tt('Model & AI Governance', 'Tadbir Urus Model & AI')}</h1>
    <p>${tt('Model health, grounding discipline, override behaviour and fairness — the evidence that the platform behaves the way the Board approved.',
            'Kesihatan model, disiplin pembuktian, tingkah laku pembatalan dan keadilan — bukti platform berkelakuan seperti yang diluluskan Lembaga.')}</p></div>
    <div class="spacer"></div><span class="tag t-gold">${tt('Policy', 'Dasar')} ${esc(g.policy_version)}</span></div>

  <div class="grid g4" style="margin-bottom:14px">
    ${kpi(tt('Council runs', 'Larian Majlis'), g.council_runs, `${tt('avg confidence', 'purata keyakinan')} ${g.avg_confidence}`)}
    ${kpi(tt('Officer overrides', 'Pembatalan pegawai'), `${g.overrides}`, `${g.override_rate}% ${tt('of', 'daripada')} ${g.decisions} ${tt('decisions', 'keputusan')}`, g.override_rate > 30 ? 'accent-amber' : '')}
    ${kpi(tt('Grounding interventions', 'Campur tangan pembuktian'), (g.grounding.unsupported_citations || 0) + (g.grounding.numeric_rewrites || 0),
      `${g.grounding.numeric_rewrites || 0} ${tt('figure rewrites', 'tulis semula angka')} · ${g.grounding.llm_positions}/${g.grounding.total_positions} ${tt('model-authored', 'oleh model')}`, 'accent-amber')}
    ${kpi(tt('Ledger integrity', 'Integriti lejar'), g.ledger.intact ? tt('Intact', 'Utuh') : 'BROKEN', `${g.ledger.records} ${tt('hash-chained records', 'rekod berantai hash')}`, g.ledger.intact ? 'accent-green' : 'accent-red')}
  </div>

  <div class="card" style="margin-bottom:14px"><div class="card-h"><h3>${tt('Model registry & health', 'Daftar & kesihatan model')}</h3></div><div class="tw"><table>
    <thead><tr><th>${tt('Model', 'Model')}</th><th>${tt('Version', 'Versi')}</th><th>${t('Status')}</th><th>${tt('Calibration', 'Kalibrasi')}</th><th>${tt('Drift', 'Hanyutan')}</th><th>${tt('Note', 'Nota')}</th></tr></thead>
    <tbody>${g.models.map(m => `<tr><td style="font-weight:560">${esc(m.name)}</td>
      <td class="mono tiny">${esc(m.version)}</td><td>${tag(m.status, m.status === 'Healthy' ? 'green' : 'blue')}</td>
      <td class="small">${esc(m.calibration)}</td>
      <td style="width:110px">${m.drift != null ? `<div class="meter"><div class="bar thin"><i style="width:${m.drift * 400}%;background:${m.drift > .1 ? 'var(--red)' : 'var(--green)'}"></i></div>
        <span class="mono tiny">${m.drift}</span></div>` : '<span class="dim">—</span>'}</td>
      <td class="small muted">${esc(m.note)}</td></tr>`).join('')}</tbody></table></div></div>

  <div class="grid g-2-1" style="margin-bottom:14px">
    <div class="card sens"><div class="card-h">${icon('alert', 15)}<h3>${tt('Model card — financial distress (possible bankruptcy)', 'Kad model — tekanan kewangan (kemungkinan bankrap)')}</h3></div>
      <div class="card-b grid g2" style="align-items:start">
        <div class="col" style="gap:8px"><div class="small">${esc(g.distress_card.context.headline)}</div>
          <dl class="kv"><dt>${tt('Training cohort', 'Kohort latihan')}</dt><dd>${num(g.distress_card.trained_on)} (${g.distress_card.positives} ${tt('cases', 'kes')})</dd>
            <dt>${tt('Calibrated base rate', 'Kadar asas dikalibrasi')}</dt><dd>${(g.distress_card.base_rate * 100).toFixed(2)}%</dd></dl>
          <div class="up">${tt('Features', 'Ciri')}</div><div class="row wrap" style="gap:5px">${g.distress_card.features.map(f => `<span class="tag t-grey">${esc(f)}</span>`).join('')}</div></div>
        <div class="col" style="gap:6px"><div class="up">${tt('Guardrails', 'Kawalan')}</div>
          <ul class="small" style="padding-left:16px;line-height:1.7">${g.distress_card.guardrails.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
          <div class="tiny dim">${g.distress_card.context.sources.map(esc).join('<br/>')}</div></div>
      </div></div>
    <div class="card"><div class="card-h"><h3>${tt('Fairness monitoring', 'Pemantauan keadilan')}</h3><span class="sub">${tt('policy pass rate by segment, live queue', 'kadar lulus dasar mengikut segmen')}</span></div>
      <div class="card-b col" style="gap:9px">
        ${g.fairness.map(f => `<div>
          <div class="row small"><span style="flex:1">${esc(f.segment)} <span class="dim">n=${f.n}</span></span>
            <b class="num">${f.approval}%</b>
            <span class="tag t-${f.flag ? 'amber' : 'grey'}">${f.delta > 0 ? '+' : ''}${f.delta}</span></div>
          <div class="bar thin" style="margin-top:4px"><i style="width:${f.approval}%;background:${f.flag ? 'var(--amber)' : 'var(--brand)'}"></i></div></div>`).join('')}
        <div class="tiny dim">${tt('Flagged segments are surfaced for human review; the platform does not act on them.', 'Segmen yang ditanda dipaparkan untuk semakan manusia; platform tidak bertindak ke atasnya.')}</div>
      </div></div>
  </div>

  <div class="grid g2">
    <div class="card"><div class="card-h"><h3>${tt('Override analytics', 'Analitik pembatalan')}</h3></div>
      ${g.override_detail.length ? `<div class="tw"><table><thead><tr><th>${tt('Case', 'Kes')}</th><th>AI</th><th>${tt('Officer', 'Pegawai')}</th>
        <th>${tt('Reason', 'Sebab')}</th><th>${tt('By', 'Oleh')}</th></tr></thead><tbody>
        ${g.override_detail.map(o => `<tr><td class="mono tiny">${esc(o.case)}</td>
          <td>${tag(o.ai_recommendation)}</td><td>${tag(o.action)}</td>
          <td class="small muted">${esc(o.reason)}</td><td class="small">${esc(o.actor)}</td></tr>`).join('')}
        </tbody></table></div>` : `<div class="card-b empty small">${tt('No overrides recorded yet.', 'Belum ada pembatalan direkod.')}</div>`}
      <div id="props2" class="card-b">${proposals(g.policy_changes)}</div></div>
    <div class="card" id="autonomyCard2"></div>
  </div>`;
  renderAutonomy($('#autonomyCard2', el), g.autonomy);
  bindProposals(el);
}

const kpi = (l, v, sub, accent = '') => `<div class="kpi ${accent}"><div class="lbl">${l}</div>
  <div class="val">${v}</div><div class="sub">${sub}</div></div>`;

// ============================================================== LEDGER
// Every record keeps its exact machine payload (that is what makes the chain auditable); this view
// renders it for people, and the raw JSON is one click away for auditors.
function readable(stage, p) {
  if (!p || typeof p !== 'object') return '';
  const kv = rows => `<dl class="kv">${rows.filter(Boolean).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join('')}</dl>`;
  const lim = l => l ? `${tt('max', 'maks')} ${money(l.max_amount)} · PD ≤ ${pct(l.max_pd, 1)} · ${tt('confidence', 'keyakinan')} ≥ ${l.min_confidence} · ${tt('disagreement', 'percanggahan')} ≤ ${l.max_disagreement} · ${(l.products || []).map(PNAME).map(esc).join(', ')}` : '—';
  if (stage === 'Autonomy Change') {
    const b = p.before || {};
    return kv([[tt('Mode', 'Mod'), b.mode && b.mode !== p.mode ? `${esc(b.mode)} → <b>${esc(p.mode)}</b>` : `<b>${esc(p.mode)}</b>`],
      [tt('Kill switch', 'Suis henti'), p.kill_switch ? tag('ENGAGED', 'red') : tag('off', 'green')],
      [tt('Limits', 'Had'), lim(p.limits)], [tt('Authority', 'Kuasa'), esc(p.approved_by || '')], [tt('Changed by', 'Diubah oleh'), esc(p.changed_by || '')]]);
  }
  if (stage.startsWith('Policy Change')) {
    return `<div class="tw"><table><thead><tr><th>${tt('Control', 'Kawalan')}</th><th class="r">${tt('Before', 'Sebelum')}</th><th class="r">${tt('After', 'Selepas')}</th></tr></thead><tbody>
      ${Object.entries(p.thresholds || {}).map(([k, v]) => { const c = CONTROLS.find(x => x.k === k);
        return `<tr><td>${esc(c ? (lang() === 'ms' ? c.label[1] : c.label[0]) : k)}</td><td class="r">${p.before?.[k] == null ? '—' : esc(c ? fmtv(c, p.before[k]) : p.before[k])}</td>
          <td class="r"><b>${esc(c ? fmtv(c, v) : v)}</b></td></tr>`; }).join('')}</tbody></table></div>` +
      kv([[t('Status'), esc(p.status)], [tt('Proposed by', 'Dicadang oleh'), esc(p.actor || '')], [tt('Justification', 'Justifikasi'), esc(p.justification || '')],
          p.reviewed_by ? [tt('Reviewed by', 'Disemak oleh'), `${esc(p.reviewed_by)} — ${esc(p.review_note || '')}`] : null,
          p.policy_version ? [tt('Policy version', 'Versi dasar'), esc(p.policy_version)] : null]);
  }
  if (stage === 'Agent Deliberation') {
    return `<div class="col" style="gap:6px">${(p.positions || []).map(x => `<div class="row small" style="gap:8px">${tag(x.stance)}
      <b style="min-width:180px">${esc(x.name)}</b><span class="muted" style="flex:1">${esc(x.headline)}</span><span class="mono dim">${x.confidence}</span></div>`).join('')}
      ${p.challenger ? `<div class="note purple small"><b>Challenger — ${esc(p.challenger.stance)}</b> ${esc(p.challenger.headline)}<div class="tiny">${esc(p.challenger.ask || '')}</div></div>` : ''}</div>`;
  }
  if (stage === 'Recommendation Synthesized') {
    return kv([[tt('Recommendation', 'Cadangan'), tag(p.recommendation)], [tt('Confidence', 'Keyakinan'), p.confidence], [tt('Disagreement', 'Percanggahan'), p.disagreement],
      [tt('Rationale', 'Rasional'), esc(p.rationale)], [tt('Decisive factor', 'Faktor penentu'), esc(p.decisive_factor)],
      [tt('Conditions', 'Syarat'), (p.conditions || []).map(esc).join('<br/>') || '—']]);
  }
  if (stage === 'Human Decision') {
    return kv([[tt('Decision', 'Keputusan'), tag(p.action)], [tt('By', 'Oleh'), `${esc(p.actor)} (${esc(p.role)})`], [tt('AI recommended', 'AI mencadangkan'), esc(p.ai_recommendation)],
      [tt('Override', 'Pembatalan'), p.override ? tag('yes', 'purple') : tt('no', 'tidak')], [tt('Reason', 'Sebab'), esc(p.reason || '—')],
      [tt('Authority', 'Kuasa'), esc(p.authority)], [tt('Snapshot', 'Snapshot'), `<span class="mono tiny">${esc(p.snapshot)}</span>`]]);
  }
  if (stage === 'Core Execution') return kv([[tt('Facility', 'Kemudahan'), esc(p.account)], [tt('Instalment', 'Ansuran'), money(p.instalment, 2)],
    [tt('First due', 'Tarikh pertama'), date(p.first_due)], [tt('Channel', 'Saluran'), esc(p.channel || '')]]);
  if (stage === 'Application Received') return kv(p.application && typeof p.application === 'object'
    ? [[t('Product'), esc(PNAME(p.application.product))], [t('Amount'), money(p.application.amount)], [t('Tenure'), `${p.application.term} ${t('months')}`], [tt('Channel', 'Saluran'), esc(p.application.channel)]]
    : [[tt('Application', 'Permohonan'), esc(p.application)], [tt('Member', 'Ahli'), esc(p.member)], [t('Amount'), money(p.amount)]]);
  if (stage === 'Policy Evaluation' && Array.isArray(p.gates)) return gatesTable(p.gates) + (p.max_financing != null ? kv([[tt('Maximum supportable', 'Maksimum disokong'), money(p.max_financing)]]) : '');
  if (stage === 'Sensitive Access') return kv([[tt('Member', 'Ahli'), esc(p.member || '—')], [tt('Viewed', 'Dilihat'), esc(p.view || 'cross-selling list')]]);
  if (stage.includes('Signal Detected')) return kv([[tt('Member', 'Ahli'), esc(p.member)], [tt('Message', 'Mesej'), esc(p.detail)], [tt('Queue', 'Baris gilir'), esc(p.queue)], ['SLA', esc(p.sla)]]);
  if (stage === 'Affordability Self-Check') return kv([[t('Product'), esc(PNAME(p.product))], [t('Amount'), money(p.amount)], [t('Tenure'), `${p.term} ${t('months')}`],
    [tt('Indicative maximum', 'Anggaran maksimum'), money(p.max_financing)], [tt('Binding limit', 'Had pengikat'), esc(p.binding)]]);
  const flat = Object.entries(p).filter(([, v]) => v == null || typeof v !== 'object').slice(0, 10);
  return flat.length ? kv(flat.map(([k, v]) => [k.replace(/_/g, ' '), esc(v)])) : '';
}

const gatesTable = gates => `<div class="col" style="gap:3px">${gates.map(g => `<div class="row small" style="gap:8px">
  <span class="tag t-${g.passed ? 'green' : g.hard ? 'red' : 'amber'}">${icon(g.passed ? 'check' : 'x', 10)}</span>
  <span style="flex:1">${esc(g.name)} <span class="tiny dim">${esc(g.id)} · ${esc(g.required)}</span></span><span class="mono tiny">${esc(g.actual)}</span></div>`).join('')}</div>`;

export async function ledger(el, param) {
  const { rows, verification } = await api('/ledger' + (param ? '?case_id=' + encodeURIComponent(param) : ''));
  el.innerHTML = `
  <div class="page-head"><div><h1>${t('Decision Ledger')}</h1>
    <p>${tt('Append-only and hash-chained: every decision, policy change, AI deliberation and sensitive access is recorded with the exact data used at that moment, so it can be re-verified independently. Records are shown in plain language; the technical record is one click away.',
            'Hanya tambah dan berantai hash: setiap keputusan, perubahan dasar, pertimbangan AI dan akses sensitif direkod dengan data tepat pada masa itu. Rekod dipaparkan dalam bahasa biasa; rekod teknikal hanya satu klik.')}</p></div>
    <div class="spacer"></div>
    ${tag(verification.intact ? tt('Chain intact', 'Rantaian utuh') : 'Chain broken', verification.intact ? 'green' : 'red')}
    <span class="tag t-grey">${verification.records} ${tt('records', 'rekod')}</span>
    ${param ? `<button class="btn sm" id="clear">${tt('Show all', 'Tunjuk semua')}</button>` : ''}</div>

  <div class="card" style="margin-bottom:14px"><div class="card-b row wrap" style="gap:8px">
    <span class="up">${tt('Reconstruct a case', 'Bina semula kes')}</span>
    <input class="inp" id="cid" placeholder="APP-104310" value="${esc(param && param.startsWith('APP') ? param : '')}" style="max-width:200px"/>
    <button class="btn primary sm" id="rec">${icon('layers', 12)} ${tt('Reconstruct', 'Bina semula')}</button>
    <div class="spacer" style="flex:1"></div>
    <span class="tiny dim mono">head ${esc(String(verification.head).slice(0, 28))}…</span></div></div>

  <div class="card"><div class="tw"><table>
    <thead><tr><th>#</th><th>${tt('Time (MYT)', 'Masa (MYT)')}</th><th>${tt('Case', 'Kes')}</th><th>${tt('Stage', 'Peringkat')}</th><th>${tt('Actor', 'Pelaku')}</th><th>${tt('Summary', 'Ringkasan')}</th><th>Hash</th></tr></thead>
    <tbody>${rows.map(r => `<tr class="clickable" data-seq="${r.seq}"><td class="mono tiny dim">${r.seq}</td>
      <td class="small">${dtime(r.at)}</td><td class="mono tiny">${esc(r.case_id)}</td>
      <td><span class="tag t-${stageTone(r.stage)}">${esc(r.stage)}</span></td>
      <td class="small">${esc(r.actor)}</td><td class="small muted">${esc(r.summary)}</td>
      <td class="mono tiny dim">${esc(String(r.hash).slice(0, 12))}…</td></tr>`).join('')}</tbody></table></div></div>`;

  $('#rec', el).onclick = () => reconstruct($('#cid', el).value.trim());
  $('#clear', el) && ($('#clear', el).onclick = () => window.go('ledger'));
  $$('[data-seq]', el).forEach(r => r.onclick = () => {
    const rec = rows.find(x => x.seq == r.dataset.seq);
    const prev = rows.find(x => x.seq === rec.seq - 1);
    drawer(`<h3>${tt('Ledger record', 'Rekod lejar')} #${rec.seq}</h3>`, `<div class="col" style="gap:12px">
      <dl class="kv"><dt>${tt('Time', 'Masa')}</dt><dd>${dtime(rec.at)} MYT</dd><dt>${tt('Case', 'Kes')}</dt><dd class="mono">${esc(rec.case_id)}</dd>
        <dt>${tt('Stage', 'Peringkat')}</dt><dd>${esc(rec.stage)}</dd><dt>${tt('Actor', 'Pelaku')}</dt><dd>${esc(rec.actor)}</dd></dl>
      <div class="note">${esc(rec.summary)}</div>
      <div class="up">${tt('What was recorded', 'Apa yang direkod')}</div>
      ${readable(rec.stage, rec.payload) || `<div class="small dim">${tt('No structured detail.', 'Tiada butiran berstruktur.')}</div>`}
      <div class="up">${tt('Chain', 'Rantaian')}</div>
      <div class="row small" style="gap:8px">${tag(verification.intact ? tt('verified', 'disahkan') : 'broken', verification.intact ? 'green' : 'red')}
        <span class="mono tiny">#${rec.seq} ← #${rec.seq - 1}</span>${prev && prev.hash === rec.prev_hash ? icon('check', 12) : ''}</div>
      <div class="small mono dim" style="word-break:break-all">prev ${esc(rec.prev_hash)}</div>
      <div class="small mono" style="word-break:break-all">this ${esc(rec.hash)}</div>
      <details><summary class="small linkish">${tt('Show technical record (JSON, for auditors)', 'Tunjuk rekod teknikal (JSON, untuk juruaudit)')}</summary>
        <pre class="mono" style="background:var(--bg-2);padding:12px;border-radius:9px;border:1px solid var(--line);overflow:auto;max-height:360px;margin-top:8px">${esc(JSON.stringify(rec.payload, null, 2))}</pre></details>
    </div>`, { wide: true });
  });
}

const stageTone = s => s.includes('Human') ? 'purple' : s.includes('Execution') || s.includes('Token') ? 'green'
  : s.includes('Autonomy') || s.includes('Policy Change') ? 'amber' : s.includes('Sensitive') ? 'gold'
  : s.includes('Hardship') || s.includes('Complaint') ? 'red' : 'grey';

function stepBody(s) {
  const d = s.detail;
  if (d == null) return `<div class="small dim">${tt('Not reached yet.', 'Belum sampai.')}</div>`;
  const kv = o => `<dl class="kv">${Object.entries(o).filter(([, v]) => v == null || typeof v !== 'object').map(([k, v]) => `<dt>${esc(k.replace(/_/g, ' '))}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`;
  if (s.kind === 'gates') return gatesTable(d);
  if (s.kind === 'documents') return `<div class="col" style="gap:3px">${d.map(x => `<div class="row small" style="gap:8px">${tag(x.status)}<span style="flex:1">${esc(x.type)} <span class="mono tiny dim">${esc(x.id)}</span></span><span class="mono tiny dim">${esc(x.hash)}</span></div>`).join('')}</div>`;
  if (s.kind === 'positions') return readable('Agent Deliberation', { positions: d });
  if (s.kind === 'summary') return readable('Recommendation Synthesized', d);
  if (s.kind === 'decision') return readable('Human Decision', d);
  if (s.kind === 'models') return kv({ 'probability of default': pct(d.risk.pd, 1), grade: d.risk.grade, score: d.risk.score, 'risk model': d.risk.model_version, 'integrity level': d.fraud.level, 'integrity score': d.fraud.score })
    + `<ul class="small" style="padding-left:16px">${(d.risk.reason_codes || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul>`;
  if (s.kind === 'routing') return kv({ path: d.path, mode: d.mode }) + `<ul class="small" style="padding-left:16px">${(d.reasons || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul>`;
  if (s.kind === 'challenger') return `<div class="small"><b>${esc(d.stance)}</b> — ${esc(d.headline)}</div><div class="tiny dim">${esc(d.ask || '')}</div>`;
  if (s.kind === 'execution') return readable('Core Execution', d);
  return Array.isArray(d) ? `<div class="small">${d.length} items</div>` : kv(d);
}

async function reconstruct(aid) {
  if (!aid) return toast(tt('Enter a case id', 'Masukkan ID kes'), '', 'warn');
  let r; try { r = await api('/ledger/reconstruct/' + encodeURIComponent(aid)); }
  catch (e) { return toast(tt('Not found', 'Tidak ditemui'), e.message, 'bad'); }
  drawer(`<h3>${tt('Reconstruction', 'Pembinaan semula')} — <span class="mono">${esc(aid)}</span></h3>`, `
    <div class="col" style="gap:10px">
      <div class="note ${r.verification.intact ? 'green' : 'red'}">
        <b>${tt('Hash chain', 'Rantaian hash')} ${r.verification.intact ? tt('verified', 'disahkan') : 'BROKEN'}</b>
        <div class="small">${r.verification.records} ${tt('records in the ledger.', 'rekod dalam lejar.')}</div></div>
      ${r.steps.map(s => `<div class="card"><div class="card-h">
        <span class="tag t-blue">${s.n}</span><h3>${esc(s.title)}</h3>
        <div class="spacer"></div><span class="small muted">${esc(String(s.summary))}</span></div>
        <div class="card-b">${stepBody(s)}
          <details style="margin-top:6px"><summary class="tiny linkish">${tt('technical record', 'rekod teknikal')}</summary>
          <pre class="mono" style="overflow:auto;max-height:220px;color:var(--ink-2);margin-top:6px">${esc(JSON.stringify(s.detail, null, 2) || 'null')}</pre></details></div></div>`).join('')}
    </div>`, { wide: true });
}

// ============================================================= COCKPIT
export async function cockpit(el) {
  const c = await api('/cockpit');
  const p = c.portfolio, k = p.kpis, g = c.governance, dsx = c.distress;
  const ms = lang() === 'ms';
  el.innerHTML = `
  <div class="page-head"><div><h1>${t('Management Cockpit')}</h1>
    <p>${tt('The institution rather than the individual case — volume, exposure, risk, recovery, member financial health and AI behaviour.',
            'Institusi, bukan kes individu — jumlah, pendedahan, risiko, pemulihan, kesihatan kewangan ahli dan tingkah laku AI.')}</p></div>
    <div class="spacer"></div><button class="btn" id="ask">${icon('msg')} ${tt('Ask the cockpit', 'Tanya kokpit')}</button></div>

  <div class="grid g5" style="margin-bottom:14px">
    ${kpi(tt('Live applications', 'Permohonan aktif'), k.pipeline, `${k.decided} ${tt('decided', 'diputuskan')} · ${k.applications_today} ${tt('today', 'hari ini')}`, 'accent')}
    ${kpi(tt('Financing requested', 'Pembiayaan dipohon'), money(k.exposure), tt('across live cases', 'merentasi kes aktif'))}
    ${kpi(tt('Predicted delinquency', 'Jangkaan tunggakan'), k.predicted_delinquency + '%', tt('exposure-weighted', 'berwajaran pendedahan'), 'accent-amber')}
    ${kpi(tt('Collections at risk', 'Kutipan berisiko'), money(c.collections.balance), `${c.collections.cases} ${tt('cases', 'kes')}`, 'accent-red')}
    ${kpi(tt('Expected recovery', 'Jangkaan pemulihan'), money(c.collections.expected), tt('modelled', 'dimodelkan'), 'accent-green')}
  </div>

  <div class="grid g-2-1" style="margin-bottom:14px">
    <div class="card"><div class="card-h"><h3>${tt('Volume and outcome trend', 'Trend jumlah dan keputusan')}</h3><span class="sub">${tt('last 16 days · hover for values · click the legend to hide a line', '16 hari lalu · halakan untuk nilai · klik petunjuk untuk sembunyi garisan')}</span></div>
      <div class="card-b">${lineChart(p.trend, { keys: ['a', 'ap', 'de'], labels: [tt('Applications received', 'Permohonan diterima'), tt('Approved', 'Diluluskan'), tt('Declined', 'Ditolak')],
        colors: ['var(--info)', 'var(--green)', 'var(--red)'], h: 210 })}</div></div>
    <div class="card"><div class="card-h"><h3>${tt('AI behaviour', 'Tingkah laku AI')}</h3></div><div class="card-b col" style="gap:10px">
      <dl class="kv">
        <dt>${tt('Council runs', 'Larian Majlis')}</dt><dd>${g.council_runs}</dd>
        <dt>${tt('Average confidence', 'Purata keyakinan')}</dt><dd>${g.avg_confidence}</dd>
        <dt>${tt('Average disagreement', 'Purata percanggahan')}</dt><dd>${g.avg_disagreement}</dd>
        <dt>${tt('Override rate', 'Kadar pembatalan')}</dt><dd>${g.override_rate}%</dd>
        <dt>${tt('Unsupported claims', 'Dakwaan tanpa sokongan')}</dt><dd>${g.grounding.unsupported_citations}</dd>
        <dt>${tt('Autonomy mode', 'Mod autonomi')}</dt><dd>${esc(g.autonomy.mode)}</dd>
        <dt>${tt('Kill switch', 'Suis henti')}</dt><dd>${g.autonomy.kill_switch ? tag('ENGAGED', 'red') : tag('off', 'green')}</dd>
        <dt>${tt('Policy version', 'Versi dasar')}</dt><dd>${esc(g.policy_version)}</dd>
      </dl></div></div>
  </div>

  <div class="grid g2" style="margin-bottom:14px">
    <div class="card sens"><div class="card-h">${icon('alert', 15)}<h3>${tt('Member financial-distress outlook', 'Tinjauan tekanan kewangan ahli')}</h3>
      <span class="sub">${tt('aggregates only — no names at Board level', 'agregat sahaja — tiada nama di peringkat Lembaga')}</span></div>
      <div class="card-b grid g2" style="align-items:center">
        <div class="row" style="gap:16px">${donut(Object.entries(dsx.bands).map(([kk, v]) => ({ k: kk, v })),
          { colors: { Low: 'var(--green)', Watch: 'var(--amber)', Elevated: 'var(--amber-2)', High: 'var(--red)' } })}
          <div class="col" style="gap:5px">${Object.entries(dsx.bands).map(([kk, v]) => `<div class="row small"><i class="sw" style="background:var(--${{ Low: 'green', Watch: 'amber', Elevated: 'amber-2', High: 'red' }[kk]})"></i>
            <span style="flex:1;min-width:70px">${esc(ms ? { Low: 'Rendah', Watch: 'Pantau', Elevated: 'Meningkat', High: 'Tinggi' }[kk] : kk)}</span><b>${v}</b></div>`).join('')}</div></div>
        <div class="col" style="gap:6px"><div class="small">${tt('Expected cases in 12 months', 'Jangkaan kes dalam 12 bulan')}: <b>${dsx.expected_cases_12m}</b> ${tt('of', 'daripada')} ${dsx.members} ${tt('members', 'ahli')}</div>
          <div class="tiny dim">${esc(dsx.context.headline)}</div>
          <div class="tw"><table><thead><tr><th>${t('Branch')}</th><th class="r">${tt('Watch', 'Pantau')}</th><th class="r">${tt('Elevated', 'Meningkat')}</th><th class="r">${tt('High', 'Tinggi')}</th></tr></thead>
            <tbody>${Object.entries(dsx.by_branch).map(([b, v]) => `<tr><td class="small">${esc(b)}</td><td class="r num">${v.Watch}</td><td class="r num">${v.Elevated}</td><td class="r num">${v.High}</td></tr>`).join('')}</tbody></table></div></div>
      </div></div>
    <div class="card"><div class="card-h"><h3>${tt('Growth opportunities', 'Peluang pertumbuhan')}</h3><span class="sub">${t('Cross-selling options')}</span></div>
      <div class="card-b">${barChart(Object.entries(c.crosssell).map(([kk, v]) => ({ l: ({ 'Potential takaful offer': 'Takaful', 'Potential financing offer': tt('Financing', 'Pembiayaan'),
        'Retention intervention': tt('Retention', 'Pengekalan'), 'Education financing': tt('Fees', 'Yuran'), 'Retirement planning': tt('Pre-retirement', 'Pra-persaraan'),
        'Short-term liquidity': 'Ar-Rahnu' })[kk] || kk, v, note: kk })), { h: 160, color: 'var(--gold)' })}</div></div>
  </div>

  <div class="grid g2" style="margin-bottom:14px">
    ${breakdownChart(tt('By branch', 'Mengikut cawangan'), c.branches)}
    ${breakdownChart(tt('By service', 'Mengikut perkhidmatan'), c.services)}
  </div>
  <div class="grid g3">
    ${breakdown(tt('By product', 'Mengikut produk'), c.products, PNAME)}
    ${breakdown(tt('By branch', 'Mengikut cawangan'), c.branches)}
    ${breakdown(tt('By officer', 'Mengikut pegawai'), c.officers)}
  </div>`;
  $('#ask', el).onclick = () => askDrawer(null, tt('Portfolio', 'Portfolio'));
}

const breakdownChart = (title, obj) => `<div class="card"><div class="card-h"><h3>${title}</h3><span class="sub">${tt('financing requested · hover a bar', 'pembiayaan dipohon · halakan bar')}</span></div>
  <div class="card-b">${barChart(Object.entries(obj).sort((a, b) => b[1].amount - a[1].amount).map(([kk, v]) => ({ l: kk, v: v.amount, note: `${v.count} ${tt('cases', 'kes')} · PD ${v.pd}%` })), { h: 170, unit: 'RM' })}</div></div>`;

const breakdown = (title, obj, nm = x => x) => `<div class="card"><div class="card-h"><h3>${title}</h3></div>
  <div class="tw"><table><thead><tr><th>${tt('Segment', 'Segmen')}</th><th class="r">${tt('Cases', 'Kes')}</th><th class="r">${t('Amount')}</th><th class="r">PD</th></tr></thead>
  <tbody>${Object.entries(obj).sort((a, b) => b[1].amount - a[1].amount).map(([kk, v]) =>
    `<tr><td class="small">${esc(nm(kk))}</td><td class="r num">${v.count}</td>
     <td class="r num">${money(v.amount)}</td><td class="r num">${v.pd}%</td></tr>`).join('')}
  </tbody></table></div></div>`;
