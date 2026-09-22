"""Polish message catalog. Mirrors the key set of :mod:`wiki_interest.i18n.en`."""

from __future__ import annotations

__all__ = ["MESSAGES"]

MESSAGES: dict[str, str] = {
    # -- reliability reasons ---------------------------------------------------------------
    "window_length.ok": "{months} miesięcy danych: wystarczy do porównania rok do roku",
    "window_length.short": "Tylko {months} miesięcy danych: wzrost rok do roku jest niedostępny",
    "window_length.too_short": "Tylko {months} miesięcy danych: za mało, by ocenić trend",
    "completeness.ok": "Brak luk w danych miesięcznych",
    "completeness.gaps": "{missing_months} miesięcy bez danych ({share:.0%} okresu)",
    "completeness.sparse": (
        "{missing_months} miesięcy bez danych ({share:.0%} okresu): szereg jest zbyt rzadki"
    ),
    "spikes.low": "Dni ze skokami to {share:.0%} odsłon: wzrost nie wynika ze skoków",
    "spikes.notable": "Dni ze skokami to {share:.0%} odsłon: część wzrostu może pochodzić z newsów",
    "spikes.dominant": "Dni ze skokami to {share:.0%} odsłon: wzrost wynika ze skoków",
    "spikes.unavailable": "Dane dzienne są niedostępne, więc nie oceniono skoków",
    "trend.significant": "Trend jest istotny statystycznie (p = {p_value:.3f}, {direction})",
    "trend.not_significant": "Trend nie jest istotny statystycznie (p = {p_value:.3f})",
    "trend.unavailable": "Za mało punktów, by przetestować trend",
    "resolution.sitelink": "Artykuł znaleziono przez Wikidata: dopasowanie jest wiarygodne",
    "resolution.search_fallback": (
        "Artykuł znaleziono wyszukiwaniem pełnotekstowym („{title}”): sprawdź, czy to właściwy"
    ),
    "resolution.manual": "Tytuły artykułów podano ręcznie",
    "resolution.not_found": (
        "Brak artykułu w tej edycji: brak artykułu nie oznacza zerowego zainteresowania"
    ),
    "automated.low": "Ruch automatyczny stanowi {share:.0%}: wpływ botów jest niewielki",
    "automated.high": "Ruch automatyczny stanowi {share:.0%}: boty mogą zawyżać liczby",
    "automated.unavailable": "Dane o ruchu automatycznym są niedostępne dla tej edycji i okresu",
    "volume.ok": "Około {views_avg:,.0f} odsłon miesięcznie: wystarczy na stabilny sygnał",
    "volume.low": "Tylko około {views_avg:,.0f} odsłon miesięcznie: sygnał jest zaszumiony",
    "bundle.consistent": "Artykuł główny i cały zestaw poruszają się w tym samym kierunku",
    "bundle.diverges": (
        "Artykuł główny ({main_direction}) i zestaw ({bundle_direction}) się rozchodzą: "
        "wniosek zależy od składu zestawu"
    ),
    # -- labels ------------------------------------------------------------------------------
    "level.high": "wysoka",
    "level.medium": "średnia",
    "level.low": "niska",
    "status.pass": "zaliczone",
    "status.warn": "ostrzeżenie",
    "status.fail": "niezaliczone",
    "status.info": "informacja",
    "direction.rising": "rośnie",
    "direction.falling": "spada",
    "direction.flat": "bez zmian",
    "direction.unknown": "nieznany",
    "profile.early_niche": "wczesna nisza",
    "profile.growth_market": "rynek rosnący",
    "profile.mature_market": "rynek dojrzały",
    "profile.declining": "spadający",
    "profile.insufficient_data": "za mało danych",
    "bundle_status.found": "znaleziono",
    "bundle_status.found_via_search": "znaleziono wyszukiwaniem",
    "bundle_status.not_found": "nie znaleziono",
    "source.sitelink": "sitelink Wikidata",
    "source.wikidata_relation": "relacja w Wikidata",
    "source.lead_link": "link ze wstępu",
    "source.search_fallback": "wyszukiwanie zapasowe",
    "source.manual": "ręcznie",
    "role.main": "główny",
    "role.related": "powiązany",
    "role.manual": "ręcznie",
    "unit.views": "odsłon",
    "unit.per_million": "odsłon na milion",
    "value.na": "b.d.",
    # -- question line ---------------------------------------------------------------------
    "question.compare": "Porównaj zainteresowanie tematem „{topics}” w edycjach {projects}",
    "question.assess": "Oceń, czy zainteresowanie tematem „{topics}” rośnie w edycjach {projects}",
    "question.rank": "Uszereguj edycje {projects} według zainteresowania tematem „{topics}”",
    # -- report sections -------------------------------------------------------------------
    "report.title_default": "Analiza zainteresowania na podstawie odsłon Wikipedii",
    "report.question": "Pytanie",
    "report.audience": "Kontekst",
    "report.key_numbers": "Kluczowe liczby",
    "report.chart": "Wykres",
    "report.charts": "Wykresy",
    "report.verdict": "Wniosek",
    "report.reliability": "Na ile można temu ufać",
    "report.limitations": "Założenia i ograniczenia",
    "report.next_steps": "Co można doprecyzować",
    "report.sources": "Źródła",
    "report.period": "Okres",
    "report.projects": "Edycje",
    "report.topics": "Tematy",
    "report.generated": "Wygenerowano",
    "report.version": "Wersja umiejętności",
    "report.data_through": "Dane do",
    "report.bundle_composition": "Skład zestawu artykułów",
    "report.comparison_table": "Porównanie",
    "report.ranking_table": "Ranking",
    "report.notes": "Uwagi",
    "report.see_summary": "… pełna lista w summary.md",
    "report.no_chart": "Dla tego uruchomienia nie utworzono wykresu",
    # -- table columns ---------------------------------------------------------------------
    "col.topic": "Temat",
    "col.project": "Edycja",
    "col.views_avg": "Odsłon/mies.",
    "col.per_million_avg": "Na milion",
    "col.growth_yoy": "Wzrost r/r",
    "col.growth_halves": "Wzrost H2/H1",
    "col.trend": "Trend",
    "col.reliability": "Wiarygodność",
    "col.rank": "Nr",
    "col.score": "Wynik",
    "col.profile": "Profil",
    "col.article": "Artykuł",
    "col.role": "Rola",
    "col.weight": "Waga",
    "col.source": "Źródło",
    "col.status": "Status",
    "col.rationale": "Dlaczego",
    # -- agent summary ---------------------------------------------------------------------
    "summary.answer": "Odpowiedź",
    "summary.key_numbers": "Kluczowe liczby",
    "summary.trust": "Na ile można temu ufać",
    "summary.caveats": "Zastrzeżenia",
    "summary.refine": "Co można doprecyzować",
    "summary.artifacts": "Pliki",
    "summary.clarification_needed": "Potrzebne doprecyzowanie",
    "summary.candidates": "Kandydaci",
    "summary.clarification_hint": (
        "Zapytaj użytkownika, o którą encję chodzi, i uruchom ponownie z tym qid w żądaniu"
    ),
    "summary.bundles": "Analizowane artykuły",
    # -- charts ----------------------------------------------------------------------------
    "chart.axis_per_million": "odsłon na milion odsłon edycji",
    "chart.axis_views": "odsłon miesięcznie",
    "chart.footnote": "Źródło: {source} · Okres: {period}",
    "chart.growth_title": "Wzrost rok do roku",
    "chart.trend_title": "Zainteresowanie w czasie z linią trendu",
    "chart.compare_title": "Zainteresowanie według edycji",
    "chart.no_data": "Brak danych za ten okres",
    "chart.score_title": "Wynik rankingu",
    "chart.axis_score": "wynik (0 = najsłabszy, 1 = najsilniejszy w zestawie)",
    "chart.axis_growth": "wzrost rok do roku, %",
    "chart.growth_halves_title": "Wzrost: druga połowa okresu do pierwszej",
    # -- werdykty ----------------------------------------------------------------------------
    "verdict.assess.headline": (
        "Zainteresowanie tematem „{topic}” w {project}: trend {direction}, {growth} rok do roku; "
        "zaufanie: {level}"
    ),
    "verdict.compare.share": "Największy udział uwagi: {label} ({value} na milion)",
    "verdict.compare.share_absolute": "Najwięcej odsłon: {label} ({value} odsłon/mies.)",
    "verdict.compare.growth": "najszybszy wzrost: {label} ({growth})",
    "verdict.compare.decline": (
        "zainteresowanie nie rośnie w żadnej edycji; najmniejszy spadek: {label} ({growth})"
    ),
    "verdict.compare.growth_unknown": "wzrostu nie udało się zmierzyć",
    "verdict.rank.headline": (
        "Najbardziej obiecująca grupa odbiorców: {label} ({profile}, wynik {score})"
    ),
    "verdict.rank.headline_declining": (
        "Zainteresowanie spada we wszystkich edycjach; "
        "relatywnie najsilniejsza grupa: {label} ({profile}, wynik {score})"
    ),
    "verdict.none.headline": (
        "Brak danych do analizy tematów {topics}: nie znaleziono artykułów w {projects}"
    ),
    "verdict.bullet.pair": (
        "{label}: {per_million} na milion, {views} odsłon/mies., wzrost {growth}, zaufanie {level}"
    ),
    "verdict.bullet.pair_absolute": (
        "{label}: {views} odsłon/mies., wzrost {growth}, zaufanie {level}"
    ),
    "verdict.bullet.not_found": "{label}: brak artykułu w tej edycji",
    "verdict.bullet.seasonality": (
        "{label}: silna sezonowość ({strength} wariancji): porównuj te same miesiące rok do roku"
    ),
    "verdict.bullet.main_vs_bundle": "{label}: sam artykuł główny: trend {direction} ({growth})",
    "rank.rationale": "{profile}: wzrost {growth}, {views} odsłon/mies., zaufanie {level}",
    "rank.rationale.insufficient": "za mało danych do rankingu",
    "note.not_found": "brak artykułu w tej edycji",
    "note.search_fallback": "artykuł znaleziony wyszukiwaniem",
    # -- ograniczenia i kolejne kroki --------------------------------------------------------
    "limitation.proxy": (
        "Czytelnictwo Wikipedii mierzy ciekawość, a nie gotowość do płacenia: traktuj wynik "
        "jako sygnał do weryfikacji, a nie jako popyt."
    ),
    "limitation.coverage": (
        "Edycje różnią się jakością opisu tematu; brakujący lub krótki artykuł zaniża sygnał "
        "niezależnie od zainteresowania odbiorców."
    ),
    "limitation.bots": (
        "Filtrowanie botów po stronie Wikimedia jest niedoskonałe; kontrole ruchu automatycznego "
        "i skoków wychwytują tylko część."
    ),
    "limitation.bundle": (
        "Liczby zależą od tego, które artykuły policzono; podano wyniki zarówno dla pakietu, "
        "jak i dla artykułu głównego."
    ),
    "limitation.missing_titles": "Te żądane tytuły nie istnieją i zostały pominięte: {titles}",
    "limitation.not_found": (
        "Dla tematu „{topic}” brak artykułu w {projects}: te edycje oznaczono jako „brak "
        "artykułu”, a nie jako zerowe zainteresowanie."
    ),
    "limitation.search_fallback": (
        "W {projects} artykuł znaleziono wyszukiwaniem pełnotekstowym; sprawdź, czy to właściwy "
        "artykuł."
    ),
    "limitation.short_window": (
        "Tylko {months} miesięcy danych: wzrost rok do roku jest niedostępny, a test trendu słaby."
    ),
    "limitation.absolute": (
        "Porównano surowe liczby odsłon bez normalizacji względem wielkości edycji."
    ),
    "next.extend_period": ("Wydłuż okres (np. 36 lub 60 miesięcy), aby sprawdzić trwałość trendu."),
    "next.add_projects": (
        "Dodaj inne edycje, aby zobaczyć, czy obraz jest specyficzny dla {projects}."
    ),
    "next.prune_bundle": (
        "Wyklucz artykuły spoza tematu (exclude_titles) albo ustal listę na stałe (bundle: manual)."
    ),
    "next.absolute": (
        "Porównaj surowe odsłony (normalization: absolute), aby ocenić wielkość grupy odbiorców, "
        "a nie udział."
    ),
    "next.per_million": "Porównaj udziały na milion, aby usunąć wpływ wielkości edycji.",
    "next.pin_title": "Podaj dokładny tytuł artykułu dla {projects} przez extra_titles.",
    "next.research": "Zbadać jako następną: {label} ({profile}).",
}
