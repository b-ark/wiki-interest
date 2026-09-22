# Benchmark (2026-09-22 21:52 UTC)

## Variants

| Variant | Scenarios × reps | Pass rate (mean ± std over reps) | Noise floor | Deterministic | Judge | Turns | Tokens in/out | Cost USD | Duration s | Errors |
|---|---|---|---|---|---|---|---|---|---|---|
| base-v1 | 12 × 3 | 97.3% ± 1.2% | 0.167 | 97.6% | 96.3% | 9.6 | 353410/3334 | 0.1009 | 76 | 0 |
| v2 | 12 × 3 | 99.3% ± 0.7% | 0.167 | 99.4% | 99.1% | 8.1 | 287282/2932 | 0.0895 | 74 | 0 |

## base-v1

- run dir: `runs\base-v1`
- requested model: `haiku`; served: ['claude-haiku-4-5-20251001']
- skill hash(es): ['a32a9f9debc6']
- statuses: {'ok': 36}; unmeasured cases by class: {}; errors later resolved by resume: 0

| Assertion type | Pass rate |
|---|---|
| answer_contains | 100.0% |
| caveats_relayed | 97.0% |
| clarification_asked | 100.0% |
| file_exists | 100.0% |
| max_turns | 100.0% |
| no_tool_called | 100.0% |
| numbers_grounded | 81.8% |
| pdf_pages | 100.0% |
| summary_field | 98.6% |
| tool_called | 100.0% |

| Rubric | Pass rate |
|---|---|
| answers-question | 100.0% |
| asks-not-guesses | 100.0% |
| explains-absolute | 100.0% |
| explains-change | 100.0% |
| explains-data-start | 100.0% |
| honest-about-decline | 100.0% |
| limitations-stated | 93.3% |
| missing-article-honest | 100.0% |
| recommends-audiences | 100.0% |
| trust-explained | 86.7% |
| user-language | 97.2% |

| Scenario | Pass rate |
|---|---|
| ambiguous-mercury | 100.0% |
| assess-astronomy-uk | 100.0% |
| compare-fasting-pl-cs | 100.0% |
| en-stoicism-assess | 94.9% |
| followup-absolute | 100.0% |
| followup-add-editions | 94.4% |
| followup-longer-period | 97.4% |
| followup-main-article-only | 91.7% |
| period-before-2015 | 91.7% |
| pl-yoga-compare | 100.0% |
| rank-english-learning | 100.0% |
| ru-chess-compare | 97.4% |

## v2

- run dir: `runs\v2`
- requested model: `haiku`; served: ['claude-haiku-4-5-20251001']
- skill hash(es): ['94ff172e875b']
- statuses: {'ok': 36}; unmeasured cases by class: {}; errors later resolved by resume: 0

| Assertion type | Pass rate |
|---|---|
| answer_contains | 91.7% |
| caveats_relayed | 100.0% |
| clarification_asked | 100.0% |
| file_exists | 100.0% |
| max_turns | 100.0% |
| no_tool_called | 100.0% |
| numbers_grounded | 97.0% |
| pdf_pages | 100.0% |
| summary_field | 100.0% |
| tool_called | 100.0% |

| Rubric | Pass rate |
|---|---|
| answers-question | 100.0% |
| asks-not-guesses | 100.0% |
| explains-absolute | 100.0% |
| explains-change | 100.0% |
| explains-data-start | 66.7% |
| honest-about-decline | 100.0% |
| limitations-stated | 100.0% |
| missing-article-honest | 100.0% |
| recommends-audiences | 100.0% |
| trust-explained | 100.0% |
| user-language | 100.0% |

| Scenario | Pass rate |
|---|---|
| ambiguous-mercury | 100.0% |
| assess-astronomy-uk | 100.0% |
| compare-fasting-pl-cs | 100.0% |
| en-stoicism-assess | 100.0% |
| followup-absolute | 100.0% |
| followup-add-editions | 100.0% |
| followup-longer-period | 100.0% |
| followup-main-article-only | 97.2% |
| period-before-2015 | 94.4% |
| pl-yoga-compare | 100.0% |
| rank-english-learning | 100.0% |
| ru-chess-compare | 100.0% |

## v2 vs base-v1

Overall delta (other − base): 0.020 on 12 common scenario(s); noise floor 0.167 (within the noise floor).

| Scenario | Base | Other | Delta |
|---|---|---|---|
| en-stoicism-assess | 94.9% | 100.0% | +0.05 |
| followup-add-editions | 94.4% | 100.0% | +0.06 |
| followup-longer-period | 97.4% | 100.0% | +0.03 |
| followup-main-article-only | 91.7% | 97.2% | +0.06 |
| period-before-2015 | 91.7% | 94.4% | +0.03 |
| ru-chess-compare | 97.4% | 100.0% | +0.03 |

## Notes

- v2 vs base-v1: delta +0.020 is within the noise floor 0.167; do not conclude either is better.
