---
title: "Two months of Argus on real pull requests"
date: 2026-11-18
draft: true
tags: ["agents", "code-review", "claude-agent-sdk", "evals", "observability"]
summary: "A code reviewer is only useful if you can trust what it posts. Argus goes after precision two ways: agents that argue before anything is posted, and a record of what happens to every finding afterward. The record looks good. The eval says the agent built to disagree rejected nothing."
ShowToc: true
ShowReadingTime: true
---

On October 2, 2026, Argus flagged a high-severity bug in its own code.

It had just learned to skip findings it had already posted.
To do that, it trusted an earlier review if a bot wrote it and the body began with Argus's marker.
GitHub reports every app as a bot, so any other app on the repository could have posted that marker and silenced it.

I had read that diff before Argus did.

Argus is my code reviewer.
I'm a builder. I have a ton of projects and a lot of ideas, and I can't be the builder and the reviewer.
AI was already making the building faster, so I wanted it to make the review faster too.
A reviewer agent is also blind to the builder's biases.

In the week ending November 16, 2026, Argus posted 145 review comments on one repository, the one where my coding agents work several at a time.
They write code faster than I can read it, so the first reviewer has to be an agent too.

That only works if I can trust what it posts.
A noisy code reviewer is one you learn to ignore, so precision is the design goal.
Argus goes after it two ways.
Its agents argue before anything is posted, and it keeps a record of what happens to every finding afterward.

The record looks good.
The eval says the agent I built to disagree rejected nothing.

## Agents that argue

Argus is built on the Claude Agent SDK, in Python.
A lead agent splits a diff across six specialists: correctness, security, tests, maintainability, design, and conventions.
Each has a narrow prompt that says what counts, what never counts, and how to look.
I put the emphasis on security, and every finding carries a severity level, from critical down to nit.

![How an Argus review runs. A pull request goes to a lead agent, which delegates to six specialists in one turn: correctness, security, tests, maintainability, design, and conventions. Each finding is recorded through a tool, triaged by the lead, curated by code, verified in a fresh query, and passed through a post rule in code before it lands as an inline review comment.](/images/posts/argus-on-real-pull-requests/review-pipeline.svg)

The agents never hand each other prose.
A specialist records a finding by calling a tool, and the tool checks it against the repository: the file must exist, and the line must be in it.
The lead triages by id. It names the findings to drop and never retypes one.
Code then merges duplicates and caps the nits.

The tools are read-only: read, search, and two small custom tools served by an in-process MCP server.
Anything that writes is removed from the tool set and denied again by a hook, so text injected into a diff has nothing to act with.

Every finding then goes to a verifier in a fresh query, with the whole file in front of it and the repository to search.
Its only job is to prove the finding wrong.
It is never told how confident the reporter was.
A finding is posted only if the verifier confirms it at 0.6 or above, and a rejected one stays visible with the verifier's reason.

I chose refutation over a confidence score for one reason.
A confidence score asks the reporter to grade its own work.
A refuter starts cold, has the opposite job, and has to quote the lines that settle it.

## What it caught

The forged marker was one catch.
The fix checks the one identity Argus posts as.
Here are two more.

**A sandbox that matched text.**
The hook that keeps reviewers inside the repository checked the text of a search pattern for `..` and `.git`.
Argus pointed out that a wildcard such as `.gi?` names the same directory without containing the string, and that a symlink inside the repository walks out of it.
The hook now scans for links that lead out, and refuses any pattern that could name `.git`.
I had read that diff too.

**A grounding check that a pair of quotes defeats.**
My health agent has a tool that answers from my documents or refuses.
The code detected a refusal with exact string equality.
From [the review](https://github.com/hamseabd/apex-agent/pull/1#pullrequestreview-5191356443):

> That is the exact failure mode the feature exists to prevent, and the unit tests only cover the byte-identical case.

If the model wraps its refusal in quotes, the check misses it, and the answer goes out stamped "from your documents".
Comparing model output with `==` is a bug waiting for a paraphrase.

## Two evals, two questions

In September I wrote that I couldn't tell you Argus's false-positive rate, only that I kept merging what it flagged.
Now there are two measurements.

The first asks whether it catches bugs.
A corpus answers that: 32 small repositories with known answers.
22 hold a seeded bug, 6 are clean changes that should draw nothing, and 4 are traps, correct code that looks like a classic defect.
On the run of November 2, 2026, Argus caught 21 of the 22, and one of the six clean changes drew a finding.
Nine of those cases run on every pull request that touches the reviewer, and more than one new miss against the last accepted run fails the check.

The second asks whether what it posts is worth reading.
Real pull requests answer that, roughly.
Every finding Argus posts can be read back.
A thumbs-up, a resolved thread, or a later commit that changed the flagged lines counts as acted on.
More thumbs-down than thumbs-up counts as a false positive.

| Window | Posted | Acted on | Marked false |
|---|---|---|---|
| Argus, 30 days to Nov 2, 2026 | 55 | 46 | 0 |
| Bosun, 7 days to Nov 16, 2026 | 145 | 99 | 2 |

Acted on is not the same as right.
Fixer agents handle the routine findings, and I fix every medium and above myself.
An agent told to fix something will usually fix it, so the acted-on count flatters the low-severity rows.
The last column is false positives, and it only counts findings someone stopped to mark.

Neither number matters unless it changes the reviewer.
When the reviewer gets better, the code gets better over time.

![The feedback loop around Argus. A review posts findings. Reactions, resolved threads, and later commits are read back into a weekly feedback report. A real finding can become an eval case. The eval gates every change to the reviewer, and prompt and code changes flow back into the next review.](/images/posts/argus-on-real-pull-requests/feedback-loop.svg)

**Feedback.**
A weekly job reads the reactions back for each repository Argus reviews, and reports acted-on and false-positive rates by specialist and by severity.

**Evals that score each agent.**
The eval scores every specialist on what it recorded, the lead on what it dropped, and the verifier on its own verdicts.
That is what retired the first design's catch-all "quality" specialist.
On the run of October 24, 2026, none of its 5 reported findings matched a real bug.

**Real findings become tests.**
A script snapshots a pull request at the commit a finding was posted on and drafts the expected answer.
One finding from October is a corpus case now.
I check each case's lines by hand first, because a wrong expectation does more harm than a small corpus.

**Traces.**
Every review is one trace in LangSmith: a span for each agent, and under it every model turn and tool call, with tokens and latency.
It shows which specialist spent the tokens, where the time went, and which runs failed.
That is how I observe my agents.

## The gap

I wanted the verifier to be restrictive.
The eval says it isn't restrictive enough yet.

On the run of November 2, 2026, half of what Argus reported matched no seeded bug.
The verifier checked 21 of those findings.
It confirmed all 21 and rejected none.
Its mean confidence was 0.93 on the real bugs and 0.80 on the others, so the 0.6 threshold filtered nothing.
Triage and curation removed 12 false findings before verification.
The verifier, the agent whose whole job is to say no, removed none.

That number is soft.
The scorer counts anything that doesn't match a seeded bug as false, including a valid point about code I planted nothing in.
A third of the 21 come from one case, a snapshot of a real pull request with a single labeled bug.
And it is one run.
I've written before that [a failing eval is a hypothesis, not a verdict]({{< ref "apex-evals-grading-what-it-does" >}}).
This one is still a hypothesis.

The two measurements also disagree.
Across the two windows above, 2 of 200 posted findings were marked false.
On the corpus, half were.
The readers are me and agents that fix what they're told, so 2 of 200 is a floor.

That is the gap I'm closing.
I'm going through the 21 one at a time to see why the verifier confirmed each.
Then I clean up and tune the prompts, and run the corpus again.

## What I learned

**Score each agent, not only the pipeline.**
Recall looked fine end to end, and only the verifier's own scorecard showed it had rejected nothing.

**Keep two evals, and read the disagreement.**
A corpus has known answers and no readers, and real pull requests have readers and no known answers.

**A fresh context doesn't make a skeptic.**
It stops the verifier from anchoring on the reporter, and it does nothing to make the verifier hard to convince.

Code: [github.com/hamseabd/argus](https://github.com/hamseabd/argus). [The first write-up]({{< ref "argus-code-review-agent" >}}) covers the original design.

If you're building agents that have to earn trust inside a real engineering workflow, I'd like to compare notes.
[GitHub](https://github.com/hamseabd) / [LinkedIn](https://www.linkedin.com/in/hamseabdi/).
