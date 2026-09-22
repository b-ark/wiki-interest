"""Wikipedia pageview interest analysis for product decisions.

The package is organised as a small hexagonal application:

* ``domain``      - pure calculations (metrics, trend tests, reliability, ranking).
* ``contracts``   - pydantic schemas shared with the agent (``request.json``, ``summary.json``).
* ``ports``       - Protocol interfaces the application needs from the outside world.
* ``application`` - use-cases that orchestrate ports and domain functions.
* ``adapters``    - concrete implementations of the ports (HTTP clients, cache, renderers).
* ``cli``         - the typer application behind ``scripts/``; the only composition root.

Dependencies point inwards only; ``import-linter`` enforces this in CI.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
