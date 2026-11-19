---
title: "Two months of Argus on real pull requests"
date: 2026-11-18
draft: true
tags: ["agents", "code-review", "claude-agent-sdk", "evals", "harness-engineering"]
summary: "Argus is my multi-agent code reviewer. Since the first write-up it grew from three specialists to six, got an eval corpus and a gate, and reviewed real pull requests across my repositories. It found holes in its own guardrails. Here is what it found, and what the evals say."
ShowToc: true
ShowReadingTime: true
---

The script that publishes Argus has one job it cannot get wrong.
It copies the private development repository to the public one, and before it pushes it scans the tree for the names of my other private repositories.

Argus reviewed the pull request that added that script.
Its top finding, HIGH at confidence 0.90: the guard fails open.
If `gh` is logged out, rate limited, or missing, the list of names comes back empty, the check is skipped, and the tree is pushed anyway.

The fix landed on the same pull request.
The script now stops when the list of names may be incomplete, and the third review of that branch reported no correctness defects in it.

That is the kind of finding I built Argus for.
This post is what two months of them look like, including the numbers that are not flattering.

## What Argus is

Argus is a code reviewer built on the Claude Agent SDK, in Python.
A lead agent hands a diff to specialist subagents, a separate verifier tries to refute each finding, and what survives lands on the pull request as inline comments.
It is read-only by construction and runs on GitHub Actions on a Claude subscription token.

[The first write-up]({{< ref "argus-code-review-agent" >}}) covers why it verifies by refutation, why it indexes nothing, and how the guardrails attach to the tools.
This one covers what changed since, and what happened when it met real code.

The code is public at [github.com/hamseabd/argus](https://github.com/hamseabd/argus).
Development happens in a private repository, and the public one gets one squashed commit per release, so the pull requests I describe below are not linkable.
Where a review is public, I link it.

## What changed since September

**Six specialists, not three.**
Correctness, security, tests, maintainability, design, and conventions.
The first version had correctness, security, and a catch-all called quality.
On that design's eval run, every false positive came from quality: 0 of its 5 reported findings were real.
The current version replaces it with four narrow specialists, and each prompt says what counts, what never counts, and how to look.

**Findings are recorded through a tool, not retyped.**
Each specialist calls `report_finding`, which validates the finding against the domain model and against the repository: the file must exist and the line must be in it.
The lead then triages by id.
It names the ids to drop as duplicates, and Argus builds the review from everything it did not drop.
No finding is rewritten by another model between the specialist and the verifier.

**Noise is a policy in code.**
Duplicates are merged, nits are capped at five and dropped entirely when anything is high or critical, and a review holds at most 25 findings.
The lead is told the rules and the pipeline enforces them.

**The verifier got stricter.**
It reads the whole changed file, not only the hunk.
It answers `confirmed`, `rejected`, or `inconclusive`, with a confidence, and it is never told how confident the reporter was.
A finding is posted as confirmed only at 0.6 or above.
Rejected findings stay visible in a folded list with the verifier's reason.

**It remembers its earlier reviews.**
A re-review covers only the commits since the last one.
A finding it already posted is marked `known` and not posted again, and one I gave a thumbs-down is `dismissed`.

**The repository's own rules reach every agent.**
`REVIEW.md` and `CLAUDE.md` are read from a branch the change cannot touch, so a pull request cannot edit the rules it is reviewed under.

Every agent now runs on Opus 5.5 at high effort.

```
context   PR or local diff, the changed files, the lines GitHub will accept a comment on
review    one query: the lead delegates to six specialists in a single turn,
          each records findings with report_finding, the lead triages by id
curate    merge duplicates, cap nits, cap the review at 25 findings
verify    one query per finding, fresh context, whole file, six at a time
rank      confirmed at 0.6 or above; rejected findings folded with the reason
report    terminal, JSON artifact, GitHub review with inline comments
```

## What it found in its own guardrails

Argus reviews its own pull requests.
The findings I value most are the ones against its own safety code.

A note on which design found what.
The six specialists landed on October 24.
The four findings below are from October 2 and October 13, so the three-specialist design found them.
The release-script finding at the top of this post is from the current one.

**Any bot could have silenced it.**
The change that taught Argus to skip findings it had already posted trusted an earlier review if its author was a bot and its body started with the Argus marker.
GitHub reports every app as a bot.
Argus flagged it, HIGH at 0.75: another app installed on the repository could post a marked review and suppress real findings.
The fix checks the one login Argus posts as, taken from the app token itself.

**A nit could have swallowed a critical.**
The same change matched a new finding to an old one by line proximity alone.
A low-severity nit two lines away would have marked an unrelated critical finding as already reported.
HIGH at 0.82.
The match now also needs the same category.

**The read confinement was a denylist.**
The hook that keeps reviewers inside the repository checked the text of a glob pattern for `..` and `.git`.
Argus flagged, HIGH at 0.65, that a wildcard such as `.gi?` or a symlink inside the repository walked straight past it.
The hook now scans for links that lead out and refuses any pattern that could name `.git`.

**Incremental review would never have come back.**
A guard forced a full review while earlier findings were still open, but it derived "open" from every comment ever posted.
One finding, once posted, would have disabled incremental review on that pull request forever.
HIGH at 0.60, and the fix landed on the same pull request.
That finding is now a case in the eval corpus, snapshotted from the pull request it was posted on.

Four high-severity findings in the reviewer's own machinery, each fixed on the branch that introduced it.

## What it found in someone else's code

The reusable workflow lets my other repositories call Argus.
Some of those reviews are public, such as [apex-agent pull request 1](https://github.com/hamseabd/apex-agent/pull/1#pullrequestreview-5191356443), a grounded knowledge base for my health agent.

Nine findings, all confirmed by the verifier.
That review is from September, on the three-specialist design.
Two of them:

- The tool re-fetched the entire S3 corpus two to three times per question, and the test fake hid it, because the fake's token count did not call the loader the way the real store does.
- The refusal check was exact string equality, so a refusal with quotes around it fell through and got the "from your documents" disclaimer appended to an answer that was explicitly not from the documents.

That pull request is still open, and those findings are flagged, not fixed.

## What the numbers say

Every finding Argus posts can be read back.
`argus feedback` treats a thumbs-up, a resolved thread, or a later commit that changed the flagged lines as acted on, and more thumbs-down than thumbs-up as a false positive.

On Argus's own repository, for the 30 days ending November 2:

| Severity | Posted | Acted on | Marked false positive |
|---|---|---|---|
| high | 5 | 5 | 0 |
| medium | 18 | 16 | 0 |
| low | 26 | 21 | 0 |
| nit | 6 | 4 | 0 |
| **all** | **55** | **46** | **0** |

By specialist the picture is less even.
Security had 10 of 11 acted on, and design had 1 of 4.
The window spans both designs: 22 of the 55 came from the old quality specialist.

[CONFIRM: across all repositories Argus reviews, the GitHub API shows 882 inline findings on 103 pull requests between September 13 and November 17, with 12 carrying a thumbs-down. That is a raw count from 2026-11-18, not `argus feedback` output. Replace it with the tool's numbers or cut it.]

Acted on is not the same as right.
Every review ends with a machine-readable block that hands its findings to a fixer agent, and an agent told to fix something will usually fix it.
[CONFIRM: how much of the acted-on count is your fixer agents versus you, and whether you want to say so.]
So I do not read 46 of 55 as precision.
For that I built an eval.

## What the evals say

The corpus is 32 small repositories with known answers: 22 seeded bugs, 6 clean controls that should draw no finding, and 4 verifier traps, correct changes that look like classic defects.
A finding matches a seeded bug when it names the same category and lands within three lines of it.

| | September design | Current |
|---|---|---|
| Corpus | 13 cases | 32 cases |
| Recall | 100% (10 of 10) | 95% (21 of 22) |
| Precision | 67% | 50% |
| Clean controls flagged | 2 of 3 | 1 of 6 |
| Verifier accuracy | 67% | 51% |
| Cost per case, at API prices | $0.25 | $0.46 |

Recall held.
Every correctness and security bug the first design caught, the current one still catches, and the new specialists caught 10 of their 11.
The miss was found, then filed under the wrong category.

Precision is the problem, and the verifier is why.
It confirmed all 21 false findings it checked and rejected none.
Its mean confidence was 0.93 on real bugs and 0.80 on false ones, and the 0.6 threshold filtered none of them.

In the first write-up I called the separate verifier the whole design.
On this corpus it is a rubber stamp.

Two things soften that, and neither excuses it.
By the scorer's rule anything that does not match a seeded bug counts as false, including a valid point about code I did not plant a bug in.
And each case is one review, one sample, so the spread between runs is unmeasured here.

The per-category numbers say where to look.
Correctness is 8 real findings to 2 false.
Design is 2 to 6, and tests and maintainability are each 3 to 5.
The specialists I added are the ones generating the noise, which matches the feedback from real pull requests, where design had the lowest acted-on rate.

## The gate

The eval is not a report I run when I am curious.
A pull request that touches the reviewer or the evals runs a nine-case smoke subset, and a gate compares it with the baseline case by case.
It fails when the run misses seeded bugs the baseline caught, beyond a tolerance of one, when a clean control gains a finding, or when a case errors.

The part I would repeat on any project: the gate comes from the default branch, not from the pull request.
The smoke cases, the scorer, the baseline, and the thresholds are all checked out from `main`, so a change cannot loosen the gate it has to pass.

New cases can come from real findings.
A script snapshots a pull request at the commit a finding was posted on and prefills the expected answer, a bug case if the finding stood, a clean control if it drew more thumbs-down than thumbs-up.
A case joins the corpus only after I check its lines by hand, because a wrong expectation does more harm than a small corpus.

## What it still gets wrong

Half of what it reports on the corpus is not a seeded bug.
The verifier does not filter, so today the real filter is the narrow specialist prompts and the curation policy.
The corpus is 32 cases, and the baseline is a single trial.
A review costs more quota than it did, because there are twice the specialists and every agent runs on Opus at high effort.

[CONFIRM: what you plan to do about the verifier. The repository documents the problem, not the fix.]

The repository is [github.com/hamseabd/argus](https://github.com/hamseabd/argus).
The README is the design doc, and [`evals/report.md`](https://github.com/hamseabd/argus/blob/main/evals/report.md) is the full run behind the table above.

If you are building agents that have to earn trust inside a real engineering workflow, I would like to compare notes.
[GitHub](https://github.com/hamseabd) / [LinkedIn](https://www.linkedin.com/in/hamseabdi/).
