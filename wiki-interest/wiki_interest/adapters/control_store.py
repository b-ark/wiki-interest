"""Control baskets as JSON files, one per edition, next to the HTTP cache.

A basket is small (a hundred titles) and must survive between runs so every request on an
edition compares against the same articles; the file says when it was built and from which
month, so ``method.md`` can name it.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from wiki_interest.ports.control import ControlBasket

__all__ = ["JsonBasketStore"]


class JsonBasketStore:
    """Implements :class:`~wiki_interest.ports.control.BasketStore` over ``<dir>/<project>.json``.

    Args:
        directory: Where the files live; created on the first save.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def load(self, project: str) -> ControlBasket | None:
        """The stored basket of ``project``; ``None`` if missing or unreadable."""
        path = self._path(project)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ControlBasket(
                project=str(data["project"]),
                reference_month=date.fromisoformat(str(data["reference_month"]) + "-01"),
                built=date.fromisoformat(str(data["built"])),
                seed=int(data["seed"]),
                titles=tuple(str(t) for t in data["titles"]),
            )
        except (ValueError, KeyError, TypeError):
            return None

    def save(self, basket: ControlBasket) -> None:
        """Write ``basket`` as JSON (UTF-8, one file per edition)."""
        self._directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "project": basket.project,
            "reference_month": f"{basket.reference_month:%Y-%m}",
            "built": basket.built.isoformat(),
            "seed": basket.seed,
            "titles": list(basket.titles),
        }
        self._path(basket.project).write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )

    def _path(self, project: str) -> Path:
        return self._directory / f"{project}.json"
