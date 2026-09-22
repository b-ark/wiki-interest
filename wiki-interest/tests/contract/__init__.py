"""Contract tests: the adapters replayed against recorded real API responses.

``record_fixtures.py`` defines the cases and re-records them from the live APIs; the tests
replay the recorded exchanges with respx and assert on parsed values. Because both sides run
the same case functions, a change in how an adapter builds a URL fails loudly here.
"""
