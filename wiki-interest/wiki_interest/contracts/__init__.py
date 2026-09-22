"""Data contracts shared with the agent.

Pydantic models for ``request.json`` (what the agent asks for) and ``summary.json`` (what the
pipeline produces). These schemas are versioned with ``schema_version``; any breaking change
bumps it and updates ``references/request-schema.md``.
"""
