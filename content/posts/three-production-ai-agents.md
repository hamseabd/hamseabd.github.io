---
title: "I built my own support staff. Three AI agents, deployed."
date: 2026-05-13
draft: false
tags: ["agents", "aws", "production", "evals"]
summary: "I needed a Scrum master, a health coach, and a market analyst. Instead of paying for them, I built them. Here's what I built, what's broken, and what I'm fixing next."
ShowToc: false
ShowReadingTime: true
---

I work a full-time engineering job and run side projects, track my health, and trade my own stock portfolio. At some point I realized I was doing all of it without any support staff.

Most people in that situation buy subscriptions. I'm an engineer, so I built agents instead.

All three are running in production. I use them every day.

## Stride — my personal Scrum master

At work, I finish what I commit to. Someone checks what I said I'd do, notices when I'm overloaded, and helps me adjust. Accountability is just part of the system.

My side projects? They die. I start strong, miss a few days, and quietly move on. I've tried the apps, the planners, the systems. The problem was never the tool — it was that nothing followed up.

So I built Stride. It texts me Monday to plan my week and break my goals down into tasks. It texts me every morning with what I said I'd do. It checks in at night. On Fridays, it shows me what I actually finished versus what I planned. And after a few weeks, it started pointing out things I couldn't see myself — like how I overcommit every Monday and underestimate anything that involves writing.

No app. No dashboard. Just something in my texts that knows my patterns better than I do.

Building it forced an architectural decision I'd make again on anything that uses LLMs at scale.

The decision I'm most pleased with: Stride uses two models. Claude Sonnet handles the full agent loop — 19 tools, multi-step reasoning, DynamoDB reads and writes across 14 entity types in a single-table design. Claude Haiku handles intent classification only, figuring out whether an incoming message is a check-in, a blocker, or something else. Haiku is 25x cheaper than Sonnet and intent detection doesn't need reasoning — just pattern matching. That one distinction keeps the cost at $1/month while keeping the quality where it needs to be.

256 tests. A2P 10DLC SMS compliance. Full Powertools observability.

## Maxy — my health and accountability bot

Tracking health feels easy until you're doing it seriously. When you're managing training, nutrition, water, sleep, and supplements at the same time, you're not forgetting because you're lazy — you're forgetting because there are too many things to remember.

I'd log breakfast and forget water. Hit my workout and forget to log protein. Go to bed and realize I couldn't remember if I'd taken my supplements or just thought about taking them.

So I built Maxy. It doesn't wait for me to open an app. It messages me — morning check-in, water reminders through the day, caffeine cutoff at 2pm, gym check-in at 5pm, bedtime checklist. I just reply. Maxy logs it, tracks it against my targets, and tells me where I'm falling short before the day is over.

The difference between a good week and a bad one stopped being motivation. It became whether I replied to my texts.

Building it raised a question I hadn't thought through: how much should the AI know, and how do you stop it from making things up?

The non-obvious piece: the AI assistant is grounded entirely in locked research docs — markdown files covering training, nutrition, supplements, sleep — loaded into the system prompt at boot. Maxy cannot answer outside that knowledge base. For a health bot, that constraint is the feature. I don't want a hallucinated answer about recovery protocols; I want the answer I wrote down when I did the research.

89 tests. 14 Strands tools. $0/month — runs entirely within the AWS free tier.

## Stock Intel — my market intelligence platform

Following the markets when you have a real job means you're always catching up. I remember sitting in a meeting while one of my positions moved 8% and finding out two hours later. By then it was priced in and the moment was gone.

I looked at Unusual Whales. It does most of what I wanted. But it's $99/month, it shows me everything, and I still had to do the thinking myself.

So I built Stock Intel. It watches my portfolio, tracks the stocks I care about, and runs eight scanners — options flow, dark pool, congressional trades, technical signals, earnings, breaking news. When something worth knowing happens, it messages me on Telegram. I don't open it unless it does.

The goal was never more information. It was only the right information, already filtered, already on my phone.

That constraint shaped every architectural decision.

The architectural decision that mattered most: 22 of the 27 commands never touch Claude at all. They're pure Python — fast, free, deterministic. Only 5 commands route to the AI, and those first gather all the data with code, then send a compact summary for Claude to reason over. That's roughly $0.02 per AI command. Every command in the codebase is annotated "Direct ($0)" or "AI (~$0.02)." Cost discipline has to be built into the architecture, not bolted on later.

376 tests. $3/month total including Claude API, versus $99/month for the commercial alternative.

## What I'm not happy with

None of them have eval suites in CI. Most production AI systems have the same problem — we ship fast, the code works, and the eval infrastructure gets deferred until something breaks in front of a user.

That's the gap a senior AI engineer notices first. Unit tests pass. The agent still hallucinates a tool argument on an edge case, or loses context after a prompt refactor, or selects the wrong tool when two are plausible. None of that surfaces in pytest. It surfaces in production, the second time a user hits the same bad path.

Stride once routed an update to the wrong project because a user mentioned an old one in passing. The test suite didn't catch it. A user did.

Observability is also uneven. Stride has Powertools and X-Ray. Maxy uses stdlib logging. Stock Intel has a logger module but no SLO on its 8 automated scanners — they could fail silently for days before I'd notice.

This is what "works in production" looks like when one engineer ships fast. It's also what "doesn't pass a senior bar" looks like.

## What I'm doing next

This series is part of a deliberate move into a senior AI engineer role. I'm not waiting until the work is perfect — I'm publishing the rework as it happens, because the thinking is the artifact.

I'm reworking all three from deployed to interview-grade. Eval suites in CI — LLM-as-judge rubrics, deterministic tool-call assertions, regression cases for past bugs. Powertools and X-Ray across all three. Pydantic on every tool input, retries with backoff, error envelopes the agent can recover from.

I'm publishing weekly on the specifics — what the eval setup looks like, what broke when I added it, what the real observability numbers look like in practice. If you're building AI agents and want to follow along, this is the work.

Next up: Stride's eval suite. I wrote the full design before touching any code — 12 deterministic assertions, 7 LLM-as-judge rubrics, a calibration protocol for keeping evals honest over time. That post is next week.

If you're building a team that ships this kind of work, or you've been through your own production agent rework and have lessons worth sharing, I'd like to hear from you. [GitHub](https://github.com/hamseabd) / [LinkedIn](https://www.linkedin.com/in/hamseabdi/).
