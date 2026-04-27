---
title: "About"
url: "/about/"
summary: about
hidemeta: true
ShowToc: false
ShowReadingTime: false
ShowWordCount: false
---

I'm Hamse, a software engineer with five years of experience, currently focused on production AI agents.

I run three deployed agentic systems on AWS:

- **Stride** — an SMS productivity coach. [Strands SDK](https://strandsagents.com) + Claude Sonnet, 19 tools, full A2P 10DLC compliance pipeline, single-table DynamoDB.
- **Maxy** — a proactive Telegram health bot. Bedrock + Strands, 9 EventBridge schedules driving check-ins throughout the day, knowledge-base-grounded AI assistant.
- **Stock Intel** — a Telegram market intelligence platform. 27 commands, 8 automated scanners, SQS alert pipeline, AI-powered analysis with cost-conscious model routing (80% of commands skip AI on purpose).

I write here about what it actually takes to ship and run agents in production:

- Agent architecture and tradeoffs
- Eval strategies that catch real bugs (pytest + LLM-as-judge, no SaaS)
- Observability for tool-using systems
- Cost optimization — how I keep three production agents running on $1–3/month

For hiring managers and engineers who care about real production AI systems, not demos. New posts roughly weekly.

## Contact

- **GitHub:** [hamseabd](https://github.com/hamseabd)
- **LinkedIn:** [hamseabdi](https://www.linkedin.com/in/hamseabdi/)
- **Email:** hmseabd at gmail
