// Bahasa Malaysia / English. Keys are the English phrase, so any string can be wrapped in t() and
// falls back to English when no translation exists. Malaysian-standard Malay throughout.
const MS = {
  // shell & navigation
  'Origination': 'Permohonan', 'Members & Servicing': 'Ahli & Servis', 'Growth': 'Pertumbuhan',
  'Governance': 'Tadbir Urus', 'Assistants': 'Pembantu', 'My account': 'Akaun saya',
  'Portfolio Overview': 'Gambaran Portfolio', 'Applications': 'Permohonan Pembiayaan', 'New Application': 'Permohonan Baharu',
  'Document Intelligence': 'Kecerdasan Dokumen', 'Member 360': 'Ahli 360', 'Early Warning': 'Amaran Awal',
  'Collections': 'Kutipan', 'Cross-selling options': 'Pilihan Jualan Silang', 'Management Cockpit': 'Kokpit Pengurusan',
  'Policy Sandbox': 'Kotak Pasir Dasar', 'Model Governance': 'Tadbir Urus Model', 'Decision Ledger': 'Lejar Keputusan',
  'KT Assistant': 'Pembantu KT', 'My Account': 'Akaun Saya', 'Check Before You Borrow': 'Semak Sebelum Memohon',
  'Search members, applications, documents, policies…': 'Cari ahli, permohonan, dokumen, dasar…',
  'Sign out': 'Log keluar', 'Refresh': 'Muat semula', 'Notifications': 'Pemberitahuan', 'Language': 'Bahasa',
  'Not available for this role': 'Tidak tersedia untuk peranan ini',
  // sign-in
  'Sign in': 'Log masuk', 'Staff': 'Kakitangan', 'Member': 'Ahli', 'Staff ID': 'ID Kakitangan',
  'Password': 'Kata laluan', 'Member number': 'No. anggota KT', 'PIN': 'PIN',
  'Demo accounts': 'Akaun demo', 'Click an account to sign in.': 'Klik akaun untuk log masuk.',
  'Incorrect ID or password': 'ID atau kata laluan tidak betul',
  'Credit intelligence for Koperasi Tentera': 'Kecerdasan kredit untuk Koperasi Tentera',
  'Synthetic demonstration data — every member, figure and document is fictional.':
    'Data demonstrasi sintetik — setiap ahli, angka dan dokumen adalah rekaan.',
  // common
  'Outstanding balance': 'Baki pembiayaan', 'Savings': 'Simpanan', 'Share capital': 'Modal syer',
  'Next deduction': 'Potongan seterusnya', 'Monthly instalment': 'Ansuran bulanan', 'Profit rate': 'Kadar keuntungan',
  'flat, per year': 'rata, setahun', 'months': 'bulan', 'Amount': 'Amaun', 'Tenure': 'Tempoh', 'Product': 'Produk',
  'Status': 'Status', 'Documents': 'Dokumen', 'Branch': 'Cawangan', 'Submitted': 'Dihantar', 'Open': 'Buka',
  'Back': 'Kembali', 'Send': 'Hantar', 'Cancel': 'Batal', 'Close': 'Tutup', 'Print': 'Cetak', 'Apply': 'Mohon',
  'Today': 'Hari ini', 'today': 'hari ini', 'yesterday': 'semalam', 'on time': 'tepat masa', 'days late': 'hari lewat',
  'Something went wrong rendering this view.': 'Ralat semasa memaparkan paparan ini.',
  // member portal
  'Member portal': 'Portal ahli', 'Welcome back': 'Selamat kembali', 'My financing': 'Pembiayaan saya',
  'My applications': 'Permohonan saya', 'Recent deductions': 'Potongan terkini', 'Takaful & Ar-Rahnu': 'Takaful & Ar-Rahnu',
  'Member Assistant': 'Pembantu Ahli', 'Statement': 'Penyata', 'Download statement': 'Muat turun penyata',
  'it answers about your account — it never makes a financing decision':
    'ia menjawab tentang akaun anda — ia tidak membuat keputusan pembiayaan',
  'Ask about your account…': 'Tanya tentang akaun anda…', 'Documents still needed': 'Dokumen yang masih diperlukan',
  'All documents received': 'Semua dokumen telah diterima', 'by salary deduction': 'melalui potongan gaji',
  'No applications in progress.': 'Tiada permohonan dalam proses.', 'Your cover': 'Perlindungan anda',
  'No takaful cover with KT yet.': 'Belum ada perlindungan takaful dengan KT.', 'Your branch': 'Cawangan anda',
  'Upload a document': 'Muat naik dokumen',
  // check before you borrow
  'Indicative maximum': 'Anggaran maksimum', 'Estimate': 'Kira', 'Proceed to apply': 'Teruskan permohonan',
  'What would improve it': 'Apa yang boleh memperbaikinya', 'Documents you will need': 'Dokumen yang diperlukan',
  'Debt service ratio': 'Nisbah khidmat hutang', 'Salary deduction cap': 'Had potongan gaji',
  'Purpose': 'Tujuan', 'Within policy': 'Dalam dasar', 'Outside policy': 'Di luar dasar',
  'at the longest tenure': 'pada tempoh terpanjang',
};

let current = null;

export function lang() {
  if (current) return current;
  try { current = localStorage.getItem('kt-lang'); } catch (e) { /* private mode */ }
  return current || 'en';
}

export function setLang(l) {
  current = l === 'ms' ? 'ms' : 'en';
  try { localStorage.setItem('kt-lang', current); } catch (e) { /* private mode */ }
  document.documentElement.lang = current === 'ms' ? 'ms' : 'en';
}

export function hasLang() {
  try { return !!localStorage.getItem('kt-lang'); } catch (e) { return false; }
}

export const t = s => (lang() === 'ms' && MS[s]) || s;
// pick between two literal strings: tt('English', 'Bahasa Malaysia')
export const tt = (en, ms) => (lang() === 'ms' ? ms : en);
