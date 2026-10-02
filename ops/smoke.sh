#!/bin/bash
# End-to-end smoke test over HTTP. Pass a base URL (default: the local service):
#   ops/smoke.sh http://127.0.0.1:8899
# Set SMOKE_LLM=1 to also exercise the local model paths (Council, assistants, drafts).
cd "$(dirname "$0")/.."
U="${1:-http://127.0.0.1:8899}"
PW="${CIOS_DEMO_PASSWORD:-KT-demo-2026}"; PIN="${CIOS_MEMBER_PIN:-123456}"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); printf '  PASS  %s\n' "$1"; }
no(){ FAIL=$((FAIL+1)); printf '  FAIL  %s — %s\n' "$1" "$2"; }
login(){ curl -s -c "$T/$1" -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' \
           -d "{\"username\":\"$1\",\"password\":\"$2\"}" "$U/api/auth/login"; }
code(){ local n="$1" who="$2" exp="$3"; shift 3
  local c; c=$(curl -s -b "$T/$who" -o /dev/null -w '%{http_code}' -m 300 "$@")
  [ "$c" = "$exp" ] && ok "$n" || no "$n" "got $c want $exp"; }
has(){ local n="$1" who="$2" needle="$3"; shift 3
  if curl -s -b "$T/$who" -m 300 "$@" | grep -q -- "$needle"; then ok "$n"; else no "$n" "missing '$needle'"; fi; }
hasnt(){ local n="$1" who="$2" needle="$3"; shift 3
  if curl -s -b "$T/$who" -m 300 "$@" | grep -q -- "$needle"; then no "$n" "found '$needle'"; else ok "$n"; fi; }

echo "base: $U"
echo "--- static + sign-in"
for p in / /app.js /styles.css /lib.js /i18n.js /vendor/pdfjs/pdf.min.mjs; do
  c=$(curl -s -o /dev/null -w '%{http_code}' "$U$p"); [ "$c" = 200 ] && ok "GET $p" || no "GET $p" "$c"; done
c=$(curl -s -o /dev/null -w '%{http_code}' "$U/api/portfolio"); [ "$c" = 401 ] && ok "anonymous API call refused" || no "anonymous refused" "$c"
for u in noraini aisha kamarul zulkifli farah priya azlan; do [ "$(login $u "$PW")" = 200 ] && ok "sign in $u" || no "sign in $u" "refused"; done
[ "$(login 104328 "$PIN")" = 200 ] && ok "sign in member 104328" || no "sign in member" "refused"
[ "$(login noraini wrong)" = 401 ] && ok "wrong password refused" || no "wrong password" "accepted"; login noraini "$PW" >/dev/null

echo "--- read surfaces (Branch Manager)"
for r in portfolio applications documents members early-warning collections governance ledger cockpit crosssell notifications; do
  code "GET /api/$r" kamarul 200 "$U/api/$r"; done
code "case detail" kamarul 200 "$U/api/applications/APP-104328"
code "member 360" kamarul 200 "$U/api/members/104328"
code "search" kamarul 200 "$U/api/search?q=ahmad"
code "ledger reconstruct" kamarul 200 "$U/api/ledger/reconstruct/APP-104172"

echo "--- role enforcement"
code "officer cannot open the cockpit" noraini 403 "$U/api/cockpit"
code "officer cannot see distress outlooks" noraini 403 "$U/api/members/104436/distress"
code "senior officer can" aisha 200 "$U/api/members/104436/distress"
code "board cannot list members" zulkifli 403 "$U/api/members"
code "member cannot read another member" 104328 403 "$U/api/members/104310"
code "officer cannot approve RM120,000" noraini 403 -X POST -H 'Content-Type: application/json' -d '{"action":"Approve","reason":"x"}' "$U/api/applications/APP-104276/decision"

echo "--- KT localisation and the reported bugs"
hasnt "no dollar amounts in the portfolio" kamarul '\$[0-9]' "$U/api/portfolio"
has "amounts in Ringgit" kamarul 'RM' "$U/api/applications/APP-104310"
has "timestamps in Malaysia time" kamarul '+08:00' "$U/api/ledger"
has "APP-104310 maximum is RM0, not -200" aisha '"max_financing":0' "$U/api/applications/APP-104310"
hasnt "no negative maximum text" aisha 'RM-\|-RM' "$U/api/applications/APP-104310"
has "60% salary-deduction cap enforced" aisha 'Salary deduction cap' "$U/api/applications/APP-104355"
has "KT branches" kamarul 'Kota Kinabalu' "$U/api/cockpit"
has "KT products" kamarul 'Personal Financing-i' "$U/api/cockpit"
has "member self-check matches policy" 104328 '"max_financing":32800' -X POST -H 'Content-Type: application/json' \
    -d '{"product":"Personal Financing-i","amount":25000,"term":48}' "$U/api/me/affordability"
has "member assistant: balance, not the application" 104328 'RM18,250' -X POST -H 'Content-Type: application/json' \
    -d '{"question":"Berapa baki pinjaman saya dan bila bayaran seterusnya?"}' "$U/api/member-assistant"
hasnt "member assistant: never RM25,000 as the balance" 104328 'baki[^"]*25,000' -X POST -H 'Content-Type: application/json' \
    -d '{"question":"Berapa baki pinjaman saya?"}' "$U/api/member-assistant"

echo "--- writes"

login priya "$PW" >/dev/null; code "sandbox simulate" priya 200 -X POST -H 'Content-Type: application/json' -d '{"dsr_ceiling":45}' "$U/api/sandbox/simulate"
code "autonomy (board)" zulkifli 200 -X POST -H 'Content-Type: application/json' -d '{"mode":"ASSIST","kill_switch":false}' "$U/api/governance/autonomy"
DOC=$(ls data/docs/104328_slip_gaji_*.pdf 2>/dev/null | head -1)
[ -n "$DOC" ] && code "document upload" noraini 200 -X POST -F "file=@$DOC;filename=slip_gaji_test.pdf" "$U/api/applications/APP-104291/documents"

if [ "${SMOKE_LLM:-0}" = "1" ]; then
  echo "--- local model paths"
  has "council positions are model-authored" aisha '"_source": "llm"' "$U/api/applications/APP-104328/council/stream"
  has "KT Assistant calls a tool" kamarul 'event: tool' -X POST -H 'Content-Type: application/json' \
      -d '{"question":"Financing requested by branch?"}' "$U/api/assistant"
  has "outreach draft from model" azlan '"_source":"llm"' -X POST -H 'Content-Type: application/json' \
      -d '{"member_id":"104328","channel":"Email","lang":"ms"}' "$U/api/collections/draft" 2>/dev/null || \
  { login azlan "$PW" >/dev/null; has "outreach draft from model" azlan '"_source":"llm"' -X POST -H 'Content-Type: application/json' \
      -d '{"member_id":"104328","channel":"Email","lang":"ms"}' "$U/api/collections/draft"; }
fi
has "ledger chain intact" kamarul '"intact":true' "$U/api/health"
echo
echo "RESULT: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
