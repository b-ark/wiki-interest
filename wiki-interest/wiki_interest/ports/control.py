"""Port: where an edition's control basket is kept between runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

__all__ = ["BasketStore", "ControlBasket"]


@dataclass(frozen=True, slots=True)
class ControlBasket:
    """The control articles of one edition: popular articles drawn at random, outliers left out.

    Attributes:
        project: The edition (``ru.wikipedia``).
        reference_month: The month whose top list the articles were drawn from.
        built: The day the basket was built.
        seed: The seed of the draw.
        titles: The articles, in the order drawn.
    """

    project: str
    reference_month: date
    built: date
    seed: int
    titles: tuple[str, ...]


class BasketStore(Protocol):
    """Keeps one basket per edition."""

    def load(self, project: str) -> ControlBasket | None:
        """The stored basket of ``project``, or ``None``."""
        ...

    def save(self, basket: ControlBasket) -> None:
        """Store ``basket``, replacing the edition's previous one."""
        ...
