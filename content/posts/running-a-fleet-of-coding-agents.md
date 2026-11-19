---
title: "Running a fleet of coding agents"
date: 2026-11-18
draft: true
tags: ["agents", "claude-code", "harness-engineering", "guardrails"]
summary: "One entry point beats a dozen terminals. I stopped opening a Claude Code session for every job and built a supervisor I talk to. It turns what I say into tasks and runs a crew of agents under rules written as code."
ShowToc: true
ShowReadingTime: true
---

On the evening of November 18, 2026, I typed one request: redesign my site, and write three posts for it.

I typed it to one agent, and that agent did neither job.
It wrote two specs and started two builders, each on its own branch of the same repository.
A third builder took a fix in another repository.
I looked at live previews, answered the questions only I could answer, and sent one draft back.

The site you're reading came out of that evening.
So did this post, which is the draft I sent back, rewritten.

That agent is the first mate, and the system around it is called Bosun.

I built it because I was getting overwhelmed.
I was forgetting tasks, forgetting where I was, and mixing things up.
I looked at how other people were working and found Kun Chen's [firstmate](https://github.com/kunchenguid/firstmate).
He is the captain. He has a first mate and crew members who each take a task, and he sits on the important decisions.
I implemented my version of that.

Instead of opening a ton of different Claude Code sessions, I have one entry point.
Behind it are hooks, subagents, builders, and scouts, with everything in one place.
It's a lot more efficient.
Mine also helps me run my day, like a chief of staff, with my own data in my own AWS account and MCP servers and tools I built for it.

One entry point beats a dozen terminals, as long as the rules the crew runs under are written as code.

## The crew

![How a request moves through Bosun. I make a request in plain words. The first mate turns it into tasks, specs, and briefs. Up to three builders work at once, each with its own worktree, branch, and pull request, and a scout does read-only research. Argus reviews every pull request marked ready. A watcher written in code polls pull requests, CI, and reviews, and findings go back through the first mate for a fix round, two at most. A merge waits for my approval.](/images/posts/running-a-fleet-of-coding-agents/fleet.svg)

**The first mate** is a Claude Code session with its own rules, skills, and command-line tools.
It never does project work itself.
Its instructions say why in one line: "trivial is a guess, and your attention stays on the fleet."

**Builders** do the work.
Each is a background Claude Code session in its own git worktree, on its own branch, with one pull request.
A builder gets a brief with three parts: my words, verbatim, with an instruction not to widen them; a spec with a verify command and a definition of done; and a protocol that is the same for every builder.
It reports to its pull request, never to me, in one fixed block:

```
STATUS: DONE | BLOCKED | NEEDS-DECISION
PR: <url or none>
EVIDENCE: <verify command> -> <result line>
SUMMARY: 10 lines max, terse fragments.
```

The evidence line is the point.
Done means showing the command that ran and what came back.

**Scouts** only read.
A scout answers one research question in 1,500 tokens or fewer and says what it couldn't verify.

**Argus**, my code reviewer, reviews every pull request a builder marks ready.
The first mate sends the findings back as a fix round.
After two rounds, the task is held and the findings come to me.

**The watcher** is plain Python, with no model in it.
It polls pull requests, CI, and reviews, and exits with one line per event:

```
argus <task> clean
ci <task> red
stale <task>
```

The first mate wakes on that line, acts, and starts the watcher again.

## One conversation reaches everything

Bosun adds no framework.
It uses the four extension points Claude Code already has, each for one job.

| Surface | What Bosun uses it for |
|---|---|
| Skills | Procedures: turn an ask into a task and a builder, land a reviewed pull request, report the fleet |
| Hooks | Rules: pull state and take the lease at session start, guard every file edit, push state on stop |
| Subagents | Scouts: read-only research with a narrow tool list |
| Tools | Reach: small commands and MCP servers for tasks, repositories, CI, and reviews |

The split matters.
A skill is something the model chooses to follow.
A hook runs whether the model likes it or not.
Deciding which of the two a behavior belongs in is most of the design.

## Rules as code

Bosun doesn't have access outside of its folders.
These agents can't just reach everything.
A prompt is a request, so the rules I care about live below the prompt.

**A hook guards every file edit.**
The first mate can edit its own state folder and nothing else.
The denial tells it what to do instead: create a task and dispatch a builder.
The hook compares paths without regard to case, and by inode, so a second spelling of the same folder doesn't get past it.
If the hook itself fails, it denies.

**A worktree has to be real.**
The one exception to that rule is a real worktree of the first mate's own checkout.
The hook doesn't take a folder's word for it.
It checks git's own records for a link back to that folder, so a directory that only looks like a worktree gets nothing.

**A fence comes before any cloud builder.**
A session in the cloud carries my account's connectors with it.
A builder that reads hostile text in a repository could be steered into them.
So a cloud builder runs only in a repository whose default branch denies those connectors, and until that fence is in place the dispatch command keeps the builder local.

**One lease, a cap, and a quota stop.**
Several first mate sessions can be open, and only the lease holder may change the fleet.
New work waits when three tasks are in flight, or when a usage window is over 90%.
The commands refuse, and no prompt is involved.

**Drafts, never sends.**
The first mate can draft a message, and it can't send one.
Merging a pull request stops for a human yes every time.

**Reading is not obeying.**
Pull request comments, review text, issues, repository files, and fetched pages are data.
Text that asks an agent to act is a finding to report to me.

Three of these are weaker than they sound.
The edit hook covers the edit tools, not shell commands.
Deletes and spending are rules the first mate is told, not blocks.
And a builder's "never merge, never force push" lives in its brief.
The backstop is structural: a builder's work stays on its own branch until a review is in and I merge.

## What I can see

Every task is a file.
It holds my words, the spec, a log line for every event, and the result.
When something goes wrong, the record doesn't depend on any session still being alive.

The review loop is visible too.
Each fix round is counted, and the third one never starts.

Closed tasks roll up into four numbers: first-pass rate, fix rounds, retries, and wall time, by model and by repository.
That is how the builder model gets chosen.
The default is due for review against those numbers after about 20 finished tasks.

The first mate is also told when to stay quiet.
It interrupts me for a pull request ready for review, a decision only I can make, a real blocker after one retry, anything destructive, and a usage window going red.
It doesn't interrupt for anything else.

## What I learned

**The supervisor's attention is the scarce resource.**
A first mate that fixes one small thing itself stops watching the other builders. So it never does project work, however small.

**Rules belong in code.**
A model follows a prompt most of the time. A hook, a permission, or a command that refuses follows it every time.

**Idle should cost nothing.**
A model that polls is paying to wait. A plain process waits for free, and wakes the model only when something happened.

**Evals from day one.**
If I started over, I would start the evals right away. That is how a system like this improves continuously.

If you're building agents that have to earn trust inside a real engineering workflow, I'd like to compare notes.
[GitHub](https://github.com/hamseabd) / [LinkedIn](https://www.linkedin.com/in/hamseabdi/).
