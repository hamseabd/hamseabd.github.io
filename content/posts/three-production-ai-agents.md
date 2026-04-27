---
title: "I built three production AI agents on AWS. Here's what I'm doing next."
date: 2026-04-27
draft: true
tags: ["agents", "aws", "production", "career"]
summary: "An SMS productivity coach, a proactive Telegram health bot, and a market intelligence platform. None of them used to have eval suites in CI. Here's why that's about to change — and what I'll publish along the way."
ShowToc: false
ShowReadingTime: true
---

> *Draft — replace with your real intro before publishing. The structure below is a starting scaffold per the pivot plan's "post #0" deliverable. Aim for 700–900 words, conversational tone, written like you're explaining to a peer engineer over coffee.*

## What I've built

Over the past year, I built three production AI agents on AWS while working full-time as a software engineer. All three are deployed, tested, observable, and run on $1–3/month total.

**Stride** is an SMS productivity coach. Text it your goals, check in daily, get a weekly review. The Scrum framework runs entirely under the hood; users see only plain language. Built on the [Strands Agents SDK](https://strandsagents.com) with Claude Sonnet, 19 tools, full A2P 10DLC compliance, single-table DynamoDB design with 14 entity types. 104 tests.

**Maxy** is a Telegram health and accountability bot. Unlike most agents, it's *proactive* — 9 EventBridge schedules drive check-ins throughout the day instead of waiting for the user. Bedrock + Strands, knowledge-base-grounded AI assistant, peptide cycle date math, intro-stage dose escalation logic. 7 test files.

**Stock Intel** is a Telegram market intelligence platform — like Unusual Whales, but mine, for $3/month. 27 commands across portfolio, research, intelligence, and AI analysis. 8 automated scanners (price thresholds, options flow, congressional trades, dark pool, technicals, earnings, news). 286 tests.

Three production systems, three different stacks, three different problems.

## What I'm not happy with

None of them have eval suites in CI.

That's the gap a senior AI engineer notices first. Unit tests are necessary but not sufficient for systems where the output is *generated*, not computed. A regression in tool selection, a prompt that loses context after a refactor, an LLM that quietly hallucinates a tool argument — none of these get caught by `pytest tests/`. They show up in production, when a user hits the same bad path the second time.

Observability is also uneven. Stride has Powertools and X-Ray. Maxy uses stdlib `logging`. Stock Intel has a logger module but no SLO on its 8 scheduled scanners — they could be silently failing for days.

Tool design is good but not great. Pydantic validators on inputs are inconsistent. Retries with backoff are missing on some external HTTP calls. Error envelopes that the agent can recover from aren't standardized.

This is what "works in production" looks like when one engineer ships fast. It's also what "doesn't pass a senior bar" looks like.

## What I'm doing next

Over the next five weeks, I'm reworking all three from "deployed" to "interview-grade." Specifically:

1. **Eval suites in CI for each app.** Pytest + LLM-as-judge with explicit rubrics, regression cases for past bugs, deterministic tool-call assertions. Blocks merge on regression. No SaaS — owning the primitives is the senior signal.
2. **Observability you can demo.** Powertools across all three, correlation IDs through tool calls, X-Ray subsegments, custom metrics for latency, tool error rate, eval pass rate, and cost-per-conversation.
3. **Hardened tool design.** Pydantic on every tool input, retries with backoff, structured error envelopes the agent can recover from, parallel tool calls where they make sense.
4. **Public READMEs that read like a senior engineer wrote them.** Design tradeoffs, failure modes considered, eval results, real cost numbers.

And I'm publishing as I go. Roughly weekly, here, on the deeper technical posts:

- *Adding real evals to a production SMS agent: 30 cases, what broke, what got better*
- *Three production AI agents, three eval strategies: SMS, scheduled, and command-driven*
- *Why my three production agents cost $1–3/month: cost optimization patterns from running them solo*

After that, I'll be looking for a senior AI engineer role at a Big Tech AI org or a mature AI-native company — somewhere I can grow, learn, and ship the kind of work I'm doing now at scale.

## Why publish at all

Most engineers don't write. The ones who do compound credibility while they sleep. A blog post is also the cheapest way to find out whether your story actually lands — if a stranger with no context can read it and care, the story is real. If they can't, the story isn't real yet.

I'd rather write five honest posts that 50 right people read than thirty posts that nobody finishes.

If any of this resonates — particularly if you're hiring for the kind of role I described, or you've reworked your own production agents and have lessons I should steal — I'd love to hear from you. Find me at [github.com/hamseabd](https://github.com/hamseabd) or [linkedin.com/in/hamseabdi](https://www.linkedin.com/in/hamseabdi/).

More soon.
