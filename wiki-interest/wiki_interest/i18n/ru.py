"""Russian interface labels.

The charts, the PDF's headings and footer, the chat answer's fixed lines and the
missing-article question.

Only what the user reads word for word lives here, written once and reviewed, so the labels
read the same in every report; the agent no longer translates them (``facts.ui`` leaves them
out). Everything else, the analysis text included, is the agent's, and the English catalog
stays the fallback for any key missing here. Keys and ``{placeholders}`` mirror
:mod:`wiki_interest.i18n.en`; a test holds them to it.

Numbers never carry a noun that would need a case ("просмотров в месяц — 1 502"), since a
template cannot agree with the number it is given.
"""

# ruff: noqa: RUF001  -- the labels are Cyrillic on purpose.

from __future__ import annotations

from collections.abc import Mapping

from wiki_interest.i18n import editions

LABELS: Mapping[str, str] = {
    "value.na": "н/д",
    "value.per_million": "{value} на миллион",
    # -- PDF
    "report.title_default": "Анализ интереса в Википедии",
    "report.title_topic": "{topic}: интерес в Википедии",
    "report.period": "Период",
    "report.happening": "Что происходит",
    "report.decision": "Что это значит для вас",
    "report.see_summary": "… полный список — в summary.md",
    "report.ranking_table": "Рейтинг",
    "report.sources": "Источники",
    "report.sources_names": "Wikimedia Pageviews API, Wikidata, MediaWiki API",
    "report.generated": "Сгенерировано",
    "report.version": "Версия навыка",
    "report.data_through": "Последний месяц данных",
    "report.footer_share": (
        "Доля внимания = просмотры статьи на 1 млн просмотров этой Википедии. Вердикт: тренд "
        "доли внимания в периоде анализа (после ступеньки внутри него — от ступеньки); "
        "стабильно — в пределах ±10 % в год. История до периода — только контекст."
    ),
    "report.footer_caveats": (
        "Просмотры показывают интерес, а не готовность платить; языковой раздел Википедии — это "
        "не страна."
    ),
    "report.footer_method": "Как посчитано каждое число: method.md",
    "limitation.period_start": (
        "Данные о просмотрах начинаются с {start}, поэтому анализ начинается оттуда, а не с "
        "{requested}."
    ),
    "limitation.period_end": (
        "{requested} ещё не закончился, поэтому анализ заканчивается на {end}, последнем полном "
        "месяце."
    ),
    # -- charts
    "chart.no_data": "Нет данных за этот период",
    "chart.axis_views": "просмотров в месяц",
    "chart.share.title": "Доля внимания во времени",
    "chart.share.subtitle": "Просмотры статьи на 1 млн просмотров этой Википедии.",
    "chart.share.axis": "на 1 млн просмотров",
    "chart.share.legend_year": "среднее за календарный год (контекст)",
    "chart.share.legend_month": "каждый месяц",
    "chart.share.legend_trend": "линия тренда в периоде анализа",
    "chart.share.legend_window": "период анализа",
    "chart.share.partial_year": "{year} ({first} – {last})",
    "chart.share.month": "{month} {year}",
    "chart.absolute.title": "Просмотры по годам",
    "chart.absolute.subtitle": "Сколько раз в месяц открывали статью.",
    "chart.absolute.axis": "просмотров в месяц",
    "chart.audience.title": "Среднее число просмотров статьи в месяц",
    "chart.audience.subtitle": (
        "Столбцы — средние просмотры в месяц: 12 месяцев перед последними 12 и последние 12,\n"
        "над ними — изменение. Ниже — вердикт периода анализа для доли внимания (▲ растёт, "
        "≈ стабильна, ▼ снижается)."
    ),
    "chart.audience.span": "{first} – {last}",
    "chart.season_title": "Месяцы относительно обычного уровня",
    "chart.axis_season": "% к обычному уровню",
    "chart.season_period": "Посчитано за {start} – {end}.",
    "chart.scatter_title": "{metric}: размер и изменение",
    "chart.scatter_subtitle": "Правее — большая доля; выше линии — рост, ниже — спад.",
    "chart.axis_growth": "изменение, %",
    "chart.axis_log": "{unit}, логарифмическая шкала",
    "chart.axis_per_million": "просмотры статьи на миллион просмотров раздела",
    # -- months: full ones stand inside a phrase ("2026: январь–август"), short ones on axes
    "month.1": "январь",
    "month.2": "февраль",
    "month.3": "март",
    "month.4": "апрель",
    "month.5": "май",
    "month.6": "июнь",
    "month.7": "июль",
    "month.8": "август",
    "month.9": "сентябрь",
    "month.10": "октябрь",
    "month.11": "ноябрь",
    "month.12": "декабрь",
    "month.short.1": "Янв",
    "month.short.2": "Фев",
    "month.short.3": "Мар",
    "month.short.4": "Апр",
    "month.short.5": "Май",
    "month.short.6": "Июн",
    "month.short.7": "Июл",
    "month.short.8": "Авг",
    "month.short.9": "Сен",
    "month.short.10": "Окт",
    "month.short.11": "Ноя",
    "month.short.12": "Дек",
    # -- chat answer
    "chat.follow_ups": "Что ещё я могу сделать:",
    "chat.follow_up.seasons": "Я могу показать, какие месяцы года самые сильные",
    "chat.follow_up.longer_period": "Я могу посмотреть более длинный период, вплоть до 2015-07",
    "chat.follow_up.add_editions": "Я могу добавить для сравнения другие языковые разделы",
    "chat.follow_up.raw_views": "Я могу сравнить простые просмотры статьи вместо доли внимания",
    "chat.follow_up.method_page": "Я могу добавить страницу с методом и проверками данных",
    "chat.instant": "мгновенно: данные уже загружены",
    "chat.pdf": "PDF-отчёт: {path}",
    "chat.previous": "По сравнению с прошлым запуском ({period}):",
    "chat.previous_share": "доля внимания {before} → {after} на миллион",
    "chat.previous_change": "её изменение {before} → {after}",
    "chat.previous_added": "Добавлены разделы: {projects}.",
    # -- the missing-article question
    "summary.topic_line": "Тема: «{label}»{description} ({qid}).",
    "gap.entity_description": " — {description}",
    "gap.question": "В {project} нет статьи о «{topic}».",
    "gap.broader_intro": "Тему охватывают более широкие статьи этого раздела:",
    "gap.mention_intro": "Более широкой статьи нет, но тему упоминают эти статьи:",
    "option.redirect": (
        "[{target}]({url}){section} охватывает тему; название «{title}» ведёт туда: просмотров "
        "в месяц под этим названием — {views}. Нижняя граница: учтены только заходы именно по "
        "этому названию."
    ),
    "option.section": ", раздел «{section}»",
    "option.broader": (
        "[{title}]({url}), более широкая тема: просмотров в месяц — {views}. Верхняя граница: "
        "большинство читателей приходят за более широкой темой."
    ),
    "option.mention": (
        "[{title}]({url}) упоминает тему: просмотров в месяц — {views}. Тема — лишь небольшая "
        "часть статьи."
    ),
    "option.snippet": "Фрагмент: «…{snippet}…»",
    "option.skip": "Не учитывать {project}: отчёт скажет «статьи нет», а не «нулевой интерес».",
    "ask.local_name": "Если вы знаете, как тема называется в {project}, напишите — я поищу её там.",
    "ask.which": "Какой вариант выбрать для {projects}? Ответьте номером.",
    "substitute.redirect": "перенаправление «{title}»",
    "substitute.broader": "более широкую статью «{title}»",
    "substitute.mention": "статью «{title}», которая упоминает тему",
    "note.substitute": "статьи нет; измерено через {what}",
    # -- v0.2: the analysis window, its verdicts and the headline
    "report.analysis_window": "Период анализа: {start} – {end}",
    "report.context": "Контекст на графиках: с {year}",
    "verdict.growing": "интерес растёт",
    "verdict.stable": "интерес стабилен",
    "verdict.declining": "интерес снижается",
    "verdict.insufficient_data": "мало данных для вывода",
    "verdict.stable_after_drop": "интерес стабилизировался после спада",
    "verdict.stable_after_rise": "интерес держится после роста",
    "verdict.declining_still": "интерес продолжает падать",
    "verdict.growing_still": "интерес продолжает расти",
    "verdict.since": "с {month}",
    "verdict.line": (
        "{label}: {verdict}. Доля внимания {since}: {start} → {end} на 1 млн просмотров, "
        "{slope} в год."
    ),
    "verdict.line_none": "{label}: {verdict}.",
    "headline.part": "{edition} {verdict}",
    "headline.topic": "{topic}: {parts}.",
    **editions.RU,
}
