"""Polish message catalog. Mirrors the key set of :mod:`wiki_interest.i18n.en`."""

from __future__ import annotations

__all__ = ["MESSAGES"]

MESSAGES: dict[str, str] = {
    # -- reliability reasons ---------------------------------------------------------------
    "window_length.ok": "{months} miesięcy danych: wystarczy do porównania rok do roku",
    "window_length.too_short": "Tylko {months} miesięcy danych: za mało, by ocenić trend",
    "completeness.ok": "Brak luk w danych miesięcznych",
    "completeness.gaps": "{missing_months} miesięcy bez danych ({share:.0%} okresu)",
    "completeness.sparse": (
        "{missing_months} miesięcy bez danych ({share:.0%} okresu): szereg jest zbyt rzadki"
    ),
    "spikes.unavailable": "Dane dzienne są niedostępne, więc nie oceniono skoków",
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
    "value.na": "b.d.",
    # -- question line ---------------------------------------------------------------------
    "question.compare": "Porównaj zainteresowanie tematem „{topics}” w edycjach {projects}",
    "question.rank": "Uszereguj edycje {projects} według zainteresowania tematem „{topics}”",
    # -- report sections -------------------------------------------------------------------
    "report.title_default": "Analiza zainteresowania na podstawie odsłon Wikipedii",
    "report.question": "Pytanie",
    "report.audience": "Kontekst",
    "report.key_numbers": "Kluczowe liczby",
    "report.chart": "Wykres",
    "report.charts": "Wykresy",
    "report.limitations": "Założenia i ograniczenia",
    "report.next_steps": "Co można doprecyzować",
    "report.sources": "Źródła",
    "report.period": "Okres",
    "report.generated": "Wygenerowano",
    "report.version": "Wersja umiejętności",
    "report.data_through": "Dane do",
    "report.ranking_table": "Ranking",
    "report.notes": "Uwagi",
    "report.see_summary": "… pełna lista w summary.md",
    # -- table columns ---------------------------------------------------------------------
    "col.topic": "Temat",
    "col.project": "Edycja",
    "col.reliability": "Wiarygodność",
    "col.rank": "Nr",
    "col.score": "Wynik",
    "col.profile": "Profil",
    "col.article": "Artykuł",
    "col.role": "Rola",
    "col.source": "Źródło",
    "col.rationale": "Dlaczego",
    # -- agent summary ---------------------------------------------------------------------
    "summary.answer": "Odpowiedź",
    "summary.caveats": "Zastrzeżenia",
    "summary.refine": "Co można doprecyzować",
    "summary.artifacts": "Pliki",
    "summary.clarification_needed": "Potrzebne doprecyzowanie",
    "summary.candidates": "Kandydaci",
    "summary.clarification_hint": (
        "Jeśli z rozmowy jasno wynika, o które znaczenie chodzi użytkownikowi, sam wpisz qid tego "
        "kandydata i powiedz, które znaczenie wybrano; w przeciwnym razie zapytaj użytkownika. "
        "Potem uruchom ponownie z topics[].qid."
    ),
    "summary.bundles": "Analizowane artykuły",
    # -- charts ----------------------------------------------------------------------------
    "chart.axis_views": "odsłon miesięcznie",
    "chart.no_data": "Brak danych za ten okres",
    # -- werdykty ----------------------------------------------------------------------------
    "verdict.rank.headline": ("Najbardziej obiecująca grupa odbiorców: {label} ({profile})"),
    "verdict.none.headline": (
        "Brak danych do analizy tematów {topics}: nie znaleziono artykułów w {projects}"
    ),
    "rank.rationale.insufficient": "za mało danych do rankingu",
    "note.not_found": "brak artykułu w tej edycji",
    "note.search_fallback": "artykuł znaleziony wyszukiwaniem",
    # -- ograniczenia i kolejne kroki --------------------------------------------------------
    "limitation.coverage": (
        "Edycje różnią się jakością opisu tematu; brakujący lub krótki artykuł zaniża sygnał "
        "niezależnie od zainteresowania odbiorców."
    ),
    "limitation.language": (
        "Edycja językowa to nie kraj: czytają ją mieszkańcy wielu krajów, a mieszkańcy "
        "jednego kraju czytają różne edycje."
    ),
    "limitation.bots": (
        "Filtrowanie botów po stronie Wikimedia jest niedoskonałe; kontrole ruchu automatycznego "
        "i skoków wychwytują tylko część."
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
    "limitation.absolute": (
        "Porównano surowe liczby odsłon bez normalizacji względem wielkości edycji."
    ),
    "next.extend_period": ("Wydłuż okres (np. 36 lub 60 miesięcy), aby sprawdzić trwałość trendu."),
    "next.add_projects": (
        "Dodaj inne edycje, aby zobaczyć, czy obraz jest specyficzny dla {projects}."
    ),
    "next.absolute": (
        "Porównaj surowe odsłony (normalization: absolute), aby ocenić wielkość grupy odbiorców, "
        "a nie udział."
    ),
    "next.per_million": "Porównaj udziały na milion, aby usunąć wpływ wielkości edycji.",
    "next.pin_title": "Podaj dokładny tytuł artykułu dla {projects} przez extra_titles.",
    "next.research": "Zbadać jako następną: {label} ({profile}).",
    # -- editions without an article: the question and the substitutes ------------------
    "resolution.substitute_redirect": (
        "Brak artykułu; zmierzono przez przekierowanie „{title}”: liczą się tylko wejścia pod tą "
        "nazwą, więc to dolna granica"
    ),
    "resolution.substitute_broader": (
        "Brak artykułu; zmierzono przez szerszy artykuł „{title}”: liczby opisują szerszy temat, "
        "więc to górna granica"
    ),
    "resolution.substitute_mention": (
        "Brak artykułu; zmierzono przez „{title}”, który tylko wspomina temat: liczby opisują ten "
        "artykuł, a nie temat"
    ),
    "bundle_status.substitute": "zamiennik",
    "source.substitute": "zamiennik wybrany przez użytkownika",
    "summary.missing_needed": "Potrzebna decyzja: brak artykułu",
    "summary.apply_choice": "Dla agenta: wartość do topics[].substitutes",
    "gap.headline": (
        "Nic jeszcze nie zmierzono: w {projects} nie ma artykułu na ten temat. Najpierw wybierz, "
        "co tam mierzyć."
    ),
    "gap.question": "W {project} nie ma artykułu „{topic}”.",
    "gap.term": "„{term}”",
    "gap.searched": "Szukano: {terms}.",
    "gap.no_terms": (
        "Nazwa tematu w tym języku jest nieznana, więc nie szukano przekierowań ani wzmianek; "
        "podaj ją w local_terms, aby je znaleźć."
    ),
    "option.redirect": (
        "Przekierowanie „{title}” prowadzi do artykułu „{target}”{section}: {views} "
        "odsłon/mies. Liczy tylko wejścia pod tą dokładną nazwą, więc to dolna granica."
    ),
    "option.section": ", sekcja „{section}”",
    "option.broader": (
        "Szerszy artykuł „{title}”: {views} odsłon/mies. Górna granica: większość czytelników "
        "przyszła po szerszy temat."
    ),
    "option.mention": (
        "Artykuł „{title}” wspomina temat: {views} odsłon/mies. Temat to tylko niewielka jego "
        "część."
    ),
    "option.snippet": "Fragment: „…{snippet}…”",
    "option.skip": "Pomiń {project}: raport poda „brak artykułu”, a nie zerowe zainteresowanie.",
    "substitute.redirect": "przekierowanie „{title}”",
    "substitute.broader": "szerszy artykuł „{title}”",
    "substitute.mention": "artykuł „{title}”, który wspomina temat",
    "note.substitute": "brak artykułu; zmierzono przez {what}",
    "limitation.substitute": (
        "Dla „{topic}” w {project} nie ma artykułu; liczby pochodzą z pomiaru przez {what}, "
        "zgodnie z wyborem."
    ),
    "rank.rationale.substitute": "poza rankingiem: zmierzono przez inny artykuł, a nie sam temat",
    "gap.entity": (
        "Temat: „{label}”{description} ({qid}). Liczba języków z artykułem: {count}, m.in. "
        "{languages}."
    ),
    "gap.entity_description": " — {description}",
    "gap.entity_nowhere": (
        "Temat: „{label}”{description} ({qid}); żadna edycja Wikipedii nie ma o nim artykułu."
    ),
    "gap.matched_en": (
        "Znaleziono go po nazwie angielskiej, bo wyszukiwanie w języku zapytania nic nie dało; "
        "upewnij się, że to właściwy temat."
    ),
    "gap.no_entity": (
        "Nie znaleziono tematu w Wikidanych, więc nie wiadomo, które edycje go opisują; sprawdź "
        "sformułowanie lub podaj query_en."
    ),
    "summary.topic_line": "Temat: „{label}”{description} ({qid}).",
    "summary.alternatives": "Inne znaczenia tej nazwy: {items}.",
    "summary.candidate_articles": "artykuły w {projects}",
    "summary.candidate_no_articles": "brak artykułu w żądanych edycjach",
    "summary.not_found_needed": "Nie znaleziono tematu",
    "notfound.headline": (
        "Dla „{query}” nic nie znaleziono ani w Wikidanych, ani w Wikipedii — ani po tym "
        "sformułowaniu, ani po nazwie angielskiej."
    ),
    "summary.not_found_hint": (
        "Powiedz o tym użytkownikowi wprost i poproś o link do artykułu Wikipedii w dowolnym "
        "języku o tym, co go interesuje. Wpisz go w topics[].article_url w request.json i uruchom "
        "ponownie."
    ),
    "summary.which_meaning": "Które znaczenie „{query}”?",
    "summary.topic_only": (
        "Tylko sprawdzenie tematu: temat ustalono, nic więcej nie zostanie uruchomione; raportu "
        "nie ma i tak ma być. Powiedz użytkownikowi, jaki temat i artykuły ustalono, i zakończ."
    ),
    # -- report findings, implications and charts --------------------------------------------
    "format.date": "{day:02d}.{month:02d}.{year}",
    "format.month_year": "{month:02d}.{year}",
    "basis.yoy": "ostatnie 12 miesięcy do poprzednich 12",
    "basis.halves": "druga połowa okresu do pierwszej",
    "basis.slope": "według trendu, rocznie",
    "basis.mixed": "według edycji",
    "finding.unit.per_million": "na milion odsłon edycji",
    "finding.unit.views": "odsłon/mies.",
    "chart.season_title": "Miesiące wobec zwykłego poziomu",
    "chart.axis_season": "% wobec zwykłego poziomu",
    "report.title_topic": "{topic}: zainteresowanie w Wikipedii",
    "report.context": "Powiązane artykuły (kontekst, nieliczone)",
    "report.method_note": "O metodzie",
    "report.sources_names": "Wikimedia Pageviews API, Wikidane, MediaWiki API",
    "summary.context": "Powiązane artykuły (kontekst, nieliczone)",
    "summary.context_item": "{title} — {views} odsłon/mies.",
    "summary.bundle_count": "zmierzono główny artykuł; powiązane artykuły jako kontekst: {related}",
    "month.1": "styczeń",
    "month.short.1": "sty",
    "month.2": "luty",
    "month.short.2": "lut",
    "month.3": "marzec",
    "month.short.3": "mar",
    "month.4": "kwiecień",
    "month.short.4": "kwi",
    "month.5": "maj",
    "month.short.5": "maj",
    "month.6": "czerwiec",
    "month.short.6": "cze",
    "month.7": "lipiec",
    "month.short.7": "lip",
    "month.8": "sierpień",
    "month.short.8": "sie",
    "month.9": "wrzesień",
    "month.short.9": "wrz",
    "month.10": "październik",
    "month.short.10": "paź",
    "month.11": "listopad",
    "month.short.11": "lis",
    "month.12": "grudzień",
    "month.short.12": "gru",
    "summary.redirects": "+{count} przekier.",
    "finding.item.season": "{label}: {peak_month} {peak}, {trough_month} {trough}",
    "finding.no_article": (
        "{label}: w tej edycji nie ma artykułu na ten temat, więc pokazano ją jako „brak danych”, "
        "a nie zerowe zainteresowanie."
    ),
    "finding.substitute": (
        "{label}: brak artykułu na ten temat; zmierzono przez {what} — to szerszy temat, więc nie "
        "jest porównywany z innymi edycjami."
    ),
    "report.bundle_composition": "Analizowane artykuły",
    "summary.missing_hint": (
        "Zatrzymaj się: pokaż użytkownikowi te opcje, zapytaj, którą wybrać dla każdej edycji, i "
        "zakończ odpowiedź tym pytaniem. Nie wybieraj za użytkownika i nie uruchamiaj ponownie, "
        "dopóki nie odpowie. Potem dodaj wartość wybranej opcji z bloku poniżej do "
        "topics[].substitutes w request.json i uruchom ponownie."
    ),
    "answer.conclusion.unknown": "Przed podjęciem decyzji wydłuż okres.",
    "answer.conclusion.low_trust": (
        "Dane są zbyt słabe na wniosek: traktuj liczby jako orientacyjne."
    ),
    "answer.no_article": (
        "Brak artykułu w {projects}: zainteresowania tam nie zmierzono, co nie oznacza jego braku."
    ),
    "outcome.unknown": "{label}: okres jest zbyt krótki, by ocenić trend.",
    "outcome.low_trust": "{label}: dane są zbyt słabe na wniosek.",
    "outcome.substitute": "{label}: zmierzono inny artykuł, więc o samym temacie mówi to niewiele.",
    "outcome.no_article": (
        "{label}: brak artykułu, zainteresowania nie zmierzono (to nie to samo co brak "
        "zainteresowania)."
    ),
    "next_step.confirm": (
        "Następny krok: potwierdzić sygnał niezależnym źródłem popytu — na przykład Google Trends, "
        "liczbą wyszukiwań lub małym testem reklamowym. Wyświetlenia Wikipedii nie pokazują "
        "gotowości do zapłaty."
    ),
    "next_step.confirm_for": (
        "Następny krok: potwierdzić sygnał dla {label} niezależnym źródłem popytu — na przykład "
        "Google Trends, liczbą wyszukiwań lub małym testem reklamowym. Wyświetlenia Wikipedii nie "
        "pokazują gotowości do zapłaty."
    ),
    "next_step.check_demand": (
        "Następny krok: przed inwestycją sprawdzić istniejący popyt niezależnym źródłem — na "
        "przykład Google Trends, liczbą wyszukiwań lub małym testem reklamowym. Wyświetlenia "
        "Wikipedii nie pokazują gotowości do zapłaty."
    ),
    "next_step.check_demand_for": (
        "Następny krok: sprawdzić istniejący popyt w {label} niezależnym źródłem — na przykład "
        "Google Trends, liczbą wyszukiwań lub małym testem reklamowym. Wyświetlenia Wikipedii nie "
        "pokazują gotowości do zapłaty."
    ),
    "next_step.low_trust": (
        "Następny krok: wydłużyć okres lub sprawdzić mierzony artykuł, a potem potwierdzić sygnał "
        "niezależnym źródłem popytu — na przykład Google Trends, liczbą wyszukiwań lub małym "
        "testem reklamowym."
    ),
    "evidence.months": "{months} mies. danych",
    "evidence.months_short": "tylko {months} mies. danych",
    "evidence.no_gaps": "bez luk w danych",
    "evidence.gaps": "brakujące miesiące: {missing_months}",
    "evidence.spikes_high": "skoki to {share} wyświetleń",
    "card.no_article": "brak artykułu",
    "value.per_million": "{value} na 1 mln",
    "report.answer": "Odpowiedź",
    "report.vs_edition": "Czy temat rośnie szybciej, czy wolniej niż jego Wikipedia?",
    "report.vs_edition_basis": "Porównanie: {basis}",
    "report.decision": "Co to oznacza dla decyzji",
    "report.other_findings": "Co jeszcze warto wiedzieć",
    "report.coverage": (
        "Kontrola pokrycia: znalezione powiązane artykuły — {items}. Służą jako kontekst i nie "
        "wchodzą do głównej miary."
    ),
    "report.coverage_item": "{project}: {count}",
    "summary.decision": "Co to oznacza dla decyzji",
    "finding.item.season_tentative": "{label}: {peak_month} {peak}, {trough_month} {trough}",
    "limitation.scope": (
        "Analiza mierzy czytanie jednego głównego artykułu i jego przekierowań: to pośrednia miara "
        "zainteresowania tematem, a nie wielkość rynku ani gotowość do zapłaty."
    ),
    "summary.findings": "Co jeszcze warto wiedzieć",
    "robustness.unknown": "{label}: nie da się ocenić trwałości: {reason}.",
    "robustness.reason.low_trust": "dane są zbyt słabe (zob. wiersz o danych)",
    "robustness.reason.low_volume": "publiczność jest za mała na porównanie trzech miesięcy",
    "robustness.reason.no_recent": "brak porównania z tymi samymi miesiącami rok wcześniej",
    "robustness.reason.no_trend": "okres jest za krótki na trend",
    "report.robustness": "Na ile trwały jest ten wniosek?",
    "report.recent_basis": "ostatnie {months} mies. wobec tych samych miesięcy rok wcześniej",
    "report.data_line": "Dane: {items}.",
    "report.data_concerns": "{label}: {items}.",
    "report.reliability": "Kontrole danych",
    "evidence.spikes_ok": "pojedyncze skoki nie decydują o wyniku",
    "outcome.recent.confirmed": "; ostatnie dane to potwierdzają",
    "outcome.recent.mixed": "; ostatnie dane jeszcze tego nie potwierdzają",
    "outcome.recent.reversing": "; w ostatnich miesiącach kierunek się zmienił",
    "metric.article_views": "Wyświetlenia artykułu",
    "metric.edition_views": "Ruch edycji",
    "metric.attention_share": "Udział w uwadze",
    "metric.attention_share_unit": "wyświetleń artykułu na 1 mln wyświetleń edycji",
    "headline.subject.share_one": "Udział w uwadze tematu {topics}",
    "headline.subject.share_many": "Udział w uwadze tematów {topics}",
    "headline.subject.views_one": "Liczba wyświetleń artykułu o temacie {topics}",
    "headline.subject.views_many": "Liczba wyświetleń artykułów o tematach {topics}",
    "headline.scope.both": "w obu edycjach",
    "headline.scope.all": "we wszystkich edycjach",
    "headline.scope.everywhere": "wszędzie",
    "headline.one.growing": "{subject} w {project} rośnie{recent}",
    "headline.one.declining": "{subject} w {project} spada{recent}",
    "headline.one.flat": "{subject} w {project} nie wykazuje wyraźnego trendu{recent}",
    "headline.unknown": "Okres jest za krótki, by ocenić, dokąd zmierza {subject}.",
    "headline.all.growing": "{subject} rośnie {scope}, {fastest}",
    "headline.all.declining": "{subject} spada {scope}, {fastest}",
    "headline.all.flat": "{subject} {scope} nie wykazuje wyraźnego trendu",
    "headline.fastest": "najszybciej w {label}",
    "headline.fastest_steadier": "w {label} szybciej i trwalej",
    "headline.mixed": "{subject}: {parts}",
    "headline.part.growing": "rośnie w {items}",
    "headline.part.declining": "spada w {items}",
    "headline.part.flat": "bez wyraźnego trendu w {items}",
    "headline.part.unknown": "za krótka historia w {items}",
    "happening.size_share": "{metric} ({unit}), średnio w okresie: {items}.",
    "happening.size_views": "{metric} miesięcznie, średnio w okresie: {items}.",
    "happening.change": "{metric}, {basis}: {items}.",
    "happening.pair": "{article} i {edition}",
    "happening.vs_edition": "{article} i {edition}, {basis}: {items}.",
    "kpi.metric": "Wskaźnik",
    "kpi.views": "Wyświetlenia artykułu miesięcznie (średnio)",
    "kpi.share": "Udział w uwadze, na 1 mln wyświetleń edycji (średnio)",
    "kpi.change": "{metric}, {basis}",
    "kpi.recent": "Czy ostatnie {months} mies. potwierdzają trend?",
    "robustness.value.confirmed": "tak",
    "robustness.value.mixed": "nie, udział stabilny",
    "robustness.value.mixed_flat": "nie, udział się przesunął",
    "robustness.value.reversing": "nie, kierunek się zmienił",
    "robustness.value.unknown": "za mało danych",
    "summary.topic_auto": "Dopasowano automatycznie do {qid} według podanego znaczenia.",
    "spikes.low": (
        "Dni skoków to {share:.0%} wyświetleń: wniosek o trendzie nie opiera się na pojedynczych "
        "skokach"
    ),
    "spikes.notable": (
        "Dni skoków to {share:.0%} wyświetleń: część trendu może wynikać z wiadomości"
    ),
    "spikes.dominant": (
        "Dni skoków to {share:.0%} wyświetleń: trend opiera się na skokach, a nie na stałym "
        "czytaniu"
    ),
    "window_length.short": (
        "Tylko {months} mies. danych: ostatnich 12 miesięcy nie ma z czym porównać"
    ),
    "limitation.short_window": (
        "Tylko {months} mies. danych: ostatnich 12 miesięcy nie ma z czym porównać, a test trendu "
        "jest słaby."
    ),
    "rank.rationale": (
        "{profile}: udział w uwadze {growth} (główne okno), wyświetlenia artykułu miesięcznie "
        "{views}, wiarygodność {level}"
    ),
    "verdict.rank.headline_declining": (
        "Udział w uwadze spada we wszystkich edycjach; względnie najsilniejsza publiczność: "
        "{label} ({profile})"
    ),
    "finding.level_shift": (
        "{label}: {metric} od {start_month} utrzymuje się na poziomie {change} względem "
        "wcześniejszego już od {months} mies. (średnio {before} → {after} {unit})."
    ),
    "finding.burst": (
        "{label}: skok wyświetleń artykułu {start} – {end}, szczyt {peak_day}: {peak_views} "
        "wyświetleń dziennie, ×{multiple} wobec zwykłych {baseline}; skok to {share} wyświetleń "
        "artykułu w okresie."
    ),
    "finding.burst_day": (
        "{label}: jednodniowy skok wyświetleń artykułu {peak_day}: {peak_views} wyświetleń, "
        "×{multiple} wobec zwykłych {baseline}; to {share} wyświetleń artykułu w okresie."
    ),
    "finding.season": (
        "{label}: wyświetlenia artykułu według miesięcy wobec zwykłego poziomu: najsilniej "
        "{peak_month} ({peak}), najsłabiej {trough_month} ({trough})."
    ),
    "finding.group.season": (
        "Wyświetlenia artykułu według miesięcy, najsilniejszy i najsłabszy miesiąc wobec zwykłego "
        "poziomu: {items}."
    ),
    "finding.season_tentative": (
        "{label}: w wyświetleniach artykułu są oznaki sezonowości ({peak_month} {peak}, "
        "{trough_month} {trough} wobec zwykłego poziomu); do pewnego wniosku potrzebna jest "
        "dłuższa historia — każdy miesiąc zaobserwowano tylko kilka razy."
    ),
    "finding.group.season_tentative": (
        "W wyświetleniach artykułu są oznaki sezonowości w {count} edycjach ({items}, wobec "
        "zwykłego poziomu); do pewnego wniosku potrzebna jest dłuższa historia."
    ),
    "card.size": "Udział w uwadze, na 1 mln wyświetleń edycji",
    "card.size_absolute": "Wyświetlenia artykułu miesięcznie",
    "card.views_note": "wyświetlenia artykułu miesięcznie: {items}",
    "card.momentum": "Udział w uwadze: zmiana",
    "card.momentum_absolute": "Wyświetlenia artykułu: zmiana",
    "card.robustness": "Czy ostatnie miesiące potwierdzają trend?",
    "col.views_avg": "Wyświetlenia artykułu/mies.",
    "col.per_million_avg": "Udział w uwadze, na 1 mln",
    "col.share_growth": "Udział w uwadze: zmiana",
    "col.views_growth": "Wyświetlenia artykułu: zmiana",
    "col.edition_growth": "Ruch edycji: zmiana",
    "col.trend": "Trend udziału w uwadze",
    "edition.gaining": (
        "{label}: wyświetlenia artykułu {article}, ruch edycji {edition} → udział w uwadze rośnie"
    ),
    "edition.losing": (
        "{label}: wyświetlenia artykułu {article}, ruch edycji {edition} → udział w uwadze spada"
    ),
    "edition.in_line": (
        "{label}: wyświetlenia artykułu {article}, ruch edycji {edition} → udział w uwadze się "
        "utrzymuje"
    ),
    "robustness.confirmed.flat": (
        "{label}: stabilnie. Udział w uwadze, {basis}: {change}, bez wyraźnego trendu; w ostatnich "
        "{months} mies. wobec tych samych miesięcy rok wcześniej wyświetlenia artykułu {article}, "
        "ruch edycji {edition}, więc udział się utrzymuje."
    ),
    "robustness.mixed.declining": (
        "{label}: sygnał mieszany. Udział w uwadze, {basis}: {change}; ale w ostatnich {months} "
        "mies. wobec tych samych miesięcy rok wcześniej wyświetlenia artykułu {article}, ruch "
        "edycji {edition}, więc udział jest stabilny. Długoterminowy spadek jest widoczny, ale nie "
        "wiadomo, czy trwa nadal."
    ),
    "robustness.mixed.growing": (
        "{label}: sygnał mieszany. Udział w uwadze, {basis}: {change}; ale w ostatnich {months} "
        "mies. wobec tych samych miesięcy rok wcześniej wyświetlenia artykułu {article}, ruch "
        "edycji {edition}, więc udział jest stabilny. Długoterminowy wzrost jest widoczny, ale nie "
        "wiadomo, czy trwa nadal."
    ),
    "robustness.mixed.flat": (
        "{label}: sygnał mieszany. Udział w uwadze, {basis}: {change}, bez wyraźnego trendu; ale w "
        "ostatnich {months} mies. wobec tych samych miesięcy rok wcześniej wyświetlenia artykułu "
        "{article}, ruch edycji {edition}, więc udział się przesunął."
    ),
    "robustness.reversing.declining": (
        "{label}: możliwe odwrócenie. Udział w uwadze, {basis}: {change}; ale w ostatnich {months} "
        "mies. wobec tych samych miesięcy rok wcześniej wyświetlenia artykułu {article}, ruch "
        "edycji {edition}, więc udział wzrósł. Potwierdzenie wymaga jeszcze kilku miesięcy."
    ),
    "robustness.reversing.growing": (
        "{label}: możliwe odwrócenie. Udział w uwadze, {basis}: {change}; ale w ostatnich {months} "
        "mies. wobec tych samych miesięcy rok wcześniej wyświetlenia artykułu {article}, ruch "
        "edycji {edition}, więc udział spadł. Potwierdzenie wymaga jeszcze kilku miesięcy."
    ),
    "outcome.large_growing": (
        "{label}: wyższy udział w uwadze, który rośnie{recent} → mocny kandydat do następnej "
        "weryfikacji."
    ),
    "outcome.large_flat": (
        "{label}: wyższy udział w uwadze, bez wyraźnego trendu{recent} → sprawdzić, czy widoczne "
        "zainteresowanie przekłada się na realny popyt."
    ),
    "outcome.large_declining": (
        "{label}: wyższy udział w uwadze, ale długoterminowo spada{recent} → sprawdzić, czy "
        "widoczne zainteresowanie przekłada się na realny popyt."
    ),
    "outcome.small_growing": (
        "{label}: niższy udział w uwadze, ale rośnie{recent} → wczesny sygnał; sprawdź, czy to nie "
        "efekt niskiej bazy."
    ),
    "outcome.small_flat": (
        "{label}: niższy udział w uwadze, bez wyraźnego trendu{recent} → słabszy sygnał do "
        "następnej weryfikacji."
    ),
    "outcome.small_declining": (
        "{label}: niższy udział w uwadze, który spada{recent} → słabszy sygnał do następnej "
        "weryfikacji."
    ),
    "outcome.single_growing": (
        "{label}: udział w uwadze rośnie{recent} → sygnał do potwierdzenia drugim źródłem."
    ),
    "outcome.single_flat": (
        "{label}: udział w uwadze bez wyraźnego trendu{recent} → istniejąca publiczność bez "
        "sygnału wzrostowego."
    ),
    "outcome.single_declining": (
        "{label}: udział w uwadze spada{recent} → brak sygnału wzrostowego."
    ),
    "answer.conclusion.strong": (
        "{label} łączy najwyższy udział w uwadze z jego wzrostem: najmocniejszy kandydat do "
        "dalszej weryfikacji."
    ),
    "answer.conclusion.emerging": (
        "{label} ma niższy udział w uwadze, ale rosnący: wczesny sygnał; sprawdź, czy to nie efekt "
        "niskiej bazy."
    ),
    "answer.conclusion.no_growth": (
        "Udział w uwadze nie rośnie w żadnej edycji; {label} ma najwyższy, więc jest lepszym "
        "kandydatem do dalszych badań, a nie do stawiania na ekspansję."
    ),
    "answer.conclusion.no_growth_ranked": (
        "Udział w uwadze nie rośnie w żadnej edycji; {label} jest pierwsza w rankingu, więc jest "
        "lepszym kandydatem do dalszych badań, a nie do stawiania na ekspansję."
    ),
    "answer.conclusion.no_growth_split": (
        "Udział w uwadze nie rośnie w żadnej edycji; {label} jest pierwsza w rankingu, a {largest} "
        "ma najwyższy udział w uwadze: obie są kandydatami do dalszych badań, a nie do stawiania "
        "na ekspansję."
    ),
    "answer.conclusion.single_growing": (
        "Udział w uwadze rośnie: ten sygnał warto potwierdzić drugim źródłem."
    ),
    "answer.conclusion.single_flat": (
        "Udział w uwadze nie wykazuje wyraźnego trendu: istniejąca publiczność bez sygnału "
        "wzrostowego."
    ),
    "answer.conclusion.single_declining": (
        "Udział w uwadze spada: dane Wikipedii nie dają dla tego tematu sygnału wzrostowego."
    ),
    "profile.growth_market": "duża publiczność, udział w uwadze rośnie",
    "profile.early_niche": "mała publiczność, udział w uwadze rośnie",
    "profile.mature_market": "duża publiczność, udział w uwadze stabilny",
    "profile.declining": "udział w uwadze spada",
    "question.assess": (
        "Oceń, dokąd zmierza udział w uwadze tematu „{topics}” w edycjach {projects}"
    ),
    "trend.significant": (
        "Trend udziału w uwadze jest istotny statystycznie (p = {p_value:.3f}, {direction})"
    ),
    "trend.not_significant": (
        "Trend udziału w uwadze nie jest istotny statystycznie (p = {p_value:.3f})"
    ),
    "robustness.confirmed.declining": (
        "{label}: trwały spadek udziału w uwadze. Udział w uwadze, {basis}: {change}; w ostatnich "
        "{months} mies. wobec tych samych miesięcy rok wcześniej wyświetlenia artykułu {article}, "
        "ruch edycji {edition}, więc udział nadal spada."
    ),
    "robustness.confirmed.growing": (
        "{label}: trwały wzrost udziału w uwadze. Udział w uwadze, {basis}: {change}; w ostatnich "
        "{months} mies. wobec tych samych miesięcy rok wcześniej wyświetlenia artykułu {article}, "
        "ruch edycji {edition}, więc udział nadal rośnie."
    ),
    "chart.index_title": "Wyświetlenia artykułu wobec ruchu edycji",
    "chart.index_subtitle": (
        "Indeks: średnia pierwszych 12 miesięcy = 100, średnia z 3 miesięcy. Artykuł poniżej "
        "edycji — temat traci udział w uwadze."
    ),
    "chart.axis_index": "indeks, pierwsze 12 mies. = 100",
    "chart.series_article_months": "wyświetlenia artykułu, miesiąc",
    "chart.series_article_smooth": "wyświetlenia artykułu",
    "chart.series_edition_short": "ruch edycji",
    "chart.note.event": "{month} ×{multiple}",
    "chart.note.possible_bot": "{month} ×{multiple}, możliwe boty",
    "chart.note.edition": "{month} edycja ×{multiple}",
    "chart.note.unknown": "{month} ×{multiple}",
    "chart.yoy_title": "{metric}: zmiana wobec tych samych miesięcy rok wcześniej",
    "chart.yoy_subtitle": (
        "Każdy punkt — ostatnie 3 miesiące wobec tych samych 3 miesięcy rok wcześniej."
    ),
    "chart.axis_growth": "zmiana, %",
    "chart.dumbbell_title": "{metric}: wcześniej i teraz",
    "chart.dumbbell_basis.yoy": "Średnia z poprzednich 12 miesięcy i z ostatnich 12 miesięcy.",
    "chart.dumbbell_basis.halves": "Średnia z pierwszej i z drugiej połowy okresu.",
    "chart.dumbbell_basis.mixed": "Średnia z wcześniejszych i z późniejszych miesięcy.",
    "chart.series_before.yoy": "poprzednie 12 mies.",
    "chart.series_after.yoy": "ostatnie 12 mies.",
    "chart.series_before.halves": "pierwsza połowa",
    "chart.series_after.halves": "druga połowa",
    "chart.series_before.mixed": "wcześniej",
    "chart.series_after.mixed": "teraz",
    "chart.scatter_title": "{metric}: wielkość i zmiana",
    "chart.scatter_subtitle": "Dalej w prawo — większy udział; nad linią — rośnie, pod — spada.",
    "chart.axis_log": "{unit}, skala logarytmiczna",
    "chart.axis_per_million": "wyświetleń artykułu na 1 mln wyświetleń edycji",
    "chart.season_period": "Obliczono za {start} – {end}.",
    "report.happening": "Co się dzieje",
    "report.footer_share": (
        "Udział w uwadze — wyświetlenia artykułu na 1 mln wyświetleń całej edycji. Zmiana: "
        "{basis}; ostatnie miesiące: {recent}."
    ),
    "report.footer_caveats": (
        "Wyświetlenia pokazują ciekawość, a nie gotowość do zapłaty; edycja językowa to nie kraj."
    ),
    "report.footer_months": "Wyróżniające się miesiące w porównaniu: {items}.",
    "report.footer_month_item": "{label} {note}, zmiana bez niego {change}",
    "report.footer_method": "Jak policzono każdą liczbę: method.md",
}
