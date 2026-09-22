# Benchmark (2026-09-22 21:28 UTC)

## Variants

| Variant | Scenarios × reps | Pass rate (mean ± std over reps) | Noise floor | Deterministic | Judge | Turns | Tokens in/out | Cost USD | Duration s | Errors |
|---|---|---|---|---|---|---|---|---|---|---|
| base-v1 | 12 × 3 | 97.3% ± 1.2% | 0.167 | 97.6% | 96.3% | 9.6 | 353410/3334 | 0.1009 | 76 | 0 |

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
