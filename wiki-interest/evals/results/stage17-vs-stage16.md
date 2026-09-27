# Benchmark (2026-09-27 00:47 UTC)

## Variants

| Variant | Scenarios × reps | Pass rate (mean ± std over reps) | Noise floor | Deterministic | Judge | Turns | Tokens in/out | Cost USD | Duration s | Errors |
|---|---|---|---|---|---|---|---|---|---|---|
| stage16-df5a4ff | 29 × 3 | 94.9% ± 2.8% | 0.107 | 96.2% | 91.9% | 11.2 | 515884/6453 | 0.1404 | 103 | 0 |
| stage17-4d13145 | 29 × 3 | 97.6% ± 2.2% | 0.107 | 98.7% | 93.6% | 10.0 | 444418/5970 | 0.1313 | 93 | 0 |

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

## stage17-4d13145

- run dir: `runs\stage17`
- requested model: `haiku`; served: ['claude-haiku-4-5-20251001']
- skill hash(es): ['4d1e1e14a76d']
- statuses: {'ok': 87}; unmeasured cases by class: {}; errors later resolved by resume: 0

| Assertion type | Pass rate |
|---|---|
| answer_contains | 96.3% |
| caveats_relayed | 98.6% |
| chat_answer_relayed | 100.0% |
| clarification_asked | 100.0% |
| file_exists | 98.7% |
| max_turns | 100.0% |
| narrative_accepted | 97.3% |
| no_tool_called | 100.0% |
| numbers_grounded | 98.7% |
| pdf_pages | 98.7% |
| question_relayed | 100.0% |
| summary_field | 97.7% |
| tool_called | 98.8% |

| Rubric | Pass rate |
|---|---|
| answers-question | 100.0% |
| asks-for-link | 100.0% |
| asks-not-guesses | 100.0% |
| explains-absolute | 100.0% |
| explains-change | 100.0% |
| explains-data-start | 100.0% |
| faithful | 81.3% |
| honest-about-decline | 100.0% |
| honest-not-found | 100.0% |
| limitations-stated | 100.0% |
| missing-article-honest | 100.0% |
| names-substitute | 100.0% |
| no-needless-question | 97.6% |
| recommends-audiences | 66.7% |
| right-meaning | 100.0% |
| shows-options | 100.0% |
| states-findings | 86.1% |
| trust-explained | 100.0% |
| user-language | 100.0% |

| Scenario | Pass rate |
|---|---|
| ambiguous-mercury | 100.0% |
| assess-astronomy-uk | 97.9% |
| chemistry-mercury-en | 97.9% |
| chemistry-merkurii-uk | 100.0% |
| compare-fasting-pl-cs | 98.3% |
| en-stoicism-assess | 100.0% |
| followup-absolute | 97.6% |
| followup-add-editions | 97.8% |
| followup-longer-period | 93.8% |
| period-before-2015 | 97.8% |
| pl-fasting-no-article | 96.5% |
| pl-yoga-compare | 100.0% |
| rank-english-learning | 94.1% |
| ru-chess-compare | 100.0% |
| topic-not-found | 100.0% |
| ts-amb-jaguar | 100.0% |
| ts-crypto-ru | 100.0% |
| ts-ctx-go-course | 100.0% |
| ts-ctx-jaguar-wildlife-uk | 97.8% |
| ts-ctx-mars-astro | 97.8% |
| ts-ctx-python-course | 97.8% |
| ts-ctx-rust-course | 93.3% |
| ts-ctx-tesla-cars | 77.8% |
| ts-ctx-tesla-unit | 100.0% |
| ts-meditation-pl | 97.8% |
| ts-miss-kombucha | 100.0% |
| ts-photosynthesis-en | 100.0% |
| ts-quantum-en | 97.8% |
| ts-veganism-cs | 97.8% |

## stage17-4d13145 vs stage16-df5a4ff

Overall delta (other − base): 0.027 on 29 common scenario(s); noise floor 0.107 (within the noise floor).

| Scenario | Base | Other | Delta |
|---|---|---|---|
| ambiguous-mercury | 83.3% | 100.0% | +0.17 |
| assess-astronomy-uk | 100.0% | 97.9% | -0.02 |
| chemistry-mercury-en | 100.0% | 97.9% | -0.02 |
| chemistry-merkurii-uk | 79.2% | 100.0% | +0.21 |
| compare-fasting-pl-cs | 97.8% | 98.3% | +0.01 |
| en-stoicism-assess | 95.8% | 100.0% | +0.04 |
| followup-absolute | 100.0% | 97.6% | -0.02 |
| followup-add-editions | 100.0% | 97.8% | -0.02 |
| period-before-2015 | 100.0% | 97.8% | -0.02 |
| pl-fasting-no-article | 98.2% | 96.5% | -0.02 |
| rank-english-learning | 92.2% | 94.1% | +0.02 |
| topic-not-found | 88.9% | 100.0% | +0.11 |
| ts-ctx-go-course | 95.6% | 100.0% | +0.04 |
| ts-ctx-jaguar-wildlife-uk | 100.0% | 97.8% | -0.02 |
| ts-ctx-mars-astro | 95.6% | 97.8% | +0.02 |
| ts-ctx-rust-course | 97.8% | 93.3% | -0.04 |
| ts-ctx-tesla-cars | 48.9% | 77.8% | +0.29 |
| ts-miss-kombucha | 91.7% | 100.0% | +0.08 |
| ts-veganism-cs | 100.0% | 97.8% | -0.02 |

## Notes

- stage17-4d13145 vs stage16-df5a4ff: delta +0.027 is within the noise floor 0.107; do not conclude either is better.
