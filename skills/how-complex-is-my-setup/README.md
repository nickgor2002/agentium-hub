# How complex is your setup?

> A free skill for the AI app you already use: it reads what you already have, tells you how complex your setup is, and gives your next moves, the simplest first.

**Ask your AI:** "How complex is my AI setup, and what should I simplify or add next?"

[See it explained online](https://tools.agentiumai.it/how-complex-is-my-setup/) · [Download it as a zip](https://tools.agentiumai.it/how-complex-is-my-setup/skill/how-complex-is-my-setup.zip) · [Read what your AI app follows](SKILL.md)

## How it works

```mermaid
flowchart LR
  s1["1. It looks first"]:::c1
  s2["2. Your jobs, one line each"]:::c2
  s3["3. Four reads on each job"]:::c3
  s4["4. Where you stand"]:::c4
  s5["5. Three moves at most"]:::c5
  s6["6. A page you keep"]:::c6
  s1 --> s2 --> s3 --> s4 --> s5 --> s6
  s6 ~~~ pad["················"]:::pad
  classDef c1 fill:#8B8AF0,stroke:#8B8AF0,color:#0f172a
  classDef c2 fill:#F08A6C,stroke:#F08A6C,color:#0f172a
  classDef c3 fill:#2EC4B6,stroke:#2EC4B6,color:#0f172a
  classDef c4 fill:#E8B04A,stroke:#E8B04A,color:#0f172a
  classDef c5 fill:#A98BF0,stroke:#A98BF0,color:#0f172a
  classDef c6 fill:#5FB3F0,stroke:#5FB3F0,color:#0f172a
  classDef pad fill:none,stroke:none,color:transparent
```

1. **It looks first.** It reads what the AI apps on your computer already have set up: standing instructions, skills, connected tools, anything that runs by itself. Names and counts only.
2. **Your jobs, one line each.** One line for each job you give to AI, as it is done today, not as you wish it were.
3. **Four reads on each job.** Who does it, what it can touch, where its rule lives, and who checks it.
4. **Where you stand.** A ladder from 0 to 4: by hand, a chat you ask, an agent that acts when asked, an agent that acts by itself, several agents together.
5. **Three moves at most.** The simplest first: take away what you do not use, shorten what is read before every answer, move a rule up for anything that can send, pay or delete, add a check to what runs by itself.
6. **A page you keep.** On your yes, it keeps one page in a folder called my-ai-setup: the date, your map, where you stand, the moves and what you chose.

## How to use it

1. Download this folder, or the zip from [its page](https://tools.agentiumai.it/how-complex-is-my-setup/).
2. Give it to your AI app. Claude Code: put the folder in `~/.claude/skills/`. Codex: `~/.codex/skills/`. Any other AI app: give it `SKILL.md` and ask it to follow it.
3. Ask it: "How complex is my AI setup, and what should I simplify or add next?"

It asks you before it reads your files, spends anything or runs anything.

## What is in this folder

| File | What it is |
|---|---|
| [`SKILL.md`](SKILL.md) | the instructions your AI app follows, in plain words: read them first |
| [`scripts/setup_reader.py`](scripts/setup_reader.py) | a small program its steps run (Python 3, nothing to install) |
| `README.md` | this page, for people. Your AI app follows `SKILL.md`, not this page |

**For an AI agent:** everything to follow is in [SKILL.md](SKILL.md); this page only describes it.

---

Free, no sign-up. Made by Niccolò Goretti, founder of [Agentium AI](https://agentiumai.it). More free tools: [tools.agentiumai.it](https://tools.agentiumai.it) · [the whole library](../../README.md)
