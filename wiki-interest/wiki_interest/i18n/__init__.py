"""Report localisation: message catalogs and the :class:`Translator`.

Lives outside the hexagonal layers because it is pure data plus string formatting: it imports
nothing from the application and is used by adapters (renderers) and, through them, by the
composition root. Catalogs are Python modules so they are versioned, type-checked and tested
like code; see :mod:`wiki_interest.i18n.en` for the reference key set.
"""

from wiki_interest.i18n.formatting import NumberStyle, style_for
from wiki_interest.i18n.translator import (
    CATALOGS,
    DEFAULT_LANGUAGE,
    LABELS,
    SUPPORTED_LANGUAGES,
    Translator,
)

__all__ = [
    "CATALOGS",
    "DEFAULT_LANGUAGE",
    "LABELS",
    "SUPPORTED_LANGUAGES",
    "NumberStyle",
    "Translator",
    "style_for",
]
