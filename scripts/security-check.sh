#!/usr/bin/env bash
# security-check.sh — local secret/security scan, mirroring internals_ci-templates scan.yml@v1.
# gitleaks when installed; key-shaped git-grep fallback otherwise.

set -uo pipefail
cd "$(dirname "$0")/.."

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --no-banner --redact
else
  echo "(gitleaks not installed — using git-grep pattern fallback; brew install gitleaks for the real scan)"
  hits=$(git grep -nE 'sk-ant-[A-Za-z0-9_-]{10,}|sk-or-v1-[A-Za-z0-9]{10,}|sk-proj-[A-Za-z0-9_-]{10,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|xox[bp]-[0-9]{5,}' -- ':!*.md' 2>/dev/null || true)
  if [ -n "$hits" ]; then
    echo "$hits"
    echo "FAIL: key-shaped strings found in tracked files" >&2
    exit 1
  fi
  echo "no key-shaped strings in tracked files"
fi
