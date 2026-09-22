"""Ports: Protocol interfaces the application depends on.

A port describes *what* the application needs (pageview series, title resolution, caching,
rendering) without saying *how*. Adapters implement them; tests substitute in-memory fakes.
"""
