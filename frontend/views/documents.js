import { api, icon, esc, tag, toneFor, dtime, h, $, $$, toast } from '/lib.js';
import { reconTable } from '/views/applications.js';

let active = null, activeField = null;

export async function documents(el, param) {
  const { rows, pipeline } = await api('/documents');
  active = rows.find(d => d.id === param) || rows.find(d => d.id === active?.id) || rows[0];

  el.innerHTML = `
  <div class="page-head">
    <div><h1>Document Intelligence</h1>
      <p>Evidence-first AI. Every extracted value is clickable and points back to the exact place in the
         source document it came from.</p></div>
    <div class="spacer"></div>
    <span class="tag t-grey">${rows.length} documents registered</span>
  </div>

  <div class="card" style="margin-bottom:14px"><div class="card-b">
    <div class="stepper">${pipeline.map((s, i) => `<div class="step done">
      <span class="n">${i + 1}</span>${esc(s)}</div>`).join('')}</div></div></div>

  <div class="grid g-1-2" style="align-items:start">
    <div class="card" style="position:sticky;top:0">
      <div class="card-h"><h3>Evidence library</h3><div class="spacer"></div>
        <span class="tiny dim">${rows.filter(d => d.status === 'Verified').length} verified</span></div>
      <div class="card-b col" style="gap:3px;max-height:70vh;overflow:auto">
        ${rows.map(d => `<button class="field-row ${active?.id === d.id ? 'on' : ''}" data-pick="${d.id}">
          ${icon(d.file.endsWith('.csv') ? 'list' : d.file.match(/png|jpg/) ? 'eye' : 'file', 15)}
          <span class="k" style="color:var(--ink-2);text-align:left">${esc(d.label)}
            <div class="tiny dim">${esc(d.doc_type)} · ${esc(d.app_id)}</div></span>
          ${tag(d.status)}<span class="conf">${d.confidence}%</span></button>`).join('')}
      </div>
    </div>
    <div class="col" style="gap:14px" id="viewer"></div>
  </div>`;

  $$('[data-pick]', el).forEach(b => b.onclick = () => { activeField = null; window.go('documents', b.dataset.pick); });
  renderViewer($('#viewer', el));
}

function renderViewer(host) {
  if (!active) { host.innerHTML = '<div class="empty">No document selected.</div>'; return; }
  const d = active;
  const isImg = /\.(png|jpe?g)$/i.test(d.file);
  const isCsv = /\.csv$/i.test(d.file);
  const url = '/api/files/' + encodeURIComponent(d.file);

  host.innerHTML = `
  <div class="card">
    <div class="card-h">${icon('file', 15)}<h3>${esc(d.label)}</h3>
      <span class="sub">${esc(d.doc_type)} · uploaded ${dtime(d.uploaded)}</span>
      <div class="spacer"></div>${tag(d.status)}
      <a class="btn sm" href="${url}" target="_blank">${icon('download', 12)} Open</a></div>
    <div class="card-b grid g2" style="align-items:start">
      <div>
        <div class="doc-stage" id="stage">
          ${isImg ? `<img src="${url}" alt="${esc(d.label)}"/>`
            : isCsv ? `<pre class="mono" id="csv" style="width:100%;height:520px;overflow:auto;padding:14px;
                        color:var(--ink-2);background:#0b111c;text-align:left"></pre>`
            : `<iframe src="${url}#toolbar=0&view=FitH" title="${esc(d.label)}"></iframe>`}
          <div class="bbox" id="bbox" style="display:none"></div>
        </div>
        <div class="tiny dim" style="margin-top:6px">Click an extracted field to highlight where it was found.</div>
      </div>
      <div class="col" style="gap:10px">
        <div class="up">Extracted fields</div>
        ${d.fields.map((f, i) => `<button class="field-row ${activeField === i ? 'on' : ''}" data-f="${i}">
          <span class="k">${esc(f.k)}</span><span class="v">${esc(f.v)}</span>
          <span class="conf">${f.c}%</span></button>`).join('')}
        <div class="sep"></div>
        <div class="up">Forensics</div>
        <dl class="kv">
          <dt>Content manipulation</dt><dd>${d.forensics.tampering ? tag('Detected', 'red') : tag('None', 'green')}</dd>
          <dt>Font / layout consistency</dt><dd>${d.forensics.font_consistency}%</dd>
          <dt>Metadata</dt><dd>${d.forensics.metadata_ok ? tag('Consistent', 'green') : tag('Anomaly', 'amber')}</dd>
          <dt>Duplicate hash</dt><dd>${d.forensics.duplicate_hash ? tag('Reused', 'red') : tag('Unique', 'green')}</dd>
          <dt>Producer</dt><dd>${esc(d.forensics.producer)}</dd>
        </dl>
        <button class="btn" data-case="${d.app_id}">${icon('layers')} Open case ${esc(d.app_id)}</button>
      </div>
    </div>
  </div>
  <div class="card" id="reconCard"><div class="card-h"><h3>Cross-source reconciliation</h3>
    <span class="sub">the system does not believe one document on its own</span></div>
    <div class="card-b" id="reconBody"><div class="center"><div class="spin"></div></div></div></div>`;

  if (isCsv) fetch(url).then(r => r.text()).then(t => { const p = host.querySelector('#csv'); if (p) p.textContent = t; });

  host.querySelectorAll('[data-f]').forEach(b => b.onclick = () => {
    const i = +b.dataset.f;
    activeField = activeField === i ? null : i;
    host.querySelectorAll('[data-f]').forEach(x => x.classList.toggle('on', +x.dataset.f === activeField));
    const box = host.querySelector('#bbox'), f = d.fields[i];
    if (activeField === null) { box.style.display = 'none'; return; }
    const stage = host.querySelector('#stage').getBoundingClientRect();
    box.style.display = 'block';
    box.style.left = f.bbox[0] + '%'; box.style.top = f.bbox[1] + '%';
    box.style.width = f.bbox[2] + '%'; box.style.height = f.bbox[3] + '%';
    box.dataset.l = `${f.k} — ${f.v} (${f.c}%)`;
  });
  host.querySelectorAll('[data-case]').forEach(b => b.onclick = () => window.go('workbench', b.dataset.case));

  api('/applications/' + d.app_id).then(c => {
    const b = host.querySelector('#reconBody'); if (!b) return;
    b.innerHTML = reconTable(c.reconciliation) +
      c.reconciliation.exceptions.map(x => `<div class="note ${x.severity === 'high' ? 'red' : 'amber'}" style="margin-top:9px">
        <b>${esc(x.title)}</b><div class="small">${esc(x.detail)}</div>
        <div class="tiny dim">${esc(x.classification)} · resolution: ${esc(x.resolution)}</div></div>`).join('') ||
      '<div class="note green">No discrepancy found across independent sources.</div>';
  }).catch(() => {});
}
