---
title: "About"
url: "/about/"
layout: "about"
summary: about
hidemeta: true
ShowToc: false
ShowReadingTime: false
ShowWordCount: false
---

I'm Hamse, an AI engineer with five years of production experience, currently building agentic systems at Travelers and on AWS.

**Day job:** At Travelers I built a multi-agent underwriting system — a reader agent feeding 11 parallel evaluator agents on Bedrock via Strands SDK — that replaced a 23-minute manual expert review with citation-backed approve/decline/escalate decisions. I designed the LLM-as-judge harness behind it: cross-validated across Claude and Amazon Nova to eliminate same-model bias, calibrated to 89% agreement at high confidence, with human-in-the-loop routing for low-confidence cases. An independent judge rated the system more accurate than the GPT-4 incumbent on 72% of 109 disagreements across 891 evaluations.

**Personal projects:** I run three deployed agentic systems on AWS:

- **Stride** — an SMS productivity coach. [Strands SDK](https://strandsagents.com) + Claude Sonnet 4.6, 21 tools, Haiku intent classifier for cost control, single-table DynamoDB (14 entity types), full A2P 10DLC compliance.
- **Apex** — a proactive Telegram health accountability bot. Bedrock + Strands, protocol YAML drives dynamic tool generation at cold start — add a metric to config and the agent gains a tool, zero code changes. 9 EventBridge schedules drive check-ins throughout the day. An eval harness grades the agent's outcomes against database state, not its transcripts.
- **Stock Intel** — a Telegram market intelligence platform. 27 commands, 8 automated scanners, SQS alert pipeline. 80% of commands skip Claude entirely; AI routes only where it adds real value.

I write here about what it takes to ship and run agents in production: multi-agent architecture, eval strategies that catch real bugs, LLM observability, and keeping three production systems running on $1–3/month.

For hiring managers and engineers who care about real production AI — not demos. New posts roughly weekly.

## Contact

- **GitHub:** [hamseabd](https://github.com/hamseabd)
- **LinkedIn:** [hamseabdi](https://www.linkedin.com/in/hamseabdi/)
- **Email:** hmseabd at gmail
