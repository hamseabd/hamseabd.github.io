---
title: "I built the code-review agent. Here's what the whiteboard version leaves out."
date: 2026-09-15
draft: false
tags: ["agents", "code-review", "claude-agent-sdk", "harness-engineering", "evals"]
summary: "Argus is a code reviewer on the Claude Agent SDK: a lead agent orchestrating three specialists, every finding checked by a second model trying to refute it, no write access to anything, $0 to run, and it reviews its own pull requests. The design is the easy part. This is the rest."
ShowToc: true
ShowReadingTime: true
---

I seeded two bugs into a repo this morning. A SQL query rebuilt as an f-string, and an off-by-one in a pagination helper. Then I pointed Argus at the branch.

It found both. A second model, whose only job was to prove the findings wrong, confirmed both. It also noticed that neither function had a test, which is how the bugs got in.

67 seconds. $0.28 of tokens.

```
3 findings: 3 confirmed.

[CRITICAL] SQL injection: find_user interpolates name into SQL via f-string
[HIGH]     Off-by-one in page_slice drops the last item of every page
[MEDIUM]   No test coverage for page_slice or find_user lets both regressions land silently

Cost $0.28 · 51,516 input tokens (51,500 cached) · 15 turns · 66.7 s · 3 subagents
Agents: lead 2 turns, 4 tool calls · correctness 1 turn, 2 tool calls, 12.9 s · security 1 turn, 1 tool call, 10.3 s · quality 3 turns, 5 tool calls, 17.5 s
```

That's the demo. The rest of this post is the part that isn't.

## Why I built it

A code-review agent is the design exercise everyone in this field has done on a whiteboard. I've done it. The whiteboard version is cheap and it's always right.

The built version has to survive an adversarial pull request, a model that ignores its own prompt, a schema it doesn't feel like filling in, and a token that must never reach a public log. I wanted to know what that costs.

The premise: the bottleneck isn't generation. Models write code and review comments faster than anyone can read them, so an agent that emits confident findings nobody checked doesn't reduce that pile, it adds to it. The design question was never "can a model find bugs in a diff." It was: what has to be true for a finding to be worth a human's minute?

Argus is my answer. It's on the [Claude Agent SDK](https://docs.anthropic.com/en/docs/agent-sdk/overview), in Python. It reviews a pull request or a local diff, posts inline comments under its own GitHub App identity, and exits with a code you can gate a merge on. It runs on four of my repos, including its own. Code: [github.com/hamseabd/argus](https://github.com/hamseabd/argus).

## The questions I ask before any architecture

Same list every time, before I draw anything.

**Is the path known?** Mostly. A review is a fixed five-stage workflow, and the open-ended part, reading a repo to judge a diff, lives inside one stage. So the pipeline is deterministic Python with the agent loop inside it.

**Where does the model go, and where doesn't it?** Two places: reviewing the change, verifying a finding. Everything else is a mechanism.

**What's the unit of work?** One finding. Verified on its own, ranked on its own, posted or dropped on its own.

**What's the oracle?** A second model with a fresh context trying to refute the finding, then a human disposition. For the system as a whole, a repo with bugs I planted, where I know the answers.

**What can it write?** Nothing.

**Which rung?** Advisory. The review never requests changes. The exit code is there if a caller wants a gate.

**What binds?** Two things bind a review agent. Signal ratio, because a bad finding costs a human a minute and they stop reading after a few. And untrusted input, because the pull request *is* the input.

## Harness, not prompt

The vocabulary here is loose, so: Claude Code is an agent harness, the loop that calls the model, runs its tool calls, spawns subagents, fires hooks, enforces permissions. The Claude Agent SDK is that harness as a library. Argus is the harness I built on top: what goes into the loop, what the loop can touch, what has to come out, and what happens next.

| The SDK gives me | What Argus does with it |
|---|---|
| `query()` with `ClaudeAgentOptions` | One query for the review, one per finding for verification. Model, effort, turn cap and dollar cap per stage. |
| `agents` / `AgentDefinition` | Three specialists: correctness, security, quality. Sonnet, 25 turns, read-only. |
| `tools`, `allowed_tools`, `disallowed_tools`, `permission_mode` | `Read`, `Grep`, `Glob`, `Agent`, one MCP tool. Every mutating tool disallowed. `dontAsk`, because nobody's at the keyboard in CI. |
| Hooks: `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `SubagentStart`, `SubagentStop` | Deny mutating tools with a reason. Cap the lead's reads. Audit every call. Count rejected outputs. Time each subagent. |
| `create_sdk_mcp_server` and `@tool` | `git_history`: in-process, read-only, refuses paths outside the repo. |
| `output_format` with a JSON Schema | `Review` and `Verdict` schemas generated from the Pydantic models, with length floors on prose. |
| `setting_sources=[]`, `strict_mcp_config` | The repo under review can't inject its own settings, hooks, `CLAUDE.md` or MCP servers into the reviewer. |
| The message stream | A runner turns it into a result plus metrics, and turns five failure modes into typed errors carrying the cost so far. A ledger attributes turns and tokens per agent. |
| `CLAUDE_CODE_OAUTH_TOKEN` | Subscription auth. No API key, no cloud, $0 to operate. |

Two things fall out of that table.

The model is used in exactly two places. Diff parsing, the index of which lines GitHub will accept a comment on, the context cap, ranking, rendering, posting, gating: deterministic Python with tests. **The harness writes. The model only answers.**

And the pipeline doesn't know the SDK exists. It's plain Python over Pydantic types, talking to the agent through a two-method protocol. The whole flow runs under test with a fake agent, offline, in seconds. One package imports the SDK, and a test enforces that by scanning the source and by importing every other module in a subprocess to check the SDK never loaded.

## No embeddings anywhere

Argus never indexes the repo. The specialists get `Grep`, `Glob`, `Read`, and one custom tool. That's the whole retrieval story, and it was a decision, not an omission.

Most questions you ask about code are *what is this connected to*. Who calls this function, where else is this pattern, when did this line change, is there a test for it. Grep answers that exactly. An embedding answers a different question, *what is this similar to*, approximately. For the security specialist tracing where untrusted input reaches a sink, approximately is worthless.

And an index is stale the moment someone pushes. Grep is always current, and code review is the one place you're looking at what changed thirty seconds ago.

The one tool I did add is `git_history`, and it follows the rule I use for every tool: **one tool, one question.** Not `run_git(command)`. It takes a path and a line range, returns the commits that touched those lines newest first, and refuses a path outside the repo root with a typed error the model can act on. It exists because "is this a fresh regression or a deliberate choice from two years ago" is a question a reviewer has to answer and a diff can't.

## Guilty until proven

The lead never checks its own findings. Each one goes to a fresh query whose entire job is to refute it: confirm only if the code path actually exhibits the issue at that location, reject if there's a guard the reporter missed, an input that can't occur, a test that already covers it, or if it's a style preference wearing a defect costume.

A finding that survives someone trying to kill it is worth a minute. A finding the reporter re-read and still liked is worth nothing, because of course it did.

The failure mode is honest too. If a verification query fails, the finding is reported as `unverified`, never as `confirmed`. The harness doesn't guess.

I also found the cost argument by accident. The first two reviews let the lead re-check its own findings, and it did: 22 to 26 Opus turns re-reading code, $0.88 of the $1.37 that [PR #8](https://github.com/hamseabd/argus/pull/8) cost. That's the verifier's job. The lead now delegates, merges, and returns, and its own thread costs about six cents.

Here's one that survived, on Argus's own code:

![An Argus inline comment on PR #21: a MEDIUM security finding on the credential redaction regex, confirmed by the verifier](/images/argus-pr-21-inline.png)

The redaction regex covered Claude tokens and not the GitHub token sitting in the same environment. Confirmed, and fixed with a test before merge.

What refutation can't do: the verifier is another model reading the same code with the same training. It catches reasoning errors. It does not catch knowledge errors. There's a case below.

## The pull request is hostile

An agent in CI holds the union of its tools' privileges and is driven by untrusted input, because the diff is the input. That's the threat model, and it's why the guardrails attach to the tools, not to the prompt.

**The cheapest guardrail is a tool that isn't there.** Nothing mutating or network-facing is loaded at all. Absent beats gated: a tool that doesn't exist can't be argued into existing.

The second layer is a `PreToolUse` hook, which matters because it's *my code* and it runs on the event whether the model cooperates or not. Ask for `Write`, `Edit`, `Bash`, `WebFetch`, and it's refused with a reason, so the model doesn't retry. With no mutating tool and no network tool, a prompt injection buried in a diff has nothing to reach for.

Third, `setting_sources=[]`. The reviewed repo's own `.claude/` config, hooks and `CLAUDE.md` never reach the reviewer. Otherwise a PR could ship instructions to the thing reviewing it.

The workflow carries the same model. Argus runs from *its own* repo at a pinned commit, never from the PR, and the PR head is checked out into a separate directory that's only ever read: the trust boundary is the checkout. The review posts with a GitHub App installation token, minted right before the review step with only `pull-requests: write`, revoked when the job ends. Actions are SHA-pinned and Dependabot moves the pins. Forks are skipped, because GitHub gives them no secrets anyway.

The first outside repo to call it was my own [apex-agent](https://github.com/hamseabd/apex-agent/pull/5#pullrequestreview-5186879344), and Argus's first review there flagged the caller for pinning to a mutable tag instead of a commit. A supply-chain finding in the file that invokes Argus. That one made me happy.

Caveat: IDE and CI are different risk profiles and I've solved the CI one. Run it locally and it's still read-only, but it's running with your credentials on your machine.

## Who's allowed to say no

Three things can refuse the model, and the order matters. The prompt asks. The schema rejects. The hook denies. I learned to reach for the right one by reaching for the wrong one first.

The lead's prompt had said, for several increments: don't re-read the code, the specialists have read it and the verifier will read it again. Then the per-agent telemetry told me what that prompt was worth. On [PR #10](https://github.com/hamseabd/argus/pull/10#pullrequestreview-5189614285) the lead made 43 tool calls on a four-file diff and the review cost $2.49. On [PR #18](https://github.com/hamseabd/argus/pull/18) it made two, for $0.42. Same prompt.

**A prompt is a request. A hook is a rule.** So the budget moved down the ladder: ten reads for the lead, enforced by a hook. Once they're gone every read is refused with a reason, and the only move left is to answer. Delegation and the final answer are never refused, so the rule can't strand a review.

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

The schema is the same move on the way out. Before the `Review` schema had a length floor on its summary, one review's output got rejected three times and then a structurally valid payload whose summary read "Test call to diagnose schema validation." passed and got posted. Now a placeholder that fits the shape is rejected by the validator and the model has to write the real thing. The count of rejected outputs is a metric on every stage, not a log line, because if a model update shifts behavior, structured output is where I expect to see it first.

## What I can see when it runs

Every run has an id. Every stage reports model, cost, tokens in and out, cache reads, turns, duration, and how many structured outputs got rejected before one validated. Every tool call is logged. It's JSON on stderr, and CI uploads the full record as an artifact.

The piece I had to build myself is per-agent attribution. The SDK reports usage for a query as a whole, which couldn't explain why two similar reviews cost $0.42 and $2.49. But every assistant message names the `Agent` call that spawned its author, and the tool hooks inside a subagent carry that subagent's id. Join those and you get turns, tokens, tool calls and duration per agent. It's the last line of the output at the top of this post.

That line paid for itself three times. It moved the specialist turn cap from 15 to 25, after I watched the quality specialist burn all 15 on three reviews running and report nothing. It kept the lead on Opus: a Sonnet lead found the same finding for $0.73 but delegated one specialist at a time and made no-op calls. And it exposed the lead's reading above.

Where it falls short: this is logs and metrics, not traces. There's no span tree, no OTel. For one review at a time I can read the JSON and know everything. If I were running this across a fleet of repos I'd want spans, so "which specialist got slow this month" is a query instead of an afternoon with `jq`.

A review costs quota, not money, because Argus runs on a subscription token. The SDK still reports what it would have cost on the API:

| Run | Cost | Time | Turns |
|---|---|---|---|
| PR #7: 2 files, 6 findings, 6 verifications | $2.34 | 306 s | 48 |
| PR #8: 3 files, 0 findings | $1.37 | 128 s | 22 |
| PR #8 re-run with the current prompts | $1.02 | 190 s | 5 |
| PR #15: 4 files, 0 findings | $0.50 | 91 s | 5 |
| PR #10: 4 files, 1 finding, lead 43 tool calls | $2.49 | 319 s | 12 |

Almost all the input is prompt-cache reads: 805,554 of 805,620 tokens on PR #7. Turns and output are what cost. Five small pull requests on one repo, so read it as the shape of the cost, not a benchmark.

## Evaluation, honestly

Evaluating an agent means evaluating the harness and the model together, because a change to either one changes the output. Argus has three layers of that, and it's missing the fourth.

The deterministic layer is the unit suite: 282 tests over the pipeline, the diff parser, the line index, the schemas, the hooks, and the workflow's shape. Offline, on every commit. It's the only layer that changes the output when it fails.

The end-to-end layer is the seeded repo from the top of this post. Planted bugs are a labeled corpus of known-bad code, so catching them is measurable at zero labeling cost, which is the cheap version of ground truth I wish I'd had on other projects. It proves harness, SDK and model still work together, which is the check I want after every update to any of them. It's also one fixture with two bugs. It does not measure precision.

The production layer is dogfooding. Every PR on Argus's own repo since the workflow landed has been reviewed by Argus, and every finding has a written disposition in the thread: taken with the fix commit, or not taken with the reason. The human is the last layer.

The fourth layer is the one I haven't built: a golden set of real pull requests with labeled findings, so precision and recall are numbers instead of impressions. The dispositions are the labels for it. That's the next increment, and until it exists I can't tell you Argus's false-positive rate, only that I keep merging what it flags.

### The time it was confidently wrong

On [PR #12](https://github.com/hamseabd/argus/pull/12) Argus reported two HIGH findings across two reviews: that `job.workflow_sha` and `job.workflow_repository` aren't valid GitHub Actions contexts, so the trusted checkout would never use the pinned commit.

The verifier confirmed both. Both were wrong. The fields exist; the finding was reasoning from older documentation. I settled it the only way you can, with two probe runs that printed the contexts from inside a called workflow, and wrote the disposition on the PR with links to the runs.

This is the limit of refutation, and it's worth being precise about. The verifier reads the code, so it catches reasoning errors. It shares the reporter's training data, so it can't catch knowledge errors. Two models can be confidently wrong about the same fact in exactly the same way. That's why the review is advisory, why the exit code is the gate, and why every finding gets a human disposition.

## How I built it

The repo is meant to be read, so the process is in it.

The design came before the code: a spec and an increment plan were committed before the first line ([`a26ca3e`](https://github.com/hamseabd/argus/commit/a26ca3e)). Every increment after that is one branch, one pull request, one squash-merge, and every PR body has the same four parts, why, what changed, a definition of done, and the verification output pasted in ([#19](https://github.com/hamseabd/argus/pull/19) is the shape). The failing test comes first. Architecture rules are tests rather than comments, so the SDK boundary, the no-print rule and the workflow's permissions are all asserted. Prompts live in the package and ship like code, reviewed on a PR. And every decision above is traceable to a PR with the numbers that caused it.

Claude Code was the pair programmer throughout. The design, the failing tests, the review of every diff and every merge were mine.

## What it doesn't do yet

No fork PRs. No review on every push, only on open and ready-for-review, plus on demand. No thread replies, and no learning from dispositions. And no measured precision, which is the next thing.

The repo is [github.com/hamseabd/argus](https://github.com/hamseabd/argus). The README is the design doc, the pull requests are the history, and the review on [PR #21](https://github.com/hamseabd/argus/pull/21#pullrequestreview-5191721455) is a good place to watch it work on real code.

If you're building agents that have to earn trust inside a real engineering workflow, I'd like to compare notes. [GitHub](https://github.com/hamseabd) / [LinkedIn](https://www.linkedin.com/in/hamseabdi/).
