"""Exception hierarchy shared by every layer.

Each error carries the process exit code the CLI should use, so the mapping from failure to
exit code lives in one place and the agent can branch on it reliably (see ``SKILL.md``):

* 2 - the request is invalid; fix it and retry.
* 3 - clarification needed; ask the user, do not guess.
* 4 - an upstream service failed after retries; try again later.
* 5 - an internal error; report it with the traceback.

Errors are raised deep inside adapters or use-cases and caught exactly once, in ``cli``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wiki_interest.domain.models import EntityCandidate

__all__ = [
    "ClarificationNeededError",
    "DataUnavailableError",
    "RenderError",
    "RequestValidationError",
    "UpstreamError",
    "WikiInterestError",
]


class WikiInterestError(Exception):
    """Base class for all errors raised by the package.

    Attributes:
        exit_code: Process exit code the CLI maps this error to.
        hint: One actionable sentence for the agent (what to do next), or ``None``.
    """

    exit_code: int = 5

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


class RequestValidationError(WikiInterestError):
    """The request could not be validated against the contract."""

    exit_code = 2


class ClarificationNeededError(WikiInterestError):
    """The pipeline cannot continue without input from the user.

    Raised when a topic query matches several plausible Wikidata entities and none is a clear
    winner. Guessing here would silently analyse the wrong subject, so the agent must show the
    candidates and ask.

    Attributes:
        topic_id: Identifier of the ambiguous topic in the request.
        candidates: Entities the query matched, best first.
    """

    exit_code = 3

    def __init__(
        self,
        message: str,
        *,
        topic_id: str,
        candidates: Sequence[EntityCandidate],
        hint: str | None = None,
    ) -> None:
        super().__init__(message, hint=hint)
        self.topic_id = topic_id
        self.candidates = tuple(candidates)


class UpstreamError(WikiInterestError):
    """A Wikimedia service failed or was unreachable after the configured retries.

    Attributes:
        retryable: Whether repeating the same request later is likely to succeed
            (timeouts, 5xx, rate limiting) as opposed to a persistent failure.
    """

    exit_code = 4

    def __init__(self, message: str, *, retryable: bool, hint: str | None = None) -> None:
        super().__init__(message, hint=hint)
        self.retryable = retryable


class DataUnavailableError(WikiInterestError):
    """No usable data exists for the whole request (for example, a period before 2015-07).

    Partial gaps are not errors: they are recorded in the series as missing points and lower the
    reliability assessment. This error is for the case where nothing can be analysed at all.
    """

    exit_code = 4


class RenderError(WikiInterestError):
    """A chart or report could not be produced from an otherwise valid summary."""

    exit_code = 5
