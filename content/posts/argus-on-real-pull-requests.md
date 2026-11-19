---
title: "Two months of Argus on real pull requests"
date: 2026-11-18
draft: true
tags: ["agents", "code-review", "claude-agent-sdk", "evals", "harness-engineering"]
summary: "Argus is my multi-agent code reviewer. In two months it grew from three specialists to six, got an eval corpus and a merge gate, and found holes in its own guardrails. Here is what it caught, what the evals measured, and where it still falls short."
ShowToc: true
ShowReadingTime: true
---

The script that publishes Argus has one job it cannot get wrong.
It copies the private development repository to the public one.
Before it pushes, it scans the tree for the names of my other private repositories.

Argus reviewed the pull request that added that script.
This was its top finding, posted on November 14, 2026:

> **[HIGH] Private-name leak guard fails open when gh fails, and the release is pushed anyway** · security · confirmed · confidence 0.90 · found by lead
>
> The only control that keeps private repository names out of the public release is skipped silently when `gh` fails (not installed, not logged in, rate limited, network error). The pipeline's failure is masked by `|| true`, the names file ends up empty, the `[[ -s ... ]]` test is false, the leak check never runs, and the script goes on to push the tree to the public repository.

Four specialists recorded that defect independently, and the lead merged them into one finding.
A fifth, the tests specialist, added that no test covered the failure.

The fix landed on the same pull request.
The second review found a quieter version of the same hole: a credential that can see only one repository returns a short list, and the scan passes with nothing to check.
That was fixed too.
The script now stops whenever the list may be incomplete.
The third review reported no correctness defects in it.

That is the kind of finding I built Argus for.
This post covers two months of them, including the numbers that are not flattering.

## What Argus is

Argus is a code reviewer built on the Claude Agent SDK, in Python.
A lead agent hands a diff to specialist subagents.
A separate verifier tries to refute each finding.
What survives lands on the pull request as inline comments.

It is read-only by construction.
It runs on GitHub Actions on a Claude subscription token, so a review costs quota, not money.

[The first write-up]({{< ref "argus-code-review-agent" >}}) covers why it verifies by refutation, why it indexes nothing, and how the guardrails attach to the tools.
This one covers what changed since, and what happened when it met real code.

The code is public at [github.com/hamseabd/argus](https://github.com/hamseabd/argus).
Development happens in a private repository, and the public one gets one squashed commit per release.
So most of the pull requests below are not linkable.
Where a review is public, I link it.

## What changed since September

![How an Argus review runs. A pull request goes to a lead agent, which delegates to six specialists in one turn: correctness, security, tests, maintainability, design, and conventions. Each finding is recorded through a tool, triaged by the lead, curated by code, verified in a fresh query, and passed through a post rule in code before it lands as an inline review comment.](/images/posts/argus-on-real-pull-requests/review-pipeline.svg)

**Six specialists, not three.**
Correctness, security, tests, maintainability, design, and conventions.
The first version had correctness, security, and a catch-all called quality.
On that design's eval run, on October 24, 2026, every false positive came from quality: 0 of its 5 reported findings were real.
Four narrow specialists replaced it.
Each prompt says what counts, what never counts, and how to look.

**Findings are recorded through a tool, not retyped.**
Each specialist calls `report_finding`, which validates the finding against the domain model and against the repository.
The file must exist, and the line must be in it.
The lead then triages by id.
It names the ids to drop, and Argus builds the review from everything it did not drop.
No model rewrites a finding between the specialist and the verifier.

**Noise is a policy in code.**
Duplicates are merged.
Nits are capped at five, and dropped entirely when anything is high or critical.
A review holds at most 25 findings.
The lead is told the rules, and the pipeline enforces them.

**The verifier reads more and can say it does not know.**
It reads the whole changed file, not only the hunk.
It answers `confirmed`, `rejected`, or `inconclusive`, with a confidence.
It is never told how confident the reporter was.
A finding is posted as confirmed only at 0.6 or above.
Rejected findings stay visible in a folded list, with the verifier's reason.

**It remembers its earlier reviews.**
A re-review covers only the commits since the last one.
A finding it already posted is marked `known` and not posted again.
One I gave a thumbs-down is `dismissed`, in a change that landed after the current public release.

**The repository's own rules reach every agent.**
`REVIEW.md` and `CLAUDE.md` are read from a branch the change cannot touch.
A pull request cannot edit the rules it is reviewed under.

Every agent now runs on Opus 5.5 at high effort.

## What it found in its own guardrails

Argus reviews its own pull requests.
The findings I value most are the ones against its own safety code.

A note on which design found what.
The six specialists merged on November 2, 2026.
The four findings below are from October 2 and October 13, so the three-specialist design found them.
The release-script finding at the top of this post is from the current one.

**Any bot could have silenced it.**
The change that taught Argus to skip findings it had already posted trusted an earlier review if its author was a bot and its body started with the Argus marker.
GitHub reports every app as a bot.
Argus flagged it, HIGH at 0.75:

> Any bot already installed on the repository that can post a review or review comment can forge a body starting with `<!-- argus:review -->` [...] and the pipeline will mark matching new findings `known`, skip verification, hide them from the report, and not gate on them.

The fix checks the one login Argus posts as.

**A nit could have swallowed a critical.**
The same change matched a new finding to an old one by line proximity alone.
A low-severity nit two lines away would have marked an unrelated critical finding as already reported.
HIGH at 0.82.
The match now also needs the same category.

**The read confinement was a denylist.**
The hook that keeps reviewers inside the repository checked the text of a glob pattern for `..` and `.git`.
Argus flagged, HIGH at 0.65, that a wildcard such as `.gi?` or a symlink inside the repository walked straight past it.
The hook now scans for links that lead out, and refuses any pattern that could name `.git`.

**Incremental review would never have come back.**
A guard forced a full review while earlier findings were still open.
But it derived "open" from every comment ever posted.
One finding, once posted, would have disabled incremental review on that pull request for good.
HIGH at 0.60.
That finding is now a case in the eval corpus, snapshotted from the pull request it was posted on.

Four high-severity findings in the reviewer's own machinery.
Each was fixed on the branch that introduced it.

[CONFIRM: "I had read all four diffs before Argus flagged them, and I missed all four." Keep, reword, or cut. Only you know if it is true.]

## What it found in someone else's code

A reusable workflow lets my other repositories call Argus.
Some of those reviews are public, such as [apex-agent pull request 1](https://github.com/hamseabd/apex-agent/pull/1#pullrequestreview-5191356443), a grounded knowledge base for my health agent.

That review is from September 13, 2026, on the three-specialist design.
It posted nine findings, all confirmed by the verifier.
Two of them show what a reviewer that reads the whole repository can see.

The first is a bug the tests could not catch, and the reason why:

> **[MEDIUM] ask_knowledge_base re-fetches the entire S3 corpus 2-3x per question** · correctness · confirmed · confidence 0.85
>
> **[LOW] FakeStore decouples total_tokens() from load_corpus(), hiding the redundant-fetch bug** · quality · confirmed · confidence 0.55
>
> The fake makes the suite green on behaviour the production store does not have.

The second is a failure of the feature's whole purpose:

> **[MEDIUM] Exact-equality refusal check appends medical disclaimer to near-miss refusals** · correctness · confirmed · confidence 0.65
>
> Grounding relies on `answer == REFUSAL` after a single `.strip()`. [...] That is the exact failure mode the feature exists to prevent, and the unit tests only cover the byte-identical case.

A refusal that comes back with quotes around it falls through the check.
It then gets the "from your documents" disclaimer appended, on an answer that is explicitly not from the documents.

As of November 18, 2026, that pull request is still open.
Those findings are flagged, not fixed.

## What the numbers say

Every finding Argus posts can be read back.
`argus feedback` counts a finding as acted on when it has a thumbs-up, a resolved thread, or a later commit that changed the flagged lines.
More thumbs-down than thumbs-up marks a false positive.

On Argus's own repository, for the 30 days ending November 2, 2026:

| Severity | Posted | Acted on | Marked false positive |
|---|---|---|---|
| high | 5 | 5 | 0 |
| medium | 18 | 16 | 0 |
| low | 26 | 21 | 0 |
| nit | 6 | 4 | 0 |
| **all** | **55** | **46** | **0** |

The window spans both designs: 22 of the 55 came from the old quality specialist.

That is one small repository.
For scale, in the seven days ending November 16, 2026, Argus posted 145 inline findings on Bosun, the repository for my fleet of coding agents.

Acted on is not the same as right.
Every review ends with a machine-readable block that hands its findings to a fixer agent.
Fixer agents handle the routine findings.
I fix every medium and above myself.
An agent told to fix something will usually fix it, so the low and nit rows say more about obedience than accuracy.
I do not read 46 of 55 as precision.

For that I built an eval.

## What the evals say

The corpus is 32 small repositories with known answers.
22 hold a seeded bug.
6 are clean controls that should draw no finding.
4 are verifier traps: correct changes that look like classic defects.
A finding matches a seeded bug when it names the same category and lands within three lines of it.

Both columns are single runs.

| | Three specialists, October 24, 2026 | Six specialists, November 2, 2026 |
|---|---|---|
| Corpus | 13 cases | 32 cases |
| Recall | 100% (10 of 10) | 95% (21 of 22) |
| Precision | 67% | 50% |
| Clean controls flagged | 2 of 3 | 1 of 6 |
| Verifier accuracy | 67% | 51% |
| Cost per case, at API prices | $0.25 | $0.46 |

Recall held.
Every correctness and security bug the first design caught, the current one still catches.
The new specialists caught 10 of their 11.
The miss was found, then filed under the wrong category.

Precision is the problem, and the verifier is why.
It checked 21 findings that matched no seeded bug.
It confirmed all 21 and rejected none.
Its mean confidence was 0.93 on real bugs and 0.80 on the others, so the 0.6 threshold filtered nothing.

In the first write-up I called the separate verifier the whole design.
On this corpus it changed no outcome.

Three things qualify that number, and none of them excuses it.

- The scorer counts anything that does not match a seeded bug as false. That includes a valid point about code I did not plant a bug in.
- A third of the 21 come from one case, the snapshot of a real pull request, where only one bug is labeled.
- Each case is one review, one sample. The spread between runs is unmeasured here.

The per-category numbers say where to look.
Correctness is 8 real findings to 2 unmatched.
Design is 2 to 6.
Tests and maintainability are each 3 to 5.
The specialists I added produce most of the noise.

**What I am doing about it.**
I am going through the 21 one at a time, to see why the verifier confirmed each.
Then I clean up and tune the prompts, and run the corpus again.

[CONFIRM: you said the verifier is "a little too strict right now". The repository shows the opposite on the November 2 run: it confirmed 21 of 21 and rejected 0, and its prompt has not changed since. If "too strict" means the scorer or the specialist prompts, say which, and adjust the paragraph above.]

## The gate

The eval is not a report I run when I am curious.
A pull request that touches the reviewer or the evals runs a nine-case smoke subset: one seeded bug per specialist, two clean controls, and one trap.
A gate compares the run with the baseline, case by case.

It fails when:

- the run misses seeded bugs the baseline caught, beyond a tolerance of one,
- a clean control gains a finding, or
- a case errors.

The tolerance is deliberate.
One review of a case is one sample, and a model's findings vary between runs.
One extra miss is read as noise.
Two is a regression.

The part I would repeat on any project: the gate comes from the default branch, not from the pull request.
The smoke cases, the scorer, the baseline, and the thresholds are all checked out from `main`.
A change cannot loosen the gate it has to pass.

New cases can come from real findings.
A script snapshots a pull request at the commit a finding was posted on and prefills the expected answer.
It becomes a bug case if the finding stood, or a clean control if it drew more thumbs-down than thumbs-up.
A case joins the corpus only after I check its lines by hand.
A wrong expectation does more harm than a small corpus.

## What it still gets wrong

Half of what it reports on the corpus matches no seeded bug.
The verifier does not filter yet, so today the real filter is the narrow specialist prompts and the curation policy.
The corpus is 32 cases, and the baseline is a single trial.
A review costs more quota than it did, because there are twice the specialists and every agent runs on Opus at high effort.

None of that is hidden.
The README is the design doc, and [`evals/report.md`](https://github.com/hamseabd/argus/blob/main/evals/report.md) is the full run behind the November 2 column.

If you are building agents that have to earn trust inside a real engineering workflow, I would like to compare notes.
[GitHub](https://github.com/hamseabd) / [LinkedIn](https://www.linkedin.com/in/hamseabdi/).
