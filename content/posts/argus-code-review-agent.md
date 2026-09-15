---
title: "Argus: I built the code-review agent, harness and all"
date: 2026-09-15
draft: true
tags: ["agents", "code-review", "claude-agent-sdk", "harness-engineering", "evals"]
summary: "Everyone can whiteboard a code-review agent. I built one on the Claude Agent SDK and wired it into CI: a harness that orchestrates specialist subagents, verifies every finding by trying to refute it, never lets the model touch the repository or post anything itself, and reviews its own pull requests for $0. Here is the design spine, the harness piece by piece, what the telemetry changed, and where it is still wrong."
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

## Why I built it

A code-review agent is the design exercise everyone in this field has done on a whiteboard, me included.
The whiteboard version is cheap and it is always right.
The built version has to survive an adversarial pull request, a model that ignores its prompt, a schema it does not feel like filling in, and a token that must never reach a public log.
I wanted to know what the built version actually costs, so I built it.

Argus is an agentic code reviewer on the [Claude Agent SDK](https://docs.anthropic.com/en/docs/agent-sdk/overview), in Python.
It reviews a pull request or a local diff, posts inline review comments under its own GitHub App identity, and exits with a code the caller can gate a merge on.
It runs on the pull requests of four of my repositories, including its own.
The code is at [github.com/hamseabd/argus](https://github.com/hamseabd/argus), and every number below comes from that repository's pull requests or from the run above.

## The questions I answer before writing an agent

The same seven questions, every time, before any architecture.
Argus's answers, one line each; the rest of the post is the evidence.

1. **Is the path known in advance?**
   Mostly.
   A review is a fixed five-stage workflow, and the open-ended part, reading a repository to judge a diff, is confined to one stage.
   So the pipeline is deterministic Python and the agent loop lives inside one stage of it.
2. **Where does the model go, and where does it not?**
   Two places: reviewing the change and verifying a finding.
   Everything else is a mechanism.
3. **What is the unit of work?**
   One finding.
   It is verified on its own, ranked on its own, and posted or dropped on its own.
4. **What is the oracle?**
   For a finding, a second model with a fresh context that tries to refute it by reading the code, and then a human disposition.
   For the system, a seeded-bug repository where the answers are known.
5. **What may it write?**
   Nothing.
   The model has no mutating tool, and the harness is what posts the review.
6. **Which rung?**
   Advisory.
   The review never requests changes; the exit code is there if a caller wants a gate.
7. **What binds, and what is the guardrail metric?**
   Two non-functionals bind a review agent: the signal ratio, because a finding costs a human a minute, and untrusted input, because the pull request is the input.
   The guardrail is cost per review, attributed per agent, and the count of structured outputs the model got wrong.

## How a review runs

```
1. context   PR number -> GitHub API -> diff, files, metadata
             local diff -> git       -> (same shape)

2. review    one query: lead reviewer (Opus) as orchestrator
                 |-> correctness specialist (Sonnet)
                 |-> security specialist    (Sonnet)
                 |-> quality specialist     (Sonnet)
             lead merges, de-duplicates, answers with a Review as structured output

3. verify    one fresh query per finding, whose only job is to refute it

4. rank      drop rejected; confirmed before unverified; then severity; then path

5. report    terminal Markdown, JSON artifact, GitHub review with inline comments
```

**Context** fetches the diff, the changed files, and the metadata from the GitHub REST API, or diffs locally from the merge base.
The diff has a 200 KB context budget; files are dropped largest first until it fits, and the lead is told which ones it may read directly instead.

**Review** is one SDK `query()`.
The lead reviewer on Opus is the orchestrator: it must delegate to three specialist subagents on Sonnet in one turn, so they run in parallel, each with its own system prompt and the same read-only tool set.
Each specialist returns a JSON array of findings; the lead merges them, drops duplicates, and answers with a `Review` as structured output.

**Verify** runs one query per finding, in its own context window, holding only the finding and its diff hunk.
At most four run concurrently.

**Rank and report** are pure functions.
A finding lands as an inline comment when its line is in the diff, otherwise in the review body.

Here is what an inline finding looks like, on Argus's own code:

![An Argus inline comment on PR #21: a MEDIUM security finding on the credential redaction regex, confirmed by the verifier](/images/argus-pr-21-inline.png)

The redaction regex covered Claude tokens but not the GitHub token in the same environment.
The verifier confirmed it, and the fix landed with a test before merge.

## The harness, piece by piece

The vocabulary is loose, so a distinction first.
Claude Code is an agent harness: the loop that calls the model, executes tool calls, spawns subagents, runs hooks, and enforces permissions.
The Claude Agent SDK is that harness as a library.
Argus is the harness I built on top of it: what goes into the loop, what the loop may touch, what must come out, and what happens next.

| The SDK provides | What Argus does with it |
|---|---|
| `query()` with `ClaudeAgentOptions` | One query for the review stage, one per finding for verification. Model, effort, turn cap, and dollar cap set per stage from a settings object. |
| `agents` and `AgentDefinition` | Three specialists, each with its own prompt, Sonnet, a 25-turn cap, and read-only tools. |
| `tools`, `allowed_tools`, `disallowed_tools`, `permission_mode` | `Read`, `Grep`, `Glob`, `Agent`, and one MCP tool. Every mutating tool disallowed. `dontAsk`, because nobody is at the keyboard in CI. |
| Hooks: `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `SubagentStart`, `SubagentStop` | Deny mutating tools with a reason. Cap the lead's reads. Audit every tool call. Count rejected structured outputs. Time each subagent. |
| `create_sdk_mcp_server` and `@tool` | `git_history`: in-process, read-only, `git log -L` for a line range, refuses paths outside the repository. |
| `output_format` with a JSON Schema | `Review` and `Verdict` schemas derived from the Pydantic domain models, with length floors on prose fields. |
| `setting_sources=[]` and `strict_mcp_config` | The repository under review cannot inject its `.claude/` settings, hooks, `CLAUDE.md`, or MCP servers into the reviewer. |
| The message stream: `AssistantMessage`, `ResultMessage`, `RateLimitEvent` | A runner turns the stream into a result plus metrics, and turns five failure modes into typed errors that carry the cost so far. A ledger attributes turns and tokens per agent. |
| `CLAUDE_CODE_OAUTH_TOKEN` | Subscription auth. No API key, no cloud, $0 to operate. |

Two things follow from this table.

The model is used in exactly two places.
Diff parsing, the index of which lines a GitHub comment may attach to, the context cap, ranking, rendering, posting, and gating are deterministic Python with unit tests.
The model never posts, never commits, never calls GitHub.
The harness writes; the model only answers.

And the pipeline does not know the SDK exists.
It is plain Python over Pydantic types, `Finding`, `Review`, `Verdict`, `ReviewResult`, and it talks to the agent through a `ReviewAgent` protocol with two methods.
The whole flow runs under test with a fake agent, offline, in seconds.
Only one package imports the SDK, and a test enforces that by scanning the source and by importing every other module in a subprocess and asserting the SDK never loaded.

## The oracle: verify by refutation

The lead never checks its own findings.
Each one goes to a fresh query whose prompt says: try to refute this by reading the code.
Confirm only if the code path exhibits the issue at the reported location.
Reject if there is a guard the reporter missed, an input that cannot occur, a test that already covers the case, or if it is a style preference dressed as a defect.

A finding that survives an independent attempt to refute it is worth a human's minute.
One the reporter re-read and still liked is not evidence of anything.
And the failure mode is honest: if a verification query fails, the finding is reported as `unverified`, never as `confirmed`.
The harness does not guess.

I also found the cost reason by measuring.
The first two reviews let the lead re-check findings itself, and it did: 22 to 26 Opus turns re-reading code, $0.88 of the $1.37 the review of [PR #8](https://github.com/hamseabd/argus/pull/8) cost.
That is the verifier's job.
The lead now delegates, merges, and returns, and its own thread costs about six cents.

The limitation: the verifier is another model reading the same code with the same training.
It catches reasoning errors.
It does not catch knowledge errors, and there is a concrete case of that below.

## The input is untrusted: an agent in CI is a supply-chain component

An agent running in CI holds the union of its tools' privileges and is driven by untrusted input, because the pull request is the input.
That is the threat model, and the guardrails attach where side effects happen: at the tools, not in the prompt.

- **The tool set is runtime policy.**
  Nothing mutating or network-facing is loaded.
- **A `PreToolUse` hook is my code.**
  It runs on the event whether the model cooperates or not.
  If `Write`, `Edit`, `Bash`, `WebFetch`, or any other denied tool is requested, the hook refuses it with a reason the model can read, so it does not retry.
  With no mutating or network tool, a prompt injection in a diff cannot write, execute, or exfiltrate.
- **`setting_sources=[]` isolates the session.**
  The reviewed repository's own configuration never reaches the reviewer.

The same threat model runs through the GitHub Actions workflow.
Argus is installed and run from its own repository at a pinned commit, never from the pull request under review.
The PR head is checked out into a separate directory that is only read; the trust boundary is the checkout.
The review is posted with a short-lived GitHub App installation token, minted just before the review step with only `pull-requests: write`, and revoked when the job ends.
Every action is pinned to a commit SHA and Dependabot moves the pins.
Pull requests from forks are skipped, because GitHub gives them no secrets anyway.

Any repository can call that workflow.
The first one that did was my own [apex-agent](https://github.com/hamseabd/apex-agent/pull/5#pullrequestreview-5186879344), and Argus's first review there flagged the caller for pinning the workflow to a mutable tag instead of a commit: a supply-chain finding in the file that invokes Argus itself.
The caller merged with a commit pin.

The limitation: IDE and CI are different risk profiles, and Argus solves the CI one.
Run it locally with `--diff` and it is still read-only, but it runs with your credentials on your machine.

## Who refuses: the enforcement ladder

Three things can refuse the model in Argus, and the order matters.
The prompt asks.
The schema rejects.
The hook denies.
I learned to reach for the right one by getting it wrong first.

The lead's prompt had said, for several increments: do not re-read the code, the specialists have read it and the verifier will read it again.
Per-agent telemetry then showed what the prompt was worth.
On the review of [PR #10](https://github.com/hamseabd/argus/pull/10#pullrequestreview-5189614285) the lead made 43 tool calls on a four-file diff, delegated to its three specialists sixteen seconds apart instead of in one message, and the review cost $2.49.
On [PR #18](https://github.com/hamseabd/argus/pull/18) it made two, for $0.42.
Same prompt.

A prompt is an instruction, and a model can ignore an instruction.
A hook is my code, and it runs whether the model cooperates or not.
So the budget moved down the ladder.
The lead gets ten reads, enforced by a `PreToolUse` hook; once they are spent, every further read is refused with a reason, and the only move left is to answer.
Delegation and the final answer are never refused, so the rule cannot strand a review.

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

The schema is the same move on the output contract.
Before the `Review` schema had a length floor on the summary, the lead's structured output was rejected three times on one review, and then a structurally valid payload whose summary was "Test call to diagnose schema validation." validated and was posted as the review.
Now a placeholder that fits the shape is rejected by the SDK's validator and the model has to write the real thing.
The count of rejected outputs is a metric on every stage rather than a log line, because if a model update shifts behaviour, structured output is a likely place to see it first.

Caps are the last refusal: the lead stops at 40 turns or $3.00, each specialist at 25 turns, each verifier at 10 turns or $0.50, and a specialist that uses every turn it has is logged, because its findings may be incomplete.

## What it costs, per agent

The SDK reports usage for a query as a whole.
That could not explain why two reviews of similar diffs cost $0.42 and $2.49, so Argus attributes usage itself.
Every assistant message in the stream names the `Agent` tool call that spawned its author, and the tool hooks inside a subagent carry that subagent's id.
Joining the two gives turns, tokens, tool calls, and duration per agent, in the JSON artifact and in the footer of every review.
It is the last line of the output at the top of this post.

That line is what changed the specialist cap from 15 to 25, after the quality specialist used all 15 on three reviews in a row and reported nothing.
It is what kept the lead on Opus: a Sonnet lead on the same diff cost $0.73 and found the same finding, but delegated one specialist at a time and made no-op `Agent` calls.
And it is what exposed the lead's reading above.

Argus authenticates with a subscription token, so a review costs quota, not money; the SDK still reports what the run would have cost on the API.

| Run | Cost | Time | Turns |
|---|---|---|---|
| PR #7: 2 files, 6 findings, 6 verifications | $2.34 | 306 s | 48 |
| PR #8: 3 files, 0 findings | $1.37 | 128 s | 22 |
| PR #8 re-run with the current prompts: 1 finding | $1.02 | 190 s | 5 |
| PR #15: 4 files, 0 findings | $0.50 | 91 s | 5 |
| PR #10: 4 files, 1 finding, lead 43 tool calls | $2.49 | 319 s | 12 |

Most of the input is prompt-cache reads: 805,554 of 805,620 input tokens on PR #7.
The marginal turn is cheap; turns and output are what cost.
Five small pull requests on one repository: read it as the shape of the cost, not a benchmark.

## Evaluation, honestly

Evaluating an agent means evaluating the harness and the model together.
Argus has three layers of that and is missing a fourth.

The deterministic layer is the unit suite: 281 tests as of today, covering the pipeline, the diff parser, the commentable-line index, the schemas, the hooks, and the workflow's shape.
It runs offline on every commit, and it is the only layer that changes the output when it fails.

The end-to-end layer is the seeded-bug fixture from the top of this post.
Seeded bugs are a labeled corpus of known-bad code, so whether Argus catches them is measurable at zero labeling cost.
It proves the harness, the SDK, and the model still work together, which is the check I want after every SDK or model update.
The limitation is size: one fixture, two bugs.
It does not measure precision.

The production layer is dogfooding.
Every pull request on Argus's own repository since the workflow landed has been reviewed by Argus, and every finding has a written disposition in the thread: taken with the fix commit, or not taken with the reason.
The human is the last layer, and merging is a human action.

The fourth layer is the one I have not built: a golden set of real pull requests with labeled findings, so precision and recall are numbers rather than impressions.
The dispositions are the labels for it.
It is the next increment.

### When it was wrong

On [PR #12](https://github.com/hamseabd/argus/pull/12), which made the workflow reusable from other repositories, Argus reported two HIGH findings across two reviews: that `job.workflow_sha` and `job.workflow_repository` are not valid GitHub Actions contexts, so the trusted checkout would never use the pinned commit.
The verifier confirmed both.
Both were wrong.
Those fields exist; the finding reflected older documentation.
I proved it the only way that settles it, with two probe runs that printed the contexts from inside a called workflow, and wrote the disposition on the pull request with links to the runs.

The verifier reads the code, so it catches reasoning errors.
It shares the reporter's knowledge cutoff, so it cannot catch knowledge errors.
That is why the review is advisory, why the exit code is the gate, and why every finding gets a human disposition.

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
- **Prompts ship like code.**
  They are Markdown files inside the package, versioned, tested where a test applies, and reviewed on a pull request, by Argus among others.
- **Argus reviews its own pull requests.**
  Every one since the workflow landed, with a disposition per finding.
- **Decisions changed by measurement.**
  The specialist cap, the lead's model, and the read budget are each traceable to a pull request with the numbers in it.

Claude Code was the pair programmer throughout.
The design, the failing tests, the review of every diff, and every merge were mine.

## What it does not do yet

It skips pull requests from forks.
It reviews a pull request when it opens or leaves draft, not on every push; a maintainer can trigger a review on demand.
It does not reply in threads, and it does not learn from dispositions.
It has no measured precision, which is the next increment, and the numbers above are from a few weeks on my own repositories.

The repository is [github.com/hamseabd/argus](https://github.com/hamseabd/argus).
The README is the design document, the pull requests are the history, and the review on [PR #21](https://github.com/hamseabd/argus/pull/21#pullrequestreview-5191721455) is a good place to see it work.

If you are building agents that have to earn trust inside a real engineering workflow, I would like to compare notes.
[GitHub](https://github.com/hamseabd) / [LinkedIn](https://www.linkedin.com/in/hamseabdi/).
