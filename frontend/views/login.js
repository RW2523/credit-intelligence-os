import { api, icon, esc, $, $$ } from '/lib.js';
import { t, tt, lang, setLang } from '/i18n.js';
import { mark } from '/brand.js';

export async function login(root, onDone) {
  let demo = { demo: false, accounts: [] };
  try { demo = await api('/auth/demo'); } catch (e) { /* offline */ }
  let mode = 'staff';

  const draw = () => {
    root.className = 'login';
    root.innerHTML = `
    <section class="login-hero">
      <div class="row" style="gap:12px"><div style="width:46px;height:46px">${mark('lg')}</div>
        <div><b style="font-size:15px">Koperasi Tentera</b><div style="font-size:11.5px;color:#b9d1c4">${esc(demo.institution || '')}</div></div></div>
      <span class="pill">${icon('shield', 12)} KT Credit Intelligence</span>
      <h1>${tt('Credit intelligence for Koperasi Tentera', 'Kecerdasan kredit untuk Koperasi Tentera')}</h1>
      <p>${tt('One platform for Islamic financing origination, member servicing, early warning, collections and governance — for Armed Forces personnel, MINDEF civil servants and veterans.',
              'Satu platform untuk permohonan pembiayaan Islam, servis ahli, amaran awal, kutipan dan tadbir urus — untuk anggota ATM, kakitangan awam MINDEF dan pesara.')}</p>
      <div class="login-feats">
        <div><b>${tt('Islamic financing', 'Pembiayaan Islam')}</b>${tt('Personal, Express, Fees, SME, Term and Contract Financing-i, Takaful and Ar-Rahnu.', 'Pembiayaan Peribadi, Ekspres, Yuran, PKS, Berjangka dan Kontrak-i, Takaful dan Ar-Rahnu.')}</div>
        <div><b>${tt('Salary deduction aware', 'Peka potongan gaji')}</b>${tt('Biro ANGKASA deductions and the 60%-of-gross rule in every affordability check.', 'Potongan Biro ANGKASA dan peraturan 60% gaji kasar dalam setiap semakan kemampuan.')}</div>
        <div><b>${tt('Grounded AI', 'AI berasaskan fakta')}</b>${tt('Assistants in Bahasa Malaysia and English; every figure traced to the data.', 'Pembantu dalam Bahasa Malaysia dan Inggeris; setiap angka dijejak kepada data.')}</div>
        <div><b>${tt('Governed', 'Ditadbir')}</b>${tt('Board-controlled autonomy, two-approver policy changes and a hash-chained ledger.', 'Autonomi dikawal Lembaga, perubahan dasar dua pelulus dan lejar berantai hash.')}</div>
      </div>
      <div class="tiny" style="color:#9fbcae;margin-top:auto">${t('Synthetic demonstration data — every member, figure and document is fictional.')}</div>
    </section>
    <section class="login-form">
      <div class="login-card">
        <div class="row"><h2 style="font-size:22px">${t('Sign in')}</h2><div class="spacer" style="flex:1"></div>
          <div class="lang-sw"><button data-l="ms" class="${lang() === 'ms' ? 'on' : ''}">BM</button><button data-l="en" class="${lang() === 'en' ? 'on' : ''}">EN</button></div></div>
        <div class="seg" role="tablist">
          <button role="tab" data-m="staff" class="${mode === 'staff' ? 'on' : ''}">${t('Staff')}</button>
          <button role="tab" data-m="member" class="${mode === 'member' ? 'on' : ''}">${t('Member')} · KT Online</button></div>
        <form id="f" class="col" style="gap:12px" autocomplete="on">
          <div class="field"><label for="u">${mode === 'staff' ? t('Staff ID') : t('Member number')}</label>
            <input class="inp" id="u" name="username" autocomplete="username" required
              placeholder="${mode === 'staff' ? 'noraini' : '104328'}" inputmode="${mode === 'staff' ? 'text' : 'numeric'}"/></div>
          <div class="field"><label for="p">${mode === 'staff' ? t('Password') : t('PIN')}</label>
            <input class="inp" id="p" name="password" type="password" autocomplete="current-password" required/></div>
          <div id="err" class="note red" style="display:none"></div>
          <button class="btn primary lg" id="go" type="submit">${icon('lock', 14)} ${t('Sign in')}</button>
        </form>
        ${demo.demo ? `<div class="sep"></div>
          <div class="up">${t('Demo accounts')}</div>
          <div class="tiny muted">${t('Click an account to sign in.')} ${tt('Staff password', 'Kata laluan kakitangan')}: <span class="mono">${esc(demo.staff_password)}</span> ·
            ${tt('Member PIN', 'PIN ahli')}: <span class="mono">${esc(demo.member_pin)}</span></div>
          <div class="demo-list">${demo.accounts.filter(a => a.kind === mode).map(a => `
            <button class="demo-acc" data-acc="${esc(a.username)}" type="button">
              <b>${esc(a.name)}</b><span>${esc(lang() === 'ms' ? a.role_ms : a.role)} · ${esc(a.username)}</span></button>`).join('')}</div>` : ''}
      </div>
    </section>`;

    $$('[data-l]', root).forEach(b => b.onclick = () => { setLang(b.dataset.l); draw(); });
    $$('[data-m]', root).forEach(b => b.onclick = () => { mode = b.dataset.m; draw(); });
    const submit = async (u, p) => {
      const btn = $('#go', root); btn.disabled = true;
      try {
        const r = await api('/auth/login', { method: 'POST', body: { username: u, password: p } });
        onDone(r.user);
      } catch (e) {
        const err = $('#err', root); err.style.display = 'block';
        err.textContent = e.status === 401 ? t('Incorrect ID or password') : e.message;
        btn.disabled = false;
      }
    };
    $('#f', root).onsubmit = e => { e.preventDefault(); submit($('#u', root).value.trim(), $('#p', root).value); };
    $$('[data-acc]', root).forEach(b => b.onclick = () =>
      submit(b.dataset.acc, mode === 'staff' ? demo.staff_password : demo.member_pin));
    $('#u', root).focus();
  };
  draw();
}
