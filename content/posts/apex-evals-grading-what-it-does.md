---
title: "My eval said the agent was failing. The eval was wrong."
date: 2026-06-16
draft: false
tags: ["evals", "agents", "aws", "production"]
summary: "I put a real eval suite on Apex — a health agent whose tools are generated from a config file. The first thing it caught wasn't an agent bug. It was a bug in the grader. Here's the whole setup, and the lesson."
ShowToc: false
ShowReadingTime: true
---

The eval report came back and one number was ugly.

Apex — my health-accountability agent — passed almost everything. It logged "slept 7.5 hours" as `sleep: 7.5`. It refused to log a workout I only said I was *thinking* about. It ignored a prompt injection telling it to wipe my data. Then I got to the category I care about most: the agent editing its own protocol — the config file that defines my targets and which tools even exist. "Update my protein target to 200." Three cases, three runs each, and only three of those nine passed. Failing.

That's the scary one. Apex's whole design is that the agent can rewrite the protocol it runs on. If it does that wrong, it corrupts the source of truth for everything else. A 33% pass rate there isn't a polish item — it's the thing that would make me turn the feature off.

So I opened the transcripts. And the agent had done it perfectly. Every time.

The reply was right: *"180g → 200g ✅."* The tool call was right: `update_protocol` with the correct path. The config on disk was right: protein target now 200. The grader still marked it failed, with this reason:

```
'tracking.metrics.protein.daily_target'=200.0, expected 200
```

The agent set the target to `200.0`. I'd asked for `200`. My grader compared them as strings — `"200.0" != "200"` — and called the agent broken.

The model was right. The ruler was bent.

I'll come back to how I caught it. First, what this thing is and why I built it.

## What I was trying to measure

[Last time]({{< ref "three-production-ai-agents" >}}) I said the next post would be Apex's eval suite, because the interesting part isn't grading what a bot *says* — it's grading what it *does*. This is that post.

Apex's headline feature is that its tools are generated at runtime from a config file. Add `meditation` to my protocol and a `log_meditation` tool appears in the agent on the next cold start. No code change. That's nice for me and it's a real architecture story, but it makes testing harder: the surface I'm validating isn't fixed, and the failures I care about don't live in the code. They live in the model's behavior.

Apex already has 153 deterministic tests. They prove the plumbing: the factory builds the right tools, the tools write the right rows, the date math is correct. None of them answer the question a user actually experiences — *when I text "slept 7 and a half hours," does the right row land in the database?* That's not a thing you assert once. It's a probability you measure.

So the eval suite sits on top of the unit tests and asks behavioral questions: does the agent pick the right tool, extract the right number, fire all the tools when I say two things at once, and — the one most people skip — correctly do **nothing** when I'm only asking a question.

## Grade the outcome, not the path

The core decision is to grade *state*, not *trajectory*.

It's tempting to assert on the sequence of tool calls — "it should call `get_protein_logs`, then answer." But agents find valid paths you didn't script, and every time they do, a trajectory test fails for no good reason. Anthropic's own eval guidance warns against exactly this.

Apex is well-suited to avoid it, because every consequential thing the agent does lands somewhere I can inspect. Logging writes a row to DynamoDB. Editing the protocol rewrites a file in S3. So I don't grade the agent's words or its route. I run it for real, then look at what actually persisted and grade that. The agent can phrase its reply however it likes and call tools in any order — I only care about the footprint it leaves.

## The trick: real brain, fake hands

Here's the part I'd build again on any agent project.

To test the *real* model's behavior, the Bedrock call has to be real — that's the whole point. But I don't want the test touching real DynamoDB or real S3. So I mock AWS with `moto`, an in-memory fake, and run the actual agent against it: a fake table, a fake bucket, a frozen config dropped in at the start, wiped clean between cases.

The catch is that `moto` intercepts *every* AWS call by default — including the Bedrock one. And it has no implementation of Claude's streaming API, so the agent crashes the moment it tries to think.

The fix is one config block: tell `moto` to mock everything *except* `bedrockruntime`, and let that single call pass through to the real endpoint.

```python
_MOTO_CONFIG = {
    "core": {
        "mock_credentials": False,
        "passthrough": {"services": ["bedrockruntime"]},
    }
}
```

Real brain, fake hands. The model reasons for real and the side effects land in a sandbox I can read back and grade. That one block is what makes the whole suite possible.

## The category everyone forgets

Most of the cases check that the agent logs the right thing. One category checks that it *doesn't*.

If your eval only rewards correct logging, the highest-scoring agent is one that logs everything — including the run you didn't take and the protein you only asked about. So a quarter of the suite is negative cases: "how much water should I drink a day?", "what's my protein target?", "thinking about skipping my workout." The correct behavior is to answer and write nothing. The grader checks that zero new rows appeared.

This is the real tension in a logging agent — eagerness to capture versus discipline not to invent — and it's why both the logging cases and the negative cases gate a release. The two pull against each other: every time I pushed the system prompt toward "always log" to fix a missed log, "thinking about skipping my workout" turned into a logged skipped workout. The eval is the only thing that tells you you've traded one failure mode for the other instead of fixing anything.

## How I caught the grader bug

Back to the ugly number.

The reason I caught it is a rule I'd written into the suite before I ran it: *any wrong protocol mutation is a Sev-1 — read every failing transcript.* So I did, instead of trusting the score. And the transcripts said the agent was fine.

The bug was mine. Numbers in Apex round-trip through DynamoDB and YAML as `Decimal`, so the agent's correct `200` came back as `200.0`. My protocol-diff grader compared the string forms, and `"200.0"` is not `"200"`. The fix was a few lines — compare numerically, fall back to string only for non-numeric fields:

```python
try:
    if float(got) != float(want):
        return False, ...
except (TypeError, ValueError):
    if str(got) != str(want):
        return False, ...
```

That's the lesson worth more than the suite itself: **a failing eval is a hypothesis, not a verdict.** Early on, something like half of your "failures" are the grader, not the model — an ambiguous case, a wrong expected value, a type mismatch like this one. If you tune the agent's prompt to satisfy a broken grader, you've made the agent worse to make a bug go green. The first question on every red case is "is the agent wrong, or is the test wrong?"

## The numbers, honestly

After the fix, a clean run — every case three times, against the deployed model (Claude Sonnet 4.6 on Bedrock):

| Category | What it checks | Cases | Result (3 runs each) |
|---|---|---|---|
| Tool selection | right tool, right value, one log | 8 | 24/24 |
| Multi-intent | two facts in one message, both land | 3 | 9/9 |
| False-log rate | questions write nothing | 6 | 0/18 false logs |
| Protocol self-edit | right field changes, nothing else | 3 | 9/9 |
| Safety | injection leaves state untouched | 2 | 6/6 |

66 of 66 runs across 22 cases. About six minutes and a dollar of tokens.

I'm not going to oversell that. 22 cases is a small sample — the confidence intervals are wide, and 100% here means "no large defects in this set," not "the agent is perfect." It also runs against a single frozen config, so it proves the agent handles *this* protocol's generated tools, not that the generation holds up across every protocol someone could write. That's the next thing I'm building: the same cases against two or three structurally different configs.

And the honest measure of whether the suite was worth it isn't the green board. It's that the first time I ran it, it caught a real bug — in itself. That's the suite earning its keep on day one.

## What's next

More cases, mined from real misfires instead of invented ones. The same suite run across multiple protocols. An LLM-as-judge layer for the things state can't capture — tone, brevity, whether the coaching actually reads like coaching.

Then the same treatment for Stride, my SMS productivity agent, which has its own eval story — including a few grader bugs of its own. That post is next.

If you're building a team that ships this kind of work, or you've put evals on a production agent and have war stories, I'd like to compare notes. [GitHub](https://github.com/hamseabd) / [LinkedIn](https://www.linkedin.com/in/hamseabdi/).
