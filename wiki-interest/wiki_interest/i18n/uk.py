"""Ukrainian interface labels.

The charts, the PDF's headings and footer, the chat answer's fixed lines and the
missing-article question.

Only what the user reads word for word lives here, written once and reviewed, so the labels
read the same in every report; the agent no longer translates them (``facts.ui`` leaves them
out). Everything else, the analysis text included, is the agent's, and the English catalog
stays the fallback for any key missing here. Keys and ``{placeholders}`` mirror
:mod:`wiki_interest.i18n.en`; a test holds them to it.

Numbers never carry a noun that would need a case ("переглядів за місяць — 1 502"), since a
template cannot agree with the number it is given.
"""

# ruff: noqa: RUF001  -- the labels are Cyrillic on purpose.

from __future__ import annotations

from collections.abc import Mapping

from wiki_interest.i18n import editions

LABELS: Mapping[str, str] = {
    "value.na": "н/д",
    "value.per_million": "{value} на мільйон",
    # -- PDF
    "report.title_default": "Аналіз інтересу у Вікіпедії",
    "report.title_topic": "{topic}: інтерес у Вікіпедії",
    "report.period": "Період",
    "report.happening": "Що відбувається",
    "report.decision": "Що це означає для вас",
    "report.see_summary": "… повний список — у summary.md",
    "report.ranking_table": "Рейтинг",
    "report.sources": "Джерела",
    "report.sources_names": "Wikimedia Pageviews API, Wikidata, MediaWiki API",
    "report.generated": "Згенеровано",
    "report.version": "Версія навички",
    "report.data_through": "Останній місяць даних",
    "report.footer_share": (
        "Частка уваги = перегляди статті на 1 млн переглядів цієї Вікіпедії. Вердикт: тренд "
        "частки уваги в періоді аналізу (після ступеньки всередині нього — від ступеньки); "
        "стабільно — у межах ±10 % за рік. Історія до періоду — лише контекст."
    ),
    "report.footer_caveats": (
        "Перегляди показують інтерес, а не готовність платити; мовний розділ Вікіпедії — це не "
        "країна."
    ),
    "report.footer_method": "Як обчислено кожне число: method.md",
    "limitation.period_start": (
        "Дані про перегляди починаються з {start}, тож аналіз починається звідти, а не з "
        "{requested}."
    ),
    "limitation.period_end": (
        "{requested} ще не завершився, тож аналіз закінчується на {end}, останньому повному місяці."
    ),
    # -- charts
    "chart.no_data": "Немає даних за цей період",
    "chart.axis_views": "переглядів за місяць",
    "chart.share.title": "Частка уваги з часом",
    "chart.share.subtitle": "Перегляди статті на 1 млн переглядів цієї Вікіпедії.",
    "chart.share.axis": "на 1 млн переглядів",
    "chart.share.legend_year": "середнє за календарний рік (контекст)",
    "chart.share.legend_month": "кожен місяць",
    "chart.share.legend_trend": "лінія тренду в періоді аналізу",
    "chart.share.artifact": "{month}: ймовірно технічна зміна",
    "chart.share.legend_window": "період аналізу",
    "chart.share.partial_year": "{year} ({first} – {last})",
    "chart.share.month": "{month} {year}",
    "chart.absolute.title": "Перегляди за роками",
    "chart.absolute.subtitle": "Скільки разів на місяць відкривали статтю.",
    "chart.absolute.axis": "переглядів за місяць",
    "chart.audience.title": "Середня кількість переглядів статті за місяць",
    "chart.audience.subtitle": (
        "Стовпці — середні перегляди за місяць: 12 місяців перед останніми 12 і останні 12,\n"
        "над ними — зміна. Нижче — вердикт періоду аналізу для частки уваги (▲ зростає, "
        "≈ стабільна, ▼ спадає)."
    ),
    "chart.audience.span": "{first} – {last}",
    "chart.season_title": "Місяці порівняно зі звичайним рівнем",
    "chart.axis_season": "% до звичайного рівня",
    "chart.season_period": "Обчислено за {start} – {end}.",
    "chart.scatter_title": "{metric}: розмір і зміна",
    "chart.scatter_subtitle": "Праворуч — більша частка; над лінією — зростання, під нею — спад.",
    "chart.axis_growth": "зміна, %",
    "chart.axis_log": "{unit}, логарифмічна шкала",
    "chart.axis_per_million": "перегляди статті на мільйон переглядів розділу",
    # -- months: full ones stand inside a phrase ("2026: січень–серпень"), short ones on axes
    "month.1": "січень",
    "month.2": "лютий",
    "month.3": "березень",
    "month.4": "квітень",
    "month.5": "травень",
    "month.6": "червень",
    "month.7": "липень",
    "month.8": "серпень",
    "month.9": "вересень",
    "month.10": "жовтень",
    "month.11": "листопад",
    "month.12": "грудень",
    "month.short.1": "Січ",
    "month.short.2": "Лют",
    "month.short.3": "Бер",
    "month.short.4": "Кві",
    "month.short.5": "Тра",
    "month.short.6": "Чер",
    "month.short.7": "Лип",
    "month.short.8": "Сер",
    "month.short.9": "Вер",
    "month.short.10": "Жов",
    "month.short.11": "Лис",
    "month.short.12": "Гру",
    # -- chat answer
    "chat.follow_ups": "Що ще я можу зробити:",
    "chat.follow_up.seasons": "Я можу показати, які місяці року найсильніші",
    "chat.follow_up.longer_period": "Я можу подивитися довший період, аж до 2015-07",
    "chat.follow_up.add_editions": "Я можу додати для порівняння інші мовні розділи",
    "chat.follow_up.raw_views": "Я можу порівняти прості перегляди статті замість частки уваги",
    "chat.follow_up.method_page": "Я можу додати сторінку з методом і перевірками даних",
    "chat.instant": "миттєво: дані вже завантажені",
    "chat.pdf": "PDF-звіт: {path}",
    "chat.previous": "Порівняно з попереднім запуском ({period}):",
    "chat.previous_share": "частка уваги {before} → {after} на мільйон",
    "chat.previous_change": "її зміна {before} → {after}",
    "chat.previous_added": "Додано розділи: {projects}.",
    # -- the missing-article question
    "summary.topic_line": "Тема: «{label}»{description} ({qid}).",
    "gap.entity_description": " — {description}",
    "gap.question": "У {project} немає статті про «{topic}».",
    "gap.broader_intro": "Тему охоплюють ширші статті цього розділу:",
    "gap.mention_intro": "Ширшої статті немає, але тему згадують ці статті:",
    "option.redirect": (
        "[{target}]({url}){section} охоплює тему; назва «{title}» веде туди: переглядів за "
        "місяць під цією назвою — {views}. Нижня межа: враховано лише відвідування саме за цією "
        "назвою."
    ),
    "option.section": ", розділ «{section}»",
    "option.broader": (
        "[{title}]({url}), ширша тема: переглядів за місяць — {views}. Верхня межа: більшість "
        "читачів приходять по ширшу тему."
    ),
    "option.mention": (
        "[{title}]({url}) згадує тему: переглядів за місяць — {views}. Тема — лише невелика "
        "частина статті."
    ),
    "option.snippet": "Уривок: «…{snippet}…»",
    "option.skip": (
        "Не враховувати {project}: звіт скаже «статті немає», а не «нульовий інтерес»."
    ),
    "ask.local_name": (
        "Якщо ви знаєте, як тема називається в {project}, напишіть — я пошукаю її там."
    ),
    "ask.which": "Який варіант обрати для {projects}? Відповідайте номером.",
    "substitute.redirect": "перенаправлення «{title}»",
    "substitute.broader": "ширшу статтю «{title}»",
    "substitute.mention": "статтю «{title}», яка згадує тему",
    "note.substitute": "статті немає; виміряно через {what}",
    # -- v0.2: the recommendation
    "rec.line": "Рекомендація: {text}",
    "rec.why": "{parts}.",
    "rec.why_part": "{label}: {verdict} ({start} → {end}, {slope}/рік)",
    "rec.why_part_none": "{label}: {verdict}",
    "rec.none_growing": "Жоден мовний розділ не показує зростання.",
    "rec.none_growing_topics": "Жодна тема не показує зростання.",
    "rec.pick": "Якщо обирати — {choice}.",
    "rec.confidence": "Довіра до вибору: {level}.",
    "rec.next.related": (
        "Наступна перевірка: суміжні статті — {items}; я можу додати їх до цього аналізу."
    ),
    "rec.next.editions": (
        "Наступна перевірка: та сама стаття в інших мовних розділах ({items}); я можу їх додати."
    ),
    "rec.next.external": (
        "Наступна перевірка: поза Вікіпедією — Google Trends або невеликий рекламний тест."
    ),
    "chat.follow_up.related_topics": "Я можу додати до аналізу суміжні статті",
    # -- v0.2: the trust in each verdict
    "trust.compact": "Довіра: {items}.",
    "trust.compact_item": "{label} — {level}{why}",
    "trust.compact_why": " ({reason})",
    "trust.line": "Довіра ({label}): {level} — {reasons}.",
    "trust.level.high": "висока",
    "trust.level.medium": "середня",
    "trust.level.low": "низька",
    "trust.reason.yoy_against": "лише {count} з {months} міс. р/р на боці вердикту",
    "trust.reason.yoy_down": "спад у {count} з {months} міс. р/р",
    "trust.reason.yoy_up": "зростання у {count} з {months} міс. р/р",
    "trust.reason.yoy_mixed": "р/р нижче у {down}, вище у {up} з {months} міс.",
    "trust.reason.slope": "{slope}/рік [{low}; {high}]",
    "trust.reason.slope_no_ci": "{slope}/рік",
    "trust.reason.control": "контрольні статті {change}/рік",
    "trust.reason.control_none": "контрольних статей немає",
    "trust.reason.renames_none": "перейменувань немає",
    "trust.reason.renames": "перейменування: {months}",
    "trust.reason.artifact": "ступенька {month} ймовірно технічна",
    "trust.reason.day_spikes": "без місяців зі сплеском за один день: {months}",
    "trust.reason.ci_zero": "інтервал включає нуль",
    "trust.reason.snr_low": "зміна в межах шуму (сигнал/шум {snr})",
    "trust.reason.control_explains": "контрольні статті змінились так само ({change}/рік)",
    "trust.reason.ci_wide": "тренд понад ±{band} %/рік не виключений",
    "trust.reason.few_months": "лише {months} міс. у тренді",
    "trust.reason.step_not_trend": "{month}: ступенька, а не тренд",
    "trust.reason.volume_low": "замало переглядів ({views} на місяць)",
    "trust.reason.window_short": "період коротший за рік",
    # -- v0.2: the analysis window, its verdicts and the headline
    "report.analysis_window": "Період аналізу: {start} – {end}",
    "report.context": "Контекст на графіках: з {year}",
    "verdict.growing": "інтерес зростає",
    "verdict.stable": "інтерес стабільний",
    "verdict.declining": "інтерес спадає",
    "verdict.insufficient_data": "замало даних для висновку",
    "verdict.stable_after_drop": "інтерес стабілізувався після спаду",
    "verdict.stable_after_rise": "інтерес утримується після зростання",
    "verdict.declining_still": "інтерес продовжує падати",
    "verdict.growing_still": "інтерес продовжує зростати",
    "verdict.since": "з {month}",
    "verdict.line": (
        "{label}: {verdict}. Частка уваги {since}: {start} → {end} на 1 млн переглядів, "
        "{slope} за рік."
    ),
    "verdict.line_none": "{label}: {verdict}.",
    "headline.part": "{edition} {verdict}",
    "headline.topic": "{topic}: {parts}.",
    **editions.UK,
}
