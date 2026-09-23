"""Message lookup with parameter formatting and an English fallback.

Catalogs are Python dictionaries (no file I/O, no gettext tooling) because the string set is
small, versioned with the code, and must be importable wherever the reports are rendered.
An unknown key raises :class:`KeyError` on purpose: a mistyped key must fail a test, not
print an empty label into a report. Only English has a catalog; for any other report language
the agent translates the labels a report uses, and :meth:`Translator.override` applies them.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from string import Formatter
from typing import Any

from wiki_interest.i18n import en
from wiki_interest.i18n.formatting import (
    NumberStyle,
    format_number,
    format_percent,
    localise_separators,
    style_for,
)

__all__ = ["CATALOGS", "DEFAULT_LANGUAGE", "SUPPORTED_LANGUAGES", "Translator"]

SUPPORTED_LANGUAGES: tuple[str, ...] = ("en",)
"""Report languages with a catalog. Any other language gets the English templates, and the
agent translates the interface labels the report uses (``facts.template.ui``)."""

DEFAULT_LANGUAGE = "en"
"""Language used for keys missing from a catalog and for unsupported request languages."""

CATALOGS: Mapping[str, Mapping[str, str]] = {
    "en": en.MESSAGES,
}

_ENUM_PARAMS: Mapping[str, str] = {"direction": "direction"}
"""Template parameters whose raw value is an enum member; they are replaced by the label
``<namespace>.<value>`` so a translated sentence never contains the raw value ``rising``."""


class _MessageFormatter(Formatter):
    """``str.format`` with enum-label substitution, tolerant specs and locale separators.

    Tolerance matters because reason parameters come from another module: if a ``share`` ever
    arrives as the string ``"n/a"``, the report should show ``n/a`` rather than crash.
    """

    def __init__(self, translator: Translator) -> None:
        super().__init__()
        self._translator = translator

    def get_field(self, field_name: str, args: Any, kwargs: Any) -> Any:
        value, key = super().get_field(field_name, args, kwargs)
        namespace = _ENUM_PARAMS.get(field_name)
        if namespace is not None and isinstance(value, str):
            label_key = f"{namespace}.{value}"
            if self._translator.has(label_key):
                value = self._translator.t(label_key)
        return value, key

    def format_field(self, value: Any, format_spec: str) -> Any:
        try:
            text = super().format_field(value, format_spec)
        except (ValueError, TypeError):
            return str(value)
        if isinstance(value, int | float) and "," in format_spec:
            return localise_separators(text, self._translator.number_style)
        return text


class Translator:
    """Resolves message keys for one report language.

    Args:
        language: Requested report language. Unsupported codes silently resolve to English:
            the request schema already validated the shape, and refusing a report over an
            unknown language would be worse than an English one.
    """

    def __init__(self, language: str) -> None:
        self.requested = language
        """The language asked for; ``language`` falls back to English without a catalog."""
        self.language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        self._catalog = CATALOGS[self.language]
        self._fallback = CATALOGS[DEFAULT_LANGUAGE]
        self._overrides: dict[str, str] = {}
        self._used: set[str] | None = None
        self.number_style: NumberStyle = style_for(language)
        self._formatter = _MessageFormatter(self)

    @property
    def has_catalog(self) -> bool:
        """Whether the requested language has its own catalog (else the agent translates)."""
        return self.requested in SUPPORTED_LANGUAGES

    def override(self, messages: Mapping[str, str]) -> None:
        """Use ``messages`` (translations the agent wrote) before the catalogs.

        Only keys the English catalog knows are taken, so a stray entry cannot shadow a
        message under a new name.
        """
        self._overrides.update({k: v for k, v in messages.items() if k in self._fallback})

    def english(self, key: str) -> str:
        """The English template of ``key``, placeholders unformatted."""
        return self._fallback[key]

    @contextmanager
    def recording(self) -> Iterator[set[str]]:
        """Collect the keys looked up inside the block (the labels a renderer uses)."""
        used: set[str] = set()
        self._used = used
        try:
            yield used
        finally:
            self._used = None

    def translates(self, key: str) -> bool:
        """Whether ``key`` reads in the requested language: its catalog, or the agent's text."""
        return self.has_catalog or key in self._overrides

    def has(self, key: str) -> bool:
        """Whether ``key`` exists in this language or the English fallback."""
        return key in self._catalog or key in self._fallback

    def t(self, key: str, **params: object) -> str:
        """Return the message for ``key`` with ``params`` substituted.

        Args:
            key: Namespaced message key, e.g. ``"spikes.notable"``.
            **params: Template fields; numbers are formatted by the spec in the template.

        Returns:
            The localised message.

        Raises:
            KeyError: If the key is unknown in both the language and the fallback, or the
                template names a parameter that was not supplied.
        """
        if self._used is not None:
            self._used.add(key)
        template = self._overrides.get(key) or self._catalog.get(key)
        if template is None:
            template = self._fallback.get(key)
        if template is None:
            msg = f"Unknown message key {key!r} for language {self.language!r}"
            raise KeyError(msg)
        return self._formatter.vformat(template, (), params)

    def label(self, namespace: str, value: object) -> str:
        """Translate an enum-like value: ``label("level", ReliabilityLevel.HIGH)``.

        ``str(value)`` is used so both ``StrEnum`` members and plain strings (as found in
        ``summary.json``) resolve to ``<namespace>.<value>``.
        """
        return self.t(f"{namespace}.{value}")

    def number(self, value: float | None, decimals: int = 0) -> str:
        """Format a number in the report locale, or the ``n/a`` label for ``None``."""
        if value is None:
            return self.t("value.na")
        return format_number(value, self.number_style, decimals)

    def date(self, value: dt.date) -> str:
        """A calendar day in the report's convention (``2025-03-14``, ``14.03.2025``)."""
        return self.t("format.date", day=value.day, month=value.month, year=value.year)

    def month_year(self, value: dt.date) -> str:
        """A month in the report's convention (``2025-03``, ``03.2025``).

        Numeric on purpose: a month name inside a sentence needs a grammatical case in the
        Slavic languages ("з березня"), which a template cannot choose.
        """
        return self.t("format.month_year", month=value.month, year=value.year)

    def month_name(self, month: int) -> str:
        """Name of a calendar month (1-12) in the nominative, for "peak month: September"."""
        return self.t(f"month.{month}")

    def percent(self, value: float | None, decimals: int = 0, *, signed: bool = False) -> str:
        """Format a fraction as a percentage in the report locale, or ``n/a`` for ``None``."""
        if value is None:
            return self.t("value.na")
        return format_percent(value, self.number_style, decimals, signed=signed)
