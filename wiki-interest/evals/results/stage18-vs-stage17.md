# Benchmark (2026-09-27 10:26 UTC)

## Variants

| Variant | Scenarios × reps | Pass rate (mean ± std over reps) | Noise floor | Deterministic | Judge | Turns | Tokens in/out | Cost USD | Duration s | Errors |
|---|---|---|---|---|---|---|---|---|---|---|
| stage17-4d13145 | 29 × 3 | 97.6% ± 2.2% | 0.107 | 98.7% | 93.6% | 10.0 | 444418/5970 | 0.1313 | 93 | 0 |
| stage18-c5bc09f | 29 × 3 | 96.8% ± 1.4% | 0.107 | 97.0% | 94.8% | 10.0 | 446113/5662 | 0.1291 | 102 | 0 |

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

## stage18-c5bc09f

- run dir: `runs\stage18`
- requested model: `haiku`; served: ['claude-haiku-4-5-20251001']
- skill hash(es): ['fbeedb2425c7']
- statuses: {'ok': 87}; unmeasured cases by class: {}; errors later resolved by resume: 7; **1 case(s) without the judge**: run `regrade --judge`

| Assertion type | Pass rate |
|---|---|
| answer_contains | 92.6% |
| caveats_relayed | 97.1% |
| chat_answer_relayed | 98.7% |
| clarification_asked | 100.0% |
| file_exists | 97.4% |
| max_turns | 100.0% |
| narrative_accepted | 89.3% |
| no_tool_called | 100.0% |
| numbers_grounded | 97.3% |
| pdf_pages | 97.3% |
| question_relayed | 91.7% |
| summary_field | 96.6% |
| tool_called | 97.5% |

| Rubric | Pass rate |
|---|---|
| answers-question | 100.0% |
| asks-for-link | 100.0% |
| asks-not-guesses | 100.0% |
| explains-absolute | 100.0% |
| explains-change | 100.0% |
| explains-data-start | 100.0% |
| faithful | 87.8% |
| honest-about-decline | 100.0% |
| honest-not-found | 100.0% |
| limitations-stated | 91.7% |
| missing-article-honest | 100.0% |
| names-substitute | 100.0% |
| no-needless-question | 95.1% |
| recommends-audiences | 66.7% |
| right-meaning | 83.3% |
| shows-options | 100.0% |
| states-findings | 94.3% |
| trust-explained | 100.0% |
| user-language | 98.8% |

| Scenario | Pass rate |
|---|---|
| ambiguous-mercury | 100.0% |
| assess-astronomy-uk | 100.0% |
| chemistry-mercury-en | 100.0% |
| chemistry-merkurii-uk | 79.2% |
| compare-fasting-pl-cs | 98.3% |
| en-stoicism-assess | 100.0% |
| followup-absolute | 100.0% |
| followup-add-editions | 95.6% |
| followup-longer-period | 100.0% |
| period-before-2015 | 95.6% |
| pl-fasting-no-article | 87.7% |
| pl-yoga-compare | 100.0% |
| rank-english-learning | 90.2% |
| ru-chess-compare | 100.0% |
| topic-not-found | 100.0% |
| ts-amb-jaguar | 100.0% |
| ts-crypto-ru | 100.0% |
| ts-ctx-go-course | 77.8% |
| ts-ctx-jaguar-wildlife-uk | 100.0% |
| ts-ctx-mars-astro | 97.8% |
| ts-ctx-python-course | 100.0% |
| ts-ctx-rust-course | 97.8% |
| ts-ctx-tesla-cars | 100.0% |
| ts-ctx-tesla-unit | 97.8% |
| ts-meditation-pl | 93.3% |
| ts-miss-kombucha | 100.0% |
| ts-photosynthesis-en | 100.0% |
| ts-quantum-en | 97.8% |
| ts-veganism-cs | 97.8% |

## stage18-c5bc09f vs stage17-4d13145

Overall delta (other − base): -0.008 on 29 common scenario(s); noise floor 0.107 (within the noise floor).

| Scenario | Base | Other | Delta |
|---|---|---|---|
| assess-astronomy-uk | 97.9% | 100.0% | +0.02 |
| chemistry-mercury-en | 97.9% | 100.0% | +0.02 |
| chemistry-merkurii-uk | 100.0% | 79.2% | -0.21 |
| followup-absolute | 97.6% | 100.0% | +0.02 |
| followup-add-editions | 97.8% | 95.6% | -0.02 |
| followup-longer-period | 93.8% | 100.0% | +0.06 |
| period-before-2015 | 97.8% | 95.6% | -0.02 |
| pl-fasting-no-article | 96.5% | 87.7% | -0.09 |
| rank-english-learning | 94.1% | 90.2% | -0.04 |
| ts-ctx-go-course | 100.0% | 77.8% | -0.22 |
| ts-ctx-jaguar-wildlife-uk | 97.8% | 100.0% | +0.02 |
| ts-ctx-python-course | 97.8% | 100.0% | +0.02 |
| ts-ctx-rust-course | 93.3% | 97.8% | +0.04 |
| ts-ctx-tesla-cars | 77.8% | 100.0% | +0.22 |
| ts-ctx-tesla-unit | 100.0% | 97.8% | -0.02 |
| ts-meditation-pl | 97.8% | 93.3% | -0.04 |

## Notes

- stage18-c5bc09f vs stage17-4d13145: delta -0.008 is within the noise floor 0.107; do not conclude either is better.
