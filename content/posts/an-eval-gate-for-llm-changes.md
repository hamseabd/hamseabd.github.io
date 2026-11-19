---
title: "An eval gate for LLM changes"
date: 2026-11-18
draft: true
tags: ["evals", "llm-as-judge", "agents", "production"]
summary: "A prompt edit or a model upgrade is a code change, and it should pass a gate before it ships. The pattern: deterministic checks on every output, a golden set on every change, and a judge from a different model family on production samples."
ShowToc: true
ShowReadingTime: true
---

A model upgrade is the easiest change to approve.
The diff is one line.
No logic moves, and every unit test still passes.

I built the eval gate for a production agent system, and it caught one of those before release.
The upgrade had regressed the system's behavior.
The fix was a prompt edit.

A prompt edit is a code change.
So is a model upgrade.
Both can break behavior that no unit test covers, so both should pass a gate before they ship.
This post is the pattern, not the system.

## The shape

```
 a change: prompt, model, or code
      |
      v
 deterministic checks ..... every output, in tests and in production
      |
      v
 golden set, a subset ..... every pull request -> blocks the merge
      |
      v
 golden set, all of it .... every release      -> blocks the release
      |
      v
 production
      |
      v
 cross-family judge ....... sampled live output -> new golden cases
```

Three layers.
Each catches a different kind of failure, and none of them is enough alone.

| Layer | Runs on | Catches |
|---|---|---|
| Deterministic checks | every output | broken structure, missing fields, rules the output must never break |
| Golden set | every change | regressions in what the system decides |
| Cross-family judge | samples of production output | quality drift the golden set does not cover |

## Deterministic checks

Start with what code can check.

- Is the output valid against its schema?
- Does every claim carry a citation?
- Is each value inside the range the system is allowed to produce?

These checks are cheap, fast, and never flaky.
They run on every output, in tests and in production.

The rule: anything code can decide should not go to a model.
Every check moved from a judge to an assertion is one less thing that can drift.

## The golden set

A golden set is a fixed list of inputs with known right answers.
The answers come from the people who do the work today, not from the model.
Domain experts label them.

The gate runs a subset on every pull request and the full set on every release.
The pull request run is small enough to wait for.
The release run is complete enough to trust.

In the system I built, every pull request runs 100 cases and every release runs all of them, more than 1,000.
[CONFIRM: these sizes are from your resume. Keep them, or cut the sentence if they are too specific for a pattern post.]

Three rules make the golden set a gate and not a dashboard.

**Compare with a baseline, not with a target.**
A change passes when it holds the baseline.
It fails when it gets cases wrong that the baseline got right.
An absolute bar such as "90% or better" lets a change trade ten old cases for ten new ones and still pass.

**Count case by case.**
A new catch on one case does not offset a new miss on another.
The misses are what users feel.

**Give noise a number.**
A model's output varies between runs, so one review of a case is one sample.
Decide ahead of time how much variation is noise, write it down, and fail on anything past it.

## Keep the gate out of reach

The gate must not be editable by the change it judges.

The cases, the scorer, the baseline, and the thresholds should come from the default branch, not from the pull request.
Otherwise a change can loosen the gate it has to pass.

The gate should also fail closed.
A case that errors is a failure, not a skip.
A result the gate cannot read is a failure too.

My code reviewer, [Argus](https://github.com/hamseabd/argus), gates its own pull requests this way, and its thresholds are public.
The [whole policy](https://github.com/hamseabd/argus/blob/main/evals/thresholds.yaml) is three settings:

- a fixed smoke subset: one seeded bug per specialist, two clean controls, and one trap,
- at most one extra miss beyond the baseline, because one is noise and two is a regression,
- no new finding on a clean control.

Clean controls matter as much as the bugs.
A gate that only checks what the system should catch will pass a change that makes it flag everything.

## A judge from a different family

Some quality has no right answer to compare against.
For that, a model grades the output against a rubric.

The judge comes from a different model family than the system it grades.
A judge from the same family tends to share the same blind spots, and to prefer outputs that sound like its own.

The judge samples production output.
It does not gate a pull request.
It tells you when quality moves, and what it finds becomes new golden cases.
That is how the golden set keeps up with real traffic.

## The regression it caught

A model upgrade caused a regression.
The gate caught it before release.

[CONFIRM: what the regression was, described as a pattern with no internal specifics, if you want to say it.]

The fix was a prompt edit.

That is the case for the gate.
Without it, the upgrade ships, and the regression is found by the people who rely on the output.

## Where to start

1. Write the deterministic checks first. They are the cheapest, and they never lie.
2. Build the golden set from real cases, labeled by the people who know the right answer.
3. Run a subset on every change and all of it on every release.
4. Compare with a baseline, case by case, with a stated tolerance for noise.
5. Take the gate's inputs from the default branch, and fail closed.
6. Use a judge from another model family, on samples, to find what the golden set misses.

If you are putting evals on a production agent, I would like to compare notes.
[GitHub](https://github.com/hamseabd) / [LinkedIn](https://www.linkedin.com/in/hamseabdi/).
