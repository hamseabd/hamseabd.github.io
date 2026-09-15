---
title: "Argus: a code reviewer that has to prove its findings"
date: 2026-09-15
draft: true
tags: ["agents", "code-review", "claude-agent-sdk", "evals", "production"]
summary: "I built a multi-agent code reviewer on the Claude Agent SDK. Every finding is checked by a second model that tries to refute it, the reviewer cannot touch the repository, it runs for $0 on GitHub Actions, and it reviews its own pull requests. Here is how it works, what the measurements changed, and where it is still wrong."
ShowToc: true
ShowReadingTime: true
---

I seeded two bugs into a small repository this morning: a SQL query rebuilt as an f-string, and an off-by-one in a pagination helper.
Then I pointed Argus at the branch.

It found both.
A second model, whose only job was to prove the findings wrong, confirmed both.
It also noticed that neither function had a test, which is how the bugs got in.
The whole run took 67 seconds and would have cost $0.28 on the API.

```
3 findings: 3 confirmed.

[CRITICAL] SQL injection: find_user interpolates name into SQL via f-string
[HIGH]     Off-by-one in page_slice drops the last item of every page
[MEDIUM]   No test coverage for page_slice or find_user lets both regressions land silently

Cost $0.28 · 51,516 input tokens (51,500 cached) · 15 turns · 66.7 s · 3 subagents
Agents: lead 2 turns, 4 tool calls · correctness 1 turn, 2 tool calls, 12.9 s · security 1 turn, 1 tool call, 10.3 s · quality 3 turns, 5 tool calls, 17.5 s
```

That is the pitch.
The rest of this post is how it works, what it cost to learn, and where it is still wrong.
The code is at [github.com/hamseabd/argus](https://github.com/hamseabd/argus).

## What Argus is

Argus is a multi-agent code-review harness built on the [Claude Agent SDK](https://docs.anthropic.com/en/docs/agent-sdk/overview), in Python.
It reviews a pull request or a local diff, posts inline review comments under its own GitHub App identity, and exits with a code you can gate a merge on.

I built it against three defaults of an LLM code reviewer.
It reports findings nobody checked.
It can edit the repository it is reviewing.
And its cost is one number for the whole run, so you cannot tell which agent is spending it.

Argus is built so that none of those three is true.

## How a review runs

Five stages.
Python owns the pipeline; the SDK owns the fan-out inside the review stage.

```
1. context   PR number -> GitHub API -> diff, files, metadata
             local diff -> git       -> (same shape)

2. review    one query: lead reviewer (Opus)
                 |-> correctness specialist (Sonnet)
                 |-> security specialist    (Sonnet)
                 |-> quality specialist     (Sonnet)
             lead merges, de-duplicates, answers with a Review as structured output

3. verify    one fresh query per finding, whose only job is to refute it

4. rank      drop rejected; confirmed before unverified; then severity; then path

5. report    terminal Markdown, JSON artifact, GitHub review with inline comments
```

**Context.**
PR mode fetches the diff, the changed files, and the metadata from the GitHub REST API.
Local mode diffs from the merge base with the base branch.
The diff has a 200 KB context budget; files are dropped largest first until it fits, and the lead is told which ones to read directly.

**Review.**
One SDK `query()` runs the lead reviewer on Opus as the orchestrator.
It must delegate to three specialist subagents on Sonnet in one turn, so they run in parallel: correctness, security, and quality, each with its own prompt.
Each specialist returns a JSON array of findings.
The lead merges them, drops duplicates, and answers with a `Review` as structured output.
The SDK validates that output against a JSON Schema derived from the Pydantic domain model, and Pydantic validates it again on the way in.

**Verify.**
Every finding gets its own query with only the finding and its diff hunk.
The verifier reads the code and confirms only if the code path actually exhibits the issue.
At most four run at once.

**Rank and report.**
Rejected findings are dropped.
A finding lands as an inline comment when its line is in the diff, otherwise in the review body.
The review never requests changes; merge gating is the CLI exit code, so the policy lives in the caller's workflow, not in the model.

Here is what an inline finding looks like, on Argus's own code:

![An Argus inline comment on PR #21: a MEDIUM security finding on the credential redaction regex, confirmed by the verifier](/images/argus-pr-21-inline.png)

The redaction regex covered Claude tokens but not the GitHub token in the same environment.
The verifier confirmed it, and the fix landed with a test before merge.

## Decision 1: verify by refutation

The lead reviewer never checks its own findings.
Each finding goes to a fresh query, with a fresh context, whose prompt says: try to refute this by reading the code.
Confirm only if the code path exhibits the issue at the reported location.
Reject if there is a guard the reporter missed, an input that cannot occur, a test that already covers it, or if it is a style preference dressed as a defect.

Two reasons.

The first is quality.
A finding that survives an independent attempt to refute it is worth more than one the reporter re-read and still liked.
And the failure mode is honest: if a verification fails, the finding is reported as `unverified`, never as `confirmed`.

The second is cost, and I found it by measuring.
The first two reviews let the lead re-check findings itself, and it did: 22 to 26 Opus turns re-reading code, $0.88 of the $1.37 the review of [PR #8](https://github.com/hamseabd/argus/pull/8) cost.
That is the verifier's job.
The lead now delegates, merges, and returns, and its own thread costs about $0.06.

## Decision 2: read-only by construction

Argus never writes, edits, or runs code in the repository it reviews.
The prompt says so, but the prompt is not the guarantee.
Three layered guardrails are.

- **The tool set.**
  Reviewers get `Read`, `Grep`, `Glob`, `Agent`, and one custom read-only tool.
  Nothing else is loaded.
- **A `PreToolUse` deny hook.**
  If `Write`, `Edit`, `Bash`, `WebFetch`, or any other mutating or network tool is ever requested, the hook denies it with a reason the model can read, so it does not retry.
  With no mutating or network tool, a prompt injection in a diff cannot write, execute, or exfiltrate.
- **`setting_sources=[]`.**
  Every query is isolated from the repository under review.
  Its `.claude/` settings, its hooks, and its own `CLAUDE.md` cannot reach the reviewer.

The one custom tool is `git_history`, served by an in-process MCP server.
It runs `git log -L` for a line range so a specialist can tell a fresh regression from a long-standing deliberate choice, and it refuses paths outside the repository root.

The same thinking runs through the GitHub Actions workflow.
Argus is installed and run from its own repository at a pinned commit, never from the pull request under review, and the PR head is checked out into a separate directory that is only read.
The trust boundary is the checkout: a pull request cannot execute its own code next to the token.
The review is posted with a short-lived GitHub App installation token, minted just before the review step with only `pull-requests: write`, and revoked when the job ends.

Any repository can call that workflow.
The first one that did was my own [apex-agent](https://github.com/hamseabd/apex-agent/pull/5#pullrequestreview-5186879344), and Argus's first review there flagged the caller for pinning the workflow to a mutable tag instead of a commit: a supply-chain risk in the file that invokes Argus itself.
The caller was fixed before it merged.

## Decision 3: Python owns the pipeline

The pipeline is plain Python over Pydantic domain types: `Finding`, `Review`, `Verdict`, `ReviewResult`.
It talks to the agent through a `ReviewAgent` protocol with two methods, `review` and `verify`, and nothing in the pipeline knows the SDK exists.

That buys two things.
The whole flow runs under test with a fake agent, offline, without credentials.
And only one package, `argus/agent/`, imports the SDK.
A test enforces that boundary by scanning the source and by importing every other module in a subprocess and asserting the SDK never loaded.

As of today there are 281 unit tests that run without network, plus one opt-in live test that builds the seeded-bug repository from the opening of this post and asserts Argus confirms a finding in it against the real SDK.

## What the measurements changed

The SDK reports usage for a query as a whole.
That was not enough to explain the cost spread between reviews, so Argus attributes usage itself.
Every assistant message in the stream names the `Agent` tool call that spawned its author, and the tool hooks inside a subagent carry that subagent's id.
Joining the two gives turns, tokens, tool calls, and duration per agent, in the JSON artifact and in the footer of every review.

That footer changed three decisions.

**The specialist cap.**
It was 15 turns until the per-agent line showed the quality specialist using all 15 on three reviews in a row and reporting nothing.
A capped run costs the same and returns less.
It is 25 now.

**The lead's model.**
I measured a Sonnet lead on the same diff as the Opus lead: $0.73, same finding.
But it delegated one specialist at a time and made no-op `Agent` calls.
The lead stays on Opus, where its share of the cost is about six cents.

**The lead's reading.**
This is the one I would tell anyone building agents.
The lead prompt had said, for several increments, do not re-read the code, the specialists have read it and the verifier will read it again.
On the review of [PR #10](https://github.com/hamseabd/argus/pull/10#pullrequestreview-5189614285) the lead made 43 tool calls on a four-file diff, delegated to its three specialists sixteen seconds apart instead of in one message, and the review cost $2.49.
On [PR #18](https://github.com/hamseabd/argus/pull/18) it made two, for $0.42.
Same prompt.

A prompt is a request.
The fix was a rule.
The lead gets a budget of ten reads, enforced by a `PreToolUse` hook; once it is spent, every further read is refused with a reason, and the only move left is to answer.
Delegation and the final answer are never refused.

```python
def limit_lead_reading(state: HookState) -> Hook:
    async def hook(data, _tool_use_id, _ctx) -> dict:
        budget = state.read_budget
        if budget is None or data.get("agent_id") or data.get("tool_name") not in READ_TOOLS:
            return {}
        if state.lead_reads < budget:
            state.lead_reads += 1
            return {}
        state.reads_denied += 1
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"You have used the {budget} reads a lead gets. The specialists have read "
                    "the change for you: merge what they reported and answer with the Review."
                ),
            }
        }

    return hook
```

The same idea shows up once more.
The `Review` schema puts a length floor on the summary, and the `Verdict` schema on the verifier's reasoning.
Before that floor, the lead's output was rejected three times on one review, and then a structurally valid payload whose summary was "Test call to diagnose schema validation." validated and was posted as the review.
Now a placeholder that fits the shape is rejected by the SDK's validator, the model has to write the real thing, and the number of rejected outputs is part of every stage's metrics.

### What a review costs

Argus authenticates with a Claude subscription token, so a review costs quota, not money.
The SDK still reports what the same run would have cost on the API.

| Run | Cost | Time | Turns |
|---|---|---|---|
| PR #7: 2 files, 6 findings, 6 verifications | $2.34 | 306 s | 48 |
| PR #8: 3 files, 0 findings | $1.37 | 128 s | 22 |
| PR #8 re-run with the current prompts: 1 finding | $1.02 | 190 s | 5 |
| PR #15: 4 files, 0 findings | $0.50 | 91 s | 5 |
| PR #10: 4 files, 1 finding, lead 43 tool calls | $2.49 | 319 s | 12 |

Most of the input is prompt-cache reads: 805,554 of 805,620 input tokens on PR #7.
These are five small pull requests on one repository, and I have not measured a false-positive rate over a larger sample.
Read the table as the shape of the cost, not as a benchmark.

## When it is wrong

Verification lowers the false-positive rate.
It does not make it zero, and the case where it failed taught me the most about what verification can and cannot do.

On [PR #12](https://github.com/hamseabd/argus/pull/12), which made the workflow reusable from other repositories, Argus reported two HIGH findings across two reviews: that `job.workflow_sha` and `job.workflow_repository` are not valid GitHub Actions contexts, so the trusted checkout would never use the pinned commit.
The verifier confirmed both.
Both were wrong.
Those fields exist; the finding reflected older documentation.
I proved it the only way that settles it, with two probe runs that printed the contexts from inside a called workflow, and wrote the disposition on the pull request with links to the runs.

The lesson: the verifier reads the code, so it catches reasoning errors.
It shares the reporter's knowledge cutoff, so it cannot catch knowledge errors.
That is why every Argus finding on this repository gets a written disposition, taken or not taken with the reason, and why the exit code is the merge gate rather than the review's opinion.

## How I built it

The repository is meant to be read, so the process is in it.

- **The design came before the code.**
  A design spec and an increment plan were committed before the first line ([`a26ca3e`](https://github.com/hamseabd/argus/commit/a26ca3e)).
- **One increment, one branch, one pull request, one squash-merge.**
  Every pull request body has the same four parts: why, what changed, a definition of done, and the verification output pasted in.
  [PR #19](https://github.com/hamseabd/argus/pull/19) is the shape.
- **The failing test comes first.**
  Every increment starts with a test that fails.
- **Architecture rules are tests, not comments.**
  The SDK boundary, the no-print rule, and the workflow's triggers, permissions, timeout, and concurrency are all asserted.
- **Argus reviews its own pull requests.**
  Every pull request since the workflow landed has been reviewed by Argus, and each finding has a disposition in the thread.
- **Decisions changed by measurement.**
  The five above, each traceable to a pull request with the numbers in it.

Claude Code was the pair programmer throughout.
The design, the failing tests, the review of every diff, and every merge were mine.

## What it does not do yet

It skips pull requests from forks, because GitHub gives them no secrets.
It reviews a pull request when it opens or leaves draft, not on every push; a maintainer can trigger a review on demand.
It does not reply in threads.
And the numbers above are from one repository over a few weeks; a false-positive rate over a larger, more varied sample is the next measurement.

The repository is [github.com/hamseabd/argus](https://github.com/hamseabd/argus).
The README is the design document, the pull requests are the history, and the review on [PR #21](https://github.com/hamseabd/argus/pull/21#pullrequestreview-5191721455) is a good place to see it work.

If you are building agents that have to earn trust in a real workflow, I would like to compare notes.
[GitHub](https://github.com/hamseabd) / [LinkedIn](https://www.linkedin.com/in/hamseabdi/).
