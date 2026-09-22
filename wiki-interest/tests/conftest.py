"""Root test configuration: shared fixtures built from ``tests/fixtures``."""

import pytest

from fixtures.summaries import example_summary
from wiki_interest.contracts.summary import AnalysisSummary


@pytest.fixture
def compare_summary() -> AnalysisSummary:
    """The English two-edition comparison used by most renderer tests."""
    return example_summary()
