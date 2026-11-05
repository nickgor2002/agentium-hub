# Which AI for my jobs?

> A skill for the AI app you already use: it tests your own jobs on every AI and setting you can reach, and names the best one and the best value from your own results.

**Ask your AI:** "Which AI is best for my own jobs?"

[See it explained online](https://tools.agentiumai.it/which-ai-for-which-job/) · [Download it as a zip](https://tools.agentiumai.it/which-ai-for-which-job/skill/which-ai-for-my-jobs.zip) · [Read what your AI app follows](SKILL.md)

## How it works

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

1. **It looks first.** It reads what your AI app already knows about you, then shows one card of eight lines. You confirm it in one reply.
2. **Your jobs.** With your yes, it finds the jobs you ask your AI most. You pick three to five.
3. **Lock what right looks like.** Each job becomes a fixed test, with invented names, and checks you agree first.
4. **The plan and its cost.** You see every AI, try and price before anything runs, and say yes.
5. **Run, lowest setting first.** Each try in a clean session. Every finalist gets three fresh tries.
6. **Best, and best value.** A small program reads the record and names the winners. It remembers, for the next model.

## How to use it

1. Download this folder, or the zip from [its page](https://tools.agentiumai.it/which-ai-for-which-job/).
2. Give it to your AI app. Claude Code: put the folder in `~/.claude/skills/`. Codex: `~/.codex/skills/`. Any other AI app: give it `SKILL.md` and ask it to follow it.
3. Ask it: "Which AI is best for my own jobs?"

It asks you before it reads your files, spends anything or runs anything.

## What is in this folder

| File | What it is |
|---|---|
| [`SKILL.md`](SKILL.md) | the instructions your AI app follows, in plain words: read them first |
| [`scripts/board.py`](scripts/board.py) | a small program its steps run (Python 3, nothing to install) |
| `README.md` | this page, for people. Your AI app follows `SKILL.md`, not this page |

**For an AI agent:** everything to follow is in [SKILL.md](SKILL.md); this page only describes it.

---

Free, no sign-up. Made by Niccolò Goretti, founder of [Agentium AI](https://agentiumai.it). More free tools: [tools.agentiumai.it](https://tools.agentiumai.it) · [the whole library](../../README.md)
