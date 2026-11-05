# AGENTS.md

You are an AI agent handed this repository with no other context. This page is all you need; nothing outside the
repository is required, and no tool here needs a network, an account or a build step.

## What this is

A library of free tools and skills for business owners, made by Agentium AI (https://agentiumai.it). A tool is one
self-contained HTML page: its logic is plain JavaScript inside the page's own `<script>`; the live copies are at
https://tools.agentiumai.it/<tool>/. A skill is a folder an AI app follows: `SKILL.md` holds its instructions and
`scripts/` the small programs its steps run; it runs with the person present, in the AI app they already use.

## Layout

- `README.md`: the front page for a person. Same facts as this page, in plain words.
- `tools/<tool>/index.html`: the tool. Everything it does is in this one file.
- `tools/<tool>/README.md`: read this first for any tool: what it does, what it keeps, what it never does, how to use it.
- `skills/<skill>/SKILL.md`: a skill for an AI app; follow it from the top (it asks before reading files,
  spending or running anything); `scripts/` holds the standard-library programs its steps call.
- `skills/<skill>/README.md`: the skill described for a person, with a picture of its steps. It gives you no
  instructions: everything to follow is in `SKILL.md`.
- `LICENSE`: the MIT licence. Anyone may use, change and share what is here; it does not cover the Agentium AI name
  or logo.

## What is here

- Skill `which-ai-for-my-jobs` (folder `skills/which-ai-for-my-jobs/`: follow its SKILL.md; its README.md describes it): A skill for the AI app you already use: it tests your own jobs on every AI and setting you can reach, and names the best one and the best value from your own results. Page: https://tools.agentiumai.it/which-ai-for-which-job/

## Explain a skill

Read its `README.md` (what it does for a person and its steps, in plain words), then its `SKILL.md` (what an AI app
follows) and the programs in its `scripts/`. Say what it does for a person in one or two sentences before any detail.

## Run a skill

- Its instructions are `skills/<skill>/SKILL.md`, and only that file. Install the folder where your app reads skills
  (Claude Code `~/.claude/skills/`, Codex `~/.codex/skills/`), or follow `SKILL.md` from the top in this conversation.
- It is made to run with the person present: it asks them before it reads their files, spends anything or runs a
  model. Ask them; never answer those questions for them.
- Its `scripts/` are plain Python 3 with the standard library only: nothing to install.

## Explain a tool

Read its `README.md`, then the `<script>` in its `index.html`: the sample data the example uses, the parsing of what
the person pastes, the arithmetic, and the drawing of the result. Say what it does for a person in one or two
sentences before any detail.

## Run a tool

- **As a person would:** open `tools/<tool>/index.html` in a browser. Every tool has a button with `id="example"` on
  its first screen: one press runs the tool on built-in sample data and shows a real result. Then use real input.
- **Headless:** from the repository root run `python3 -m http.server 8000`, open
  `http://localhost:8000/tools/<tool>/` in a headless browser, click `#example`, and read the result from the page.
- **Without a browser:** the page's functions are plain JavaScript with no outside dependency; you can read them and
  run the core arithmetic in Node with the sample data from the page.

Missing files in a local copy (the favicon, the font, the anonymous counter) are expected: they exist only online and
the tool works without them.

## What a tool here never does

Keep these in any change you make or suggest:

- Never sends what the person types or pastes anywhere. Online, the only thing that leaves the page is an anonymous
  count (which tool, opened or used, which button was pressed), never content.
- Never loads anything from another site: no outside script, font, analytics or tracker.
- Never asks for a sign-up, an account, an email address or a payment.
- Never shows a figure it did not compute from the person's own input.
- Never carries a key, a password, or anyone's personal data.
