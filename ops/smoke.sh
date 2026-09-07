#!/bin/bash
# End-to-end smoke test. Defaults to the public tunnel URL; pass a base URL to override:
#   ops/smoke.sh http://127.0.0.1:8899
cd "$(dirname "$0")/.."
U="${1:-$(cat "${STATE_DIR:-$HOME/.local/state/cios}/public_url" 2>/dev/null)}"
[ -n "$U" ] || { echo "no base URL — pass one, or start cios-tunnel"; exit 2; }
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); printf '  PASS  %s\n' "$1"; }
no(){ FAIL=$((FAIL+1)); printf '  FAIL  %s — %s\n' "$1" "$2"; }
code(){ local n="$1" exp="$2"; shift 2
  local c; c=$(curl -s -o /dev/null -w '%{http_code}' -m 300 "$@")
  [ "$c" = "$exp" ] && ok "$n" || no "$n" "got $c want $exp"; }
has(){ local n="$1" needle="$2"; shift 2
  if curl -s -m 300 "$@" | grep -q -- "$needle"; then ok "$n"; else no "$n" "missing '$needle'"; fi; }

echo "base: $U"
echo "--- static + meta ---"
for path in / /app.js /styles.css /lib.js /api/health /api/bootstrap; do code "GET $path" 200 "$U$path"; done
echo "--- read surfaces ---"
for r in portfolio applications documents members early-warning collections \
         governance ledger cockpit notifications support-tasks; do code "GET /api/$r" 200 "$U/api/$r"; done
code "case detail"        200 "$U/api/applications/APP-104328"
code "member detail"      200 "$U/api/members/104328"
code "search"             200 "$U/api/search?q=carter"
code "ledger reconstruct" 200 "$U/api/ledger/reconstruct/APP-104172"
echo "--- evidence files ---"
for f in payslip_david_carter_mar_2024.pdf national_id_david_carter.png \
         member_payment_history_david_carter.csv; do code "file $f" 200 "$U/api/files/$f"; done
echo "--- guardrails ---"
code "unknown case -> 404"       404 "$U/api/applications/APP-000000"
code "promote w/o justification" 400 -X POST "$U/api/sandbox/promote" \
     -H 'Content-Type: application/json' -d '{"thresholds":{"dsr_ceiling":34},"justification":" "}'
echo "--- writes ---"
code "sandbox simulate" 200 -X POST "$U/api/sandbox/simulate" -H 'Content-Type: application/json' -d '{"dsr_ceiling":34}'
code "autonomy set"     200 -X POST "$U/api/governance/autonomy" -H 'Content-Type: application/json' -d '{"mode":"ASSIST","kill_switch":false}'
code "doc upload"       200 -X POST "$U/api/applications/APP-104328/documents" -F "file=@demo_files/bank_statement_david_carter_q1_2024.pdf"
echo "--- local model paths ---"
has "council positions are model-authored" '"_source": "llm"' "$U/api/applications/APP-104328/council/stream"
has "copilot streams tokens"  'event: token' -X POST "$U/api/ask" \
    -H 'Content-Type: application/json' -d '{"question":"What is the DSR?","application_id":"APP-104328"}'
has "hardship cue -> support task" '"kind":"Hardship"' -X POST "$U/api/member-assistant" \
    -H 'Content-Type: application/json' -d '{"question":"I lost my job and cannot pay","member_id":"104328"}'
has "outreach draft from model" '"_source":"llm"' -X POST "$U/api/collections/draft" \
    -H 'Content-Type: application/json' -d '{"member_id":"104328","channel":"Email"}'
has "ledger chain intact" '"intact":true' "$U/api/health"

echo
echo "RESULT: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
