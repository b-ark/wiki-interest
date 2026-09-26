"""Pure domain logic: models and calculations with no I/O.

Everything here is deterministic and side-effect free so it can be tested with synthetic
series. Thresholds and other tunables are passed in explicitly, never read from the
environment.
"""
