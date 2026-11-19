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
The eval gate failed it.

[CONFIRM: what broke, as a pattern with no internal specifics: what got worse, and which part of the gate caught it. Your resume says only that a model upgrade regressed and the gate caught it before release.]

A prompt edit fixed it, and the regression never reached a release.

I built that gate for a production system, and every prompt and model change has to pass it.
A prompt or model change is a code change, so it ships through a gate that can say no.

## Why spot checks fail

Most prompt changes get a spot check.
Someone runs a handful of inputs, reads the outputs, and they look fine.

The sample is the cases the author thought of, which are the cases the prompt already handles.
The reader is the author, who knows what the output is supposed to say.
And a spot check has no memory.
Nothing compares today's output with last week's, so a case that quietly got worse looks the same as one that was never good.

A model upgrade is worse.
The diff is one line and every unit test passes.
There is nothing to review except behavior, and that was the change the gate failed.

## Three parts

![The three layers of an eval gate. A change to a prompt, a model, or code passes deterministic checks on every output. A subset of the golden set runs on every pull request and blocks the merge. The full golden set runs on every release and blocks the release. In production, a judge from a different model family samples live output, and what it finds can become new golden cases.](/images/posts/an-eval-gate-for-llm-changes/gate.svg)

**Deterministic checks, for what must never happen.**
Start with what code can decide.
The output matches its schema.
A citation points at something that exists.
A value sits inside the range the system is allowed to produce.
The check never varies, so a failure belongs to the output.
These run on every output.

**A golden set, labeled by domain experts.**
A golden set is a list of inputs with right answers that subject matter experts wrote down.
A subset runs on every pull request, and all of it runs on every release.
It measures what the system decides, which is what a regression changes.

**A judge from a different model family.**
Some outputs have no single right answer, so a model grades them against a rubric.
The judge comes from a different family than the system it grades, so it doesn't favor answers that sound like its own.
It samples production output.

A different family only fixes that one bias.
A judge still has to be checked against expert labels, and I have a recent reminder of why.
In my code reviewer, the agent that checks each finding confirmed all 21 of the unmatched findings it saw on its eval run of November 2, 2026.
I only know because that agent is scored on its own.

## What makes it a gate

A score on a dashboard gets read after the release.
A failed check gets read before it.

The rules below are from [Argus](https://github.com/hamseabd/argus), my code reviewer, because its [gate policy](https://github.com/hamseabd/argus/blob/main/evals/thresholds.yaml) is public and you can read every line.

**Compare with the baseline, case by case.**
A change passes when it holds what the last accepted run got right.
A fixed bar such as "90% or better" lets a change trade ten old cases for ten new ones and still pass.

**Put a number on noise.**
A model's output varies between runs, so one run of a case is one sample.
Argus allows one extra miss across its nine pull request cases.
Its baseline is a single run, so that allowance is a judgment until I measure how much a case varies.

**Test the clean cases too.**
Two of the nine cases are clean changes, and a new finding on either one fails the gate.
A gate that only checks what the system should catch will pass a change that makes it flag everything.

**Keep the gate out of the change's reach.**
The cases, the scorer, the baseline, and the thresholds come from the default branch, not from the pull request.
Otherwise a change can loosen the gate it has to pass.
A case that errors fails.

## Watching production

A gate only sees the cases someone wrote down.
Production sees the rest.

That is the judge's job, with the deterministic checks beside it on every output.
Neither can block a release that already happened.
What they can do is find the case nobody wrote down, so an expert can label it and it can join the golden set.

## What I learned

**A failing eval is a hypothesis.**
On [a side project]({{< ref "apex-evals-grading-what-it-does" >}}) an ugly failure turned out to be a bug in my grader, so the first question on any red case is whether the system is wrong or the test is.

**The judge needs its own eval.**
A model that grades other models can agree with everything, and nothing in the pipeline's numbers will show it.

**My own gate has a blind spot.**
Argus's gate counts misses and findings on clean changes, so a change that only added noise to the buggy cases would pass.

If you're putting evals on a production system, I'd like to compare notes.
[GitHub](https://github.com/hamseabd) / [LinkedIn](https://www.linkedin.com/in/hamseabdi/).
