---
title: "About"
url: "/about/"
layout: "about"
description: "Hamse Abdi is a software engineer in Atlanta. He builds agentic AI systems, the evals that gate them, and the platform they run on."
hiddenInRss: true
---

I'm Hamse, a software engineer in Atlanta.
I build agentic AI systems, the evals that gate them, and the platform they run on.
I have been at Travelers since 2021.

## Experience

### Software Engineer, Agentic AI

Travelers, 2023 to present

- Took a generative AI pilot to production as the underwriters' daily workbench and cut case review from roughly 6 hours to 30 minutes.
- Designed and built a multi-agent renewal system on the Strands SDK and Bedrock AgentCore, now in pilot with early users.
- Built the eval gate that every prompt and model change has to pass. It caught a model-upgrade regression before release, fixed with a prompt edit.
- Put the guardrails in code, not prompts. Agents never write to policy systems, and an underwriter approves every adverse decision.
- Routed agent tools through an MCP gateway with Okta handling identity, and sent OpenTelemetry traces to Braintrust and Datadog.
- Led both systems through Legal, Compliance, AI Risk, and Architecture review.

### Full Stack Software Engineer

Travelers, 2021 to 2023

- Built a REST API platform with OpenAPI contracts that product teams adopted. The AI platform still runs on it.
- Built the team's first generative AI pilot end to end in 2023. It led to the production build.

## Projects

### Argus

Multi-agent code reviewer on the Claude Agent SDK.

- A lead agent hands the diff to 6 specialist subagents, and a verifier tries to refute each finding before it posts.
- Its own pull requests are gated on seeded-bug evals. The baseline catches 21 of 22 bugs on a 32-case corpus.
- Runs as a GitHub Action on a Claude subscription token at $0 a review.

[Code](https://github.com/hamseabd/argus) and [write-up]({{< ref "posts/argus-code-review-agent" >}}).

### Bosun

Supervised fleet of coding agents, in a private repository.

- A supervisor agent turns a plain request into a spec and hands it to parallel builder agents across repos, each on its own branch.
- It watches CI and Argus reviews, sends findings back to the builders for fix rounds, and brings decisions to me.
- Merges, sends, and spending stay behind human approval.

### Stride

Proactive Agile coach over SMS.

- Texts first, using a no-model scheduler and a Haiku router in front of a Sonnet agent with 21 tools.
- Ran a serverless private beta with 14,004 scheduler runs and zero errors, at two cents a turn.
- 345 tests and 97 eval checks gate every pull request.

[Code](https://github.com/hamseabd/Stride).

## Skills

AI and agents
: Strands Agents SDK, Bedrock AgentCore, LangGraph, Claude Agent SDK, Claude Code, MCP, Azure OpenAI, RAG, OpenSearch

Evals and tracing
: LLM-as-judge, Braintrust, OpenTelemetry, Datadog, CloudWatch, X-Ray, GitHub Actions, pytest

Full stack
: Python, SQL, TypeScript, JavaScript, FastAPI, Pydantic, Node.js, React, Next.js, OpenAPI, OAuth 2.0, Okta, PostgreSQL, MongoDB, Redis, RabbitMQ, Kafka

AWS and infra
: Lambda, API Gateway, Step Functions, EventBridge, SQS, S3, CloudFront, EC2, EKS, DynamoDB, Cognito, Docker, Terraform

## Education

University of Minnesota, Twin Cities. B.S. Computer Science, 2021.

AWS Certified Developer, Associate.

## Contact

[Resume](/resume.pdf), [GitHub](https://github.com/hamseabd), [LinkedIn](https://www.linkedin.com/in/hamseabdi/), or [hmseabd@gmail.com](mailto:hmseabd@gmail.com).
