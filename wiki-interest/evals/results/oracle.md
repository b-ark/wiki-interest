# Grader sanity check (oracle vs null agent)

- Healthy: **yes**
- Oracle pass rate (should be 100 %): 95%
- Null pass rate on work-requiring assertions (should be 0 %): 0%

## Problems

None.

## Checks only a model can pass

The report is not in English, and the oracle's text is the code's own English one.

- `compare-fasting-pl-cs` a11 `answer_contains`
- `compare-fasting-pl-cs` a12 `narrative_accepted`
- `assess-astronomy-uk` a9 `narrative_accepted`
- `rank-english-learning` a9 `narrative_accepted`
- `followup-longer-period` a10 `narrative_accepted`
- `ru-chess-compare` a10 `narrative_accepted`
- `chemistry-merkurii-uk` a10 `narrative_accepted`
- `pl-yoga-compare` a9 `narrative_accepted`
- `period-before-2015` a10 `narrative_accepted`
- `followup-absolute` a9 `narrative_accepted`
- `followup-add-editions` a9 `narrative_accepted`
- `ts-ctx-jaguar-wildlife-uk` a9 `narrative_accepted`
- `ts-ctx-tesla-cars` a9 `narrative_accepted`
- `ts-ctx-go-course` a9 `narrative_accepted`
- `ts-ctx-mars-astro` a9 `narrative_accepted`
- `ts-crypto-ru` a9 `narrative_accepted`

## Per scenario

| Scenario | Exit codes | Oracle | Null |
|---|---|---|---|
| compare-fasting-pl-cs | 3, 0 | 13/15 | 4/15 |
| assess-astronomy-uk | 0 | 10/11 | 3/11 |
| rank-english-learning | 0 | 11/12 | 4/12 |
| followup-longer-period | 0, 0 | 11/12 | 3/12 |
| ru-chess-compare | 0 | 11/12 | 3/12 |
| en-stoicism-assess | 0 | 12/12 | 3/12 |
| ambiguous-mercury | 3 | 4/4 | 2/4 |
| chemistry-mercury-en | 0 | 12/12 | 3/12 |
| chemistry-merkurii-uk | 0 | 11/12 | 3/12 |
| topic-not-found | 3 | 6/6 | 2/6 |
| pl-fasting-no-article | 3, 0 | 15/15 | 4/15 |
| pl-yoga-compare | 0 | 10/11 | 3/11 |
| period-before-2015 | 0 | 11/12 | 3/12 |
| followup-absolute | 0, 0 | 10/11 | 3/11 |
| followup-add-editions | 0, 0 | 10/11 | 3/11 |
| ts-ctx-python-course | 0 | 11/11 | 3/11 |
| ts-ctx-tesla-unit | 0 | 11/11 | 3/11 |
| ts-ctx-jaguar-wildlife-uk | 0 | 10/11 | 3/11 |
| ts-ctx-tesla-cars | 0 | 10/11 | 3/11 |
| ts-ctx-go-course | 0 | 10/11 | 3/11 |
| ts-ctx-rust-course | 0 | 11/11 | 3/11 |
| ts-ctx-mars-astro | 0 | 10/11 | 3/11 |
| ts-crypto-ru | 0 | 10/11 | 3/11 |
| ts-photosynthesis-en | 0 | 11/11 | 3/11 |
| ts-veganism-cs | 0 | 11/11 | 3/11 |
| ts-meditation-pl | 0 | 11/11 | 3/11 |
| ts-quantum-en | 0 | 11/11 | 3/11 |
| ts-amb-jaguar | 3 | 3/3 | 2/3 |
| ts-miss-kombucha | 3 | 6/6 | 3/6 |
