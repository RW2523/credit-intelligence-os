import { api, icon, esc, tag, dtime, $, $$ } from '/lib.js';
import { t, tt, lang } from '/i18n.js';
import { reconTable } from '/views/applications.js';

let active = null, activeField = null, zoom = 1, pdfjs = null;

async function loadPdfjs() {
  if (!pdfjs) {
    pdfjs = await import('/vendor/pdfjs/pdf.min.mjs');
    pdfjs.GlobalWorkerOptions.workerSrc = '/vendor/pdfjs/pdf.worker.min.mjs';
  }
  return pdfjs;
}

export async function documents(el, param) {
  const { rows, pipeline } = await api('/documents');
  const prev = active?.id;
  active = rows.find(d => d.id === param) || rows.find(d => d.id === prev) || rows[0];
  if (active?.id !== prev) { activeField = null; zoom = 1; }
  const ms = lang() === 'ms';

  el.innerHTML = `
  <div class="page-head">
    <div><h1>${t('Document Intelligence')}</h1>
      <p>${tt('Evidence-first AI. Every extracted value is clickable and is boxed on the exact place in the document it came from.',
              'AI berasaskan bukti. Setiap nilai yang diekstrak boleh diklik dan ditanda pada tempat tepat dalam dokumen asalnya.')}</p></div>
    <div class="spacer"></div>
    <span class="tag t-grey">${rows.length} ${tt('documents registered', 'dokumen didaftarkan')}</span>
  </div>

  <div class="card" style="margin-bottom:14px"><div class="card-b">
    <div class="stepper">${pipeline.map((s, i) => `<div class="step done"><span class="n">${i + 1}</span>${esc(s)}</div>`).join('')}</div></div></div>

  <div class="grid g-1-2" style="align-items:start">
    <div class="card" style="position:sticky;top:0">
      <div class="card-h"><h3>${tt('Evidence library', 'Pustaka bukti')}</h3><div class="spacer"></div>
        <span class="tiny dim">${rows.filter(d => d.status === 'Verified').length} ${tt('verified', 'disahkan')}</span></div>
      <div class="card-b" style="padding:8px 10px"><input class="inp" id="dq" placeholder="${tt('Filter by name, type or case…', 'Tapis mengikut nama, jenis atau kes…')}"/></div>
      <div class="card-b col" style="gap:3px;max-height:68vh;overflow:auto;padding-top:0" id="dlist">
        ${rows.map(d => `<button class="field-row ${active?.id === d.id ? 'on' : ''}" data-pick="${d.id}"
            data-s="${esc((d.label + ' ' + d.doc_type + ' ' + (d.doc_type_ms || '') + ' ' + d.app_id).toLowerCase())}">
          ${icon(d.file.endsWith('.csv') ? 'list' : /\.(png|jpe?g)$/i.test(d.file) ? 'eye' : 'file', 15)}
          <span class="k" style="color:var(--ink-2);text-align:left">${esc(d.label)}
            <div class="tiny dim">${esc(ms ? (d.doc_type_ms || d.doc_type) : d.doc_type)} · ${esc(d.app_id)}</div></span>
          ${tag(d.status)}<span class="conf">${d.confidence}%</span></button>`).join('')}
      </div>
    </div>
    <div class="col" style="gap:14px" id="viewer"></div>
  </div>`;

  $$('[data-pick]', el).forEach(b => b.onclick = () => window.go('documents', b.dataset.pick));
  $('#dq', el).oninput = e => { const q = e.target.value.toLowerCase();
    $$('[data-pick]', el).forEach(b => b.style.display = b.dataset.s.includes(q) ? '' : 'none'); };
  el.querySelector('.field-row.on')?.scrollIntoView({ block: 'nearest' });
  renderViewer($('#viewer', el));
}

function renderViewer(host) {
  if (!active) { host.innerHTML = '<div class="empty">No document selected.</div>'; return; }
  const d = active;
  const kind = /\.(png|jpe?g)$/i.test(d.file) ? 'img' : /\.csv$/i.test(d.file) ? 'csv' : /\.pdf$/i.test(d.file) ? 'pdf' : 'other';
  const url = '/api/files/' + encodeURIComponent(d.file);
  const ms = lang() === 'ms';
  host.innerHTML = `
  <div class="card">
    <div class="card-h">${icon('file', 15)}<h3>${esc(d.label)}</h3>
      <span class="sub">${esc(ms ? (d.doc_type_ms || d.doc_type) : d.doc_type)} · ${tt('uploaded', 'dimuat naik')} ${dtime(d.uploaded)}</span>
      <div class="spacer"></div>${tag(d.status)}
      <a class="btn sm" href="${url}" target="_blank" rel="noopener">${icon('download', 12)} ${t('Open')}</a></div>
    <div class="card-b grid g2" style="align-items:start">
      <div>
        <div class="doc-stage" id="stage"><div class="center" style="height:300px"><div class="spin"></div></div></div>
        <div class="doc-meta">
          <span class="tiny dim" style="flex:1">${kind === 'csv' ? tt('Click a field to highlight the rows it came from.', 'Klik medan untuk menanda baris asalnya.')
            : tt('Click an extracted field to box where it was found.', 'Klik medan untuk menanda tempat ia ditemui.')}</span>
          ${kind === 'pdf' ? `<button class="btn sm" data-z="-1" aria-label="Zoom out">−</button><span class="tiny mono" id="zl">${Math.round(zoom * 100)}%</span>
            <button class="btn sm" data-z="1" aria-label="Zoom in">+</button>` : ''}
        </div>
      </div>
      <div class="col" style="gap:10px">
        <div class="up">${tt('Extracted fields', 'Medan diekstrak')}</div>
        ${d.fields.map((f, i) => `<button class="field-row ${activeField === i ? 'on' : ''}" data-f="${i}" ${f.meta ? 'data-meta="1"' : ''}>
          <span class="k">${esc(f.k)}${f.label && f.label !== f.k ? `<div class="tiny dim">“${esc(f.label)}”</div>` : ''}</span>
          <span class="v">${esc(f.v)}${f.src && f.src !== f.v ? `<div class="tiny dim mono" style="font-weight:400">${tt('printed', 'tercetak')}: ${esc(f.src)}</div>` : ''}</span>
          <span class="conf">${f.c}%</span></button>`).join('')}
        <div class="sep"></div>
        <div class="up">${tt('Forensics', 'Forensik')}</div>
        <dl class="kv">
          <dt>${tt('Content manipulation', 'Manipulasi kandungan')}</dt><dd>${d.forensics.tampering ? tag('Detected', 'red') : tag('None', 'green')}</dd>
          <dt>${tt('Font / layout consistency', 'Konsistensi fon / susun atur')}</dt><dd>${d.forensics.font_consistency}%</dd>
          <dt>${tt('Metadata', 'Metadata')}</dt><dd>${d.forensics.metadata_ok ? tag('Consistent', 'green') : tag('Anomaly', 'amber')}</dd>
          <dt>${tt('Duplicate hash', 'Hash pendua')}</dt><dd>${d.forensics.duplicate_hash ? tag('Reused', 'red') : tag('Unique', 'green')}</dd>
          <dt>${tt('Producer', 'Penghasil')}</dt><dd>${esc(d.forensics.producer)}</dd>
          ${d.sha256 ? `<dt>SHA-256</dt><dd class="mono tiny">${esc(d.sha256)}</dd>` : ''}
        </dl>
        <button class="btn" data-case="${esc(d.app_id)}">${icon('layers')} ${tt('Open case', 'Buka kes')} ${esc(d.app_id)}</button>
      </div>
    </div>
  </div>
  <div class="card" id="reconCard"><div class="card-h"><h3>${tt('Cross-source reconciliation', 'Penyesuaian silang sumber')}</h3>
    <span class="sub">${tt('the system does not believe one document on its own', 'sistem tidak mempercayai satu dokumen sahaja')}</span></div>
    <div class="card-b" id="reconBody"><div class="center"><div class="spin"></div></div></div></div>`;

  const stage = host.querySelector('#stage');
  let csvRows = null;
  const drawBox = () => {
    host.querySelectorAll('[data-f]').forEach(x => x.classList.toggle('on', +x.dataset.f === activeField));
    const f = activeField == null ? null : d.fields[activeField];
    if (kind === 'csv') {
      stage.querySelectorAll('tr.hit').forEach(r => r.classList.remove('hit'));
      (f?.rows || []).forEach(i => stage.querySelector(`tr[data-r="${i}"]`)?.classList.add('hit'));
      stage.querySelector('tr.hit')?.scrollIntoView({ block: 'nearest' });
      return;
    }
    const page = stage.querySelector('.doc-page'); if (!page) return;
    let box = page.querySelector('.bbox');
    if (!f || !f.bbox) { box && (box.style.display = 'none'); return; }
    if (!box) { box = document.createElement('div'); box.className = 'bbox'; page.appendChild(box); }
    const [x, y, w, hh] = f.bbox;
    Object.assign(box.style, { display: 'block', left: x + '%', top: y + '%', width: w + '%', height: hh + '%' });
    box.classList.toggle('r', x + w > 55);            // keep the label on the page for right-aligned values
    box.classList.toggle('b', y < 6);
    box.dataset.l = `${f.k} — ${f.v} (${f.c}%)`;
    const pr = page.getBoundingClientRect(), br = box.getBoundingClientRect(), sr = stage.getBoundingClientRect();
    if (br.top < sr.top || br.bottom > sr.bottom) stage.scrollTop += br.top - sr.top - sr.height / 3;
    void pr;
  };

  const render = async () => {
    if (kind === 'pdf') {
      try {
        const lib = await loadPdfjs();
        const doc = await lib.getDocument({ url, withCredentials: true }).promise;
        const pg = await doc.getPage(1);
        const base = pg.getViewport({ scale: 1 });
        const width = Math.max(260, (stage.clientWidth - 28) * zoom);
        const vp = pg.getViewport({ scale: width / base.width });
        const dpr = window.devicePixelRatio || 1;
        const canvas = document.createElement('canvas');
        canvas.width = Math.floor(vp.width * dpr); canvas.height = Math.floor(vp.height * dpr);
        stage.innerHTML = `<div class="doc-page" style="width:${vp.width}px"></div>`;
        stage.firstElementChild.appendChild(canvas);
        await pg.render({ canvasContext: canvas.getContext('2d'), viewport: vp, transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null }).promise;
        if (doc.numPages > 1) stage.insertAdjacentHTML('beforeend', `<div class="tiny dim" style="text-align:center;margin-top:6px">${tt('Page', 'Halaman')} 1 / ${doc.numPages}</div>`);
      } catch (e) {
        stage.innerHTML = `<div class="empty small">${icon('alert', 20)} ${esc(e.message)}</div>`;
      }
    } else if (kind === 'img') {
      stage.innerHTML = `<div class="doc-page" style="width:min(100%, 640px)"><img alt="${esc(d.label)}" src="${url}"/></div>`;
      await new Promise(r => { const im = stage.querySelector('img'); im.complete ? r() : (im.onload = im.onerror = r); });
    } else if (kind === 'csv') {
      const text = await fetch(url, { credentials: 'same-origin' }).then(r => r.text());
      csvRows = text.trim().split(/\r?\n/).map(l => l.split(','));
      stage.innerHTML = `<div class="csv-table"><table><thead><tr>${csvRows[0].map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead>
        <tbody>${csvRows.slice(1).map((r, i) => `<tr data-r="${i + 1}">${r.map(c => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    } else {
      stage.innerHTML = `<div class="empty small">${tt('Preview not available — open the file.', 'Pratonton tidak tersedia — buka fail.')}</div>`;
    }
    drawBox();
  };
  render();

  host.querySelectorAll('[data-f]').forEach(b => b.onclick = () => {
    if (b.dataset.meta) return;
    const i = +b.dataset.f;
    activeField = activeField === i ? null : i;
    drawBox();
  });
  host.querySelectorAll('[data-z]').forEach(b => b.onclick = () => {
    zoom = Math.max(0.6, Math.min(2.4, zoom + (+b.dataset.z) * 0.2));
    host.querySelector('#zl').textContent = Math.round(zoom * 100) + '%';
    render();
  });
  host.querySelectorAll('[data-case]').forEach(b => b.onclick = () => window.go('workbench', b.dataset.case));
  let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => document.body.contains(stage) && kind === 'pdf' && render(), 250); }, { once: true });

  api('/applications/' + d.app_id).then(c => {
    const b = host.querySelector('#reconBody'); if (!b) return;
    b.innerHTML = reconTable(c.reconciliation) +
      (c.reconciliation.exceptions.map(x => `<div class="note ${x.severity === 'high' ? 'red' : 'amber'}" style="margin-top:9px">
        <b>${esc(x.title)}</b><div class="small">${esc(x.detail)}</div>
        <div class="tiny dim">${esc(x.classification)} · ${tt('resolution', 'penyelesaian')}: ${esc(x.resolution)}</div></div>`).join('') ||
      `<div class="note green" style="margin-top:9px">${tt('No discrepancy found across independent sources.', 'Tiada percanggahan antara sumber bebas.')}</div>`);
  }).catch(() => { const b = host.querySelector('#reconBody'); if (b) b.innerHTML = '<div class="small dim">—</div>'; });
}
