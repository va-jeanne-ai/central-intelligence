#!/usr/bin/env bash
# verify.sh — the single local proof command (SOP 18). The local mirror of CI:
# agents and humans run the SAME command. "Prove the work before asking for trust."
#
# HONESTY RULE: a stage that isn't configured yet reports SKIP with a reason —
# never fake a green stage. Ratchet SKIPs to real stages as the repo grows them.
#
# Monorepo layout: frontend/ (Next.js 14) + backend/ (Python, pytest via backend/.venv).
# NOTE: `next build` corrupts a running `next dev` server — restart dev clean after
# running this (dev must be on port 3000, never auto-bumped).
#
# Exit: 0 = every real stage passed; 1 = at least one real stage failed.

set -uo pipefail
cd "$(dirname "$0")/.."

PASS=0; FAIL=0
declare -a SUMMARY

run_stage() { local name="$1"; shift
  printf '\n=== %s ===\n' "$name"
  if "$@"; then SUMMARY+=("PASS  $name"); PASS=$((PASS+1))
  else SUMMARY+=("FAIL  $name"); FAIL=$((FAIL+1)); fi
}
skip_stage() { printf '\n=== %s ===\nSKIP: %s\n' "$1" "$2"; SUMMARY+=("SKIP  $1 — $2"); }

frontend_lint()      { (cd frontend && npm run --silent lint); }
frontend_typecheck() { (cd frontend && npx tsc --noEmit); }
frontend_tests()     { (cd frontend && npm run --silent test); }
frontend_build()     { (cd frontend && npm run --silent build); }
backend_tests()      { (cd backend && .venv/bin/python -m pytest tests -q); }

# Deterministic gates FIRST — cheap checks fail before slow ones run.

# 1. Format
skip_stage "format" "no prettier/ruff config in repo — ratchet later"

# 2. Lint
run_stage "frontend-lint" frontend_lint

# 3. Typecheck
run_stage "frontend-typecheck" frontend_typecheck

# 4. Tests
run_stage "frontend-tests" frontend_tests
run_stage "backend-tests" backend_tests

# 5. Build — Vercel parity: deploys fail on lint/type errors that dev mode hides
run_stage "frontend-build" frontend_build

# 6. Security scan
run_stage "security" ./scripts/security-check.sh

printf '\n========== verify.sh summary ==========\n'
printf '%s\n' "${SUMMARY[@]}"
printf 'passed: %d  failed: %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
