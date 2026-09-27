# Tool calls: assess-astronomy-uk

## User turn 1

> Ми думаємо додати курс з астрономії до освітнього застосунку. Чи зростає інтерес до цієї теми в україномовній Wikipedia, і наскільки цьому зростанню можна довіряти?

- **Skill** `{"skill": "wiki-interest", "args": "topic: астрономія, languages: uk"}`
  - result: `Launching skill: wiki-interest`

**Assistant:**

Зрозумів, аналізую тренд астрономії на українській Wikipedia. Напишу запит і запущу аналіз.

- **Write** `{"file_path": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\\request.json", "content": "{\n  \"question_type\": \"assess\",\n  \"topics\": [\n    {\n      \"query\": \"астрономія\",\n      \"query_language\": \"uk\",\n      \"query_en\": \"astronomy\",\n      \"id\": \"astronomy\",\n      \"meaning\": \"the scientific study of celestial objects and space\"\n    }\n  ],\n  \"projects\": [\"uk\"],\n  \"report\": {\n    \"language\": \"uk\",\n    \"audience_note\": \"освітній застосунок з курсом астрономії\"\n  },\n  \"session\": \"astronomy-uk-assess\"\n}\n"}`
  - result: `File created successfully at: X:\personal_projects\wiki-interest\tools\skill-evals\runs\stage18\sandboxes\assess-astronomy-uk-rep-1\request.json (file state is current in your context — no need to Read it back)`
- **PowerShell** `{"command": "cd \"X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\"; uv run --project \"X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\\.claude\\skills\\wiki-interest\" \"X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\\.claude\\skills\\wiki-interest\\scripts\\run.py\" request.json", "timeout": 600000, "description": "Run wiki-interest skill analysis for astronomy on Ukrainian Wikipedia"}`
  - result: `{
   "status": "ok",
   "exit_code": 0,
   "run_id": "20260927-095450-9cac",
   "run_dir": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\\wiki-interest-runs\\astronomy-uk-assess\\20260927-095450-9cac",
   "summary_md": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\\wiki-interest-runs\\astronomy-uk-assess\\20260927-095450-9cac\\summary.md",
   "summary_json": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-`
- **Read** `{"file_path": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\\wiki-interest-runs\\astronomy-uk-assess\\20260927-095450-9cac\\facts.json"}`
  - result: `1	{ 2	  "schema_version": "3", 3	  "language": "uk", 4	  "question": "assess", 5	  "audience_note": "освітній застосунок з курсом астрономії", 6	  "period": "2024-09 – 2026-08", 7	  "topics": [ 8	    "astronomy: астрономія (Q333), одна з найдавніших наук, що включає спостереження і пояснення подій, які відбуваються за межами Землі та її атмосфери" 9	  ], 10	  "observations": [ 11	    { 12	      "id": "trend:astronomy/uk", 13	      "kind": "trend", 14	      "pair": "astronomy/uk", 15	      "weight": "high", 16	      "statement": "Verdict for the analysis window (September 2024 – August 2026): t`

**Assistant:**

Now I'll write the narrative based on the observations:

- **Write** `{"file_path": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\\narrative.json", "content": "{\n  \"language\": \"uk\",\n  \"topic\": \"астрономія, наука про небесні тіла і простір\",\n  \"story\": [\n    {\n      \"text\": \"В українському мовному розділі Вікіпедії інтерес до астрономії спадає. Частка уваги статті впала з 16,4 до 7,1 переглядів на мільйон переглядів розділу (−35 % на рік). Цей спад надійний: в 10 з 12 місяців показники були нижче за аналогічні місяці року раніше. Статтю відкривають близько 560 разів на місяць, але це вже значно менше, ніж раніше.\",\n      \"uses\": [\n        \"trend:astronomy/uk\",\n        \"trust:astronomy/uk\",\n        \"size:astronomy/uk\"\n      ]\n    },\n    {\n      \"text\": \"Спад `
  - result: `File created successfully at: X:\personal_projects\wiki-interest\tools\skill-evals\runs\stage18\sandboxes\assess-astronomy-uk-rep-1\narrative.json (file state is current in your context — no need to Read it back)`
- **PowerShell** `{"command": "cd \"X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\"; uv run --project \"X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\\.claude\\skills\\wiki-interest\" \"X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\\.claude\\skills\\wiki-interest\\scripts\\render.py\" \"X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\\wiki-interest-runs\\astronomy-uk-assess\\20260927-095450-9cac\" --narrative narrative.json", "timeout": 60000, "description": "Render the narrative into the final report and chat answer"}`
  - result: `{
   "status": "accepted",
   "exit_code": 0,
   "run_dir": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\\wiki-interest-runs\\astronomy-uk-assess\\20260927-095450-9cac",
   "report_pdf": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\\wiki-interest-runs\\astronomy-uk-assess\\20260927-095450-9cac\\report.pdf",
   "summary_md": "X:\\personal_projects\\wiki-interest\\tools\\skill-evals\\runs\\stage18\\sandboxes\\assess-astronomy-uk-rep-1\\wiki-interest-runs\\astronomy-`

**Assistant:**

астрономія, наука про небесні тіла і простір

**Астрономія: в українській Вікіпедії інтерес спадає.**

uk: інтерес спадає. Частка уваги з 2024-09: 16,4 → 7,1 на 1 млн переглядів, −35 % за рік.
Довіра (uk): висока — спад у 10 з 12 міс. р/р; −35 %/рік [−53; −4]; контрольні статті +3 %/рік; перейменувань немає.

В українському мовному розділі Вікіпедії інтерес до астрономії спадає. Частка уваги статті впала з 16,4 до 7,1 переглядів на мільйон переглядів розділу (−35 % на рік). Цей спад надійний: в 10 з 12 місяців показники були нижче за аналогічні місяці року раніше. Статтю відкривають близько 560 разів на місяць, але це вже значно менше, ніж раніше.

Спад став крутішим у травні 2025 року, коли частка уваги впала на 37 %. Одночасно впала й загальна кількість переглядів українського розділу, тому частина падіння статті може бути пов'язана із змінами в самому розділі. Але разом з тим стаття втратила на 60 % переглядів, тоді як розділ загалом — лише на 25 %, тобто астрономія втрачає увагу швидше за весь розділ.

Аудиторія статті — здебільшого школярі. Кожного вересня кількість переглядів стрибає на 245 % вище звичайного рівня, а влітку в липні впадає на 56 %. Цей ритм повторюється щороку, що вказує на школярів, які читають про астрономію в навчальних цілях. На ширшому фоні з 2021 року частка уваги падала майже щороку — у 2025 році вона була близько чверті від рівня 2021-го.

Рекомендація: uk: інтерес спадає (16,4 → 7,1, −35 %/рік). Довіра до вибору: висока.
**Що це означає для вас:** Інтерес до астрономії в українській Вікіпедії скорочується і не подає сигнали зростання, якими варто було б керуватися при розробці освітнього застосунку. Якщо вирішуватимете додавати курс астрономії, розраховуйте більше на школярів і готуйте матеріал до вересня, коли інтерес піками. Перевірте сусідні теми — фізичні та точні науки — щоб див'ятися, чи є там ростучі аудиторії.
Наступна перевірка: суміжні статті — фізичні науки, точні науки; я можу додати їх до цього аналізу.

_Перегляди Вікіпедії показують інтерес до теми, але не готовність платити або використовувати продукт; мовний розділ — це мова, а не крайна._

Що ще я можу зробити:
- Я можу додати до аналізу суміжні статті
- Я можу показати, які місяці року найсильніші (миттєво: дані вже завантажені)
- Я можу подивитися довший період, аж до 2015-07

PDF-звіт: X:\personal_projects\wiki-interest\tools\skill-evals\runs\stage18\sandboxes\assess-astronomy-uk-rep-1\wiki-interest-runs\astronomy-uk-assess\20260927-095450-9cac\report.pdf


Turns: 8, cost: 0.160937 USD, duration: 95841 ms.
