# skill-evals

Development harness that measures how well the `wiki-interest` skill works when driven by a
cheap agent model, and whether a change to `SKILL.md` made things better or worse.

Status: skeleton. The runner, model providers, graders and reporting are added in later phases;
the design is in [`docs/technical-plan.md`](../../docs/technical-plan.md), section 11.

What it will do:

- run each scenario from `wiki-interest/evals/evals.json` through a real agent
  (headless Claude Code on Haiku 4.5 via `claude -p`, or an OpenRouter model) in an isolated
  working directory, several repetitions each;
- grade the outputs deterministically (pipeline invoked, artifacts present, numbers in the answer
  match `summary.json`, caveats relayed) and with an LLM judge per rubric property;
- compare two skill versions pairwise and report deltas together with the noise floor;
- write summaries back to `wiki-interest/evals/results/`.

```bash
uv sync
uv run pytest
```
