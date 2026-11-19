---
title: "Two months of Argus on real pull requests"
date: 2026-11-18
draft: true
tags: ["agents", "code-review", "claude-agent-sdk", "evals", "observability"]
summary: "A code reviewer is only useful if you can trust what it posts. Argus chases precision two ways: agents that argue before anything is posted, and a record of what happens to every finding afterward. Two months in, one of those is working better than the other."
ShowToc: true
ShowReadingTime: true
---

In September I wrote that I couldn't tell you Argus's false-positive rate, only that I kept merging what it flagged.
Now I can measure it two ways, and the two don't agree.

Argus is my code reviewer.
In the week ending November 16, 2026, it posted 145 review comments on one repository, the one where my coding agents work several at a time.
They write code faster than I can read it, so the first reviewer has to be an agent too.

[HAMSE: why you built Argus, in a line or two. What was review like before it, and what made an agent reviewer necessary?]

That only works if I can trust what it posts.
A noisy reviewer gets skimmed, then ignored, and the one finding that mattered gets ignored with the rest.
So precision is the design goal.

Argus goes after it two ways.
Its agents argue with each other before anything is posted.
And it keeps a record of what happens to every finding afterward.
Two months in, one of those is working better than the other.

## Agents that argue

Argus is built on the Claude Agent SDK, in Python.
A lead agent splits a diff across six specialists: correctness, security, tests, maintainability, design, and conventions.
Each has a narrow prompt that says what counts, what never counts, and how to look.

![How an Argus review runs. A pull request goes to a lead agent, which delegates to six specialists in one turn: correctness, security, tests, maintainability, design, and conventions. Each finding is recorded through a tool, triaged by the lead, curated by code, verified in a fresh query, and passed through a post rule in code before it lands as an inline review comment.](/images/posts/argus-on-real-pull-requests/review-pipeline.svg)

The agents never hand each other prose.
A specialist records a finding by calling a tool, and the tool checks it against the repository: the file must exist, and the line must be in it.
The lead then triages by id.
It names the findings to drop, and it never retypes one.

The tools are read-only.
The agents get read, search, and two small custom tools served by an in-process MCP server.
Anything that writes is removed from the tool set and denied again by a hook, so text injected into a diff has nothing to act with.

Then comes the argument.
Every finding goes to a verifier in a fresh query, with the whole file in front of it and the repository to search.
Its only job is to prove the finding wrong.
It is never told how confident the reporter was.
A finding is posted only if the verifier confirms it at 0.6 or above, and a rejected one stays visible with the verifier's reason.

I chose refutation over a confidence score for one reason.
A confidence score asks the author to grade its own work.
A refuter starts cold, has the opposite job, and has to quote the lines that settle it.
The threshold still exists, but it applies to the skeptic's confidence, not the author's.

## Two evals, two questions

The first question is whether it catches bugs.
A corpus answers that: 32 small repositories with known answers.
22 hold a seeded bug, 6 are clean changes that should draw nothing, and 4 are traps, correct code that looks like a classic defect.
On the run of November 2, 2026, Argus caught 21 of the 22.
A subset of that corpus gates every pull request that touches the reviewer.

The second question is whether what it posts is worth reading.
No corpus can answer that.
Real pull requests can.

Every finding Argus posts can be read back.
A thumbs-up, a resolved thread, or a later commit that changed the flagged lines counts as acted on.
More thumbs-down than thumbs-up counts as a false positive.

| Repository and window | Posted | Acted on | Marked false positive |
|---|---|---|---|
| Argus itself, 30 days ending November 2, 2026 | 55 | 46 | 0 |
| Bosun, 7 days ending November 16, 2026 | 145 | 99 | 2 |

Acted on is not the same as right.
Fixer agents handle the routine findings, and I fix every medium and above myself.
An agent told to fix something will usually fix it, so the acted-on count flatters the low-severity rows.
The last column is the harder signal, and it only counts findings someone stopped to mark.

The corpus measures recall against known answers.
The feedback measures trust in use.
I need both, because neither one can stand in for the other.

Neither number matters unless it changes the reviewer.
Closing that loop takes three kinds of visibility.

![The feedback loop around Argus. A review posts findings. Reactions, resolved threads, and later commits are read back into a weekly feedback report. A real finding can become an eval case. The eval gates every change to the reviewer, and prompt and code changes flow back into the next review.](/images/posts/argus-on-real-pull-requests/feedback-loop.svg)

**Traces.**
Every review is one OpenTelemetry trace: the run, each verification, and under them every model turn and tool call, with tokens.
Each review also records what shaped it: the models, the caps, and a digest of the prompts.
Two reviews can be told apart by what they ran.

**Feedback.**
A weekly job reads the reactions back for each repository Argus reviews.
It reports acted-on and false-positive rates by specialist and by severity.

**Evals that score each agent.**
The eval does not stop at a pipeline number.
It scores every specialist on what it recorded, the lead on what it dropped, and the verifier on its own verdicts.
That is what retired the first design's catch-all "quality" specialist.
On the run of October 24, 2026, none of its 5 reported findings was real.
Four narrow specialists replaced it.

The loop closes when a real finding becomes a test.
A script snapshots a pull request at the commit a finding was posted on and drafts the expected answer.
I check its lines by hand before it joins the corpus, because a wrong expectation does more harm than a small corpus.

## What it caught

**A forged review could have silenced it.**
Argus learned to skip findings it had already posted.
To do that, it trusted an earlier review if the author was a bot and the body began with its marker.
GitHub reports every app as a bot.
On October 2, 2026, reviewing its own change, Argus flagged it as high severity:

> Any bot already installed on the repository that can post a review or review comment can forge a body starting with `<!-- argus:review -->` [...] and the pipeline will mark matching new findings `known`, skip verification, hide them from the report, and not gate on them.

The fix checks the one identity Argus posts as.
An agent that reads another agent's output needs to know who wrote it.

**A sandbox that matched text.**
The hook that keeps reviewers inside the repository checked the text of a search pattern for `..` and `.git`.
Argus pointed out that a wildcard such as `.gi?` names the same directory without containing the string, and that a symlink inside the repository walks out of it.
The hook now scans for links that lead out, and refuses any pattern that could name `.git`.
A guardrail that inspects what the model typed is weaker than one that inspects what the call can reach.

[HAMSE: had you read these two diffs yourself before Argus flagged them? One honest line, or cut this.]

**A grounding check that a pair of quotes defeats.**
My health agent has a tool that answers from my documents or refuses.
The code detected a refusal with exact string equality.
From [the public review](https://github.com/hamseabd/apex-agent/pull/1#pullrequestreview-5191356443):

> That is the exact failure mode the feature exists to prevent, and the unit tests only cover the byte-identical case.

If the model wraps its refusal in quotes, the check misses it, and the answer goes out stamped "from your documents".
Comparing model output with `==` is a bug waiting for a paraphrase.

[HAMSE: a review that surprised you. Which finding did you not expect it to catch, or which one was it confidently wrong about, and what did you do?]

## The gap

Catching 21 of 22 is the flattering number.
Here is the other one from the same run: half of what Argus reported matched no seeded bug.

The verifier is why.
It checked 21 findings that matched no seeded bug.
It confirmed all 21 and rejected none.
Its mean confidence was 0.93 on the real bugs and 0.80 on the others, so the 0.6 threshold filtered nothing.
The lead's triage and the curation rules removed 12 false findings before verification.
The verifier, the agent whose whole job is to say no, removed none.

The number needs three qualifiers.
The scorer counts anything that does not match a seeded bug as false, including a valid point about code I planted nothing in.
A third of the 21 come from one case, a snapshot of a real pull request with a single labeled bug.
And it is one run.

The two evals also disagree.
Across the two windows above, 2 of 200 posted findings were marked false.
On the corpus, half were.
Either the corpus is too strict about what counts, or readers are too generous.

I'm going through the 21 one at a time to see why the verifier confirmed each.
Then I clean up and tune the prompts, and run the corpus again.

[HAMSE: which way is it off? You said "a little too strict right now". On the November 2 run the verifier is the opposite: it confirmed 21 of 21 and rejected 0, and its prompt hasn't changed since. The scorer may be the strict part. Your read, in your words, and the two paragraphs above follow it.]

## What I learned

**Score each agent, not only the pipeline.**
End to end, the numbers looked like a working system. Only the verifier's own scorecard showed it had rejected nothing.

**Keep two evals, and read the disagreement.**
A corpus has known answers and no readers, and real pull requests have readers and no known answers. Where the two differ is where the next week of work is.

**A fresh context doesn't make a skeptic.**
It stops the verifier from anchoring on the reporter. It doesn't make the verifier hard to convince, and that has to be built and measured on its own.

**Put the policy in code.**
The read-only tools, the caps on noise, and the posting rule are enforced by the harness. The model is told the rules, and the code is what holds them.

Argus is open source at [github.com/hamseabd/argus](https://github.com/hamseabd/argus), and [the first write-up]({{< ref "argus-code-review-agent" >}}) covers the original design.

If you are building agents that have to earn trust inside a real engineering workflow, I would like to compare notes.
[GitHub](https://github.com/hamseabd) / [LinkedIn](https://www.linkedin.com/in/hamseabdi/).
