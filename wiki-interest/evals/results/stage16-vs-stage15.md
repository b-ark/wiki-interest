# Benchmark (2026-09-26 19:59 UTC)

## Variants

| Variant | Scenarios × reps | Pass rate (mean ± std over reps) | Noise floor | Deterministic | Judge | Turns | Tokens in/out | Cost USD | Duration s | Errors |
|---|---|---|---|---|---|---|---|---|---|---|
| stage15-7a4f12b | 29 × 3 | 96.7% ± 1.2% | 0.107 | 97.3% | 93.6% | 10.7 | 456583/5640 | 0.1218 | 90 | 0 |
| stage16-df5a4ff | 29 × 3 | 94.9% ± 2.8% | 0.107 | 96.2% | 91.9% | 11.2 | 515884/6453 | 0.1404 | 103 | 0 |

## stage15-7a4f12b

- run dir: `runs\stage15`
- requested model: `haiku`; served: ['claude-haiku-4-5-20251001']
- skill hash(es): ['5ec15247db6a']
- statuses: {'ok': 87}; unmeasured cases by class: {}; errors later resolved by resume: 0; **1 case(s) without the judge**: run `regrade --judge`

| Assertion type | Pass rate |
|---|---|
| answer_contains | 92.6% |
| caveats_relayed | 98.6% |
| chat_answer_relayed | 96.0% |
| clarification_asked | 100.0% |
| file_exists | 96.2% |
| max_turns | 100.0% |
| narrative_accepted | 92.0% |
| no_tool_called | 100.0% |
| numbers_grounded | 98.7% |
| pdf_pages | 97.3% |
| question_relayed | 100.0% |
| summary_field | 96.6% |
| tool_called | 98.8% |

| Rubric | Pass rate |
|---|---|
| answers-question | 100.0% |
| asks-for-link | 100.0% |
| asks-not-guesses | 100.0% |
| explains-absolute | 100.0% |
| explains-change | 66.7% |
| explains-data-start | 100.0% |
| faithful | 86.5% |
| honest-about-decline | 100.0% |
| honest-not-found | 100.0% |
| limitations-stated | 100.0% |
| missing-article-honest | 100.0% |
| names-substitute | 66.7% |
| no-needless-question | 97.6% |
| recommends-audiences | 66.7% |
| right-meaning | 100.0% |
| shows-options | 100.0% |
| states-findings | 91.7% |
| trust-explained | 92.9% |
| user-language | 96.5% |

| Scenario | Pass rate |
|---|---|
| ambiguous-mercury | 100.0% |
| assess-astronomy-uk | 100.0% |
| chemistry-mercury-en | 97.9% |
| chemistry-merkurii-uk | 100.0% |
| compare-fasting-pl-cs | 93.3% |
| en-stoicism-assess | 100.0% |
| followup-absolute | 92.9% |
| followup-add-editions | 93.3% |
| followup-longer-period | 91.7% |
| period-before-2015 | 95.6% |
| pl-fasting-no-article | 91.2% |
| pl-yoga-compare | 100.0% |
| rank-english-learning | 84.3% |
| ru-chess-compare | 95.8% |
| topic-not-found | 100.0% |
| ts-amb-jaguar | 100.0% |
| ts-crypto-ru | 100.0% |
| ts-ctx-go-course | 97.8% |
| ts-ctx-jaguar-wildlife-uk | 100.0% |
| ts-ctx-mars-astro | 100.0% |
| ts-ctx-python-course | 97.8% |
| ts-ctx-rust-course | 100.0% |
| ts-ctx-tesla-cars | 100.0% |
| ts-ctx-tesla-unit | 77.8% |
| ts-meditation-pl | 100.0% |
| ts-miss-kombucha | 100.0% |
| ts-photosynthesis-en | 100.0% |
| ts-quantum-en | 97.8% |
| ts-veganism-cs | 97.8% |

## stage16-df5a4ff

- run dir: `runs\stage16`
- requested model: `haiku`; served: ['claude-haiku-4-5-20251001']
- skill hash(es): ['dcb3c8114995']
- statuses: {'ok': 87}; unmeasured cases by class: {}; errors later resolved by resume: 0; **5 case(s) without the judge**: run `regrade --judge`

| Assertion type | Pass rate |
|---|---|
| answer_contains | 92.6% |
| caveats_relayed | 98.6% |
| chat_answer_relayed | 100.0% |
| clarification_asked | 91.7% |
| file_exists | 96.2% |
| max_turns | 100.0% |
| narrative_accepted | 88.0% |
| no_tool_called | 100.0% |
| numbers_grounded | 96.0% |
| pdf_pages | 96.0% |
| question_relayed | 91.7% |
| summary_field | 94.3% |
| tool_called | 97.5% |

| Rubric | Pass rate |
|---|---|
| answers-question | 100.0% |
| asks-for-link | 100.0% |
| asks-not-guesses | 83.3% |
| explains-absolute | 100.0% |
| explains-change | 100.0% |
| explains-data-start | 100.0% |
| faithful | 85.7% |
| honest-about-decline | 100.0% |
| honest-not-found | 66.7% |
| limitations-stated | 90.0% |
| missing-article-honest | 100.0% |
| names-substitute | 100.0% |
| no-needless-question | 90.0% |
| recommends-audiences | 66.7% |
| right-meaning | 80.0% |
| shows-options | 100.0% |
| states-findings | 85.7% |
| trust-explained | 100.0% |
| user-language | 98.8% |

| Scenario | Pass rate |
|---|---|
| ambiguous-mercury | 83.3% |
| assess-astronomy-uk | 100.0% |
| chemistry-mercury-en | 100.0% |
| chemistry-merkurii-uk | 79.2% |
| compare-fasting-pl-cs | 97.8% |
| en-stoicism-assess | 95.8% |
| followup-absolute | 100.0% |
| followup-add-editions | 100.0% |
| followup-longer-period | 93.8% |
| period-before-2015 | 100.0% |
| pl-fasting-no-article | 98.2% |
| pl-yoga-compare | 100.0% |
| rank-english-learning | 92.2% |
| ru-chess-compare | 100.0% |
| topic-not-found | 88.9% |
| ts-amb-jaguar | 100.0% |
| ts-crypto-ru | 100.0% |
| ts-ctx-go-course | 95.6% |
| ts-ctx-jaguar-wildlife-uk | 100.0% |
| ts-ctx-mars-astro | 95.6% |
| ts-ctx-python-course | 97.8% |
| ts-ctx-rust-course | 97.8% |
| ts-ctx-tesla-cars | 48.9% |
| ts-ctx-tesla-unit | 100.0% |
| ts-meditation-pl | 97.8% |
| ts-miss-kombucha | 91.7% |
| ts-photosynthesis-en | 100.0% |
| ts-quantum-en | 97.8% |
| ts-veganism-cs | 100.0% |

## stage16-df5a4ff vs stage15-7a4f12b

Overall delta (other − base): -0.018 on 29 common scenario(s); noise floor 0.107 (within the noise floor).

| Scenario | Base | Other | Delta |
|---|---|---|---|
| ambiguous-mercury | 100.0% | 83.3% | -0.17 |
| chemistry-mercury-en | 97.9% | 100.0% | +0.02 |
| chemistry-merkurii-uk | 100.0% | 79.2% | -0.21 |
| compare-fasting-pl-cs | 93.3% | 97.8% | +0.04 |
| en-stoicism-assess | 100.0% | 95.8% | -0.04 |
| followup-absolute | 92.9% | 100.0% | +0.07 |
| followup-add-editions | 93.3% | 100.0% | +0.07 |
| followup-longer-period | 91.7% | 93.8% | +0.02 |
| period-before-2015 | 95.6% | 100.0% | +0.04 |
| pl-fasting-no-article | 91.2% | 98.2% | +0.07 |
| rank-english-learning | 84.3% | 92.2% | +0.08 |
| ru-chess-compare | 95.8% | 100.0% | +0.04 |
| topic-not-found | 100.0% | 88.9% | -0.11 |
| ts-ctx-go-course | 97.8% | 95.6% | -0.02 |
| ts-ctx-mars-astro | 100.0% | 95.6% | -0.04 |
| ts-ctx-rust-course | 100.0% | 97.8% | -0.02 |
| ts-ctx-tesla-cars | 100.0% | 48.9% | -0.51 |
| ts-ctx-tesla-unit | 77.8% | 100.0% | +0.22 |
| ts-meditation-pl | 100.0% | 97.8% | -0.02 |
| ts-miss-kombucha | 100.0% | 91.7% | -0.08 |
| ts-veganism-cs | 97.8% | 100.0% | +0.02 |

## Notes

- stage16-df5a4ff vs stage15-7a4f12b: delta -0.018 is within the noise floor 0.107; do not conclude either is better.
