"""Russian message catalog. Mirrors the key set of :mod:`wiki_interest.i18n.en`."""

# ruff: noqa: RUF001  -- Cyrillic letters are homoglyphs of Latin ones by nature.

from __future__ import annotations

__all__ = ["MESSAGES"]

MESSAGES: dict[str, str] = {
    # -- reliability reasons ---------------------------------------------------------------
    "window_length.ok": "{months} месяцев данных: достаточно для сравнения год к году",
    "window_length.short": "Только {months} месяцев данных: рост год к году недоступен",
    "window_length.too_short": "Только {months} месяцев данных: слишком мало для оценки тренда",
    "completeness.ok": "В месячных данных нет пропусков",
    "completeness.gaps": "{missing_months} месяцев без данных ({share:.0%} периода)",
    "completeness.sparse": (
        "{missing_months} месяцев без данных ({share:.0%} периода): ряд слишком разреженный"
    ),
    "spikes.low": "На дни всплесков приходится {share:.0%} просмотров: рост не вызван всплесками",
    "spikes.notable": (
        "На дни всплесков приходится {share:.0%} просмотров: часть роста может быть новостной"
    ),
    "spikes.dominant": (
        "На дни всплесков приходится {share:.0%} просмотров: рост вызван всплесками"
    ),
    "spikes.unavailable": "Дневные данные недоступны, поэтому всплески оценить не удалось",
    "trend.significant": "Тренд статистически значим (p = {p_value:.3f}, {direction})",
    "trend.not_significant": "Тренд статистически незначим (p = {p_value:.3f})",
    "trend.unavailable": "Слишком мало точек для проверки тренда",
    "resolution.sitelink": "Статья найдена через Wikidata: соответствие надёжное",
    "resolution.search_fallback": (
        "Статья найдена полнотекстовым поиском («{title}»): проверьте, что это именно она"
    ),
    "resolution.manual": "Названия статей заданы вручную",
    "resolution.not_found": (
        "В этом разделе нет статьи: отсутствие статьи не означает нулевой интерес"
    ),
    "automated.low": "Автоматизированный трафик составляет {share:.0%}: влияние ботов невелико",
    "automated.high": (
        "Автоматизированный трафик составляет {share:.0%}: боты могут завышать цифры"
    ),
    "automated.unavailable": (
        "Данные об автоматизированном трафике для этого раздела и периода недоступны"
    ),
    "volume.ok": "Около {views_avg:,.0f} просмотров в месяц: достаточно для устойчивого сигнала",
    "volume.low": "Только около {views_avg:,.0f} просмотров в месяц: сигнал зашумлён",
    "bundle.consistent": "Главная статья и вся связка движутся в одном направлении",
    "bundle.diverges": (
        "Главная статья ({main_direction}) и связка ({bundle_direction}) расходятся: "
        "вывод зависит от состава связки"
    ),
    # -- labels ------------------------------------------------------------------------------
    "level.high": "высокая",
    "level.medium": "средняя",
    "level.low": "низкая",
    "status.pass": "пройдено",
    "status.warn": "предупреждение",
    "status.fail": "не пройдено",
    "status.info": "справочно",
    "direction.rising": "растёт",
    "direction.falling": "падает",
    "direction.flat": "без изменений",
    "direction.unknown": "неизвестно",
    "profile.early_niche": "ранняя ниша",
    "profile.growth_market": "растущий рынок",
    "profile.mature_market": "зрелый рынок",
    "profile.declining": "снижается",
    "profile.insufficient_data": "недостаточно данных",
    "bundle_status.found": "найдено",
    "bundle_status.found_via_search": "найдено поиском",
    "bundle_status.not_found": "не найдено",
    "source.sitelink": "sitelink Wikidata",
    "source.wikidata_relation": "связь в Wikidata",
    "source.lead_link": "ссылка из преамбулы",
    "source.search_fallback": "резервный поиск",
    "source.manual": "вручную",
    "role.main": "главная",
    "role.related": "смежная",
    "role.manual": "вручную",
    "unit.views": "просмотров",
    "unit.per_million": "просмотров на миллион",
    "value.na": "н/д",
    # -- question line ---------------------------------------------------------------------
    "question.compare": "Сравнить интерес к теме «{topics}» в разделах {projects}",
    "question.assess": "Оценить, растёт ли интерес к теме «{topics}» в разделах {projects}",
    "question.rank": "Ранжировать разделы {projects} по интересу к теме «{topics}»",
    # -- report sections -------------------------------------------------------------------
    "report.title_default": "Анализ интереса по просмотрам Википедии",
    "report.question": "Вопрос",
    "report.audience": "Контекст",
    "report.key_numbers": "Ключевые числа",
    "report.chart": "График",
    "report.charts": "Графики",
    "report.verdict": "Вывод",
    "report.reliability": "Насколько можно доверять",
    "report.limitations": "Допущения и ограничения",
    "report.next_steps": "Что можно уточнить",
    "report.sources": "Источники",
    "report.period": "Период",
    "report.projects": "Разделы",
    "report.topics": "Темы",
    "report.generated": "Сформировано",
    "report.version": "Версия навыка",
    "report.data_through": "Данные по",
    "report.bundle_composition": "Состав связки статей",
    "report.comparison_table": "Сравнение",
    "report.ranking_table": "Рейтинг",
    "report.notes": "Примечания",
    "report.see_summary": "… полный список в summary.md",
    "report.no_chart": "Для этого запуска график не построен",
    # -- table columns ---------------------------------------------------------------------
    "col.topic": "Тема",
    "col.project": "Раздел",
    "col.views_avg": "Просмотров/мес.",
    "col.per_million_avg": "На миллион",
    "col.growth_yoy": "Рост г/г",
    "col.growth_halves": "Рост П2/П1",
    "col.trend": "Тренд",
    "col.reliability": "Надёжность",
    "col.rank": "№",
    "col.score": "Балл",
    "col.profile": "Профиль",
    "col.article": "Статья",
    "col.role": "Роль",
    "col.weight": "Вес",
    "col.source": "Источник",
    "col.status": "Статус",
    "col.rationale": "Почему",
    # -- agent summary ---------------------------------------------------------------------
    "summary.answer": "Ответ",
    "summary.key_numbers": "Ключевые числа",
    "summary.trust": "Насколько можно доверять",
    "summary.caveats": "Оговорки",
    "summary.refine": "Что можно уточнить",
    "summary.artifacts": "Файлы",
    "summary.clarification_needed": "Нужно уточнение",
    "summary.candidates": "Кандидаты",
    "summary.clarification_hint": (
        "Спросите пользователя, какую сущность он имеет в виду, и повторите запуск с этим qid"
    ),
    "summary.bundles": "Проанализированные статьи",
    # -- charts ----------------------------------------------------------------------------
    "chart.axis_per_million": "просмотров на миллион просмотров раздела",
    "chart.axis_views": "просмотров в месяц",
    "chart.footnote": "Источник: {source} · Период: {period}",
    "chart.growth_title": "Рост год к году",
    "chart.trend_title": "Интерес во времени с линией тренда",
    "chart.compare_title": "Интерес по разделам",
    "chart.no_data": "Нет данных за этот период",
}
