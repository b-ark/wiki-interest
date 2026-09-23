"""Czech message catalog. Mirrors the key set of :mod:`wiki_interest.i18n.en`."""

from __future__ import annotations

__all__ = ["MESSAGES"]

MESSAGES: dict[str, str] = {
    # -- reliability reasons ---------------------------------------------------------------
    "window_length.ok": "{months} měsíců dat: dost pro meziroční srovnání",
    "window_length.too_short": "Jen {months} měsíců dat: příliš málo pro posouzení trendu",
    "completeness.ok": "V měsíčních datech nejsou mezery",
    "completeness.gaps": "{missing_months} měsíců bez dat ({share:.0%} období)",
    "completeness.sparse": (
        "{missing_months} měsíců bez dat ({share:.0%} období): řada je příliš řídká"
    ),
    "spikes.unavailable": "Denní data nejsou k dispozici, špičky proto nebylo možné posoudit",
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
    "question.rank": "Seřadit edice {projects} podle zájmu o téma „{topics}“",
    # -- report sections -------------------------------------------------------------------
    "report.title_default": "Analýza zájmu podle zobrazení Wikipedie",
    "report.question": "Otázka",
    "report.audience": "Kontext",
    "report.key_numbers": "Klíčová čísla",
    "report.chart": "Graf",
    "report.charts": "Grafy",
    "report.verdict": "Závěr",
    "report.limitations": "Předpoklady a omezení",
    "report.next_steps": "Co lze upřesnit",
    "report.sources": "Zdroje",
    "report.period": "Období",
    "report.projects": "Edice",
    "report.topics": "Témata",
    "report.generated": "Vygenerováno",
    "report.version": "Verze dovednosti",
    "report.data_through": "Data do",
    "report.comparison_table": "Srovnání",
    "report.ranking_table": "Pořadí",
    "report.notes": "Poznámky",
    "report.see_summary": "… úplný seznam je v summary.md",
    "report.no_chart": "Pro tento běh nebyl vytvořen žádný graf",
    # -- table columns ---------------------------------------------------------------------
    "col.topic": "Téma",
    "col.project": "Edice",
    "col.reliability": "Spolehlivost",
    "col.rank": "Poř.",
    "col.score": "Skóre",
    "col.profile": "Profil",
    "col.article": "Článek",
    "col.role": "Role",
    "col.source": "Zdroj",
    "col.status": "Stav",
    "col.rationale": "Proč",
    # -- agent summary ---------------------------------------------------------------------
    "summary.answer": "Odpověď",
    "summary.key_numbers": "Klíčová čísla",
    "summary.caveats": "Výhrady",
    "summary.refine": "Co lze upřesnit",
    "summary.artifacts": "Soubory",
    "summary.clarification_needed": "Je třeba upřesnění",
    "summary.candidates": "Kandidáti",
    "summary.clarification_hint": (
        "Pokud z rozhovoru jasně plyne, který význam uživatel myslí, zadejte qid tohoto kandidáta "
        "sami a řekněte, který význam jste zvolili; jinak se zeptejte uživatele. Poté spusťte "
        "znovu s topics[].qid."
    ),
    "summary.bundles": "Analyzované články",
    # -- charts ----------------------------------------------------------------------------
    "chart.axis_views": "zobrazení měsíčně",
    "chart.footnote": "Zdroj: {source} · Období: {period}",
    "chart.no_data": "Za toto období nejsou data",
    # -- verdikty ----------------------------------------------------------------------------
    "verdict.rank.headline": "Nejslibnější publikum: {label} ({profile})",
    "verdict.none.headline": (
        "Pro témata {topics} nejsou data k analýze: v {projects} nebyly nalezeny články"
    ),
    "rank.rationale.insufficient": "nedostatek dat pro řazení",
    "note.not_found": "v této edici článek chybí",
    "note.search_fallback": "článek nalezen vyhledáváním",
    # -- omezení a další kroky ---------------------------------------------------------------
    "limitation.coverage": (
        "Edice pokrývají téma různě; chybějící nebo krátký článek signál snižuje bez ohledu "
        "na zájem publika."
    ),
    "limitation.language": (
        "Jazyková edice není země: čtou ji obyvatelé mnoha zemí a obyvatelé jedné země čtou "
        "různé edice."
    ),
    "limitation.bots": (
        "Filtrování botů na straně Wikimedia není dokonalé; kontroly automatizovaného provozu "
        "a špiček zachytí jen část."
    ),
    "limitation.missing_titles": "Tyto požadované názvy neexistují a byly přeskočeny: {titles}",
    "limitation.not_found": (
        "Pro téma „{topic}“ chybí článek v {projects}: tyto edice jsou označeny jako „článek "
        "chybí“, ne jako nulový zájem."
    ),
    "limitation.search_fallback": (
        "V {projects} byl článek nalezen fulltextovým vyhledáváním; ověřte, že jde o správný "
        "článek."
    ),
    "limitation.absolute": (
        "Porovnávaly se hrubé počty zobrazení bez normalizace na velikost edice."
    ),
    "next.extend_period": "Prodlužte období (např. 36 nebo 60 měsíců) a ověřte, zda trend vydrží.",
    "next.add_projects": "Přidejte další edice a zjistěte, zda je obraz specifický pro {projects}.",
    "next.absolute": (
        "Porovnejte hrubá zobrazení (normalization: absolute) pro odhad velikosti publika "
        "místo podílu."
    ),
    "next.per_million": "Porovnejte podíly na milion, abyste odstranili vliv velikosti edice.",
    "next.pin_title": "Zadejte přesný název článku pro {projects} přes extra_titles.",
    "next.research": "Prozkoumat jako další: {label} ({profile}).",
    # -- editions without an article: the question and the substitutes ------------------
    "resolution.substitute_redirect": (
        "Článek chybí; měřeno přes přesměrování „{title}“: počítají se jen návštěvy pod tímto "
        "názvem, jde tedy o dolní mez"
    ),
    "resolution.substitute_broader": (
        "Článek chybí; měřeno přes širší článek „{title}“: čísla popisují širší téma, jde tedy o "
        "horní mez"
    ),
    "resolution.substitute_mention": (
        "Článek chybí; měřeno přes „{title}“, který téma jen zmiňuje: čísla popisují ten článek, "
        "ne téma"
    ),
    "bundle_status.substitute": "náhrada",
    "source.substitute": "náhrada zvolená uživatelem",
    "summary.missing_needed": "Je třeba rozhodnout: článek chybí",
    "summary.apply_choice": "Pro agenta: hodnota pro topics[].substitutes",
    "gap.headline": (
        "Zatím nic nebylo změřeno: v {projects} chybí článek na toto téma. Nejdřív zvolte, co tam "
        "měřit."
    ),
    "gap.question": "V {project} chybí článek „{topic}“.",
    "gap.term": "„{term}“",
    "gap.searched": "Hledáno: {terms}.",
    "gap.no_terms": (
        "Název tématu v tomto jazyce není znám, proto se přesměrování ani zmínky nehledaly; uveďte "
        "ho v local_terms, aby se našly."
    ),
    "option.redirect": (
        "Přesměrování „{title}“ vede na článek „{target}“{section}: {views} zobrazení/měs. Počítá "
        "jen návštěvy pod tímto přesným názvem, jde tedy o dolní mez."
    ),
    "option.section": ", oddíl „{section}“",
    "option.broader": (
        "Širší článek „{title}“: {views} zobrazení/měs. Horní mez: většina čtenářů přišla kvůli "
        "širšímu tématu."
    ),
    "option.mention": (
        "Článek „{title}“ zmiňuje téma: {views} zobrazení/měs. Téma je jen jeho malou částí."
    ),
    "option.snippet": "Úryvek: „…{snippet}…“",
    "option.skip": "Vynechat {project}: zpráva uvede „článek chybí“, nikoli nulový zájem.",
    "substitute.redirect": "přesměrování „{title}“",
    "substitute.broader": "širší článek „{title}“",
    "substitute.mention": "článek „{title}“, který téma zmiňuje",
    "note.substitute": "článek chybí; měřeno přes {what}",
    "limitation.substitute": (
        "Pro „{topic}“ v {project} chybí článek; čísla tam pocházejí z měření přes {what}, jak "
        "bylo zvoleno."
    ),
    "rank.rationale.substitute": "neřazeno: měřeno přes jiný článek, ne samotné téma",
    "gap.entity": (
        "Téma: „{label}“{description} ({qid}). Počet jazyků s článkem: {count}, mimo jiné "
        "{languages}."
    ),
    "gap.entity_description": " — {description}",
    "gap.entity_nowhere": (
        "Téma: „{label}“{description} ({qid}); žádná jazyková verze Wikipedie o něm nemá článek."
    ),
    "gap.matched_en": (
        "Bylo nalezeno podle anglického názvu, protože hledání v jazyce dotazu nic nenašlo; "
        "ověřte, že jde o správné téma."
    ),
    "gap.no_entity": (
        "Téma nebylo ve Wikidatech nalezeno, takže není známo, které verze ho pokrývají; "
        "zkontrolujte formulaci nebo uveďte query_en."
    ),
    "summary.topic_line": "Téma: „{label}“{description} ({qid}).",
    "summary.alternatives": "Další významy tohoto názvu: {items}.",
    "summary.candidate_articles": "články v {projects}",
    "summary.candidate_no_articles": "v požadovaných verzích článek chybí",
    "summary.not_found_needed": "Téma nenalezeno",
    "notfound.headline": (
        "Pro „{query}“ se ve Wikidatech ani ve Wikipedii nic nenašlo — ani podle této formulace, "
        "ani podle anglického názvu."
    ),
    "summary.not_found_hint": (
        "Řekněte to uživateli na rovinu a požádejte o odkaz na článek Wikipedie v libovolném "
        "jazyce o tom, co ho zajímá. Vložte ho do topics[].article_url v request.json a spusťte "
        "znovu."
    ),
    "summary.which_meaning": "Který význam „{query}“?",
    "summary.topic_only": (
        "Pouze kontrola tématu: téma bylo určeno a nic dalšího se nespustí; zpráva není a tak je "
        "to v pořádku. Řekněte uživateli, jaké téma a články byly určeny, a skončete."
    ),
    # -- report findings, implications and charts --------------------------------------------
    "format.date": "{day:02d}.{month:02d}.{year}",
    "format.month_year": "{month:02d}.{year}",
    "basis.yoy": "posledních 12 měsíců oproti předchozím 12",
    "basis.halves": "druhá polovina období oproti první",
    "basis.slope": "podle trendu, za rok",
    "basis.mixed": "podle edic",
    "finding.unit.per_million": "na milion zobrazení edice",
    "finding.unit.views": "zobrazení/měs.",
    "chart.season_title": "Měsíce oproti obvyklé úrovni",
    "chart.axis_season": "% oproti obvyklé úrovni",
    "report.title_topic": "{topic}: zájem na Wikipedii",
    "report.context": "Související články (kontext, nezapočteno)",
    "report.method_note": "O metodě",
    "report.sources_names": "Wikimedia Pageviews API, Wikidata, MediaWiki API",
    "summary.context": "Související články (kontext, nezapočteno)",
    "summary.context_item": "{title} — {views} zobrazení/měs.",
    "summary.bundle_count": "měřen hlavní článek; souvisejících článků jako kontext: {related}",
    "summary.method": "O metodě",
    "month.1": "leden",
    "month.short.1": "led",
    "month.2": "únor",
    "month.short.2": "úno",
    "month.3": "březen",
    "month.short.3": "bře",
    "month.4": "duben",
    "month.short.4": "dub",
    "month.5": "květen",
    "month.short.5": "kvě",
    "month.6": "červen",
    "month.short.6": "čvn",
    "month.7": "červenec",
    "month.short.7": "čvc",
    "month.8": "srpen",
    "month.short.8": "srp",
    "month.9": "září",
    "month.short.9": "zář",
    "month.10": "říjen",
    "month.short.10": "říj",
    "month.11": "listopad",
    "month.short.11": "lis",
    "month.12": "prosinec",
    "month.short.12": "pro",
    "summary.redirects": "+{count} přesměr.",
    "finding.item.season": "{label}: {peak_month} {peak}, {trough_month} {trough}",
    "finding.no_article": (
        "{label}: v této edici článek na téma chybí, proto je uvedena jako „bez dat“, ne jako "
        "nulový zájem."
    ),
    "finding.substitute": (
        "{label}: článek na téma chybí; měřeno přes {what} — to je širší téma, proto se nesrovnává "
        "s ostatními edicemi."
    ),
    "report.bundle_composition": "Analyzované články",
    "summary.missing_hint": (
        "Zastavte se: ukažte uživateli tyto možnosti, zeptejte se, kterou použít pro každou edici, "
        "a odpověď zakončete touto otázkou. Nevybírejte za uživatele a nespouštějte znovu, dokud "
        "neodpoví. Pak vložte hodnotu zvolené možnosti z bloku níže do topics[].substitutes v "
        "request.json a spusťte znovu."
    ),
    "answer.conclusion.unknown": "Než se rozhodnete, prodlužte období.",
    "answer.conclusion.low_trust": "Data jsou na závěr příliš slabá: berte čísla jako orientační.",
    "answer.no_article": (
        "V {projects} článek chybí: zájem tam nebyl změřen, což neznamená, že žádný není."
    ),
    "outcome.unknown": "{label}: období je příliš krátké na posouzení trendu.",
    "outcome.low_trust": "{label}: data jsou na závěr příliš slabá.",
    "outcome.substitute": "{label}: byl změřen jiný článek, o samotném tématu to proto říká málo.",
    "outcome.no_article": (
        "{label}: článek chybí, zájem nebyl změřen (to není totéž co žádný zájem)."
    ),
    "next_step.confirm": (
        "Další krok: potvrdit signál nezávislým zdrojem poptávky — například Google Trends, "
        "objemem vyhledávání nebo malým reklamním testem. Zobrazení na Wikipedii neukazují ochotu "
        "platit."
    ),
    "next_step.confirm_for": (
        "Další krok: potvrdit signál pro {label} nezávislým zdrojem poptávky — například Google "
        "Trends, objemem vyhledávání nebo malým reklamním testem. Zobrazení na Wikipedii neukazují "
        "ochotu platit."
    ),
    "next_step.check_demand": (
        "Další krok: před investicí ověřit stávající poptávku nezávislým zdrojem — například "
        "Google Trends, objemem vyhledávání nebo malým reklamním testem. Zobrazení na Wikipedii "
        "neukazují ochotu platit."
    ),
    "next_step.check_demand_for": (
        "Další krok: ověřit stávající poptávku v {label} nezávislým zdrojem — například Google "
        "Trends, objemem vyhledávání nebo malým reklamním testem. Zobrazení na Wikipedii neukazují "
        "ochotu platit."
    ),
    "next_step.low_trust": (
        "Další krok: prodloužit období nebo ověřit měřený článek, pak potvrdit signál nezávislým "
        "zdrojem poptávky — například Google Trends, objemem vyhledávání nebo malým reklamním "
        "testem."
    ),
    "evidence.months": "{months} měs. dat",
    "evidence.months_short": "jen {months} měs. dat",
    "evidence.no_gaps": "žádné chybějící měsíce",
    "evidence.gaps": "chybějící měsíce: {missing_months}",
    "evidence.spikes_high": "výkyvy tvoří {share} zobrazení",
    "card.no_article": "článek chybí",
    "value.per_million": "{value} na 1 mil.",
    "report.answer": "Odpověď",
    "report.vs_edition": "Roste téma rychleji, nebo pomaleji než jeho Wikipedie?",
    "report.vs_edition_basis": "Srovnání: {basis}",
    "report.decision": "Co to znamená pro rozhodnutí",
    "report.other_findings": "Co je ještě dobré vědět",
    "report.coverage": (
        "Kontrola pokrytí: nalezené související články — {items}. Slouží jako kontext a nejsou "
        "součástí hlavní metriky."
    ),
    "report.coverage_item": "{project}: {count}",
    "summary.decision": "Co to znamená pro rozhodnutí",
    "finding.item.season_tentative": "{label}: {peak_month} {peak}, {trough_month} {trough}",
    "limitation.scope": (
        "Analýza měří čtení jednoho hlavního článku a jeho přesměrování: je to nepřímý ukazatel "
        "zájmu o téma, ne velikost trhu ani ochota platit."
    ),
    "summary.findings": "Co je ještě dobré vědět",
    "robustness.unknown": "{label}: o stabilitě nelze rozhodnout: {reason}.",
    "robustness.reason.low_trust": "data jsou příliš slabá (viz řádek o datech)",
    "robustness.reason.low_volume": "publikum je na tříměsíční srovnání příliš malé",
    "robustness.reason.no_recent": "chybí srovnání se stejnými měsíci před rokem",
    "robustness.reason.no_trend": "období je na trend příliš krátké",
    "report.robustness": "Jak stabilní je tento závěr?",
    "report.recent_basis": "posledních {months} měs. oproti stejným měsícům před rokem",
    "report.data_line": "Data: {items}.",
    "report.data_concerns": "{label}: {items}.",
    "report.reliability": "Kontroly dat",
    "evidence.spikes_ok": "jednotlivé výkyvy výsledek neurčují",
    "outcome.recent.confirmed": "; poslední data to potvrzují",
    "outcome.recent.mixed": "; poslední data to zatím nepotvrzují",
    "outcome.recent.reversing": "; v posledních měsících se směr změnil",
    "metric.article_views": "Zobrazení článku",
    "metric.edition_views": "Provoz edice",
    "metric.attention_share": "Podíl pozornosti",
    "metric.attention_share_unit": "zobrazení článku na 1 mil. zobrazení edice",
    "headline.subject.share_one": "Podíl pozornosti tématu {topics}",
    "headline.subject.share_many": "Podíl pozornosti témat {topics}",
    "headline.subject.views_one": "Počet zobrazení článku o tématu {topics}",
    "headline.subject.views_many": "Počet zobrazení článků o tématech {topics}",
    "headline.scope.both": "v obou edicích",
    "headline.scope.all": "ve všech edicích",
    "headline.scope.everywhere": "všude",
    "headline.one.growing": "{subject} v {project} roste{recent}",
    "headline.one.declining": "{subject} v {project} klesá{recent}",
    "headline.one.flat": "{subject} v {project} nemá zřetelný trend{recent}",
    "headline.unknown": "Období je příliš krátké na posouzení, kam směřuje {subject}.",
    "headline.all.growing": "{subject} roste {scope}, {fastest}",
    "headline.all.declining": "{subject} klesá {scope}, {fastest}",
    "headline.all.flat": "{subject} {scope} nemá zřetelný trend",
    "headline.fastest": "nejrychleji v {label}",
    "headline.fastest_steadier": "v {label} rychleji a stabilněji",
    "headline.mixed": "{subject}: {parts}",
    "headline.part.growing": "roste v {items}",
    "headline.part.declining": "klesá v {items}",
    "headline.part.flat": "bez zřetelného trendu v {items}",
    "headline.part.unknown": "příliš krátká historie v {items}",
    "happening.size_share": "{metric} ({unit}), v průměru za období: {items}.",
    "happening.size_views": "{metric} za měsíc, v průměru za období: {items}.",
    "happening.change": "{metric}, {basis}: {items}.",
    "happening.pair": "{article} a {edition}",
    "happening.vs_edition": "{article} a {edition}, {basis}: {items}.",
    "kpi.metric": "Ukazatel",
    "kpi.views": "Zobrazení článku za měsíc (průměr)",
    "kpi.share": "Podíl pozornosti, na 1 mil. zobrazení edice (průměr)",
    "kpi.change": "{metric}, {basis}",
    "kpi.recent": "Potvrzují trend posledních {months} měs.?",
    "robustness.value.confirmed": "ano",
    "robustness.value.mixed": "ne, podíl je stabilní",
    "robustness.value.mixed_flat": "ne, podíl se posunul",
    "robustness.value.reversing": "ne, směr se změnil",
    "robustness.value.unknown": "málo dat",
    "summary.topic_auto": "Automaticky přiřazeno k {qid} podle uvedeného významu.",
    "spikes.low": (
        "Dny výkyvů tvoří {share:.0%} zobrazení: závěr o trendu nestojí na jednotlivých výkyvech"
    ),
    "spikes.notable": "Dny výkyvů tvoří {share:.0%} zobrazení: část trendu může pocházet ze zpráv",
    "spikes.dominant": (
        "Dny výkyvů tvoří {share:.0%} zobrazení: trend stojí na výkyvech, ne na stálém čtení"
    ),
    "window_length.short": "Jen {months} měs. dat: posledních 12 měsíců není s čím srovnat",
    "limitation.short_window": (
        "Jen {months} měs. dat: posledních 12 měsíců není s čím srovnat a test trendu je slabý."
    ),
    "rank.rationale": (
        "{profile}: podíl pozornosti {growth} (hlavní okno), zobrazení článku za měsíc {views}, "
        "spolehlivost {level}"
    ),
    "verdict.rank.headline_declining": (
        "Podíl pozornosti klesá ve všech edicích; relativně nejsilnější publikum: {label} "
        "({profile})"
    ),
    "finding.level_shift": (
        "{label}: {metric} se od {start_month} drží na úrovni {change} oproti dřívější už {months} "
        "měs. (průměr {before} → {after} {unit})."
    ),
    "finding.burst": (
        "{label}: výkyv zobrazení článku {start} – {end}, vrchol {peak_day}: {peak_views} "
        "zobrazení za den, ×{multiple} oproti obvyklým {baseline}; výkyv tvoří {share} zobrazení "
        "článku za období."
    ),
    "finding.burst_day": (
        "{label}: jednodenní výkyv zobrazení článku {peak_day}: {peak_views} zobrazení, "
        "×{multiple} oproti obvyklým {baseline}; to je {share} zobrazení článku za období."
    ),
    "finding.season": (
        "{label}: zobrazení článku podle měsíců oproti obvyklé úrovni: nejsilnější {peak_month} "
        "({peak}), nejslabší {trough_month} ({trough})."
    ),
    "finding.group.season": (
        "Zobrazení článku podle měsíců, nejsilnější a nejslabší měsíc oproti obvyklé úrovni: "
        "{items}."
    ),
    "finding.season_tentative": (
        "{label}: v zobrazeních článku jsou náznaky sezónnosti ({peak_month} {peak}, "
        "{trough_month} {trough} oproti obvyklé úrovni); k jistému závěru je potřeba delší "
        "historie — každý měsíc byl pozorován jen několikrát."
    ),
    "finding.group.season_tentative": (
        "V zobrazeních článku jsou náznaky sezónnosti v {count} edicích ({items}, oproti obvyklé "
        "úrovni); k jistému závěru je potřeba delší historie."
    ),
    "card.size": "Podíl pozornosti, na 1 mil. zobrazení edice",
    "card.size_absolute": "Zobrazení článku za měsíc",
    "card.views_note": "zobrazení článku za měsíc: {items}",
    "card.momentum": "Podíl pozornosti: změna",
    "card.momentum_absolute": "Zobrazení článku: změna",
    "card.robustness": "Potvrzují trend poslední měsíce?",
    "col.views_avg": "Zobrazení článku/měs.",
    "col.per_million_avg": "Podíl pozornosti, na 1 mil.",
    "col.share_growth": "Podíl pozornosti: změna",
    "col.views_growth": "Zobrazení článku: změna",
    "col.edition_growth": "Provoz edice: změna",
    "col.trend": "Trend podílu pozornosti",
    "edition.gaining": (
        "{label}: zobrazení článku {article}, provoz edice {edition} → podíl pozornosti roste"
    ),
    "edition.losing": (
        "{label}: zobrazení článku {article}, provoz edice {edition} → podíl pozornosti klesá"
    ),
    "edition.in_line": (
        "{label}: zobrazení článku {article}, provoz edice {edition} → podíl pozornosti se drží"
    ),
    "robustness.confirmed.flat": (
        "{label}: stabilní. Podíl pozornosti, {basis}: {change}, bez zřetelného trendu; za "
        "posledních {months} měs. oproti stejným měsícům před rokem zobrazení článku {article}, "
        "provoz edice {edition}, takže podíl se drží."
    ),
    "robustness.mixed.declining": (
        "{label}: smíšený signál. Podíl pozornosti, {basis}: {change}; ale za posledních {months} "
        "měs. oproti stejným měsícům před rokem zobrazení článku {article}, provoz edice "
        "{edition}, takže podíl je stabilní. Dlouhodobý pokles je vidět, ale není jasné, zda "
        "pokračuje i teď."
    ),
    "robustness.mixed.growing": (
        "{label}: smíšený signál. Podíl pozornosti, {basis}: {change}; ale za posledních {months} "
        "měs. oproti stejným měsícům před rokem zobrazení článku {article}, provoz edice "
        "{edition}, takže podíl je stabilní. Dlouhodobý růst je vidět, ale není jasné, zda "
        "pokračuje i teď."
    ),
    "robustness.mixed.flat": (
        "{label}: smíšený signál. Podíl pozornosti, {basis}: {change}, bez zřetelného trendu; ale "
        "za posledních {months} měs. oproti stejným měsícům před rokem zobrazení článku {article}, "
        "provoz edice {edition}, takže se podíl posunul."
    ),
    "robustness.reversing.declining": (
        "{label}: možný obrat. Podíl pozornosti, {basis}: {change}; ale za posledních {months} "
        "měs. oproti stejným měsícům před rokem zobrazení článku {article}, provoz edice "
        "{edition}, takže podíl vzrostl. Potvrzení vyžaduje ještě několik měsíců."
    ),
    "robustness.reversing.growing": (
        "{label}: možný obrat. Podíl pozornosti, {basis}: {change}; ale za posledních {months} "
        "měs. oproti stejným měsícům před rokem zobrazení článku {article}, provoz edice "
        "{edition}, takže podíl klesl. Potvrzení vyžaduje ještě několik měsíců."
    ),
    "outcome.large_growing": (
        "{label}: vyšší podíl pozornosti, který roste{recent} → silný kandidát na další ověření."
    ),
    "outcome.large_flat": (
        "{label}: vyšší podíl pozornosti bez zřetelného trendu{recent} → ověřit, zda se viditelný "
        "zájem mění ve skutečnou poptávku."
    ),
    "outcome.large_declining": (
        "{label}: vyšší podíl pozornosti, ale dlouhodobě klesá{recent} → ověřit, zda se viditelný "
        "zájem mění ve skutečnou poptávku."
    ),
    "outcome.small_growing": (
        "{label}: nižší podíl pozornosti, ale roste{recent} → časný signál; ověřte, že nejde o "
        "efekt nízkého základu."
    ),
    "outcome.small_flat": (
        "{label}: nižší podíl pozornosti bez zřetelného trendu{recent} → slabší signál pro další "
        "ověření."
    ),
    "outcome.small_declining": (
        "{label}: nižší podíl pozornosti, který klesá{recent} → slabší signál pro další ověření."
    ),
    "outcome.single_growing": (
        "{label}: podíl pozornosti roste{recent} → signál k potvrzení druhým zdrojem."
    ),
    "outcome.single_flat": (
        "{label}: podíl pozornosti bez zřetelného trendu{recent} → existující publikum bez "
        "vzestupného signálu."
    ),
    "outcome.single_declining": "{label}: podíl pozornosti klesá{recent} → žádný vzestupný signál.",
    "answer.conclusion.strong": (
        "{label} spojuje nejvyšší podíl pozornosti s jeho růstem: nejsilnější kandidát na další "
        "ověření."
    ),
    "answer.conclusion.emerging": (
        "{label} má nižší podíl pozornosti, ale rostoucí: časný signál; ověřte, že nejde o efekt "
        "nízkého základu."
    ),
    "answer.conclusion.no_growth": (
        "Podíl pozornosti neroste v žádné edici; {label} má nejvyšší, a je proto lepším kandidátem "
        "na další průzkum, ne na sázku na expanzi."
    ),
    "answer.conclusion.no_growth_ranked": (
        "Podíl pozornosti neroste v žádné edici; {label} je v pořadí první, a je proto lepším "
        "kandidátem na další průzkum, ne na sázku na expanzi."
    ),
    "answer.conclusion.no_growth_split": (
        "Podíl pozornosti neroste v žádné edici; {label} je v pořadí první a {largest} má nejvyšší "
        "podíl pozornosti: obě jsou kandidáty na další průzkum, ne na sázku na expanzi."
    ),
    "answer.conclusion.single_growing": (
        "Podíl pozornosti roste: tento signál stojí za to potvrdit druhým zdrojem."
    ),
    "answer.conclusion.single_flat": (
        "Podíl pozornosti nemá zřetelný trend: existující publikum bez vzestupného signálu."
    ),
    "answer.conclusion.single_declining": (
        "Podíl pozornosti klesá: data Wikipedie pro toto téma nedávají vzestupný signál."
    ),
    "profile.growth_market": "velké publikum, podíl pozornosti roste",
    "profile.early_niche": "malé publikum, podíl pozornosti roste",
    "profile.mature_market": "velké publikum, podíl pozornosti stabilní",
    "profile.declining": "podíl pozornosti klesá",
    "question.assess": (
        "Posoudit, kam směřuje podíl pozornosti tématu „{topics}“ v edicích {projects}"
    ),
    "trend.significant": (
        "Trend podílu pozornosti je statisticky významný (p = {p_value:.3f}, {direction})"
    ),
    "trend.not_significant": (
        "Trend podílu pozornosti není statisticky významný (p = {p_value:.3f})"
    ),
    "robustness.confirmed.declining": (
        "{label}: trvalý pokles podílu pozornosti. Podíl pozornosti, {basis}: {change}; za "
        "posledních {months} měs. oproti stejným měsícům před rokem zobrazení článku {article}, "
        "provoz edice {edition}, takže podíl dál klesá."
    ),
    "robustness.confirmed.growing": (
        "{label}: trvalý růst podílu pozornosti. Podíl pozornosti, {basis}: {change}; za "
        "posledních {months} měs. oproti stejným měsícům před rokem zobrazení článku {article}, "
        "provoz edice {edition}, takže podíl dál roste."
    ),
    "chart.index_title": "Zobrazení článku proti provozu edice",
    "chart.index_subtitle": (
        "Index: průměr prvních 12 měsíců = 100, průměr za 3 měsíce. Článek pod edicí — téma ztrácí "
        "podíl pozornosti."
    ),
    "chart.axis_index": "index, prvních 12 měs. = 100",
    "chart.series_article_months": "zobrazení článku, měsíc",
    "chart.series_article_smooth": "zobrazení článku",
    "chart.series_edition_short": "provoz edice",
    "chart.note.event": "{month} ×{multiple}",
    "chart.note.possible_bot": "{month} ×{multiple}, možná boti",
    "chart.note.edition": "{month} edice ×{multiple}",
    "chart.note.unknown": "{month} ×{multiple}",
    "chart.yoy_title": "{metric}: změna oproti stejným měsícům před rokem",
    "chart.yoy_subtitle": "Každý bod — poslední 3 měsíce oproti stejným 3 měsícům před rokem.",
    "chart.axis_growth": "změna, %",
    "chart.dumbbell_title": "{metric}: dříve a nyní",
    "chart.dumbbell_basis.yoy": "Průměr předchozích 12 měsíců a posledních 12 měsíců.",
    "chart.dumbbell_basis.halves": "Průměr první a druhé poloviny období.",
    "chart.dumbbell_basis.mixed": "Průměr dřívějších a pozdějších měsíců.",
    "chart.series_before.yoy": "předchozích 12 měs.",
    "chart.series_after.yoy": "posledních 12 měs.",
    "chart.series_before.halves": "první polovina",
    "chart.series_after.halves": "druhá polovina",
    "chart.series_before.mixed": "dříve",
    "chart.series_after.mixed": "nyní",
    "chart.scatter_title": "{metric}: velikost a změna",
    "chart.scatter_subtitle": "Vpravo — větší podíl; nad čarou — roste, pod ní — klesá.",
    "chart.axis_log": "{unit}, logaritmická stupnice",
    "chart.axis_per_million": "zobrazení článku na 1 mil. zobrazení edice",
    "chart.season_period": "Spočteno za {start} – {end}.",
}
