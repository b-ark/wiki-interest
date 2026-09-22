"""Czech message catalog. Mirrors the key set of :mod:`wiki_interest.i18n.en`."""

from __future__ import annotations

__all__ = ["MESSAGES"]

MESSAGES: dict[str, str] = {
    # -- reliability reasons ---------------------------------------------------------------
    "window_length.ok": "{months} měsíců dat: dost pro meziroční srovnání",
    "window_length.short": "Jen {months} měsíců dat: meziroční růst není k dispozici",
    "window_length.too_short": "Jen {months} měsíců dat: příliš málo pro posouzení trendu",
    "completeness.ok": "V měsíčních datech nejsou mezery",
    "completeness.gaps": "{missing_months} měsíců bez dat ({share:.0%} období)",
    "completeness.sparse": (
        "{missing_months} měsíců bez dat ({share:.0%} období): řada je příliš řídká"
    ),
    "spikes.low": "Dny se špičkami tvoří {share:.0%} zobrazení: růst není dán špičkami",
    "spikes.notable": (
        "Dny se špičkami tvoří {share:.0%} zobrazení: část růstu může být zpravodajská"
    ),
    "spikes.dominant": "Dny se špičkami tvoří {share:.0%} zobrazení: růst je dán špičkami",
    "spikes.unavailable": "Denní data nejsou k dispozici, špičky proto nebylo možné posoudit",
    "trend.significant": "Trend je statisticky významný (p = {p_value:.3f}, {direction})",
    "trend.not_significant": "Trend není statisticky významný (p = {p_value:.3f})",
    "trend.unavailable": "Příliš málo bodů pro test trendu",
    "resolution.sitelink": "Článek nalezen přes Wikidata: přiřazení je spolehlivé",
    "resolution.search_fallback": (
        "Článek nalezen fulltextovým vyhledáváním („{title}“): ověřte, že jde o ten správný"
    ),
    "resolution.manual": "Názvy článků byly zadány ručně",
    "resolution.not_found": "V této edici článek chybí: chybějící článek neznamená nulový zájem",
    "automated.low": "Automatizovaný provoz tvoří {share:.0%}: vliv botů je malý",
    "automated.high": "Automatizovaný provoz tvoří {share:.0%}: boti mohou čísla nadhodnocovat",
    "automated.unavailable": (
        "Data o automatizovaném provozu nejsou pro tuto edici a období k dispozici"
    ),
    "volume.ok": "Přibližně {views_avg:,.0f} zobrazení měsíčně: dost pro stabilní signál",
    "volume.low": "Jen přibližně {views_avg:,.0f} zobrazení měsíčně: signál je zašuměný",
    "bundle.consistent": "Hlavní článek i celý svazek se vyvíjejí stejným směrem",
    "bundle.diverges": (
        "Hlavní článek ({main_direction}) a svazek ({bundle_direction}) se rozcházejí: "
        "závěr závisí na složení svazku"
    ),
    # -- labels ------------------------------------------------------------------------------
    "level.high": "vysoká",
    "level.medium": "střední",
    "level.low": "nízká",
    "status.pass": "splněno",
    "status.warn": "varování",
    "status.fail": "nesplněno",
    "status.info": "informace",
    "direction.rising": "roste",
    "direction.falling": "klesá",
    "direction.flat": "beze změny",
    "direction.unknown": "neznámý",
    "profile.early_niche": "raná nika",
    "profile.growth_market": "rostoucí trh",
    "profile.mature_market": "zralý trh",
    "profile.declining": "klesající",
    "profile.insufficient_data": "nedostatek dat",
    "bundle_status.found": "nalezeno",
    "bundle_status.found_via_search": "nalezeno vyhledáváním",
    "bundle_status.not_found": "nenalezeno",
    "source.sitelink": "sitelink Wikidata",
    "source.wikidata_relation": "vazba ve Wikidata",
    "source.lead_link": "odkaz z úvodu",
    "source.search_fallback": "záložní vyhledávání",
    "source.manual": "ručně",
    "role.main": "hlavní",
    "role.related": "související",
    "role.manual": "ručně",
    "unit.views": "zobrazení",
    "unit.per_million": "zobrazení na milion",
    "value.na": "n/a",
    # -- question line ---------------------------------------------------------------------
    "question.compare": "Porovnat zájem o téma „{topics}“ v edicích {projects}",
    "question.assess": "Posoudit, zda zájem o téma „{topics}“ v edicích {projects} roste",
    "question.rank": "Seřadit edice {projects} podle zájmu o téma „{topics}“",
    # -- report sections -------------------------------------------------------------------
    "report.title_default": "Analýza zájmu podle zobrazení Wikipedie",
    "report.question": "Otázka",
    "report.audience": "Kontext",
    "report.key_numbers": "Klíčová čísla",
    "report.chart": "Graf",
    "report.charts": "Grafy",
    "report.verdict": "Závěr",
    "report.reliability": "Nakolik tomu lze věřit",
    "report.limitations": "Předpoklady a omezení",
    "report.next_steps": "Co lze upřesnit",
    "report.sources": "Zdroje",
    "report.period": "Období",
    "report.projects": "Edice",
    "report.topics": "Témata",
    "report.generated": "Vygenerováno",
    "report.version": "Verze dovednosti",
    "report.data_through": "Data do",
    "report.bundle_composition": "Složení svazku článků",
    "report.comparison_table": "Srovnání",
    "report.ranking_table": "Pořadí",
    "report.notes": "Poznámky",
    "report.see_summary": "… úplný seznam je v summary.md",
    "report.no_chart": "Pro tento běh nebyl vytvořen žádný graf",
    # -- table columns ---------------------------------------------------------------------
    "col.topic": "Téma",
    "col.project": "Edice",
    "col.views_avg": "Zobrazení/měs.",
    "col.per_million_avg": "Na milion",
    "col.growth_yoy": "Růst meziročně",
    "col.growth_halves": "Růst H2/H1",
    "col.trend": "Trend",
    "col.reliability": "Spolehlivost",
    "col.rank": "Poř.",
    "col.score": "Skóre",
    "col.profile": "Profil",
    "col.article": "Článek",
    "col.role": "Role",
    "col.weight": "Váha",
    "col.source": "Zdroj",
    "col.status": "Stav",
    "col.rationale": "Proč",
    # -- agent summary ---------------------------------------------------------------------
    "summary.answer": "Odpověď",
    "summary.key_numbers": "Klíčová čísla",
    "summary.trust": "Nakolik tomu lze věřit",
    "summary.caveats": "Výhrady",
    "summary.refine": "Co lze upřesnit",
    "summary.artifacts": "Soubory",
    "summary.clarification_needed": "Je třeba upřesnění",
    "summary.candidates": "Kandidáti",
    "summary.clarification_hint": (
        "Zeptejte se uživatele, kterou entitu má na mysli, a spusťte běh znovu s tímto qid"
    ),
    "summary.bundles": "Analyzované články",
    # -- charts ----------------------------------------------------------------------------
    "chart.axis_per_million": "zobrazení na milion zobrazení edice",
    "chart.axis_views": "zobrazení měsíčně",
    "chart.footnote": "Zdroj: {source} · Období: {period}",
    "chart.growth_title": "Meziroční růst",
    "chart.trend_title": "Zájem v čase s linií trendu",
    "chart.compare_title": "Zájem podle edic",
    "chart.no_data": "Za toto období nejsou data",
}
