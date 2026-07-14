"""Parity baselines for the productization refactor.

Fixtures here freeze the current (Greg/WGR) instance behavior — prompt text,
per-table row counts, metric values — so every productization phase can prove
it changed nothing for the existing client before release. See
docs/staging-parity-runbook.html for how these gate a release.
"""
