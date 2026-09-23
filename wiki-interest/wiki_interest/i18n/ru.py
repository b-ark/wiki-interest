"""Russian message catalog. Mirrors the key set of :mod:`wiki_interest.i18n.en`."""

# ruff: noqa: RUF001  -- Cyrillic letters are homoglyphs of Latin ones by nature.

from __future__ import annotations

__all__ = ["MESSAGES"]

MESSAGES: dict[str, str] = {
    # -- reliability reasons ---------------------------------------------------------------
    "window_length.ok": "{months} месяцев данных: достаточно для сравнения год к году",
    "window_length.too_short": "Только {months} месяцев данных: слишком мало для оценки тренда",
    "completeness.ok": "В месячных данных нет пропусков",
    "completeness.gaps": "{missing_months} месяцев без данных ({share:.0%} периода)",
    "completeness.sparse": (
        "{missing_months} месяцев без данных ({share:.0%} периода): ряд слишком разреженный"
    ),
    "spikes.unavailable": "Дневные данные недоступны, поэтому всплески оценить не удалось",
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
    "question.rank": "Ранжировать разделы {projects} по интересу к теме «{topics}»",
    # -- report sections -------------------------------------------------------------------
    "report.title_default": "Анализ интереса по просмотрам Википедии",
    "report.question": "Вопрос",
    "report.audience": "Контекст",
    "report.key_numbers": "Ключевые числа",
    "report.chart": "График",
    "report.charts": "Графики",
    "report.verdict": "Вывод",
    "report.limitations": "Допущения и ограничения",
    "report.next_steps": "Что можно уточнить",
    "report.sources": "Источники",
    "report.period": "Период",
    "report.projects": "Разделы",
    "report.topics": "Темы",
    "report.generated": "Сформировано",
    "report.version": "Версия навыка",
    "report.data_through": "Данные по",
    "report.comparison_table": "Сравнение",
    "report.ranking_table": "Рейтинг",
    "report.notes": "Примечания",
    "report.see_summary": "… полный список в summary.md",
    "report.no_chart": "Для этого запуска график не построен",
    # -- table columns ---------------------------------------------------------------------
    "col.topic": "Тема",
    "col.project": "Раздел",
    "col.reliability": "Надёжность",
    "col.rank": "№",
    "col.score": "Балл",
    "col.profile": "Профиль",
    "col.article": "Статья",
    "col.role": "Роль",
    "col.source": "Источник",
    "col.status": "Статус",
    "col.rationale": "Почему",
    # -- agent summary ---------------------------------------------------------------------
    "summary.answer": "Ответ",
    "summary.key_numbers": "Ключевые числа",
    "summary.caveats": "Оговорки",
    "summary.refine": "Что можно уточнить",
    "summary.artifacts": "Файлы",
    "summary.clarification_needed": "Нужно уточнение",
    "summary.candidates": "Кандидаты",
    "summary.clarification_hint": (
        "Если из разговора понятно, какое значение имеет в виду пользователь, сами укажите qid "
        "этого кандидата и скажите, какое значение выбрано; иначе спросите пользователя. Затем "
        "запустите снова с topics[].qid."
    ),
    "summary.bundles": "Проанализированные статьи",
    # -- charts ----------------------------------------------------------------------------
    "chart.axis_views": "просмотров в месяц",
    "chart.footnote": "Источник: {source} · Период: {period}",
    "chart.no_data": "Нет данных за этот период",
    # -- вердикты ----------------------------------------------------------------------------
    "verdict.rank.headline": "Самая перспективная аудитория: {label} ({profile})",
    "verdict.none.headline": (
        "Нет данных для анализа тем {topics}: статей в {projects} не найдено"
    ),
    "rank.rationale.insufficient": "недостаточно данных для ранжирования",
    "note.not_found": "нет статьи в этом разделе",
    "note.search_fallback": "статья найдена поиском",
    # -- ограничения и следующие шаги --------------------------------------------------------
    "limitation.coverage": (
        "Разделы по-разному освещают тему; отсутствующая или короткая статья занижает сигнал "
        "независимо от интереса аудитории."
    ),
    "limitation.language": (
        "Языковой раздел — не страна: его читают жители многих стран, а жители одной страны "
        "читают разные разделы."
    ),
    "limitation.bots": (
        "Фильтрация ботов на стороне Wikimedia несовершенна; проверки автоматического трафика "
        "и всплесков ловят лишь часть."
    ),
    "limitation.missing_titles": (
        "Эти запрошенные названия не существуют и были пропущены: {titles}"
    ),
    "limitation.not_found": (
        "Для темы «{topic}» нет статьи в {projects}: эти разделы помечены как «нет статьи», "
        "а не как нулевой интерес."
    ),
    "limitation.search_fallback": (
        "В {projects} статья найдена полнотекстовым поиском; проверьте, что это именно та статья."
    ),
    "limitation.absolute": (
        "Сравнивались сырые количества просмотров без нормализации на размер раздела."
    ),
    "next.extend_period": (
        "Расширьте период (например, 36 или 60 месяцев), чтобы проверить устойчивость тренда."
    ),
    "next.add_projects": (
        "Добавьте другие разделы, чтобы увидеть, специфична ли картина для {projects}."
    ),
    "next.absolute": (
        "Сравните сырые просмотры (normalization: absolute), чтобы оценить размер аудитории, "
        "а не долю."
    ),
    "next.per_million": "Сравните доли на миллион, чтобы убрать влияние размера раздела.",
    "next.pin_title": "Укажите точное название статьи для {projects} через extra_titles.",
    "next.research": "Исследовать следующей: {label} ({profile}).",
    # -- editions without an article: the question and the substitutes ------------------
    "resolution.substitute_redirect": (
        "Статьи нет; измерено через перенаправление «{title}»: учтены только переходы по этому "
        "названию, поэтому это нижняя граница"
    ),
    "resolution.substitute_broader": (
        "Статьи нет; измерено через более общую статью «{title}»: числа описывают более широкую "
        "тему, поэтому это верхняя граница"
    ),
    "resolution.substitute_mention": (
        "Статьи нет; измерено через «{title}», где тема только упоминается: числа описывают ту "
        "статью, а не тему"
    ),
    "bundle_status.substitute": "замена",
    "source.substitute": "замена, выбранная пользователем",
    "summary.missing_needed": "Нужно решение: нет статьи",
    "summary.apply_choice": "Для агента: значение для topics[].substitutes",
    "gap.headline": (
        "Пока ничего не измерено: в {projects} нет статьи на эту тему. Сначала выберите, что там "
        "измерять."
    ),
    "gap.question": "В {project} нет статьи «{topic}».",
    "gap.term": "«{term}»",
    "gap.searched": "Искали: {terms}.",
    "gap.no_terms": (
        "Название темы на этом языке неизвестно, поэтому перенаправления и упоминания не искали; "
        "укажите его в local_terms, чтобы найти их."
    ),
    "option.redirect": (
        "Перенаправление «{title}» ведёт на статью «{target}»{section}: {views} просмотров/мес. "
        "Учитывает только переходы именно по этому названию, поэтому это нижняя граница."
    ),
    "option.section": ", раздел статьи «{section}»",
    "option.broader": (
        "Более общая статья «{title}»: {views} просмотров/мес. Верхняя граница: большинство "
        "читателей пришли за более широкой темой."
    ),
    "option.mention": (
        "Статья «{title}» упоминает тему: {views} просмотров/мес. Тема — лишь малая её часть."
    ),
    "option.snippet": "Фрагмент: «…{snippet}…»",
    "option.skip": "Не анализировать {project}: в отчёте будет «нет статьи», а не нулевой интерес.",
    "substitute.redirect": "перенаправление «{title}»",
    "substitute.broader": "более общую статью «{title}»",
    "substitute.mention": "статью «{title}», где упоминается тема",
    "note.substitute": "статьи нет; измерено через {what}",
    "limitation.substitute": (
        "Для «{topic}» в {project} нет статьи; числа там получены через {what}, как было выбрано."
    ),
    "rank.rationale.substitute": "не ранжировано: измерено через другую статью, а не саму тему",
    "gap.entity": (
        "Тема: «{label}»{description} ({qid}). Языков, где есть статья: {count}, в том числе "
        "{languages}."
    ),
    "gap.entity_description": " — {description}",
    "gap.entity_nowhere": (
        "Тема: «{label}»{description} ({qid}); статьи о ней нет ни в одном разделе Википедии."
    ),
    "gap.matched_en": (
        "Она найдена по английскому названию, потому что поиск на языке запроса ничего не дал; "
        "убедитесь, что это нужная тема."
    ),
    "gap.no_entity": (
        "Тема не найдена в Wikidata, поэтому неизвестно, в каких разделах она есть; проверьте "
        "формулировку или укажите query_en."
    ),
    "summary.topic_line": "Тема: «{label}»{description} ({qid}).",
    "summary.alternatives": "Другие значения этого названия: {items}.",
    "summary.candidate_articles": "статьи есть в {projects}",
    "summary.candidate_no_articles": "статей в запрошенных разделах нет",
    "summary.not_found_needed": "Тема не найдена",
    "notfound.headline": (
        "По запросу «{query}» ничего не найдено ни в Wikidata, ни в Википедии — ни по этой "
        "формулировке, ни по английскому названию."
    ),
    "summary.not_found_hint": (
        "Честно скажите об этом пользователю и попросите ссылку на статью Википедии на любом языке "
        "о том, что его интересует. Вставьте её в topics[].article_url в request.json и запустите "
        "снова."
    ),
    "summary.which_meaning": "Какое значение «{query}» имеется в виду?",
    "summary.topic_only": (
        "Только проверка темы: тема определена, больше ничего запускаться не будет; отчёта нет, и "
        "это ожидаемо. Скажите пользователю, какая тема и статьи определены, и завершите."
    ),
    # -- report findings, implications and charts --------------------------------------------
    "format.date": "{day:02d}.{month:02d}.{year}",
    "format.month_year": "{month:02d}.{year}",
    "basis.yoy": "последние 12 месяцев к предыдущим 12",
    "basis.halves": "вторая половина периода к первой",
    "basis.slope": "по тренду, в год",
    "basis.mixed": "по разделам",
    "finding.unit.per_million": "на миллион просмотров раздела",
    "finding.unit.views": "просмотров/мес",
    "chart.season_title": "Месяцы относительно обычного уровня",
    "chart.axis_season": "% к обычному уровню",
    "report.title_topic": "{topic}: интерес в Википедии",
    "report.context": "Связанные статьи (контекст, не учтены)",
    "report.method_note": "О методе",
    "report.sources_names": "Wikimedia Pageviews API, Викиданные, MediaWiki API",
    "summary.context": "Связанные статьи (контекст, не учтены)",
    "summary.context_item": "{title} — {views} просмотров/мес",
    "summary.bundle_count": "измерена главная статья; связанных статей как контекст: {related}",
    "summary.method": "О методе",
    "month.1": "январь",
    "month.short.1": "янв",
    "month.2": "февраль",
    "month.short.2": "фев",
    "month.3": "март",
    "month.short.3": "мар",
    "month.4": "апрель",
    "month.short.4": "апр",
    "month.5": "май",
    "month.short.5": "май",
    "month.6": "июнь",
    "month.short.6": "июн",
    "month.7": "июль",
    "month.short.7": "июл",
    "month.8": "август",
    "month.short.8": "авг",
    "month.9": "сентябрь",
    "month.short.9": "сен",
    "month.10": "октябрь",
    "month.short.10": "окт",
    "month.11": "ноябрь",
    "month.short.11": "ноя",
    "month.12": "декабрь",
    "month.short.12": "дек",
    "summary.redirects": "+{count} перенаправл.",
    "finding.item.season": "{label}: {peak_month} {peak}, {trough_month} {trough}",
    "finding.no_article": (
        "{label}: в этом разделе нет статьи на тему, поэтому он показан как «нет данных», а не как "
        "нулевой интерес."
    ),
    "finding.substitute": (
        "{label}: статьи на тему нет; измерено через {what} — это более широкая тема, поэтому с "
        "другими разделами не сравнивается."
    ),
    "report.bundle_composition": "Проанализированные статьи",
    "summary.missing_hint": (
        "Остановитесь: покажите пользователю эти варианты, спросите, какой взять для каждого "
        "раздела, и закончите ответ этим вопросом. Не выбирайте за пользователя и не запускайте "
        "снова, пока он не ответит. Затем добавьте значение выбранного варианта из блока ниже в "
        "topics[].substitutes в request.json и запустите снова."
    ),
    "answer.conclusion.unknown": "Прежде чем решать, расширьте период.",
    "answer.conclusion.low_trust": (
        "Данных недостаточно для вывода: считайте цифры ориентировочными."
    ),
    "answer.no_article": (
        "В {projects} нет статьи: интерес там не измерен, и это не то же самое, что отсутствие "
        "интереса."
    ),
    "outcome.unknown": "{label}: период слишком короткий, чтобы судить о тренде.",
    "outcome.low_trust": "{label}: данных недостаточно для вывода.",
    "outcome.substitute": "{label}: измерена другая статья, поэтому о самой теме это говорит мало.",
    "outcome.no_article": (
        "{label}: статьи нет, интерес не измерен (это не то же самое, что отсутствие интереса)."
    ),
    "next_step.confirm": (
        "Следующий шаг: подтвердить сигнал независимым источником спроса — например, Google "
        "Trends, объёмом поисковых запросов или небольшим рекламным тестом. Просмотры Википедии не "
        "показывают готовность платить."
    ),
    "next_step.confirm_for": (
        "Следующий шаг: подтвердить сигнал для {label} независимым источником спроса — например, "
        "Google Trends, объёмом поисковых запросов или небольшим рекламным тестом. Просмотры "
        "Википедии не показывают готовность платить."
    ),
    "next_step.check_demand": (
        "Следующий шаг: прежде чем вкладываться, проверить существующий спрос независимым "
        "источником — например, Google Trends, объёмом поисковых запросов или небольшим рекламным "
        "тестом. Просмотры Википедии не показывают готовность платить."
    ),
    "next_step.check_demand_for": (
        "Следующий шаг: проверить существующий спрос в {label} независимым источником — например, "
        "Google Trends, объёмом поисковых запросов или небольшим рекламным тестом. Просмотры "
        "Википедии не показывают готовность платить."
    ),
    "next_step.low_trust": (
        "Следующий шаг: расширить период или уточнить статью, затем подтвердить сигнал независимым "
        "источником спроса — например, Google Trends, объёмом поисковых запросов или небольшим "
        "рекламным тестом."
    ),
    "evidence.months": "{months} мес. наблюдений",
    "evidence.months_short": "всего {months} мес. наблюдений",
    "evidence.no_gaps": "нет пропущенных месяцев",
    "evidence.gaps": "пропущено месяцев: {missing_months}",
    "evidence.spikes_high": "всплески дают {share} просмотров",
    "card.no_article": "нет статьи",
    "value.per_million": "{value} на 1 млн",
    "report.answer": "Ответ",
    "report.vs_edition": "Тема растёт быстрее или медленнее своей Википедии?",
    "report.vs_edition_basis": "Сравнение: {basis}",
    "report.decision": "Что это означает для решения",
    "report.other_findings": "Что ещё стоит знать",
    "report.coverage": (
        "Проверка охвата: найдены связанные статьи — {items}. Они служат контекстом и не входят в "
        "основную метрику."
    ),
    "report.coverage_item": "{project}: {count}",
    "summary.decision": "Что это означает для решения",
    "finding.item.season_tentative": "{label}: {peak_month} {peak}, {trough_month} {trough}",
    "limitation.scope": (
        "Анализ измеряет чтение одной основной статьи и её перенаправлений: это косвенный "
        "показатель интереса к теме, а не размер рынка и не готовность платить."
    ),
    "summary.findings": "Что ещё стоит знать",
    "robustness.unknown": "{label}: об устойчивости судить нельзя: {reason}.",
    "robustness.reason.low_trust": "данные слишком слабые (см. строку о данных)",
    "robustness.reason.low_volume": "аудитория слишком мала для сравнения за три месяца",
    "robustness.reason.no_recent": "нет сравнения с теми же месяцами год назад",
    "robustness.reason.no_trend": "период слишком короткий для тренда",
    "report.robustness": "Насколько устойчив этот вывод?",
    "report.recent_basis": "последние {months} мес. к тем же месяцам год назад",
    "report.data_line": "Данные: {items}.",
    "report.data_concerns": "{label}: {items}.",
    "report.reliability": "Проверки данных",
    "evidence.spikes_ok": "отдельные всплески не определяют результат",
    "outcome.recent.confirmed": "; недавние данные это подтверждают",
    "outcome.recent.mixed": "; недавние данные это пока не подтверждают",
    "outcome.recent.reversing": "; в последние месяцы направление сменилось",
    "metric.article_views": "Просмотры статьи",
    "metric.edition_views": "Трафик раздела",
    "metric.attention_share": "Доля внимания",
    "metric.attention_share_unit": "просмотров статьи на 1 млн просмотров раздела",
    "headline.subject.share_one": "Доля внимания к теме {topics}",
    "headline.subject.share_many": "Доля внимания к темам {topics}",
    "headline.subject.views_one": "Число просмотров статьи о теме {topics}",
    "headline.subject.views_many": "Число просмотров статей о темах {topics}",
    "headline.scope.both": "в обоих разделах",
    "headline.scope.all": "во всех разделах",
    "headline.scope.everywhere": "везде",
    "headline.one.growing": "{subject} в {project} растёт{recent}",
    "headline.one.declining": "{subject} в {project} снижается{recent}",
    "headline.one.flat": "{subject} в {project} без выраженного тренда{recent}",
    "headline.unknown": "Период слишком короткий, чтобы судить, куда движется {subject}.",
    "headline.all.growing": "{subject} растёт {scope}, {fastest}",
    "headline.all.declining": "{subject} снижается {scope}, {fastest}",
    "headline.all.flat": "{subject} {scope} без выраженного тренда",
    "headline.fastest": "быстрее всего — в {label}",
    "headline.fastest_steadier": "в {label} — быстрее и устойчивее",
    "headline.mixed": "{subject}: {parts}",
    "headline.part.growing": "растёт в {items}",
    "headline.part.declining": "снижается в {items}",
    "headline.part.flat": "без выраженного тренда в {items}",
    "headline.part.unknown": "слишком короткая история в {items}",
    "happening.size_share": "{metric} ({unit}), в среднем за период: {items}.",
    "happening.size_views": "{metric} в месяц, в среднем за период: {items}.",
    "happening.change": "{metric}, {basis}: {items}.",
    "happening.pair": "{article} и {edition}",
    "happening.vs_edition": "{article} и {edition}, {basis}: {items}.",
    "kpi.metric": "Показатель",
    "kpi.views": "Просмотры статьи в месяц (в среднем)",
    "kpi.share": "Доля внимания, на 1 млн просмотров раздела (в среднем)",
    "kpi.change": "{metric}, {basis}",
    "kpi.recent": "Последние {months} мес. подтверждают тренд?",
    "robustness.value.confirmed": "да",
    "robustness.value.mixed": "нет, доля стабильна",
    "robustness.value.mixed_flat": "нет, доля сдвинулась",
    "robustness.value.reversing": "нет, направление изменилось",
    "robustness.value.unknown": "недостаточно данных",
    "summary.topic_auto": "Автоматически сопоставлено с {qid} по указанному смыслу.",
    "spikes.low": (
        "На дни всплесков приходится {share:.0%} просмотров: вывод о тренде не определяется "
        "отдельными всплесками"
    ),
    "spikes.notable": (
        "На дни всплесков приходится {share:.0%} просмотров: часть тренда может быть новостной"
    ),
    "spikes.dominant": (
        "На дни всплесков приходится {share:.0%} просмотров: тренд держится на всплесках, а не на "
        "постоянном чтении"
    ),
    "window_length.short": "Только {months} мес. данных: последние 12 месяцев не с чем сравнить",
    "limitation.short_window": (
        "Только {months} мес. данных: последние 12 месяцев не с чем сравнить, а тест тренда слаб."
    ),
    "rank.rationale": (
        "{profile}: доля внимания {growth} (основное окно), просмотров статьи в месяц {views}, "
        "надёжность {level}"
    ),
    "verdict.rank.headline_declining": (
        "Доля внимания снижается во всех разделах; относительно самая сильная аудитория: {label} "
        "({profile})"
    ),
    "finding.level_shift": (
        "{label}: {metric} с {start_month} держится на уровне {change} к прежнему уже {months} "
        "мес. (в среднем {before} → {after} {unit})."
    ),
    "finding.burst": (
        "{label}: всплеск просмотров статьи {start} – {end}, пик {peak_day}: {peak_views} "
        "просмотров за день, ×{multiple} к обычным {baseline}; на всплеск приходится {share} "
        "просмотров статьи за период."
    ),
    "finding.burst_day": (
        "{label}: однодневный всплеск просмотров статьи {peak_day}: {peak_views} просмотров, "
        "×{multiple} к обычным {baseline}; это {share} просмотров статьи за период."
    ),
    "finding.season": (
        "{label}: просмотры статьи по месяцам к обычному уровню: сильнее всего {peak_month} "
        "({peak}), слабее всего {trough_month} ({trough})."
    ),
    "finding.group.season": (
        "Просмотры статьи по месяцам, самый сильный и самый слабый месяц к обычному уровню: "
        "{items}."
    ),
    "finding.season_tentative": (
        "{label}: в просмотрах статьи есть признаки сезонности ({peak_month} {peak}, "
        "{trough_month} {trough} к обычному уровню); для уверенного вывода нужна более длинная "
        "история — каждый месяц наблюдался лишь несколько раз."
    ),
    "finding.group.season_tentative": (
        "В просмотрах статьи есть признаки сезонности в {count} разделах ({items}, к обычному "
        "уровню); для уверенного вывода нужна более длинная история."
    ),
    "card.size": "Доля внимания, на 1 млн просмотров раздела",
    "card.size_absolute": "Просмотры статьи в месяц",
    "card.views_note": "просмотры статьи в месяц: {items}",
    "card.momentum": "Доля внимания: изменение",
    "card.momentum_absolute": "Просмотры статьи: изменение",
    "card.robustness": "Последние месяцы подтверждают тренд?",
    "col.views_avg": "Просмотры статьи/мес.",
    "col.per_million_avg": "Доля внимания, на 1 млн",
    "col.share_growth": "Доля внимания: изменение",
    "col.views_growth": "Просмотры статьи: изменение",
    "col.edition_growth": "Трафик раздела: изменение",
    "col.trend": "Тренд доли внимания",
    "edition.gaining": (
        "{label}: просмотры статьи {article}, трафик раздела {edition} → доля внимания растёт"
    ),
    "edition.losing": (
        "{label}: просмотры статьи {article}, трафик раздела {edition} → доля внимания снижается"
    ),
    "edition.in_line": (
        "{label}: просмотры статьи {article}, трафик раздела {edition} → доля внимания держится"
    ),
    "robustness.confirmed.flat": (
        "{label}: стабильно. Доля внимания, {basis}: {change}, выраженного тренда нет; за "
        "последние {months} мес. к тем же месяцам год назад просмотры статьи {article}, трафик "
        "раздела {edition}, то есть доля держится."
    ),
    "robustness.mixed.declining": (
        "{label}: смешанный сигнал. Доля внимания, {basis}: {change}; но за последние {months} "
        "мес. к тем же месяцам год назад просмотры статьи {article}, трафик раздела {edition}, то "
        "есть доля стабильна. Долгосрочное снижение видно, но пока неясно, продолжается ли оно "
        "сейчас."
    ),
    "robustness.mixed.growing": (
        "{label}: смешанный сигнал. Доля внимания, {basis}: {change}; но за последние {months} "
        "мес. к тем же месяцам год назад просмотры статьи {article}, трафик раздела {edition}, то "
        "есть доля стабильна. Долгосрочный рост виден, но пока неясно, продолжается ли он сейчас."
    ),
    "robustness.mixed.flat": (
        "{label}: смешанный сигнал. Доля внимания, {basis}: {change}, выраженного тренда нет; но "
        "за последние {months} мес. к тем же месяцам год назад просмотры статьи {article}, трафик "
        "раздела {edition}, то есть доля сдвинулась."
    ),
    "robustness.reversing.declining": (
        "{label}: возможный разворот. Доля внимания, {basis}: {change}; но за последние {months} "
        "мес. к тем же месяцам год назад просмотры статьи {article}, трафик раздела {edition}, то "
        "есть доля выросла. Чтобы это подтвердить, нужно ещё несколько месяцев."
    ),
    "robustness.reversing.growing": (
        "{label}: возможный разворот. Доля внимания, {basis}: {change}; но за последние {months} "
        "мес. к тем же месяцам год назад просмотры статьи {article}, трафик раздела {edition}, то "
        "есть доля снизилась. Чтобы это подтвердить, нужно ещё несколько месяцев."
    ),
    "outcome.large_growing": (
        "{label}: доля внимания выше и растёт{recent} → сильный кандидат для следующей проверки."
    ),
    "outcome.large_flat": (
        "{label}: доля внимания выше, выраженного тренда нет{recent} → проверить, превращается ли "
        "заметный интерес в реальный спрос."
    ),
    "outcome.large_declining": (
        "{label}: доля внимания выше, но долгосрочно снижается{recent} → проверить, превращается "
        "ли заметный интерес в реальный спрос."
    ),
    "outcome.small_growing": (
        "{label}: доля внимания ниже, но растёт{recent} → ранний сигнал; проверьте, не эффект ли "
        "это низкой базы."
    ),
    "outcome.small_flat": (
        "{label}: доля внимания ниже, выраженного тренда нет{recent} → более слабый сигнал для "
        "следующей проверки."
    ),
    "outcome.small_declining": (
        "{label}: доля внимания ниже и снижается{recent} → более слабый сигнал для следующей "
        "проверки."
    ),
    "outcome.single_growing": (
        "{label}: доля внимания растёт{recent} → сигнал, который стоит подтвердить вторым "
        "источником."
    ),
    "outcome.single_flat": (
        "{label}: у доли внимания нет выраженного тренда{recent} → существующая аудитория без "
        "восходящего сигнала."
    ),
    "outcome.single_declining": (
        "{label}: доля внимания снижается{recent} → восходящего сигнала нет."
    ),
    "answer.conclusion.strong": (
        "{label} сочетает самую высокую долю внимания с её ростом: самый сильный кандидат для "
        "дальнейшей проверки."
    ),
    "answer.conclusion.emerging": (
        "У {label} доля внимания ниже, но растёт: ранний сигнал; проверьте, не эффект ли это "
        "низкой базы."
    ),
    "answer.conclusion.no_growth": (
        "Доля внимания не растёт ни в одном разделе; у {label} она самая высокая, поэтому это "
        "лучший кандидат для дальнейшего исследования, а не для ставки на расширение."
    ),
    "answer.conclusion.no_growth_ranked": (
        "Доля внимания не растёт ни в одном разделе; {label} на первом месте в рейтинге, поэтому "
        "это лучший кандидат для дальнейшего исследования, а не для ставки на расширение."
    ),
    "answer.conclusion.no_growth_split": (
        "Доля внимания не растёт ни в одном разделе; {label} на первом месте в рейтинге, а у "
        "{largest} самая высокая доля внимания: оба — кандидаты для дальнейшего исследования, а не "
        "для ставки на расширение."
    ),
    "answer.conclusion.single_growing": (
        "Доля внимания растёт: этот сигнал стоит подтвердить вторым источником."
    ),
    "answer.conclusion.single_flat": (
        "У доли внимания нет выраженного тренда: существующая аудитория без восходящего сигнала."
    ),
    "answer.conclusion.single_declining": (
        "Доля внимания снижается: по данным Википедии восходящего сигнала у темы нет."
    ),
    "profile.growth_market": "крупная аудитория, доля внимания растёт",
    "profile.early_niche": "небольшая аудитория, доля внимания растёт",
    "profile.mature_market": "крупная аудитория, доля внимания стабильна",
    "profile.declining": "доля внимания снижается",
    "question.assess": (
        "Оценить, куда движется доля внимания к теме «{topics}» в разделах {projects}"
    ),
    "trend.significant": (
        "Тренд доли внимания статистически значим (p = {p_value:.3f}, {direction})"
    ),
    "trend.not_significant": "Тренд доли внимания статистически незначим (p = {p_value:.3f})",
    "robustness.confirmed.declining": (
        "{label}: устойчивое снижение доли внимания. Доля внимания, {basis}: {change}; за "
        "последние {months} мес. к тем же месяцам год назад просмотры статьи {article}, трафик "
        "раздела {edition}, то есть доля продолжает снижаться."
    ),
    "robustness.confirmed.growing": (
        "{label}: устойчивый рост доли внимания. Доля внимания, {basis}: {change}; за последние "
        "{months} мес. к тем же месяцам год назад просмотры статьи {article}, трафик раздела "
        "{edition}, то есть доля продолжает расти."
    ),
    "chart.index_title": "Просмотры статьи против трафика раздела",
    "chart.index_subtitle": (
        "Индекс: среднее первых 12 месяцев = 100, среднее за 3 месяца. Статья ниже раздела — тема "
        "теряет долю внимания."
    ),
    "chart.axis_index": "индекс, первые 12 мес. = 100",
    "chart.series_article_months": "просмотры статьи, месяц",
    "chart.series_article_smooth": "просмотры статьи",
    "chart.series_edition_short": "трафик раздела",
    "chart.note.event": "{month} ×{multiple}",
    "chart.note.possible_bot": "{month} ×{multiple}, возможно боты",
    "chart.note.edition": "{month} раздел ×{multiple}",
    "chart.note.unknown": "{month} ×{multiple}",
    "chart.yoy_title": "{metric}: изменение к тем же месяцам год назад",
    "chart.yoy_subtitle": "Каждая точка — последние 3 месяца к тем же 3 месяцам год назад.",
    "chart.axis_growth": "изменение, %",
    "chart.dumbbell_title": "{metric}: раньше и сейчас",
    "chart.dumbbell_basis.yoy": "Среднее за предыдущие 12 месяцев и за последние 12 месяцев.",
    "chart.dumbbell_basis.halves": "Среднее за первую и за вторую половину периода.",
    "chart.dumbbell_basis.mixed": "Среднее за ранние и за поздние месяцы.",
    "chart.series_before.yoy": "предыдущие 12 мес.",
    "chart.series_after.yoy": "последние 12 мес.",
    "chart.series_before.halves": "первая половина",
    "chart.series_after.halves": "вторая половина",
    "chart.series_before.mixed": "раньше",
    "chart.series_after.mixed": "сейчас",
    "chart.scatter_title": "{metric}: размер и изменение",
    "chart.scatter_subtitle": "Правее — доля больше; выше линии — растёт, ниже — снижается.",
    "chart.axis_log": "{unit}, логарифмическая шкала",
    "chart.axis_per_million": "просмотров статьи на 1 млн просмотров раздела",
    "chart.season_period": "Рассчитано за {start} – {end}.",
}
