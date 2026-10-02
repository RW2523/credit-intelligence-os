import { api, sse, icon, esc, md, h, $, drawer, barChart, lineChart, money } from '/lib.js';
import { t, tt, lang } from '/i18n.js';
import { state } from '/app.js';

const TOOL_LABEL = {
  list_applications: ['Listing applications', 'Menyenaraikan permohonan'], portfolio_breakdown: ['Aggregating the portfolio', 'Mengagregat portfolio'],
  get_case: ['Reading the case file', 'Membaca fail kes'], get_member: ['Opening the member profile', 'Membuka profil ahli'],
  search_members: ['Searching members', 'Mencari ahli'], early_warning: ['Checking early warnings', 'Menyemak amaran awal'],
  collections_summary: ['Reading collections', 'Membaca kutipan'], policy_lookup: ['Searching the policy library', 'Mencari pustaka dasar'],
  ledger_search: ['Searching the ledger', 'Mencari lejar'], application_trend: ['Reading the trend', 'Membaca trend'],
  distress_overview: ['Summarising financial-distress bands', 'Meringkaskan jalur tekanan kewangan'],
  crosssell_overview: ['Ranking cross-sell opportunities', 'Menyusun peluang jualan silang'],
  affordability_check: ['Running the affordability engine', 'Menjalankan enjin kemampuan'],
};

function suggestions(role, caseId) {
  if (caseId) return lang() === 'ms'
    ? ['Kenapa kes ini gagal dasar?', 'Bandingkan slip gaji dengan penyata bank.', 'Apakah yang akan mengubah keputusan?', 'Dokumen apa yang masih tiada?']
    : ['Why does this case fail policy?', 'Compare the payslip with the bank statement.', 'What would change the outcome?', 'What evidence is missing?'];
  const ms = lang() === 'ms';
  const by = {
    board: ms ? ['Tunjukkan jumlah pembiayaan mengikut cawangan', 'Berapa ramai ahli dalam jalur tekanan kewangan tinggi?', 'Apakah trend permohonan 16 hari lalu?']
              : ['Show financing requested by branch', 'How many members are in the high financial-distress band?', 'What is the application trend over the last 16 days?'],
    manager: ms ? ['Kes Lumut yang masih menunggu dokumen?', 'Jumlah pembiayaan mengikut produk', 'Siapa calon jualan silang takaful terbaik?']
                : ['Which Lumut cases are waiting on documents?', 'Financing requested by product', 'Who are the best takaful cross-sell candidates?'],
    marketing: ms ? ['Senaraikan peluang takaful', 'Ahli mana yang perlukan panggilan pengekalan?'] : ['List the takaful opportunities', 'Which members need a retention call?'],
    collections: ms ? ['Ahli mana paling berisiko bulan ini?', 'Ringkaskan kes kutipan'] : ['Which members are most at risk this month?', 'Summarise the collections cases'],
  };
  return by[role] || (ms ? ['Kes mana yang menunggu dokumen?', 'Kenapa Kpl Mohd Ridzuan gagal dasar?', 'Jumlah pembiayaan Pembiayaan Peribadi-i mengikut cawangan', 'Berapa boleh Sjn Udara Nurul Huda pinjam untuk 60 bulan?']
    : ['Which cases are waiting on documents?', 'Why did Kpl Mohd Ridzuan fail policy?', 'Personal Financing-i requested by branch', 'How much could Sjn Udara Nurul Huda borrow over 60 months?']);
}

export function chatPanel(host, { appId = null, endpoint = '/assistant', height = '60vh' } = {}) {
  const history = [];
  host.innerHTML = `
    <div class="chat" id="chat" style="min-height:${height === 'auto' ? '0' : '200px'};max-height:${height};overflow-y:auto;padding:2px 2px 8px"></div>
    <div class="chips" id="sug" style="margin:8px 0">${suggestions(state.user.role, appId).map(q => `<button class="chip">${esc(q)}</button>`).join('')}</div>
    <form class="row" id="f"><input class="inp" id="qin" placeholder="${tt('Ask in English or Bahasa Malaysia…', 'Tanya dalam Bahasa Malaysia atau English…')}" aria-label="Question"/>
      <button class="btn primary" id="send" type="submit" aria-label="${t('Send')}">${icon('send')}</button></form>`;
  const chat = $('#chat', host), input = $('#qin', host);
  const scroll = () => { chat.scrollTop = chat.scrollHeight; };

  let busy = false;
  const setBusy = on => {
    busy = on;
    host.querySelectorAll('#qin, #send, #sug .chip').forEach(x => x.disabled = on);
  };
  const send = q => {
    if (!q || busy) return;
    setBusy(true);
    input.value = '';
    chat.insertAdjacentHTML('beforeend', `<div class="msg me">${esc(q)}</div>`);
    const steps = h('<div class="col" style="gap:5px;align-self:flex-start"></div>');
    const bubble = h(`<div class="msg ai"></div>`);
    chat.append(steps, bubble); scroll();
    let text = '', charts = [], stage = tt('Reading your question', 'Membaca soalan anda');
    const t0 = Date.now();
    const waiting = () => `<span class="row small muted" style="gap:8px"><span class="pulse"></span>${esc(stage)}…
      <span class="mono tiny">${Math.round((Date.now() - t0) / 1000)} s</span></span>`;
    const timer = setInterval(() => { if (!text) bubble.innerHTML = waiting(); }, 1000);
    const finish = () => { clearInterval(timer); setBusy(false); input.focus(); };
    const paint = () => { bubble.innerHTML = text ? md(text) : waiting(); scroll(); };
    paint();
    sse(endpoint, {
      meta: m => { steps.dataset.model = m.model || ''; stage = tt('Deciding which data to look up', 'Menentukan data yang perlu dicari'); paint(); },
      tool: x => {
        const [en, ms] = TOOL_LABEL[x.name] || [x.name, x.name];
        steps.insertAdjacentHTML('beforeend', `<div class="tool-step">${icon(x.ok ? 'check' : 'alert', 11)}
          ${esc(lang() === 'ms' ? ms : en)} <b>${esc(x.name)}</b> · ${esc(x.summary || '')}</div>`);
        stage = tt('Writing the answer from that data', 'Menulis jawapan daripada data itu'); paint();
      },
      chart: c => charts.push(c),
      check: x => { steps.insertAdjacentHTML('beforeend', `<div class="tool-step" style="border-color:var(--amber-line)">${icon('alert', 11)}
        ${tt('Figures not found in the data — asking the model to check', 'Angka tiada dalam data — model diminta menyemak')} (${esc(x.unverified.slice(0, 3).join(', '))})</div>`);
        stage = tt('Re-checking the figures', 'Menyemak semula angka'); },
      token: x => { text += x.t; paint(); },
      replace: x => { text = x.t; paint(); },
      done: d => {
        finish();
        paint();
        history.push({ role: 'user', content: q }, { role: 'assistant', content: text });
        for (const c of charts) {
          const html = c.type === 'line'
            ? lineChart(c.labels.map((l, i) => Object.fromEntries([['d', l], ...Object.entries(c.series).map(([k, v]) => [k, v[i]])])),
                { keys: Object.keys(c.series), labels: Object.keys(c.series), h: 170, colors: ['var(--info)', 'var(--green)', 'var(--red)'] })
            : barChart(c.labels.map((l, i) => ({ l, v: c.values[i] })), { h: 170, unit: c.unit, color: 'var(--brand)' });
          bubble.insertAdjacentHTML('afterend', `<div class="chat-chart"><div class="ttl">${esc(c.title)}</div>${html}</div>`);
        }
        const g = d.grounding || {};
        if (!g.figures && d.source !== 'deterministic') {
          bubble.insertAdjacentHTML('beforeend', `<div class="ground tag t-grey">${icon('info', 11)} ${tt('No figures quoted', 'Tiada angka dinyatakan')}</div>`);
        }
        if (g.figures) {
          const ok = !g.unverified?.length;
          bubble.insertAdjacentHTML('beforeend', `<div class="ground tag t-${ok ? 'green' : 'amber'}"
            title="${esc(ok ? '' : tt('Not found in the data: ', 'Tiada dalam data: ') + g.unverified.join(', '))}">${icon(ok ? 'check' : 'alert', 11)}
            ${ok ? tt(`All ${g.figures} figures traced to the data`, `Kesemua ${g.figures} angka dijejak kepada data`)
                 : tt(`${g.verified}/${g.figures} figures traced — check ${g.unverified.join(', ')}`, `${g.verified}/${g.figures} angka dijejak — semak ${g.unverified.join(', ')}`)}</div>`);
        }
        if (d.source === 'deterministic') bubble.insertAdjacentHTML('beforeend', `<div class="ground tag t-amber">${tt('Model offline — deterministic answer', 'Model luar talian — jawapan deterministik')}</div>`);
        scroll();
      },
      error: e => { finish(); bubble.textContent = tt('Assistant unavailable: ', 'Pembantu tidak tersedia: ') + e.message; },
      close: () => { if (busy) { finish(); if (!text) bubble.textContent = tt('No answer came back — please try again.', 'Tiada jawapan — sila cuba lagi.'); } },
    }, { method: 'POST', body: { question: q, history: history.slice(-6), application_id: appId, lang: lang() } });
  };
  $('#f', host).onsubmit = e => { e.preventDefault(); send(input.value.trim()); };
  host.querySelectorAll('#sug .chip').forEach(b => b.onclick = () => send(b.textContent));
  return { send };
}

export async function assistantPage(el) {
  const u = state.user;
  el.innerHTML = `
  <div class="page-head"><div><h1>${t('KT Assistant')}</h1>
    <p>${tt('Ask about cases, members, the portfolio or policy in English or Bahasa Malaysia. It looks the answer up in live data using only the tools your role allows, shows each step, and checks every figure it quotes.',
            'Tanya tentang kes, ahli, portfolio atau dasar dalam Bahasa Malaysia atau English. Ia mencari jawapan dalam data semasa menggunakan alat yang dibenarkan untuk peranan anda, menunjukkan setiap langkah dan menyemak setiap angka.')}</p></div></div>
  <div class="grid g-2-1" style="align-items:start">
    <div class="card"><div class="card-h">${icon('msg', 15)}<h3>${t('KT Assistant')}</h3>
      <span class="sub">${esc(u.name)} · ${esc(lang() === 'ms' ? u.role_ms : u.role_label)}</span></div>
      <div class="card-b" id="panel"></div></div>
    <div class="col" style="gap:14px">
      <div class="card"><div class="card-h"><h3>${tt('How it stays accurate', 'Bagaimana ia kekal tepat')}</h3></div><div class="card-b col small muted" style="gap:8px">
        <div>${icon('layers', 13)} ${tt('Answers come from the same engines as the screens — the model never invents a figure.', 'Jawapan datang daripada enjin yang sama dengan skrin — model tidak mereka angka.')}</div>
        <div>${icon('shield', 13)} ${tt('Your role decides which data it can read; the Board sees aggregates only.', 'Peranan anda menentukan data yang boleh dibaca; Lembaga melihat agregat sahaja.')}</div>
        <div>${icon('check', 13)} ${tt('Each answer reports how many of its figures were traced back to the data.', 'Setiap jawapan melaporkan berapa angka yang dijejak kembali kepada data.')}</div>
        <div>${icon('cpu', 13)} ${tt('Runs on this machine', 'Berjalan pada mesin ini')}: <span class="mono">${esc(state.boot.llm?.model || '—')}</span></div>
      </div></div>
    </div>
  </div>`;
  chatPanel($('#panel', el), { endpoint: '/assistant', height: '58vh' });
}

export function askDrawer(appId, who) {
  drawer(`<div class="row">${icon('msg', 16)}<h3>${appId ? tt('Ask about this case', 'Tanya tentang kes ini') : tt('Ask the cockpit', 'Tanya kokpit')}${who ? ` — ${esc(who)}` : ''}</h3></div>`,
    `<div class="note small">${appId
      ? tt('Grounded in this case\'s frozen snapshot, its evidence and the policy library. It will not state a credit decision.', 'Berasaskan snapshot kes ini, bukti dan pustaka dasar. Ia tidak menyatakan keputusan kredit.')
      : tt('Portfolio questions are answered from live data; aggregate answers come with a chart.', 'Soalan portfolio dijawab daripada data semasa; jawapan agregat disertakan carta.')}</div>
     <div id="panel" style="margin-top:10px"></div>`,
    { wide: true, onMount: d => chatPanel(d.querySelector('#panel'), { appId, endpoint: '/ask', height: '62vh' }) });
}
