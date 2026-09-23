"""Ukrainian message catalog. Mirrors the key set of :mod:`wiki_interest.i18n.en`."""

# ruff: noqa: RUF001  -- Cyrillic letters are homoglyphs of Latin ones by nature.

from __future__ import annotations

__all__ = ["MESSAGES"]

MESSAGES: dict[str, str] = {
    # -- reliability reasons ---------------------------------------------------------------
    "window_length.ok": "{months} місяців даних: достатньо для порівняння рік до року",
    "window_length.too_short": "Лише {months} місяців даних: замало для оцінки тренду",
    "completeness.ok": "У місячних даних немає пропусків",
    "completeness.gaps": "{missing_months} місяців без даних ({share:.0%} періоду)",
    "completeness.sparse": (
        "{missing_months} місяців без даних ({share:.0%} періоду): ряд надто розріджений"
    ),
    "spikes.unavailable": "Денні дані недоступні, тому сплески оцінити не вдалося",
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
    "question.rank": "Ранжувати розділи {projects} за інтересом до теми «{topics}»",
    # -- report sections -------------------------------------------------------------------
    "report.title_default": "Аналіз інтересу за переглядами Вікіпедії",
    "report.question": "Питання",
    "report.audience": "Контекст",
    "report.key_numbers": "Ключові числа",
    "report.chart": "Графік",
    "report.charts": "Графіки",
    "report.verdict": "Висновок",
    "report.limitations": "Допущення та обмеження",
    "report.next_steps": "Що можна уточнити",
    "report.sources": "Джерела",
    "report.period": "Період",
    "report.projects": "Розділи",
    "report.topics": "Теми",
    "report.generated": "Сформовано",
    "report.version": "Версія навички",
    "report.data_through": "Дані до",
    "report.comparison_table": "Порівняння",
    "report.ranking_table": "Рейтинг",
    "report.notes": "Примітки",
    "report.see_summary": "… повний перелік у summary.md",
    "report.no_chart": "Для цього запуску графік не побудовано",
    # -- table columns ---------------------------------------------------------------------
    "col.topic": "Тема",
    "col.project": "Розділ",
    "col.reliability": "Надійність",
    "col.rank": "№",
    "col.score": "Бал",
    "col.profile": "Профіль",
    "col.article": "Стаття",
    "col.role": "Роль",
    "col.source": "Джерело",
    "col.status": "Статус",
    "col.rationale": "Чому",
    # -- agent summary ---------------------------------------------------------------------
    "summary.answer": "Відповідь",
    "summary.key_numbers": "Ключові числа",
    "summary.caveats": "Застереження",
    "summary.refine": "Що можна уточнити",
    "summary.artifacts": "Файли",
    "summary.clarification_needed": "Потрібне уточнення",
    "summary.candidates": "Кандидати",
    "summary.clarification_hint": (
        "Якщо з розмови зрозуміло, яке значення має на увазі користувач, самі вкажіть qid цього "
        "кандидата й скажіть, яке значення обрано; інакше запитайте користувача. Потім запустіть "
        "знову з topics[].qid."
    ),
    "summary.bundles": "Проаналізовані статті",
    # -- charts ----------------------------------------------------------------------------
    "chart.axis_views": "переглядів на місяць",
    "chart.footnote": "Джерело: {source} · Період: {period}",
    "chart.no_data": "Немає даних за цей період",
    # -- вердикти ----------------------------------------------------------------------------
    "verdict.rank.headline": "Найперспективніша аудиторія: {label} ({profile})",
    "verdict.none.headline": (
        "Немає даних для аналізу тем {topics}: статей у {projects} не знайдено"
    ),
    "rank.rationale.insufficient": "недостатньо даних для ранжування",
    "note.not_found": "немає статті в цьому розділі",
    "note.search_fallback": "статтю знайдено пошуком",
    # -- обмеження та наступні кроки ---------------------------------------------------------
    "limitation.coverage": (
        "Розділи по-різному висвітлюють тему; відсутня або коротка стаття занижує сигнал "
        "незалежно від інтересу аудиторії."
    ),
    "limitation.language": (
        "Мовний розділ — не країна: його читають мешканці багатьох країн, а мешканці однієї "
        "країни читають різні розділи."
    ),
    "limitation.bots": (
        "Фільтрація ботів на боці Wikimedia недосконала; перевірки автоматичного трафіку та "
        "сплесків ловлять лише частину."
    ),
    "limitation.missing_titles": "Ці запитані назви не існують і були пропущені: {titles}",
    "limitation.not_found": (
        "Для теми «{topic}» немає статті у {projects}: ці розділи позначено як «немає статті», "
        "а не як нульовий інтерес."
    ),
    "limitation.search_fallback": (
        "У {projects} статтю знайдено повнотекстовим пошуком; перевірте, що це саме та стаття."
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
    "next.absolute": (
        "Порівняйте сирі перегляди (normalization: absolute), щоб оцінити розмір аудиторії, "
        "а не частку."
    ),
    "next.per_million": "Порівняйте частки на мільйон, щоб прибрати вплив розміру розділу.",
    "next.pin_title": "Вкажіть точну назву статті для {projects} через extra_titles.",
    "next.research": "Дослідити наступною: {label} ({profile}).",
    # -- editions without an article: the question and the substitutes ------------------
    "resolution.substitute_redirect": (
        "Статті немає; виміряно через перенаправлення «{title}»: враховано лише переходи за цією "
        "назвою, тож це нижня межа"
    ),
    "resolution.substitute_broader": (
        "Статті немає; виміряно через ширшу статтю «{title}»: числа описують ширшу тему, тож це "
        "верхня межа"
    ),
    "resolution.substitute_mention": (
        "Статті немає; виміряно через «{title}», де тему лише згадано: числа описують ту статтю, а "
        "не тему"
    ),
    "bundle_status.substitute": "заміна",
    "source.substitute": "заміна, обрана користувачем",
    "summary.missing_needed": "Потрібне рішення: немає статті",
    "summary.apply_choice": "Для агента: значення для topics[].substitutes",
    "gap.headline": (
        "Ще нічого не виміряно: у {projects} немає статті на цю тему. Спершу оберіть, що там "
        "вимірювати."
    ),
    "gap.question": "У {project} немає статті «{topic}».",
    "gap.term": "«{term}»",
    "gap.searched": "Шукали: {terms}.",
    "gap.no_terms": (
        "Назва теми цією мовою невідома, тож перенаправлення й згадки не шукали; вкажіть її в "
        "local_terms, щоб знайти їх."
    ),
    "option.redirect": (
        "Перенаправлення «{title}» веде на статтю «{target}»{section}: {views} переглядів/міс. "
        "Враховує лише переходи саме за цією назвою, тож це нижня межа."
    ),
    "option.section": ", розділ статті «{section}»",
    "option.broader": (
        "Ширша стаття «{title}»: {views} переглядів/міс. Верхня межа: більшість читачів прийшли по "
        "ширшу тему."
    ),
    "option.mention": (
        "Стаття «{title}» згадує тему: {views} переглядів/міс. Тема — лише мала її частина."
    ),
    "option.snippet": "Уривок: «…{snippet}…»",
    "option.skip": "Не аналізувати {project}: у звіті буде «немає статті», а не нульовий інтерес.",
    "substitute.redirect": "перенаправлення «{title}»",
    "substitute.broader": "ширшу статтю «{title}»",
    "substitute.mention": "статтю «{title}», що згадує тему",
    "note.substitute": "статті немає; виміряно через {what}",
    "limitation.substitute": (
        "Для «{topic}» у {project} немає статті; числа там отримано через {what}, як обрано."
    ),
    "rank.rationale.substitute": "не ранжовано: виміряно через іншу статтю, а не саму тему",
    "gap.entity": (
        "Тема: «{label}»{description} ({qid}). Мов, де є стаття: {count}, зокрема {languages}."
    ),
    "gap.entity_description": " — {description}",
    "gap.entity_nowhere": (
        "Тема: «{label}»{description} ({qid}); статті про неї немає в жодному розділі Вікіпедії."
    ),
    "gap.matched_en": (
        "Її знайдено за англійською назвою, бо пошук мовою запиту нічого не дав; переконайтеся, що "
        "це саме та тема."
    ),
    "gap.no_entity": (
        "Тему не знайдено у Wikidata, тож невідомо, в яких розділах вона є; перевірте формулювання "
        "або вкажіть query_en."
    ),
    "summary.topic_line": "Тема: «{label}»{description} ({qid}).",
    "summary.alternatives": "Інші значення цієї назви: {items}.",
    "summary.candidate_articles": "статті є в {projects}",
    "summary.candidate_no_articles": "статей у запитаних розділах немає",
    "summary.not_found_needed": "Тему не знайдено",
    "notfound.headline": (
        "За запитом «{query}» нічого не знайдено ні у Wikidata, ні у Вікіпедії — ні за цим "
        "формулюванням, ні за англійською назвою."
    ),
    "summary.not_found_hint": (
        "Чесно скажіть про це користувачу й попросіть посилання на статтю Вікіпедії будь-якою "
        "мовою про те, що його цікавить. Вставте його в topics[].article_url у request.json і "
        "запустіть знову."
    ),
    "summary.which_meaning": "Яке значення «{query}» мається на увазі?",
    "summary.topic_only": (
        "Лише перевірка теми: тему визначено, більше нічого не запускатиметься; звіту немає, і це "
        "очікувано. Скажіть користувачу, яку тему й статті визначено, і завершіть."
    ),
    # -- report findings, implications and charts --------------------------------------------
    "format.date": "{day:02d}.{month:02d}.{year}",
    "format.month_year": "{month:02d}.{year}",
    "basis.yoy": "останні 12 місяців до попередніх 12",
    "basis.halves": "друга половина періоду до першої",
    "basis.slope": "за трендом, на рік",
    "basis.mixed": "по розділах",
    "finding.unit.per_million": "на мільйон переглядів розділу",
    "finding.unit.views": "переглядів/міс",
    "chart.season_title": "Місяці відносно звичайного рівня",
    "chart.axis_season": "% до звичайного рівня",
    "report.title_topic": "{topic}: інтерес у Вікіпедії",
    "report.context": "Пов’язані статті (контекст, не враховано)",
    "report.method_note": "Про метод",
    "report.sources_names": "Wikimedia Pageviews API, Вікідані, MediaWiki API",
    "summary.context": "Пов’язані статті (контекст, не враховано)",
    "summary.context_item": "{title} — {views} переглядів/міс",
    "summary.bundle_count": "виміряно головну статтю; пов’язаних статей як контекст: {related}",
    "summary.method": "Про метод",
    "month.1": "січень",
    "month.short.1": "січ",
    "month.2": "лютий",
    "month.short.2": "лют",
    "month.3": "березень",
    "month.short.3": "бер",
    "month.4": "квітень",
    "month.short.4": "кві",
    "month.5": "травень",
    "month.short.5": "тра",
    "month.6": "червень",
    "month.short.6": "чер",
    "month.7": "липень",
    "month.short.7": "лип",
    "month.8": "серпень",
    "month.short.8": "сер",
    "month.9": "вересень",
    "month.short.9": "вер",
    "month.10": "жовтень",
    "month.short.10": "жов",
    "month.11": "листопад",
    "month.short.11": "лис",
    "month.12": "грудень",
    "month.short.12": "гру",
    "summary.redirects": "+{count} перенаправл.",
    "finding.item.season": "{label}: {peak_month} {peak}, {trough_month} {trough}",
    "finding.no_article": (
        "{label}: у цьому розділі немає статті на тему, тому він показаний як «немає даних», а не "
        "як нульовий інтерес."
    ),
    "finding.substitute": (
        "{label}: статті на тему немає; виміряно через {what} — це ширша тема, тому з іншими "
        "розділами не порівнюється."
    ),
    "report.bundle_composition": "Проаналізовані статті",
    "summary.missing_hint": (
        "Зупиніться: покажіть користувачу ці варіанти, спитайте, який узяти для кожного розділу, і "
        "завершіть відповідь цим питанням. Не вибирайте за користувача і не запускайте знову, доки "
        "він не відповість. Потім додайте значення вибраного варіанта з блоку нижче в "
        "topics[].substitutes у request.json і запустіть знову."
    ),
    "answer.conclusion.unknown": "Перш ніж вирішувати, розширте період.",
    "answer.conclusion.low_trust": "Даних недостатньо для висновку: вважайте цифри орієнтовними.",
    "answer.no_article": (
        "У {projects} немає статті: інтерес там не виміряно, і це не те саме, що відсутність "
        "інтересу."
    ),
    "outcome.unknown": "{label}: період закороткий, щоб судити про тренд.",
    "outcome.low_trust": "{label}: даних недостатньо для висновку.",
    "outcome.substitute": "{label}: виміряно іншу статтю, тож про саму тему це говорить мало.",
    "outcome.no_article": (
        "{label}: статті немає, інтерес не виміряно (це не те саме, що відсутність інтересу)."
    ),
    "next_step.confirm": (
        "Наступний крок: підтвердити сигнал незалежним джерелом попиту — наприклад, Google Trends, "
        "обсягом пошукових запитів або невеликим рекламним тестом. Перегляди Вікіпедії не "
        "показують готовності платити."
    ),
    "next_step.confirm_for": (
        "Наступний крок: підтвердити сигнал для {label} незалежним джерелом попиту — наприклад, "
        "Google Trends, обсягом пошукових запитів або невеликим рекламним тестом. Перегляди "
        "Вікіпедії не показують готовності платити."
    ),
    "next_step.check_demand": (
        "Наступний крок: перш ніж інвестувати, перевірити наявний попит незалежним джерелом — "
        "наприклад, Google Trends, обсягом пошукових запитів або невеликим рекламним тестом. "
        "Перегляди Вікіпедії не показують готовності платити."
    ),
    "next_step.check_demand_for": (
        "Наступний крок: перевірити наявний попит у {label} незалежним джерелом — наприклад, "
        "Google Trends, обсягом пошукових запитів або невеликим рекламним тестом. Перегляди "
        "Вікіпедії не показують готовності платити."
    ),
    "next_step.low_trust": (
        "Наступний крок: розширити період або уточнити статтю, потім підтвердити сигнал незалежним "
        "джерелом попиту — наприклад, Google Trends, обсягом пошукових запитів або невеликим "
        "рекламним тестом."
    ),
    "evidence.months": "{months} міс. спостережень",
    "evidence.months_short": "лише {months} міс. спостережень",
    "evidence.no_gaps": "немає пропущених місяців",
    "evidence.gaps": "пропущено місяців: {missing_months}",
    "evidence.spikes_high": "сплески дають {share} переглядів",
    "card.no_article": "немає статті",
    "value.per_million": "{value} на 1 млн",
    "report.answer": "Відповідь",
    "report.vs_edition": "Тема зростає швидше чи повільніше за свою Вікіпедію?",
    "report.vs_edition_basis": "Порівняння: {basis}",
    "report.decision": "Що це означає для рішення",
    "report.other_findings": "Що ще варто знати",
    "report.coverage": (
        "Перевірка охоплення: знайдено пов’язані статті — {items}. Вони слугують контекстом і не "
        "входять до основної метрики."
    ),
    "report.coverage_item": "{project}: {count}",
    "summary.decision": "Що це означає для рішення",
    "finding.item.season_tentative": "{label}: {peak_month} {peak}, {trough_month} {trough}",
    "limitation.scope": (
        "Аналіз вимірює читання однієї основної статті та її перенаправлень: це непрямий показник "
        "інтересу до теми, а не розмір ринку чи готовність платити."
    ),
    "summary.findings": "Що ще варто знати",
    "robustness.unknown": "{label}: про стійкість судити не можна: {reason}.",
    "robustness.reason.low_trust": "дані надто слабкі (див. рядок про дані)",
    "robustness.reason.low_volume": "аудиторія замала для порівняння за три місяці",
    "robustness.reason.no_recent": "немає порівняння з тими самими місяцями рік тому",
    "robustness.reason.no_trend": "період закороткий для тренду",
    "report.robustness": "Наскільки стійкий цей висновок?",
    "report.recent_basis": "останні {months} міс. до тих самих місяців рік тому",
    "report.data_line": "Дані: {items}.",
    "report.data_concerns": "{label}: {items}.",
    "report.reliability": "Перевірки даних",
    "evidence.spikes_ok": "окремі сплески не визначають результат",
    "outcome.recent.confirmed": "; нещодавні дані це підтверджують",
    "outcome.recent.mixed": "; нещодавні дані це поки не підтверджують",
    "outcome.recent.reversing": "; останніми місяцями напрям змінився",
    "metric.article_views": "Перегляди статті",
    "metric.edition_views": "Трафік розділу",
    "metric.attention_share": "Частка уваги",
    "metric.attention_share_unit": "переглядів статті на 1 млн переглядів розділу",
    "headline.subject.share_one": "Частка уваги до теми {topics}",
    "headline.subject.share_many": "Частка уваги до тем {topics}",
    "headline.subject.views_one": "Кількість переглядів статті про тему {topics}",
    "headline.subject.views_many": "Кількість переглядів статей про теми {topics}",
    "headline.scope.both": "в обох розділах",
    "headline.scope.all": "в усіх розділах",
    "headline.scope.everywhere": "скрізь",
    "headline.one.growing": "{subject} в {project} зростає{recent}",
    "headline.one.declining": "{subject} в {project} знижується{recent}",
    "headline.one.flat": "{subject} в {project} без вираженого тренду{recent}",
    "headline.unknown": "Період закороткий, щоб судити, куди рухається {subject}.",
    "headline.all.growing": "{subject} зростає {scope}, {fastest}",
    "headline.all.declining": "{subject} знижується {scope}, {fastest}",
    "headline.all.flat": "{subject} {scope} без вираженого тренду",
    "headline.fastest": "найшвидше — в {label}",
    "headline.fastest_steadier": "в {label} — швидше й стійкіше",
    "headline.mixed": "{subject}: {parts}",
    "headline.part.growing": "зростає в {items}",
    "headline.part.declining": "знижується в {items}",
    "headline.part.flat": "без вираженого тренду в {items}",
    "headline.part.unknown": "закоротка історія в {items}",
    "happening.size_share": "{metric} ({unit}), у середньому за період: {items}.",
    "happening.size_views": "{metric} на місяць, у середньому за період: {items}.",
    "happening.change": "{metric}, {basis}: {items}.",
    "happening.pair": "{article} і {edition}",
    "happening.vs_edition": "{article} і {edition}, {basis}: {items}.",
    "kpi.metric": "Показник",
    "kpi.views": "Перегляди статті на місяць (у середньому)",
    "kpi.share": "Частка уваги, на 1 млн переглядів розділу (у середньому)",
    "kpi.change": "{metric}, {basis}",
    "kpi.recent": "Останні {months} міс. підтверджують тренд?",
    "robustness.value.confirmed": "так",
    "robustness.value.mixed": "ні, частка стабільна",
    "robustness.value.mixed_flat": "ні, частка зсунулася",
    "robustness.value.reversing": "ні, напрям змінився",
    "robustness.value.unknown": "недостатньо даних",
    "summary.topic_auto": "Автоматично зіставлено з {qid} за вказаним змістом.",
    "spikes.low": (
        "На дні сплесків припадає {share:.0%} переглядів: висновок про тренд не визначається "
        "окремими сплесками"
    ),
    "spikes.notable": (
        "На дні сплесків припадає {share:.0%} переглядів: частина тренду може бути новинною"
    ),
    "spikes.dominant": (
        "На дні сплесків припадає {share:.0%} переглядів: тренд тримається на сплесках, а не на "
        "постійному читанні"
    ),
    "window_length.short": "Лише {months} міс. даних: останні 12 місяців нема з чим порівняти",
    "limitation.short_window": (
        "Лише {months} міс. даних: останні 12 місяців нема з чим порівняти, а тест тренду слабкий."
    ),
    "rank.rationale": (
        "{profile}: частка уваги {growth} (основне вікно), переглядів статті на місяць {views}, "
        "надійність {level}"
    ),
    "verdict.rank.headline_declining": (
        "Частка уваги знижується в усіх розділах; відносно найсильніша аудиторія: {label} "
        "({profile})"
    ),
    "finding.level_shift": (
        "{label}: {metric} з {start_month} тримається на рівні {change} до попереднього вже "
        "{months} міс. (у середньому {before} → {after} {unit})."
    ),
    "finding.burst": (
        "{label}: сплеск переглядів статті {start} – {end}, пік {peak_day}: {peak_views} "
        "переглядів за день, ×{multiple} до звичайних {baseline}; на сплеск припадає {share} "
        "переглядів статті за період."
    ),
    "finding.burst_day": (
        "{label}: одноденний сплеск переглядів статті {peak_day}: {peak_views} переглядів, "
        "×{multiple} до звичайних {baseline}; це {share} переглядів статті за період."
    ),
    "finding.season": (
        "{label}: перегляди статті за місяцями до звичайного рівня: найсильніший {peak_month} "
        "({peak}), найслабший {trough_month} ({trough})."
    ),
    "finding.group.season": (
        "Перегляди статті за місяцями, найсильніший і найслабший місяць до звичайного рівня: "
        "{items}."
    ),
    "finding.season_tentative": (
        "{label}: у переглядах статті є ознаки сезонності ({peak_month} {peak}, {trough_month} "
        "{trough} до звичайного рівня); для впевненого висновку потрібна довша історія — кожен "
        "місяць спостерігався лише кілька разів."
    ),
    "finding.group.season_tentative": (
        "У переглядах статті є ознаки сезонності в {count} розділах ({items}, до звичайного "
        "рівня); для впевненого висновку потрібна довша історія."
    ),
    "card.size": "Частка уваги, на 1 млн переглядів розділу",
    "card.size_absolute": "Перегляди статті на місяць",
    "card.views_note": "перегляди статті на місяць: {items}",
    "card.momentum": "Частка уваги: зміна",
    "card.momentum_absolute": "Перегляди статті: зміна",
    "card.robustness": "Останні місяці підтверджують тренд?",
    "col.views_avg": "Перегляди статті/міс.",
    "col.per_million_avg": "Частка уваги, на 1 млн",
    "col.share_growth": "Частка уваги: зміна",
    "col.views_growth": "Перегляди статті: зміна",
    "col.edition_growth": "Трафік розділу: зміна",
    "col.trend": "Тренд частки уваги",
    "edition.gaining": (
        "{label}: перегляди статті {article}, трафік розділу {edition} → частка уваги зростає"
    ),
    "edition.losing": (
        "{label}: перегляди статті {article}, трафік розділу {edition} → частка уваги знижується"
    ),
    "edition.in_line": (
        "{label}: перегляди статті {article}, трафік розділу {edition} → частка уваги тримається"
    ),
    "robustness.confirmed.flat": (
        "{label}: стабільно. Частка уваги, {basis}: {change}, вираженого тренду немає; за останні "
        "{months} міс. до тих самих місяців рік тому перегляди статті {article}, трафік розділу "
        "{edition}, тобто частка тримається."
    ),
    "robustness.mixed.declining": (
        "{label}: змішаний сигнал. Частка уваги, {basis}: {change}; але за останні {months} міс. "
        "до тих самих місяців рік тому перегляди статті {article}, трафік розділу {edition}, тобто "
        "частка стабільна. Довгострокове зниження видно, але поки неясно, чи триває воно зараз."
    ),
    "robustness.mixed.growing": (
        "{label}: змішаний сигнал. Частка уваги, {basis}: {change}; але за останні {months} міс. "
        "до тих самих місяців рік тому перегляди статті {article}, трафік розділу {edition}, тобто "
        "частка стабільна. Довгострокове зростання видно, але поки неясно, чи триває воно зараз."
    ),
    "robustness.mixed.flat": (
        "{label}: змішаний сигнал. Частка уваги, {basis}: {change}, вираженого тренду немає; але "
        "за останні {months} міс. до тих самих місяців рік тому перегляди статті {article}, трафік "
        "розділу {edition}, тобто частка зсунулася."
    ),
    "robustness.reversing.declining": (
        "{label}: можливий розворот. Частка уваги, {basis}: {change}; але за останні {months} міс. "
        "до тих самих місяців рік тому перегляди статті {article}, трафік розділу {edition}, тобто "
        "частка зросла. Щоб це підтвердити, потрібно ще кілька місяців."
    ),
    "robustness.reversing.growing": (
        "{label}: можливий розворот. Частка уваги, {basis}: {change}; але за останні {months} міс. "
        "до тих самих місяців рік тому перегляди статті {article}, трафік розділу {edition}, тобто "
        "частка знизилася. Щоб це підтвердити, потрібно ще кілька місяців."
    ),
    "outcome.large_growing": (
        "{label}: частка уваги вища і зростає{recent} → сильний кандидат для наступної перевірки."
    ),
    "outcome.large_flat": (
        "{label}: частка уваги вища, вираженого тренду немає{recent} → перевірити, чи "
        "перетворюється помітний інтерес на реальний попит."
    ),
    "outcome.large_declining": (
        "{label}: частка уваги вища, але довгостроково знижується{recent} → перевірити, чи "
        "перетворюється помітний інтерес на реальний попит."
    ),
    "outcome.small_growing": (
        "{label}: частка уваги нижча, але зростає{recent} → ранній сигнал; перевірте, чи це не "
        "ефект низької бази."
    ),
    "outcome.small_flat": (
        "{label}: частка уваги нижча, вираженого тренду немає{recent} → слабший сигнал для "
        "наступної перевірки."
    ),
    "outcome.small_declining": (
        "{label}: частка уваги нижча і знижується{recent} → слабший сигнал для наступної перевірки."
    ),
    "outcome.single_growing": (
        "{label}: частка уваги зростає{recent} → сигнал, який варто підтвердити другим джерелом."
    ),
    "outcome.single_flat": (
        "{label}: у частки уваги немає вираженого тренду{recent} → наявна аудиторія без висхідного "
        "сигналу."
    ),
    "outcome.single_declining": (
        "{label}: частка уваги знижується{recent} → висхідного сигналу немає."
    ),
    "answer.conclusion.strong": (
        "{label} поєднує найвищу частку уваги з її зростанням: найсильніший кандидат для подальшої "
        "перевірки."
    ),
    "answer.conclusion.emerging": (
        "У {label} частка уваги нижча, але зростає: ранній сигнал; перевірте, чи це не ефект "
        "низької бази."
    ),
    "answer.conclusion.no_growth": (
        "Частка уваги не зростає в жодному розділі; у {label} вона найвища, тож це кращий кандидат "
        "для подальшого дослідження, а не для ставки на розширення."
    ),
    "answer.conclusion.no_growth_ranked": (
        "Частка уваги не зростає в жодному розділі; {label} на першому місці в рейтингу, тож це "
        "кращий кандидат для подальшого дослідження, а не для ставки на розширення."
    ),
    "answer.conclusion.no_growth_split": (
        "Частка уваги не зростає в жодному розділі; {label} на першому місці в рейтингу, а в "
        "{largest} найвища частка уваги: обидва — кандидати для подальшого дослідження, а не для "
        "ставки на розширення."
    ),
    "answer.conclusion.single_growing": (
        "Частка уваги зростає: цей сигнал варто підтвердити другим джерелом."
    ),
    "answer.conclusion.single_flat": (
        "У частки уваги немає вираженого тренду: наявна аудиторія без висхідного сигналу."
    ),
    "answer.conclusion.single_declining": (
        "Частка уваги знижується: за даними Вікіпедії висхідного сигналу в теми немає."
    ),
    "profile.growth_market": "велика аудиторія, частка уваги зростає",
    "profile.early_niche": "невелика аудиторія, частка уваги зростає",
    "profile.mature_market": "велика аудиторія, частка уваги стабільна",
    "profile.declining": "частка уваги знижується",
    "question.assess": (
        "Оцінити, куди рухається частка уваги до теми «{topics}» у розділах {projects}"
    ),
    "trend.significant": "Тренд частки уваги статистично значущий (p = {p_value:.3f}, {direction})",
    "trend.not_significant": "Тренд частки уваги статистично незначущий (p = {p_value:.3f})",
    "robustness.confirmed.declining": (
        "{label}: стійке зниження частки уваги. Частка уваги, {basis}: {change}; за останні "
        "{months} міс. до тих самих місяців рік тому перегляди статті {article}, трафік розділу "
        "{edition}, тобто частка далі знижується."
    ),
    "robustness.confirmed.growing": (
        "{label}: стійке зростання частки уваги. Частка уваги, {basis}: {change}; за останні "
        "{months} міс. до тих самих місяців рік тому перегляди статті {article}, трафік розділу "
        "{edition}, тобто частка далі зростає."
    ),
    "chart.index_title": "Перегляди статті проти трафіку розділу",
    "chart.index_subtitle": (
        "Індекс: середнє перших 12 місяців = 100, середнє за 3 місяці. Стаття нижче розділу — тема "
        "втрачає частку уваги."
    ),
    "chart.axis_index": "індекс, перші 12 міс. = 100",
    "chart.series_article_months": "перегляди статті, місяць",
    "chart.series_article_smooth": "перегляди статті",
    "chart.series_edition_short": "трафік розділу",
    "chart.note.event": "{month} ×{multiple}",
    "chart.note.possible_bot": "{month} ×{multiple}, можливо боти",
    "chart.note.edition": "{month} розділ ×{multiple}",
    "chart.note.unknown": "{month} ×{multiple}",
    "chart.yoy_title": "{metric}: зміна до тих самих місяців рік тому",
    "chart.yoy_subtitle": "Кожна точка — останні 3 місяці до тих самих 3 місяців рік тому.",
    "chart.axis_growth": "зміна, %",
    "chart.dumbbell_title": "{metric}: раніше і зараз",
    "chart.dumbbell_basis.yoy": "Середнє за попередні 12 місяців і за останні 12 місяців.",
    "chart.dumbbell_basis.halves": "Середнє за першу і за другу половину періоду.",
    "chart.dumbbell_basis.mixed": "Середнє за ранні і за пізні місяці.",
    "chart.series_before.yoy": "попередні 12 міс.",
    "chart.series_after.yoy": "останні 12 міс.",
    "chart.series_before.halves": "перша половина",
    "chart.series_after.halves": "друга половина",
    "chart.series_before.mixed": "раніше",
    "chart.series_after.mixed": "зараз",
    "chart.scatter_title": "{metric}: розмір і зміна",
    "chart.scatter_subtitle": "Правіше — частка більша; вище лінії — зростає, нижче — знижується.",
    "chart.axis_log": "{unit}, логарифмічна шкала",
    "chart.axis_per_million": "переглядів статті на 1 млн переглядів розділу",
    "chart.season_period": "Розраховано за {start} – {end}.",
}
