<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="https://tools.agentiumai.it/kit/logo.png"><img src="https://tools.agentiumai.it/kit/logo-dark.png" alt="Agentium AI" height="30"></picture></p>

# Agentium Hub

Free tools and skills for people who run or work in a business, by Niccolò Goretti, founder of Agentium AI. Each
one solves one small, real problem. A tool runs entirely in your browser and keeps nothing you type; a skill runs in
the AI app you already use, on your own computer, and asks before it reads, spends or runs anything.

- **Use them online:** https://tools.agentiumai.it
- **Who makes them:** Agentium AI (https://agentiumai.it) helps companies bring AI agents into their day to day and
  teaches their team to build, run and own them. These tools are the free part: take what helps.

## Tools and skills

### [Which AI for my jobs?](skills/which-ai-for-my-jobs/) · a skill

A skill for the AI app you already use: it tests your own jobs on every AI and setting you can reach, and names the best one and the best value from your own results.

**Ask your AI:** "Which AI is best for my own jobs?"

<details><summary>How it works, in 6 steps</summary>

```mermaid
flowchart LR
  s1["1. It looks first"]:::c1
  s2["2. Your jobs"]:::c2
  s3["3. Lock what right looks like"]:::c3
  s4["4. The plan and its cost"]:::c4
  s5["5. Run, lowest setting first"]:::c5
  s6["6. Best, and best value"]:::c6
  s1 --> s2 --> s3 --> s4 --> s5 --> s6
  s6 ~~~ pad["················"]:::pad
  classDef c1 fill:#8B8AF0,stroke:#8B8AF0,color:#0f172a
  classDef c2 fill:#F08A6C,stroke:#F08A6C,color:#0f172a
  classDef c3 fill:#2EC4B6,stroke:#2EC4B6,color:#0f172a
  classDef c4 fill:#E8B04A,stroke:#E8B04A,color:#0f172a
  classDef c5 fill:#A98BF0,stroke:#A98BF0,color:#0f172a
  classDef c6 fill:#F07AA8,stroke:#F07AA8,color:#0f172a
  classDef pad fill:none,stroke:none,color:transparent
```

</details>

[Open the folder](skills/which-ai-for-my-jobs/) · [See it explained online](https://tools.agentiumai.it/which-ai-for-which-job/)

## Use a skill from this repository

1. Download or clone this repository.
2. Put the skill's folder (`skills/<skill>/`) where your AI app reads skills (Claude Code `~/.claude/skills/`, Codex
   `~/.codex/skills/`), or give any AI app its `SKILL.md` and ask it to follow it.
3. Its `README.md` says what it does and shows its steps, in plain words.

## What every skill promises

- It runs in the AI app you already use, on your own computer.
- It asks you before it reads your files, spends anything or runs a model.
- No sign-up, no account, nothing to buy from us.

## What is in here

| Path | What it is |
|---|---|
| `skills/<skill>/README.md` | a skill explained for people: what it does, a picture of its steps, how to use it |
| `skills/<skill>/SKILL.md` | a skill for the AI app you already use; `scripts/` holds the small programs its steps run |
| `AGENTS.md` | the map for an AI agent |
| `LICENSE` | the MIT licence |

## Licence

Free to take, change and share under the MIT licence (see `LICENSE`). The licence does not cover the Agentium AI name
or logo.
