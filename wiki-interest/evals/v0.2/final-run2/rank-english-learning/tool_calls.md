# Tool calls: rank-english-learning

## User turn 1

> Ми створюємо застосунок для вивчення мов. Порівняй інтерес до вивчення англійської в українському, польському, чеському, румунському та угорському розділах Wikipedia та підготуй короткий звіт: які аудиторії варто дослідити наступними й чому?


**Assistant:**

Я використаю skill `wiki-interest` для аналізу інтересу до вивчення англійської мови за різними мовними розділами Wikipedia.

- **Skill** `{"skill": "wiki-interest", "args": "topic: English language learning, languages: uk, pl, cs, ro, hu"}`
  - result: `Launching skill: wiki-interest`

**Assistant:**

Розумію. Вам потрібно порівняти інтерес до вивчення англійської мови (як предмета) у різних мовних розділах Wikipedia і визначити, які аудиторії варто дослідити наступними.

Згідно з workflow, вимірювання інтересу до навчання предмета — це аналіз самого предмета. Я створю запит для аналізу теми "Англійська мова" з питанням типу `rank` (які аудиторії дослідити далі).

- **Write** `{"file_path": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\\request.json", "content": "{\n  \"question_type\": \"rank\",\n  \"topics\": [\n    {\n      \"query\": \"Англійська мова\",\n      \"query_language\": \"uk\",\n      \"query_en\": \"English language\",\n      \"id\": \"en_lang\",\n      \"meaning\": \"English language as a subject\"\n    }\n  ],\n  \"projects\": [\"uk\", \"pl\", \"cs\", \"ro\", \"hu\"],\n  \"report\": {\n    \"language\": \"uk\",\n    \"audience_note\": \"Порівняння інтересу учнів та розробників мобільного додатку для вивчення мов у різних європейських регіонах\"\n  },\n  \"session\": \"english-learning-rank-1\"\n}\n"}`
  - result: `File created successfully at: X:\personal_projects\wiki-interest\tools\skill-evals\runs\v02-final2\sandboxes\rank-english-learning-rep-1\request.json (file state is current in your context — no need to Read it back)`

**Assistant:**

Тепер запускаю аналіз:

- **PowerShell** `{"command": "cd \"X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\"; uv run --project \".\\.claude\\skills\\wiki-interest\" \".\\.claude\\skills\\wiki-interest\\scripts\\run.py\" request.json", "timeout": 600000, "description": "Run wiki-interest analysis to compare English language interest across Wikipedia editions"}`
  - result: `{
   "status": "ok",
   "exit_code": 0,
   "run_id": "20260926-180234-0b39",
   "run_dir": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\\wiki-interest-runs\\english-learning-rank-1\\20260926-180234-0b39",
   "summary_md": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\\wiki-interest-runs\\english-learning-rank-1\\20260926-180234-0b39\\summary.md",
   "summary_json": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\ran`

**Assistant:**

Чудово! Дані зібрано. Тепер прочитаю факти для написання аналізу:

- **Read** `{"file_path": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\\wiki-interest-runs\\english-learning-rank-1\\20260926-180234-0b39\\facts.json"}`
  - result: `1	{ 2	  "schema_version": "3", 3	  "language": "uk", 4	  "question": "rank", 5	  "audience_note": "Порівняння інтересу учнів та розробників мобільного додатку для вивчення мов у різних європейських регіонах", 6	  "period": "2024-09 – 2026-08", 7	  "topics": [ 8	    "en-lang: Англійська мова (Q1860), західногерманська мова, яка виникла в Англії" 9	  ], 10	  "observations": [ 11	    { 12	      "id": "trend:en-lang/uk", 13	      "kind": "trend", 14	      "pair": "en-lang/uk", 15	      "weight": "high", 16	      "statement": "Verdict for the analysis window (September 2024 – August 2026): the atte`

**Assistant:**

Чудово! Маю всі дані. Тепер напишу аналізу для звіту:

- **Write** `{"file_path": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\\narrative.json", "content": "{\n  \"language\": \"uk\",\n  \"topic\": \"Англійська мова, західногерманська мова, яка виникла в Англії\",\n  \"story\": [\n    {\n      \"text\": \"Найбільша аудиторія — українська Вікіпедія: стаття про англійську мову відкривається близько 6,800 разів на місяць, або 120 переглядів на мільйон переглядів розділу. Це удвічі більше, ніж у румунській Вікіпедії (76,9 на мільйон), і істотно більше, ніж у чеській (48,2) чи польській (43,5). Однак розміри не кажуть про динаміку: всі п'ять розділів рухаються в однаку сторону — цікавість падає або стоїть на місці. Жоден не показує зростання.\",\n      \"uses\": [\n        \"size:en-lang/uk\`
  - result: `File created successfully at: X:\personal_projects\wiki-interest\tools\skill-evals\runs\v02-final2\sandboxes\rank-english-learning-rep-1\narrative.json (file state is current in your context — no need to Read it back)`

**Assistant:**

Тепер рендерую звіт з моєю аналізою:

- **PowerShell** `{"command": "cd \"X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\"; uv run --project \".\\.claude\\skills\\wiki-interest\" \".\\.claude\\skills\\wiki-interest\\scripts\\render.py\" \"X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\\wiki-interest-runs\\english-learning-rank-1\\20260926-180234-0b39\" --narrative narrative.json", "timeout": 60000, "description": "Render the wiki-interest report with narrative"}`
  - result: `Exit code 2 {
   "status": "rejected",
   "exit_code": 2,
   "run_dir": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\\wiki-interest-runs\\english-learning-rank-1\\20260926-180234-0b39",
   "report_pdf": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\\wiki-interest-runs\\english-learning-rank-1\\20260926-180234-0b39\\report.pdf",
   "summary_md": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-re`

**Assistant:**

Потрібно виправити кілька речей. Давайте:

- **Write** `{"file_path": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\\narrative.json", "content": "{\n  \"language\": \"uk\",\n  \"topic\": \"Англійська мова, західногерманська мова, яка виникла в Англії\",\n  \"story\": [\n    {\n      \"text\": \"Найбільша аудиторія — українська Вікіпедія: стаття про англійську мову відкривається близько 6,800 разів на місяць, або 120 переглядів на мільйон переглядів розділу. Це удвічі більше, ніж у румунській Вікіпедії (76,9 на мільйон) і істотно більше, ніж у чеській чи польській. Однак жоден розділ не показує зростання — все рухається в один бік.\",\n      \"uses\": [\n        \"size:en-lang/uk\",\n        \"size:en-lang/pl\",\n        \"size:en-lang/cs\",\n        \"size:en-lang/ro\",\n    `
  - result: `The file X:\personal_projects\wiki-interest\tools\skill-evals\runs\v02-final2\sandboxes\rank-english-learning-rep-1\narrative.json has been updated successfully. (file state is current in your context — no need to Read it back)`

**Assistant:**

Тепер рендерую знову:

- **PowerShell** `{"command": "cd \"X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\"; uv run --project \".\\.claude\\skills\\wiki-interest\" \".\\.claude\\skills\\wiki-interest\\scripts\\render.py\" \"X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\\wiki-interest-runs\\english-learning-rank-1\\20260926-180234-0b39\" --narrative narrative.json", "timeout": 60000, "description": "Render the wiki-interest report"}`
  - result: `{
   "status": "accepted",
   "exit_code": 0,
   "run_dir": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\\wiki-interest-runs\\english-learning-rank-1\\20260926-180234-0b39",
   "report_pdf": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\\wiki-interest-runs\\english-learning-rank-1\\20260926-180234-0b39\\report.pdf",
   "summary_md": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\v02-final2\\sandboxes\\rank-english-learning-rep-1\\wiki-in`

**Assistant:**

Англійська мова, західногерманська мова, яка виникла в Англії

**Англійська мова: в українській Вікіпедії інтерес спадає; у польській Вікіпедії інтерес стабільний; у чеській Вікіпедії інтерес стабільний; у румунській Вікіпедії інтерес спадає; в угорській Вікіпедії інтерес спадає.**

uk: інтерес спадає. Частка уваги з 2024-09: 150,0 → 109,0 на 1 млн переглядів, −16 % за рік.
Довіра (uk): висока — спад у 12 з 12 міс. р/р; −16 %/рік [−19; −9]; контрольні статті +3 %/рік; перейменувань немає.
pl: інтерес стабільний. Частка уваги з 2024-09: 49,2 → 42,8 на 1 млн переглядів, −7 % за рік.
Довіра (pl): середня — −7 %/рік [−15; −1]; р/р нижче у 9, вище у 3 з 12 міс.; тренд понад ±10 %/рік не виключений; контрольні статті +8 %/рік; перейменувань немає.
cs: інтерес стабільний. Частка уваги з 2024-09: 57,2 → 48,4 на 1 млн переглядів, −8 % за рік.
Довіра (cs): середня — −8 %/рік [−18; −3]; р/р нижче у 10, вище у 2 з 12 міс.; тренд понад ±10 %/рік не виключений; контрольні статті +12 %/рік; перейменувань немає.
ro: інтерес спадає. Частка уваги з 2024-09: 109,0 → 73,7 на 1 млн переглядів, −19 % за рік.
Довіра (ro): висока — спад у 12 з 12 міс. р/р; −19 %/рік [−26; −13]; контрольні статті −3 %/рік; перейменувань немає.
hu: інтерес спадає. Частка уваги з 2024-09: 46,9 → 27,6 на 1 млн переглядів, −24 % за рік.
Довіра (hu): висока — спад у 12 з 12 міс. р/р; −24 %/рік [−28; −18]; контрольні статті +2 %/рік; перейменувань немає.

Найбільша аудиторія — українська Вікіпедія: стаття про англійську мову відкривається близько 6,800 разів на місяць, або 120 переглядів на мільйон переглядів розділу. Це удвічі більше, ніж у румунській Вікіпедії (76,9 на мільйон) і істотно більше, ніж у чеській чи польській. Однак жоден розділ не показує зростання — все рухається в один бік.

У українській і румунській Вікіпедіях інтерес падає надійно: −16 % та −19 % щорічно з усіх 12 місяців року гірше, ніж роком раніше. Угорська мовна розділ показує найгірше (−24 % щорічно). Польська й чеська вікіпедії стабільніші, але також втрачають переглядів швидше, ніж їхні мовні розділи в цілому, що вказує на специфічний спад інтересу до теми, не на загальне скорочення аудиторії.

У ширшому контексті з 2021 року гарячий інтерес до англійської мови був у 2022 році. Потім упав в усіх розділах: українська втратила близько трьох чвертей від піку, угорська — близько двох третин. Це не короткочасний всплиск, а зміна довгострокового тренду: аудиторія перейшла на інші джерела чи втратила інтерес.

Рекомендація: uk: інтерес спадає (150,0 → 109,0, −16 %/рік); pl: інтерес стабільний (49,2 → 42,8, −7 %/рік); cs: інтерес стабільний (57,2 → 48,4, −8 %/рік); ro: інтерес спадає (109,0 → 73,7, −19 %/рік); hu: інтерес спадає (46,9 → 27,6, −24 %/рік). Жоден мовний розділ не показує зростання. Якщо обирати — польська Вікіпедія. Довіра до вибору: середня.
**Що це означає для вас:** Жодна мовна Вікіпедія не показує зростання, тому сигнал про майбутній попит слабий. Якщо все ж вибирати: польська мовна розділ. Вона не падає так різко, як інші. Довіра до цього вибору помірна, але це найстабільніший сигнал серед п'яти. Варто перевірити сусідні теми — американську та британську англійську, щоб розібратись, чи людей відштовхує сама мова чи окремі варіанти.
Наступна перевірка: суміжні статті — Американська англійська, Британська англійська; я можу додати їх до цього аналізу.

_Переглядність показує інтерес, а не готовність платити. Кожна мовна Вікіпедія — це мовна аудиторія, не територіальна._

Що ще я можу зробити:
- Я можу додати до аналізу суміжні статті
- Я можу показати, які місяці року найсильніші (миттєво: дані вже завантажені)
- Я можу подивитися довший період, аж до 2015-07

PDF-звіт: X:\personal_projects\wiki-interest\tools\skill-evals\runs\v02-final2\sandboxes\rank-english-learning-rep-1\wiki-interest-runs\english-learning-rank-1\20260926-180234-0b39\report.pdf


Turns: 10, cost: 0.1647467 USD, duration: 131745 ms.
