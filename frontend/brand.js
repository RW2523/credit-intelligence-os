// Interim KT mark: a shield monogram in KT green and gold. Replace with KT's own logo when supplied (plan §6, K7).
export const mark = (id = 'm') => `<svg viewBox="0 0 40 40" aria-hidden="true">
  <defs><linearGradient id="${id}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2f8a60"/><stop offset="1" stop-color="#123d2b"/></linearGradient></defs>
  <path d="M20 2 35 7v12c0 9.5-6.6 16.3-15 19-8.4-2.7-15-9.5-15-19V7z" fill="url(#${id}g)" stroke="#d6b04a" stroke-width="1.6"/>
  <path d="M20 6.5l1.2 2.5 2.7.4-2 1.9.5 2.7-2.4-1.3-2.4 1.3.5-2.7-2-1.9 2.7-.4z" fill="#e8c870"/>
  <text x="20" y="29" text-anchor="middle" font-family="-apple-system,Segoe UI,Roboto,sans-serif" font-size="12.5" font-weight="800" fill="#fff" letter-spacing="-.3">KT</text>
</svg>`;
