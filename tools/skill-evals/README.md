# skill-evals

Development harness that measures how well the `wiki-interest` skill works when a cheap agent
model drives it, and whether a change to `SKILL.md` made things better or worse. Design:
`docs/technical-plan.md` section 11 and ADRs 0003/0004.

What it does:

- runs each scenario from `wiki-interest/evals/evals.json` through a real agent in an isolated
  sandbox (headless Claude Code on Haiku 4.5 via `claude -p`, or an OpenRouter model), several
  repetitions each;
- grades the trajectory and artifacts deterministically (pipeline invoked, one-page PDF present,
  every number in the answer exists in `summary.json`, caveats relayed, budgets) and with an LLM
  judge (Sonnet) per rubric criterion;
- compares skill variants pairwise and reports deltas next to an explicit noise floor;
- checks whether the skill's `description` triggers on the right queries.

## Setup

```powershell
$env:UV_LINK_MODE = "copy"                 # only needed on this Windows machine
cd tools/skill-evals
uv sync
uv run pytest                              # offline: no network, no CLI calls
uv run skill-evals smoke                   # one real claude -p call: prints served model and cost
```

Requirements: `uv`, Python 3.12+ (3.14 pinned in `.python-version`), and for live runs the
Claude Code CLI. The CLI is located in this order: `SKILL_EVALS_CLAUDE_BIN`, `claude` on
PATH, then the VS Code extension bundle
`~/.vscode/extensions/anthropic.claude-code-<ver>-win32-x64/resources/native-binary/claude.exe`
(highest version). It works on the user's subscription; no API key is needed.
The OpenRouter provider needs `OPENROUTER_API_KEY`.

## Commands

```text
skill-evals validate-scenarios <evals.json>
skill-evals run      -s <evals.json> -k <skill-dir> -n <run-name> [--reps 3] [--parallelism 2]
                     [--provider claude|openrouter] [--model haiku] [--judge/--no-judge]
                     [--judge-model sonnet] [--warm-cache <dir>] [--resume/--no-resume]
                     [--keep-sandboxes/--delete-sandboxes] [--max-turns 30] [--timeout-s 900]
                     [--allowed-tools Skill,Bash,...] [--only id1,id2] [--tags a,b]
                     [--runs-root runs] [--variant <label>]
skill-evals compare  <run-dir> [<run-dir> ...] [--out runs/_benchmarks]
skill-evals trigger  -c <trigger_evals.json> -k <skill-dir> -n <run-name> [--reps 3]
skill-evals smoke    [--model haiku]
```

A typical A/B cycle:

```powershell
uv run skill-evals run -s ../../wiki-interest/evals/evals.json -k ../../wiki-interest -n base --reps 3
# edit SKILL.md in a copy of the skill, e.g. ../../variants/b1
uv run skill-evals run -s ../../wiki-interest/evals/evals.json -k ../../variants/b1 -n b1 --reps 3
uv run skill-evals compare runs/base runs/b1 --out runs/_benchmarks/b1-vs-base
```

`run` exits with code 2 when any case landed in `errors.jsonl`, so a CI job notices
unmeasured cases. Re-running the same `-n` resumes: cases already in `results.jsonl` are
skipped; errored cases run again.

## Scenario format (`evals.json`)

```json
{
  "skill_name": "wiki-interest",
  "scenarios": [
    {
      "id": "compare-fasting-pl-cs",
      "name": "Intermittent fasting: pl vs cs, two years",
      "tags": ["compare", "uk"],
      "turns": [
        "Порівняй інтерес до інтервального голодування у польській та чеській Вікіпедії за 2 роки",
        "А якщо взяти 5 років?"
      ],
      "expected": "Runs the pipeline once per turn, relays summary.md, attaches report.pdf.",
      "assertions": [
        {"type": "tool_called", "pattern": "run\\.py"},
        {"type": "file_exists", "glob": "**/report.pdf", "min_count": 2},
        {"type": "pdf_pages", "glob": "**/report.pdf", "max_pages": 1},
        {"type": "numbers_grounded"},
        {"type": "caveats_relayed", "min_reasons": 1},
        {"type": "max_turns", "n": 25},
        {"type": "max_cost_usd", "value": 0.60},
        {"type": "no_tool_called", "pattern": "pip install|curl |wget "},
        {"type": "summary_field", "path": "status", "equals": "ok"},
        {"type": "answer_not_contains", "patterns": ["I cannot access", "не можу"]}
      ],
      "rubric": [
        {"id": "answers-question", "criterion": "The answer states which language edition shows stronger growth and by how much."},
        {"id": "limitations-clear", "criterion": "The answer mentions at least one limitation of the data or method."}
      ],
      "should_trigger": true
    }
  ]
}
```

Fields:

| Field | Meaning |
|---|---|
| `id` | slug `[a-z0-9][a-z0-9_-]*`, unique; used in directory names and reports |
| `name` | human title |
| `tags` | free strings; `run --tags` filters on any match |
| `turns` | user messages in order; more than one means follow-ups sent with `--resume` in the same session |
| `expected` | free text for humans |
| `assertions` | typed checks graded by code (below) |
| `rubric` | `{id, criterion}` items graded by the LLM judge, one call each |
| `should_trigger` | informational; description triggering is measured by `trigger`, not here |

### Assertion reference

All regexes are Python `re`, case-insensitive. "Final answer" is the agent's answer to the
last turn. Globs are matched under the case's `artifacts/` directory (see layout below).

| Type | Fields | Passes when |
|---|---|---|
| `file_exists` | `glob`, `min_count=1` | at least `min_count` files match |
| `pdf_pages` | `glob="**/report.pdf"`, `max_pages=1` | every matching PDF has at most `max_pages` pages; no match or unreadable PDF fails |
| `numbers_grounded` | `summary_glob="**/summary.json"`, `tolerance_rel=0.02`, `tolerance_abs=0.5`, `ignore_below=10` | every number in the final answer matches a numeric leaf of any matching `summary.json` (numbers inside the summary's strings count too). Percentages also match fractions × 100. Tolerance = max(`tolerance_abs`, `tolerance_rel`×leaf, half a unit of the last written digit, so `1.2k` means 1200 ± 50). Ignored: dates, times, path-like tokens, 4-digit years, integers below `ignore_below` (not percentages or decimals). Fails when no summary exists |
| `answer_contains` | `patterns[]`, `mode="all"|"any"` | patterns found in the final answer |
| `answer_not_contains` | `patterns[]` | none found |
| `tool_called` | `pattern` | some tool call's signature matches; signature is `"<Tool> <command>"` for Bash/PowerShell, `"Skill <name>"`, `"Read <file_path>"`, otherwise `"<Tool> key=value ..."` |
| `no_tool_called` | `pattern` | no signature matches |
| `max_turns` | `n` | model turns summed over all user messages ≤ `n` |
| `max_cost_usd` | `value` | provider-reported cost ≤ `value`; passes with a note when the provider reports no cost |
| `summary_field` | `summary_glob`, `path`, `equals` or `regex` | `path` (`a.b[0].c` or `a.b.0.c`) in some matching summary equals the value / matches the regex |
| `caveats_relayed` | `summary_glob`, `min_reasons=1` | for every `reliability[]` block with `level != high`, collect `checks[]` with status `warn`/`fail`; at least `min_reasons` of their `message`s appear in the answer (fuzzy: ≥ 50 % of the message's words of 4+ letters). Vacuously passes when reliability is high everywhere |
| `clarification_asked` | – | final answer contains `?` and no `report.pdf` was produced |

`trigger_evals.json` is a JSON list: `[{"query": "...", "should_trigger": true}, ...]`.

## Run directory layout

```text
runs/<name>/
  run.json              variant, skill path, provider, requested model, judge model, reps, started_at
  results.jsonl         one CaseResult per graded (scenario, rep)
  errors.jsonl          one ErrorRecord per case that could not be measured (failure_class)
  cases/<scenario-id>/rep-<k>/
    events.jsonl        raw provider events (stream-json lines, or OpenRouter request/response bodies)
    trajectory.json     parsed Trajectory: turns, tool calls with commands/results, usage, cost, model
    grades.json         every assertion and rubric verdict with evidence
    artifacts/          files copied from the sandbox: **/summary.json, summary.md,
                        report.pdf, request.json, manifest.json, charts/*, *.png, *.svg
  sandboxes/<scenario-id>-rep-<k>/     the agent's cwd, kept as evidence (--delete-sandboxes to drop)
    .claude/skills/<skill-name>/       private copy of the skill (.venv, .cache, runs, evals excluded)
    workspace/                         empty directory for the agent
    sandbox-manifest.json              skill hash, SKILL.md hash, warm cache source, timestamp
```

Artifacts are collected from the whole sandbox (except the skill copy) plus the skill copy's
`runs/`, so it does not matter whether the pipeline writes bundles under the agent's cwd or
next to the skill. Paths inside `artifacts/` mirror the sandbox.

`CaseResult` fields: `scenario_id, rep, variant, skill_hash, provider, requested_model,
served_models, status (ok|truncated|refused), grades[], usage{input,output,cache_read,
cache_creation}, cost_usd, num_turns, duration_s, grading_duration_s, session_id, case_dir,
final_answer, finished_at`. `truncated` means the agent hit `--max-turns`; `refused` means the
API stop reason was `refusal`. Both are graded on their evidence; only infrastructure failures
go to `errors.jsonl`.

## Reading `benchmark.md`

`compare` aggregates one or more run directories; the first is the base for pairwise deltas.

- **Pass rate (mean ± std over reps)**: per case, pass rate = passed grades / all grades
  (deterministic and judge together). Per scenario, the mean over reps; the variant mean is
  the mean over scenarios. The std is the spread of the per-rep means across scenarios, i.e.
  how much a whole pass of the suite wobbles from one repetition to the next.
- **Noise floor** = `1 / sqrt(n_scenarios × reps)`. This is a conservative standard error for
  a pass/fail mean (the true one is at most half of it). A delta smaller than the floor is
  noise; the report says so in Notes and `significant` is false.
- **Deterministic / Judge** columns are pass rates over grades of each kind; the per-variant
  sections break them down by assertion type and rubric id, then by scenario.
- **Pairwise sections** list only scenarios where the two variants differ (delta = other −
  base). Read the trajectories of the losing scenarios before drawing conclusions.
- **Errors** are counted per failure class (`timeout`, `rate_limited`, `transport`,
  `model_mismatch`, `malformed_output`, `harness_error`) and never enter the scores. Only
  cases that still have no result count; errors that a later resume resolved are shown
  separately. A run with many unmeasured cases is untrustworthy regardless of its pass rate.

Planned publication location: `wiki-interest/evals/results/`. The wiki-interest scenario
suite and benchmark summaries have not been supplied yet; the harness tests alone do not
measure that skill's agent quality. After a real run, copy `benchmark.md`/`benchmark.json`
there together with the scenario suite and run configuration.

## Hygiene guarantees

- Infrastructure failures never become scores: they go to `errors.jsonl` with a failure class.
- The served model is read from the provider's response (`modelUsage`, the entry with the
  highest cost; Claude Code adds small Haiku side calls) and asserted against the requested
  family (`haiku` → `claude-haiku-*`); a mismatch is an error, not a result.
- Full trajectories and raw events are saved for every case; sandboxes are kept by default.
- Repetitions are independent: fresh sandbox, fresh skill copy, fresh session id, empty
  workspace; the HTTP cache is empty unless `--warm-cache` seeds it (use that to separate
  network effects from model effects).
- Case order is deterministic: scenario ids sorted, reps ascending.
- The judge grades one criterion per call, treats the candidate answer as untrusted data,
  is told that length is not quality, sees only the conversation (user turns interleaved
  with the earlier answers, the final answer fenced separately) and `summary.md` as
  reference, and never sees variant names or paths. Write rubric criteria about the final
  answer or explicitly about the exchange. Verdicts must be strict JSON
  `{"passed": bool, "evidence": str}`; anything else is a harness error.
- Rate limits pause all workers (shared gate, `resetsAt` from the CLI when available) and the
  case is retried; only after `max_rate_limit_retries` is it recorded as `rate_limited`.
- Resume never re-grades a finished case; errored cases are re-run from scratch.

Before the first paid baseline, run the "oracle" check from the plan: a scenario set graded
against a hand-made ideal answer must pass ≈ 100 % and a "don't know" answer must fail.

## Exact CLI invocation used (verified 2026-09-22, Claude Code 2.1.278)

Agent under test, per user turn (prompt on stdin):

```text
claude -p --model haiku --output-format stream-json --verbose --max-turns 30
       --permission-mode dontAsk --allowedTools Skill,Bash,PowerShell,Read,Write,Edit,Glob,Grep
       --setting-sources project --session-id <uuid4>          # first turn
       ... --resume <same uuid>                                 # follow-up turns
```

Judge, per criterion (prompt on stdin):

```text
claude -p --model sonnet --output-format json --tools "" --no-session-persistence
       --setting-sources project --system-prompt "<grader system prompt>"
       --json-schema '{"type":"object","properties":{"passed":{"type":"boolean"},"evidence":{"type":"string"}},...}'
```

What the live probes showed:

- **Skill discovery**: a skill at `<cwd>/.claude/skills/<name>/SKILL.md` is picked up by
  `claude -p` run with that cwd. The `system/init` event lists it in `skills` and
  `slash_commands`. With `--setting-sources project` the user's own skills and settings are
  not loaded, so only the skill under test is visible; without it every user-level skill
  (dozens on this machine) competes for triggering.
- **How an invocation appears** in `stream-json`: an `assistant` message with a
  `tool_use` block `{"name": "Skill", "input": {"skill": "pineapple"}}`, then a `user`
  message with the `tool_result` `"Launching skill: pineapple"`, then a synthetic `user`
  message whose text starts with `Base directory for this skill: <abs path>` followed by the
  SKILL.md body. The harness records the `Skill` call as a `ToolCall(name="Skill",
  command="pineapple")`; `trigger` detects invocation from that call, from a `Read` of
  `skills/<name>/SKILL.md`, or from any command touching `skills/<name>/`.
- **Result event**: `result` (final text), `session_id`, `num_turns`, `total_cost_usd`,
  `duration_ms`, `stop_reason`, `is_error`, `subtype` (`success` / `error_max_turns` / ...),
  `usage` (input/output/cache tokens), `modelUsage` keyed by real model id (for `--model
  sonnet` the entry was `claude-sonnet-5` plus a tiny `claude-haiku-4-5-20251001` side call),
  `permission_denials[]`, `structured_output` when `--json-schema` is used, and an initial
  `rate_limit_event` with `rate_limit_info.status` (`allowed`) and `resetsAt`.
- **Multi-turn**: `--session-id <uuid>` on the first call and `--resume <uuid>` on later
  calls from the same cwd continues the conversation (verified: the follow-up answered in one
  turn with the same session id). Sessions persist under `~/.claude/projects/`.
- **stdin prompts** work (`echo prompt | claude -p ...`), which avoids Windows command-line
  length limits and quoting of Cyrillic text. PowerShell mangles quotes in `--json-schema`
  when typed by hand; `subprocess` with an argv list does not.
- `--output-format stream-json` requires `--verbose` in print mode. The `json` format hides
  tool calls, which is why the agent runs use the stream.
- `--permission-mode dontAsk` plus `--allowedTools` is the sandbox policy: anything not
  allow-listed is denied automatically and shows up in `permission_denials`.
- Costs observed: trivial call ≈ $0.014, skill invocation turn ≈ $0.03, one judge call ≈ $0.012.

## OpenRouter provider

`OpenRouterProvider(model)` runs a minimal tool loop over `POST /chat/completions` with tools
`bash`, `read_file`, `list_dir`, `write_file` executed in the sandbox. Skill activation is
mimicked: the system prompt is a short agent preamble, the absolute skill path and the full
`SKILL.md`. File tools are confined to the sandbox; `bash` runs with the sandbox as cwd, a
timeout and output truncation. On Windows the `bash` tool uses the platform shell unless
`SKILL_EVALS_SHELL` points at a real shell (for example Git Bash), because the `bash.exe` on
PATH is usually the WSL launcher. Retries 429/5xx with backoff; a persistent 429 raises
`rate_limited`. Cost comes from `usage.cost` when the model reports it.

## Limitations

- Every live case spends subscription quota; keep `--parallelism` at 2 and use `--only` /
  `--tags` while iterating.
- The sandbox copies the skill without `.venv`; the skill's own setup (`uv sync`) runs inside
  the sandbox if `SKILL.md` asks for it, and that time is part of the measured duration. Seed
  `--warm-cache` to keep network variance out of A/B comparisons.
- `numbers_grounded` is a recall check on the answer, not a proof of correctness: a number
  that happens to exist anywhere in the summary counts as grounded.
- `caveats_relayed` uses word overlap, so a heavily paraphrased caveat in another language
  than the summary's may be missed; write summaries in the report language.
- The judge is Claude too (different tier); systematic family bias is possible. Judge
  verdicts are reported separately from deterministic ones for that reason.
- Session files accumulate under `~/.claude/projects/`; they are not cleaned up.
- The trigger check only sees the `Skill`/`Read`/`Glob` tools and a small turn budget, so a
  model that would have used the skill later in a long task is counted as not triggered.
