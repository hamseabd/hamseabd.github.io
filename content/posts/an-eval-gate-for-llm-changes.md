---
title: "An eval gate for LLM changes"
date: 2026-11-18
draft: true
tags: ["evals", "llm-as-judge", "agents", "production"]
summary: "A prompt or model change is a code change, so it ships through a gate that can say no. The parts: deterministic checks for what must never happen, a golden set labeled by domain experts, and a judge from a different model family watching production."
ShowToc: true
ShowReadingTime: true
---

A model upgrade was ready to ship.
The eval gate said no.

[CONFIRM: what the regression was, as a pattern with no internal specifics. Your resume says only that a model upgrade regressed and the gate caught it before release.]

The fix was a prompt edit.
The regression was caught before release, so nobody who relies on that system ever saw it.

I built that gate for a production agent system.
The idea behind it is simple: a prompt or model change is a code change, so it ships through a gate that can say no.

## Why spot checks fail

Without a gate, a prompt change gets tested the way most of them do.
Someone runs a handful of inputs, reads the outputs, and they look fine.

That fails for three reasons.
The sample is the cases the author thought of, which are the cases the prompt already handles.
The reader is the author, who knows what the output is supposed to say.
And a spot check has no memory.
Nothing compares today's output with last week's, so a case that quietly got worse looks the same as one that was never good.

A model upgrade makes all three worse.
The diff is often one line, no logic moves, and every unit test still passes.
There is nothing to review except behavior.

## Three parts

![The three layers of an eval gate. A change to a prompt, a model, or code passes deterministic checks on every output. A subset of the golden set runs on every pull request and blocks the merge. The full golden set runs on every release and blocks the release. In production, a judge from a different model family samples live output and does not gate, and what it finds becomes new golden cases.](/images/posts/an-eval-gate-for-llm-changes/gate.svg)

**Deterministic checks, for what must never happen.**
Start with what code can decide.
The output has to match its schema.
Every claim has to carry a citation.
A value has to sit inside the range the system is allowed to produce.
These checks are cheap and never flaky, so they run on every output, in tests and in production.
Anything code can decide shouldn't go to a model.

**A golden set, labeled by domain experts.**
A golden set is a fixed list of inputs with known right answers.
The answers come from the people who do the work today, not from the model and not from me.
It measures what the system decides, which is the thing a regression changes.

**A judge from a different model family.**
Some quality has no single right answer.
For that, a model grades the output against a rubric.
The judge comes from a different family than the system it grades, because a judge from the same family tends to share its blind spots and to prefer answers that sound like its own.

## On every pull request

A subset of the golden set runs on every pull request, and all of it runs on every release.
The first is small enough to wait for.
The second is complete enough to trust.

Three rules turn that from a report into a gate.

**Compare with the baseline, case by case.**
A change passes when it holds what the last accepted run got right.
A fixed bar such as "90% or better" lets a change trade ten old cases for ten new ones and still pass.
A new catch on one case doesn't pay for a new miss on another.

**Give noise a number.**
A model's output varies between runs, so one run of a case is one sample.
Decide ahead of time how much variation is noise, write it down, and fail on anything past it.

**Keep the gate out of the change's reach.**
The cases, the scorer, the baseline, and the thresholds come from the default branch, not from the pull request.
Otherwise a change can loosen the gate it has to pass.
And the gate fails closed: a case that errors is a failure, not a skip.

My code reviewer, [Argus](https://github.com/hamseabd/argus), gates its own pull requests this way, and its [whole policy](https://github.com/hamseabd/argus/blob/main/evals/thresholds.yaml) is public.
It runs nine cases on every change to the reviewer: one seeded bug per specialist, two clean changes that should draw nothing, and one trap.
It allows one extra miss beyond the baseline, because one is noise and two is a regression.
It allows no new finding on a clean change.

The clean cases matter as much as the bugs.
A gate that only checks what the system should catch will pass a change that makes it flag everything.

## Watching production

A gate only sees the cases someone wrote down.
Production sees everything else.

So the judge samples live output.
It doesn't block anything.
It shows when quality moves, and what it finds becomes new golden cases.
That is how the golden set keeps up with real traffic, and how a problem seen once in production becomes a test that runs on every change after it.

The deterministic checks run in production too, on every output.
The same rule that fails a test also flags a live answer.

## What I learned

**A gate has to be able to say no.**
A dashboard that shows a score dropping is information. A check that blocks the merge is a decision, made before anyone is tempted to ship anyway.

**A failing eval is a hypothesis.**
I learned this on [a side project]({{< ref "apex-evals-grading-what-it-does" >}}), where an ugly failure turned out to be a bug in my grader. The first question on any failure is whether the system is wrong or the test is.

**The baseline is the bar.**
"Is it good?" has no stable answer for a model. "Did it get worse than what we accepted last time?" does.

**Use a model to judge only what code can't.**
Every check that moves from a judge to an assertion is one less thing that can drift, and one less thing to pay for.

If you're putting evals on a production agent, I'd like to compare notes.
[GitHub](https://github.com/hamseabd) / [LinkedIn](https://www.linkedin.com/in/hamseabdi/).
