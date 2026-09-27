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
    "chart.share.artifact": "{month}: вероятно, техническое изменение",
    "chart.share.legend_window": "период анализа",
    "chart.share.partial_year": "{year} ({first} – {last})",
    "chart.share.month": "{month} {year}",
    "chart.absolute.title": "Просмотры по годам",
    "chart.absolute.subtitle": "Сколько раз в месяц открывали статью.",
    "chart.absolute.axis": "просмотров в месяц",
    "chart.audience.title": "Среднее число просмотров статьи в месяц по годам",
    "chart.audience.subtitle": (
        "Столбцы — средние просмотры в месяц за каждый календарный год; над ними — изменение "
        "просмотров к предыдущему году."
    ),
    "chart.audience.partial": "{year}: {first} – {last} против тех же месяцев {previous} года.",
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
    "chat.follow_up.add_sections": "Я могу добавить для сравнения другие языковые разделы",
    "chat.follow_up.raw_views": "Я могу сравнить простые просмотры статьи вместо доли внимания",
    "chat.follow_up.method_page": "Я могу добавить страницу с методом и проверками данных",
    "chat.instant": "мгновенно: данные уже загружены",
    "chat.pdf": "PDF-отчёт: {path}",
    "chat.previous": "По сравнению с прошлым запуском ({period}):",
    "chat.previous_verdict": "{label}: раньше — {before}; теперь — {after}",
    "chat.previous_same": "{label}: {verdict}, как и раньше",
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
    # -- v0.2: the recommendation
    "rec.line": "Рекомендация: {text}",
    "rec.why": "{parts}.",
    "rec.why_part": "{label}: {verdict} ({start} → {end}, {slope}/год)",
    "rec.why_part_none": "{label}: {verdict}",
    "rec.none_growing": "Ни один языковой раздел не показывает роста.",
    "rec.none_growing_topics": "Ни одна тема не показывает роста.",
    "rec.then": "Следующие в том же порядке: {items}.",
    "rec.pick.verdict": (
        "Если выбирать — {choice}: здесь и лучше динамика интереса, и самая большая аудитория."
    ),
    "rec.pick.verdict_smaller": (
        "Если выбирать — {choice}: решает динамика интереса, хотя самая большая аудитория — "
        "{largest}."
    ),
    "rec.pick.trust": (
        "Если выбирать — {choice}: вывод тот же, но надёжнее, и аудитория самая большая."
    ),
    "rec.pick.trust_smaller": (
        "Если выбирать — {choice}: вывод тот же, но надёжнее, хотя самая большая "
        "аудитория — {largest}."
    ),
    "rec.pick.size": (
        "Если выбирать — {choice}: при одинаковых выводе и доверии решает размер аудитории."
    ),
    "rec.pick.size_smaller": (
        "Если выбирать — {choice}: при одинаковых выводе и доверии решает размер аудитории, "
        "хотя самая большая аудитория в целом — {largest}."
    ),
    "rec.confidence": "Доверие к выбору: {level}.",
    "rec.next.related": (
        "Следующая проверка: смежные статьи — {items}; я могу добавить их в этот анализ."
    ),
    "rec.next.editions": (
        "Следующая проверка: та же статья в других языковых разделах ({items}); я могу их добавить."
    ),
    "rec.next.external": (
        "Следующая проверка: вне Википедии — Google Trends или небольшой рекламный тест."
    ),
    "chat.follow_up.related_topics": "Я могу добавить в анализ смежные статьи",
    # -- v0.2: the trust in each verdict
    "trust.compact": "Доверие: {items}.",
    "trust.compact_item": "{label} — {level}{why}",
    "trust.compact_why": " ({reason})",
    "trust.line": "Доверие ({label}): {level} — {reasons}.",
    "trust.level.high": "высокое",
    "trust.level.medium": "среднее",
    "trust.level.low": "низкое",
    "trust.reason.yoy_against": "лишь {count} из {months} мес. г/г на стороне вердикта",
    "trust.reason.yoy_down": "спад в {count} из {months} мес. г/г",
    "trust.reason.yoy_up": "рост в {count} из {months} мес. г/г",
    "trust.reason.yoy_mixed": "г/г ниже в {down}, выше в {up} из {months} мес.",
    "trust.reason.slope": "{slope}/год [{low}; {high}]",
    "trust.reason.slope_no_ci": "{slope}/год",
    "trust.reason.control": "контрольные статьи {change}/год",
    "trust.reason.control_none": "контрольных статей нет",
    "trust.reason.renames_none": "переименований нет",
    "trust.reason.renames": "переименования: {months}",
    "trust.reason.artifact": "ступенька {month} вероятно техническая",
    "trust.reason.day_spikes": "без месяцев со всплеском за один день: {months}",
    "trust.reason.ci_zero": "интервал включает ноль",
    "trust.reason.snr_low": "изменение в пределах шума (сигнал/шум {snr})",
    "trust.reason.control_explains": "контрольные статьи изменились так же ({change}/год)",
    "trust.reason.ci_wide": "тренд больше ±{band} %/год не исключён",
    "trust.reason.few_months": "только {months} мес. в тренде",
    "trust.reason.step_not_trend": "{month}: ступенька, а не тренд",
    "trust.reason.volume_low": "мало просмотров ({views} в месяц)",
    "trust.reason.window_short": "период короче года",
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
