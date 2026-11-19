---
title: "An eval gate for LLM changes"
date: 2026-11-18
draft: true
tags: ["evals", "llm-as-judge", "agents", "production"]
summary: "A prompt edit or a model upgrade is a code change. It should pass a gate before it ships. The pattern: deterministic checks on every output, a golden set on every change, and a judge from a different model family on production samples."
ShowToc: true
ShowReadingTime: true
---

A prompt edit is a code change.
So is a model upgrade.
Both can break behavior that no unit test covers.

The fix is a gate that every prompt and model change has to pass before it ships.
I built one for a production agent system.
This post is the pattern, not the system.

## Three layers

Each layer catches a different kind of failure.
None of them is enough alone.

| Layer | Runs on | Catches |
|---|---|---|
| Deterministic checks | every output | broken structure, missing fields, rules the output must never break |
| Golden set | every change | regressions in what the system decides |
| Cross-family judge | samples of production output | quality drift the golden set does not cover |

## Deterministic checks

Start with what code can check.
Is the output valid against its schema?
Does every claim carry a citation?
Is a value inside the range the system is allowed to produce?

These checks are cheap, fast, and never flaky.
They run on every output, in tests and in production.
Anything a rule can decide should not go to a model.

## The golden set

A golden set is a fixed list of inputs with known right answers.
The answers come from the people who do the work today, not from the model.
Domain experts label them.

The gate runs a subset on every pull request and the full set on every release.
The pull request run is fast enough to wait for.
The release run is complete enough to trust.

A change passes when it holds the baseline.
It fails when it gets cases wrong that the baseline got right.

Keep the gate out of reach of the change it judges.
The cases, the scorer, the baseline, and the thresholds should come from the default branch, not from the pull request.
Otherwise a change can loosen the gate it has to pass.
My code reviewer, [Argus](https://github.com/hamseabd/argus), gates its own pull requests this way.

## A judge from a different family

Some quality has no right answer to compare against.
For that, a model grades the output against a rubric.

The judge comes from a different model family than the system it grades.
A judge from the same family tends to share the same blind spots, and to prefer outputs that sound like its own.

The judge samples production output.
It does not gate a pull request.
It tells you when quality moves, so you can turn what it finds into new golden cases.

## The regression it caught

A model upgrade looked like a free improvement.
The gate said otherwise.
It caught a regression before the release.

[CONFIRM: what the regression was, described as a pattern with no internal specifics, if you want to say it.]

The fix was a prompt edit.
No code changed.

That is the case for the gate.
Without it, the upgrade ships, and the regression is found by the people who rely on the output.

## What I would tell a team starting out

- Write the deterministic checks first. They are the cheapest and they never lie.
- Build the golden set from real cases, labeled by the people who know the right answer.
- Run a subset on every change and all of it on every release.
- Take the gate's inputs from the default branch.
- Use a judge from another model family, on samples, to find what the golden set misses.

If you are putting evals on a production agent, I would like to compare notes.
[GitHub](https://github.com/hamseabd) / [LinkedIn](https://www.linkedin.com/in/hamseabdi/).
