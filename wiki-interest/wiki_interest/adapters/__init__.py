"""Adapters: concrete implementations of the ports.

Wikimedia REST pageviews, Wikidata and MediaWiki clients, the on-disk cache, and the chart and
report renderers. Adapters may import ``ports``, ``contracts`` and ``domain``; nothing imports
an adapter except the composition root in ``cli``.
"""
