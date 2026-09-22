"""Ukrainian message catalog. Mirrors the key set of :mod:`wiki_interest.i18n.en`."""

# ruff: noqa: RUF001  -- Cyrillic letters are homoglyphs of Latin ones by nature.

from __future__ import annotations

__all__ = ["MESSAGES"]

MESSAGES: dict[str, str] = {
    # -- reliability reasons ---------------------------------------------------------------
    "window_length.ok": "{months} місяців даних: достатньо для порівняння рік до року",
    "window_length.short": "Лише {months} місяців даних: зростання рік до року недоступне",
    "window_length.too_short": "Лише {months} місяців даних: замало для оцінки тренду",
    "completeness.ok": "У місячних даних немає пропусків",
    "completeness.gaps": "{missing_months} місяців без даних ({share:.0%} періоду)",
    "completeness.sparse": (
        "{missing_months} місяців без даних ({share:.0%} періоду): ряд надто розріджений"
    ),
    "spikes.low": (
        "На дні сплесків припадає {share:.0%} переглядів: зростання не зумовлене сплесками"
    ),
    "spikes.notable": (
        "На дні сплесків припадає {share:.0%} переглядів: частина зростання може бути новинною"
    ),
    "spikes.dominant": (
        "На дні сплесків припадає {share:.0%} переглядів: зростання зумовлене сплесками"
    ),
    "spikes.unavailable": "Денні дані недоступні, тому сплески оцінити не вдалося",
    "trend.significant": "Тренд статистично значущий (p = {p_value:.3f}, {direction})",
    "trend.not_significant": "Тренд статистично незначущий (p = {p_value:.3f})",
    "trend.unavailable": "Замало точок для перевірки тренду",
    "resolution.sitelink": "Статтю знайдено через Wikidata: відповідність надійна",
    "resolution.search_fallback": (
        "Статтю знайдено повнотекстовим пошуком («{title}»): перевірте, що це саме вона"
    ),
    "resolution.manual": "Назви статей задано вручну",
    "resolution.not_found": (
        "У цьому розділі немає статті: відсутність статті не означає нульовий інтерес"
    ),
    "automated.low": "Автоматизований трафік становить {share:.0%}: вплив ботів незначний",
    "automated.high": "Автоматизований трафік становить {share:.0%}: боти можуть завищувати цифри",
    "automated.unavailable": (
        "Дані про автоматизований трафік для цього розділу й періоду недоступні"
    ),
    "volume.ok": "Близько {views_avg:,.0f} переглядів на місяць: достатньо для стабільного сигналу",
    "volume.low": "Лише близько {views_avg:,.0f} переглядів на місяць: сигнал зашумлений",
    "bundle.consistent": "Головна стаття та вся зв'язка рухаються в одному напрямку",
    "bundle.diverges": (
        "Головна стаття ({main_direction}) і зв'язка ({bundle_direction}) розходяться: "
        "висновок залежить від складу зв'язки"
    ),
    # -- labels ------------------------------------------------------------------------------
    "level.high": "висока",
    "level.medium": "середня",
    "level.low": "низька",
    "status.pass": "пройдено",
    "status.warn": "попередження",
    "status.fail": "не пройдено",
    "status.info": "довідково",
    "direction.rising": "зростає",
    "direction.falling": "спадає",
    "direction.flat": "без змін",
    "direction.unknown": "невідомо",
    "profile.early_niche": "рання ніша",
    "profile.growth_market": "ринок, що зростає",
    "profile.mature_market": "зрілий ринок",
    "profile.declining": "спадає",
    "profile.insufficient_data": "недостатньо даних",
    "bundle_status.found": "знайдено",
    "bundle_status.found_via_search": "знайдено пошуком",
    "bundle_status.not_found": "не знайдено",
    "source.sitelink": "sitelink Wikidata",
    "source.wikidata_relation": "зв'язок у Wikidata",
    "source.lead_link": "посилання з преамбули",
    "source.search_fallback": "резервний пошук",
    "source.manual": "вручну",
    "role.main": "головна",
    "role.related": "суміжна",
    "role.manual": "вручну",
    "unit.views": "переглядів",
    "unit.per_million": "переглядів на мільйон",
    "value.na": "н/д",
    # -- question line ---------------------------------------------------------------------
    "question.compare": "Порівняти інтерес до теми «{topics}» у розділах {projects}",
    "question.assess": "Оцінити, чи зростає інтерес до теми «{topics}» у розділах {projects}",
    "question.rank": "Ранжувати розділи {projects} за інтересом до теми «{topics}»",
    # -- report sections -------------------------------------------------------------------
    "report.title_default": "Аналіз інтересу за переглядами Вікіпедії",
    "report.question": "Питання",
    "report.audience": "Контекст",
    "report.key_numbers": "Ключові числа",
    "report.chart": "Графік",
    "report.charts": "Графіки",
    "report.verdict": "Висновок",
    "report.reliability": "Наскільки можна довіряти",
    "report.limitations": "Допущення та обмеження",
    "report.next_steps": "Що можна уточнити",
    "report.sources": "Джерела",
    "report.period": "Період",
    "report.projects": "Розділи",
    "report.topics": "Теми",
    "report.generated": "Сформовано",
    "report.version": "Версія навички",
    "report.data_through": "Дані до",
    "report.bundle_composition": "Склад зв'язки статей",
    "report.comparison_table": "Порівняння",
    "report.ranking_table": "Рейтинг",
    "report.notes": "Примітки",
    "report.see_summary": "… повний перелік у summary.md",
    "report.no_chart": "Для цього запуску графік не побудовано",
    # -- table columns ---------------------------------------------------------------------
    "col.topic": "Тема",
    "col.project": "Розділ",
    "col.views_avg": "Переглядів/міс.",
    "col.per_million_avg": "На млн переглядів розділу",
    "col.growth_yoy": "Зростання р/р",
    "col.growth_halves": "Зростання П2/П1",
    "col.trend": "Тренд",
    "col.reliability": "Надійність",
    "col.rank": "№",
    "col.score": "Бал",
    "col.profile": "Профіль",
    "col.article": "Стаття",
    "col.role": "Роль",
    "col.weight": "Вага",
    "col.source": "Джерело",
    "col.status": "Статус",
    "col.rationale": "Чому",
    # -- agent summary ---------------------------------------------------------------------
    "summary.answer": "Відповідь",
    "summary.key_numbers": "Ключові числа",
    "summary.trust": "Наскільки можна довіряти",
    "summary.caveats": "Застереження",
    "summary.refine": "Що можна уточнити",
    "summary.artifacts": "Файли",
    "summary.clarification_needed": "Потрібне уточнення",
    "summary.candidates": "Кандидати",
    "summary.clarification_hint": (
        "Запитайте користувача, яку сутність він має на увазі, і повторіть запуск із цим qid"
    ),
    "summary.bundles": "Проаналізовані статті",
    "summary.bundle_count": "статей: {total} (суміжних: {related})",
    # -- charts ----------------------------------------------------------------------------
    "chart.axis_per_million": "переглядів на мільйон переглядів розділу",
    "chart.axis_views": "переглядів на місяць",
    "chart.footnote": "Джерело: {source} · Період: {period}",
    "chart.growth_title": "Зростання рік до року",
    "chart.trend_title": "Інтерес у часі з лінією тренду",
    "chart.compare_title": "Інтерес за розділами",
    "chart.no_data": "Немає даних за цей період",
    "chart.score_title": "Бал ранжування",
    "chart.axis_score": "бал (0 = найслабший, 1 = найсильніший у наборі)",
    "chart.axis_growth": "зростання рік до року, %",
    "chart.growth_halves_title": "Зростання: друга половина періоду до першої",
    # -- вердикти ----------------------------------------------------------------------------
    "verdict.assess.headline": (
        "Інтерес до теми «{topic}» у {project}: тренд {direction}, {growth} рік до року; "
        "довіра: {level}"
    ),
    "verdict.compare.share": (
        "Найбільша частка уваги: {label} ({value} на мільйон переглядів розділу)"
    ),
    "verdict.compare.share_absolute": "Найбільше переглядів: {label} ({value} переглядів/міс)",
    "verdict.compare.growth": "найшвидше зростання: {label} ({growth})",
    "verdict.compare.decline": (
        "інтерес не зростає в жодному розділі; найменше падіння: {label} ({growth})"
    ),
    "verdict.compare.growth_unknown": "зростання виміряти не вдалося",
    "verdict.rank.headline": "Найперспективніша аудиторія: {label} ({profile}, бал {score})",
    "verdict.rank.headline_declining": (
        "Інтерес падає в усіх розділах; "
        "відносно найсильніша аудиторія: {label} ({profile}, бал {score})"
    ),
    "verdict.none.headline": (
        "Немає даних для аналізу тем {topics}: статей у {projects} не знайдено"
    ),
    "verdict.bullet.pair": (
        "{label}: {per_million} на мільйон переглядів розділу, {views} переглядів/міс, "
        "зростання {growth}, "
        "довіра {level}"
    ),
    "verdict.bullet.pair_absolute": (
        "{label}: {views} переглядів/міс, зростання {growth}, довіра {level}"
    ),
    "verdict.bullet.not_found": "{label}: у цьому розділі немає статті",
    "verdict.bullet.seasonality": (
        "{label}: сильна сезонність ({strength} дисперсії): порівнюйте однакові місяці рік до року"
    ),
    "verdict.bullet.main_vs_bundle": (
        "{label}: сама лише головна стаття: тренд {direction} ({growth})"
    ),
    "rank.rationale": "{profile}: зростання {growth}, {views} переглядів/міс, довіра {level}",
    "rank.rationale.insufficient": "недостатньо даних для ранжування",
    "note.not_found": "немає статті в цьому розділі",
    "note.search_fallback": "статтю знайдено пошуком",
    # -- обмеження та наступні кроки ---------------------------------------------------------
    "limitation.proxy": (
        "Читання Вікіпедії вимірює цікавість, а не готовність платити: сприймайте результат "
        "як сигнал для перевірки, а не як попит."
    ),
    "limitation.coverage": (
        "Розділи по-різному висвітлюють тему; відсутня або коротка стаття занижує сигнал "
        "незалежно від інтересу аудиторії."
    ),
    "limitation.bots": (
        "Фільтрація ботів на боці Wikimedia недосконала; перевірки автоматичного трафіку та "
        "сплесків ловлять лише частину."
    ),
    "limitation.bundle": (
        "Числа залежать від того, які статті враховано; наведено результати і для зв'язки, "
        "і для головної статті."
    ),
    "limitation.missing_titles": "Ці запитані назви не існують і були пропущені: {titles}",
    "limitation.not_found": (
        "Для теми «{topic}» немає статті у {projects}: ці розділи позначено як «немає статті», "
        "а не як нульовий інтерес."
    ),
    "limitation.search_fallback": (
        "У {projects} статтю знайдено повнотекстовим пошуком; перевірте, що це саме та стаття."
    ),
    "limitation.short_window": (
        "Лише {months} місяців даних: зростання рік до року недоступне, а тест тренду слабкий."
    ),
    "limitation.absolute": (
        "Порівнювалися сирі кількості переглядів без нормалізації на розмір розділу."
    ),
    "next.extend_period": (
        "Розширте період (наприклад, 36 або 60 місяців), щоб перевірити стійкість тренду."
    ),
    "next.add_projects": (
        "Додайте інші розділи, щоб побачити, чи специфічна ця картина для {projects}."
    ),
    "next.prune_bundle": (
        "Виключіть статті, що не належать до теми (exclude_titles), або зафіксуйте список "
        "(bundle: manual)."
    ),
    "next.absolute": (
        "Порівняйте сирі перегляди (normalization: absolute), щоб оцінити розмір аудиторії, "
        "а не частку."
    ),
    "next.per_million": "Порівняйте частки на мільйон, щоб прибрати вплив розміру розділу.",
    "next.pin_title": "Вкажіть точну назву статті для {projects} через extra_titles.",
    "next.research": "Дослідити наступною: {label} ({profile}).",
}
