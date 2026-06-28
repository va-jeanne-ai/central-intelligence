"""Data-intelligence engine.

The north star (New Documents/north-star-data-intelligence.md): pool data → analyze
the actual data → surface what works / what needs to change → recommend, grounded
PURELY in the data (statistical only, no heuristics) → monitor progress over time.

This package is the engine:
  - registry:  the declarative catalog of outcome metrics (what we measure + the SQL)
  - (next)     snapshot store + compute (track metrics over time)
  - (next)     trend/significance + data-cited recommendations

It generalizes the ``tasks/market_signals.py`` pattern: recompute from the real
tables, no heuristics, fully auditable.
"""
