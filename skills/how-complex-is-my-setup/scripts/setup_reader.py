#!/usr/bin/env python3
"""setup_reader: the same reading of an AI setup, every time it is asked.

    python3 setup_reader.py look       what the AI apps on this computer have set up (reading only)
    python3 setup_reader.py read       the agreed map of jobs on standard input -> where you stand and your next moves
    python3 setup_reader.py changed    the same map on standard input -> what changed since the last saved reading
    python3 setup_reader.py save       the same map on standard input -> keeps the reading (only after the person's yes)

What it promises, in code:
- It reads; it never changes, removes or switches off anything in a setup.
- From settings files it takes NAMES and COUNTS only: the name of a connected tool, how many rules, which kind of
  guard. It never prints a value, a key, a password, a command line or the text of a hook.
- It never opens chats, mail, documents or login files, and it sends nothing anywhere (no network code in this file).
- `save` is the only command that writes, and only inside the folder ~/my-ai-setup (or MY_AI_SETUP_HOME); where the
  app may not write there, inside a folder my-ai-setup in the folder the person is working in, and it says which.

Standard library only. Python 3.8 or newer.
"""
import datetime
import json
import os
import plistlib
import re
import subprocess
import sys

HOME = os.path.expanduser("~")
KEEP = os.environ.get("MY_AI_SETUP_HOME") or os.path.join(HOME, "my-ai-setup")
# A line the apps' makers draw themselves: Claude Code warns when an instruction file gets large, and Codex stops
# reading its instruction files after 32 KiB unless that setting was raised. 40,000 characters read before every
# answer is this skill's own line for "heavy"; under it the number is simply shown.
HEAVY_CHARS = 40000
CODEX_DOC_BYTES = 32768
AI_WORDS = ("claude", "codex", "gemini", "openclaw", "hermes", "ollama", "aider", "goose", "opencode", "llm")

WHO = {"hand": 0, "chat": 1, "asked": 2, "alone": 3, "several": 4}
RULE_WORDS = {"none": "nowhere", "words": "in words", "setting": "in a setting", "code": "in code"}
STEP_WORDS = ("done by hand", "a chat you ask", "an agent that acts when you ask",
              "an agent that acts by itself", "several agents working together")
REACH = ("read", "write", "send", "pay", "delete")
RISKY = ("pay", "delete", "send")                      # what cannot be taken back, the costliest first
RULE = ("none", "words", "setting", "code")
WRONG = ("little", "some", "a lot")


def short(path):
    return "~" + path[len(HOME):] if path.startswith(HOME) else path


def text_len(path):
    try:
        with open(path, "rb") as f:
            raw = f.read()
        return len(raw.decode("utf-8", "replace")), len(raw)
    except OSError:
        return None


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def names_in(folders, need=None, ext=None):
    """Names only: the folders (holding `need`) or the files (ending `ext`) inside each folder, a folder met twice
    read once (run from the home folder, the project's own folder IS the app's folder)."""
    out = []
    for folder in once(folders):
        out += _names_in(folder, need, ext)
    return sorted(set(out))


def once(paths):
    seen, out = set(), []
    for p in paths:
        real = os.path.realpath(p)
        if real not in seen:
            seen.add(real)
            out.append(p)
    return out


def _names_in(folder, need, ext):
    out = []
    try:
        for n in sorted(os.listdir(folder)):
            p = os.path.join(folder, n)
            if n.startswith("."):
                continue
            if need and os.path.isfile(os.path.join(p, need)):
                out.append(n)
            elif ext and n.endswith(ext) and os.path.isfile(p):
                out.append(n[:-len(ext)])
    except OSError:
        pass
    return out


def instructions(paths):
    seen, out = set(), []
    for p in paths:
        real = os.path.realpath(p)
        size = text_len(p)
        if size is None or real in seen:
            continue
        seen.add(real)
        out.append({"file": short(p), "characters": size[0], "bytes": size[1]})
    return out


def look_claude(cwd):
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude")
    if not os.path.isdir(home):
        return None
    proj = os.path.join(cwd, ".claude")
    ins = instructions([os.path.join(home, "CLAUDE.md"), os.path.join(cwd, "CLAUDE.md"),
                        os.path.join(proj, "CLAUDE.md"), os.path.join(cwd, "CLAUDE.local.md")])
    tools = set()
    for state in once([os.path.join(home, ".claude.json"), os.path.join(HOME, ".claude.json")]):
        s = load_json(state)
        tools.update((s.get("mcpServers") or {}).keys())
        tools.update((((s.get("projects") or {}).get(cwd) or {}).get("mcpServers") or {}).keys())
    tools.update((load_json(os.path.join(cwd, ".mcp.json")).get("mcpServers") or {}).keys())
    rules = {"allow": 0, "ask": 0, "deny": 0}
    mode, hooks, plugins = None, {}, set()
    for sf in once([os.path.join(home, "settings.json"), os.path.join(proj, "settings.json"), os.path.join(proj, "settings.local.json")]):
        s = load_json(sf)
        perm = s.get("permissions") if isinstance(s.get("permissions"), dict) else {}
        for k in rules:
            rules[k] += len(perm.get(k) or [])
        mode = perm.get("defaultMode") or mode
        for event, items in (s.get("hooks") or {}).items():
            hooks[event] = hooks.get(event, 0) + (len(items) if isinstance(items, list) else 1)
        plugins.update(k for k, on in (s.get("enabledPlugins") or {}).items() if on)
    return {"app": "Claude Code", "instructions": ins,
            "skills": names_in([os.path.join(home, "skills"), os.path.join(proj, "skills")], need="SKILL.md"),
            "helpers": names_in([os.path.join(home, "agents"), os.path.join(proj, "agents")], ext=".md"),
            "connected_tools": sorted(tools), "add_ons": sorted(plugins),
            "rules_as_settings": {"allowed without asking": rules["allow"], "ask first": rules["ask"], "never": rules["deny"],
                                  "mode": mode if isinstance(mode, str) else None},
            "rules_in_code": {"guards": hooks, "can_refuse_an_action": "PreToolUse" in hooks}}


def look_codex(cwd):
    home = os.environ.get("CODEX_HOME") or os.path.join(HOME, ".codex")
    if not os.path.isdir(home):
        return None
    tools, top, in_top = [], {}, True
    try:
        with open(os.path.join(home, "config.toml"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                m = re.match(r"^\[mcp_servers\.(?:\"([^\"]+)\"|([A-Za-z0-9_-]+))", line)   # the tool's name; its own sub-tables repeat it
                if m:
                    tools.append(m.group(1) or m.group(2))
                if line.startswith("["):
                    in_top = False
                m = re.match(r"^(approval_policy|sandbox_mode)\s*=\s*\"([a-z-]+)\"", line)
                if m and in_top:
                    top[m.group(1)] = m.group(2)
    except OSError:
        pass
    hooks = {}
    for event, items in (load_json(os.path.join(home, "hooks.json")).get("hooks") or {}).items():
        hooks[event] = len(items) if isinstance(items, list) else 1
    ins = instructions([os.path.join(home, "AGENTS.md"), os.path.join(cwd, "AGENTS.md")])
    for i in ins:
        i["past_the_app_default_limit"] = i["bytes"] > CODEX_DOC_BYTES
    return {"app": "Codex", "instructions": ins, "skills": names_in([os.path.join(home, "skills")], need="SKILL.md"),
            "helpers": [], "connected_tools": sorted(set(tools)), "add_ons": [],
            "rules_as_settings": {"asks before acting": top.get("approval_policy"), "may touch": top.get("sandbox_mode")},
            "rules_in_code": {"guards": hooks, "can_refuse_an_action": any(re.sub(r"[^a-z]", "", e.lower()) == "pretooluse" for e in hooks)}}


def plain_app(name, ins=(), tools=()):
    return {"app": name, "instructions": list(ins), "skills": [], "helpers": [], "connected_tools": sorted(set(tools)),
            "add_ons": [], "rules_as_settings": {}, "rules_in_code": {"guards": {}, "can_refuse_an_action": False}}


def look_desktop(cwd):
    """The Claude desktop app: the tools connected on this computer, by name, from the app's own settings file (where
    its maker documents it per system). A file or a key that is not there is simply not counted."""
    places = [os.path.join(HOME, "Library", "Application Support", "Claude"), os.path.join(HOME, ".config", "Claude")]
    if os.environ.get("APPDATA"):
        places.append(os.path.join(os.environ["APPDATA"], "Claude"))
    for place in places:
        f = os.path.join(place, "claude_desktop_config.json")
        if os.path.isfile(f):
            return plain_app("Claude desktop app", tools=(load_json(f).get("mcpServers") or {}).keys())
    return None


def look_gemini(cwd):
    home = os.path.join(HOME, ".gemini")
    if not os.path.isdir(home):
        return None
    tools = set()
    for sf in once([os.path.join(home, "settings.json"), os.path.join(cwd, ".gemini", "settings.json")]):
        tools.update((load_json(sf).get("mcpServers") or {}).keys())
    return plain_app("Gemini", instructions([os.path.join(home, "GEMINI.md"), os.path.join(cwd, "GEMINI.md")]), tools)


def ai_word(text):
    low = text.lower()
    return next((w for w in AI_WORDS if re.search(r"(?<![a-z])%s(?![a-z])" % re.escape(w), low)), None)


def look_scheduled():
    """What this computer starts by itself. Only how many there are, and for those that start an AI tool, when and
    which tool: never the command."""
    found, total, seen = [], 0, []
    try:
        out = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        lines = [l.strip() for l in out.stdout.splitlines() if l.strip() and not l.strip().startswith("#")] if out.returncode == 0 else []
        seen.append("the schedule table")
        for l in lines:
            if re.match(r"^[A-Za-z_]+\s*=", l):
                continue
            total += 1
            w = ai_word(l)
            if w:
                when = l.split()[0] if l.startswith("@") else " ".join(l.split()[:5])
                found.append({"where": "the schedule table", "when": when, "starts": w})
    except (OSError, subprocess.SubprocessError):
        pass
    agents = os.path.join(HOME, "Library", "LaunchAgents")
    if os.path.isdir(agents):
        seen.append("this Mac's own start list")
        for n in sorted(os.listdir(agents)):
            if not n.endswith(".plist"):
                continue
            total += 1
            try:
                with open(os.path.join(agents, n), "rb") as f:
                    p = plistlib.load(f)
                w = ai_word(" ".join(str(a) for a in (p.get("ProgramArguments") or [p.get("Program") or ""])))
            except Exception:
                w = None
            if w:
                found.append({"where": "this Mac's own start list", "when": "see its entry", "starts": w, "name": n[:-6]})
    timers = os.path.join(HOME, ".config", "systemd", "user")
    if os.path.isdir(timers):
        seen.append("this computer's own timers")
        for n in sorted(os.listdir(timers)):
            if not n.endswith(".timer"):
                continue
            total += 1
            try:
                with open(os.path.join(timers, n[:-6] + ".service"), encoding="utf-8") as f:
                    w = ai_word(f.read())
            except OSError:
                w = None
            if w:
                found.append({"where": "this computer's own timers", "when": "see its timer", "starts": w, "name": n[:-6]})
    return {"looked_in": seen, "everything_scheduled": total, "starts_an_ai_tool": found}


def look():
    cwd = os.getcwd()
    apps = [a for a in (look_claude(cwd), look_codex(cwd), look_desktop(cwd), look_gemini(cwd)) if a]
    for a in apps:
        a["read_before_every_answer"] = sum(i["characters"] for i in a["instructions"])
        a["heavy"] = a["read_before_every_answer"] > HEAVY_CHARS
    return {"looked_on": datetime.date.today().isoformat(), "folder": short(cwd), "apps": apps,
            "runs_by_itself": look_scheduled(),
            "could_not_tell": [
                "which connected tools and skills are really used: only the person knows, ask",
                "tools connected through the person's account rather than on this computer: the app shows those in the conversation itself",
                "a scheduled program that calls an AI from inside itself: only the ones that start an AI tool directly are seen",
                "anything that lives outside this computer: a rented agent, a chat app's own memory or schedules, an automation service",
                "what each job costs when it goes wrong: only the person knows, ask"],
            "nothing_found": not apps}


def fail(msg):
    sys.stderr.write("setup_reader: %s\n" % msg)
    sys.exit(2)


def the_map():
    try:
        m = json.loads(sys.stdin.read() or "{}")
    except ValueError as e:
        fail("the map is not valid JSON (%s)" % e)
    jobs = m.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        fail('the map needs "jobs": at least one line, for example {"name": "replies to customers", "who": "chat", '
             '"reach": ["read"], "rule": "none", "checked": true, "wrong": "some", "weekly": true}')
    for j in jobs:
        if not isinstance(j, dict) or not str(j.get("name") or "").strip():
            fail("every job needs a name")
        if j.get("who") not in WHO:
            fail('job "%s": "who" is one of %s' % (j["name"], ", ".join(WHO)))
        j["reach"] = j.get("reach") or []
        if not isinstance(j["reach"], list) or any(r not in REACH for r in j["reach"]):
            fail('job "%s": "reach" is a list from %s' % (j["name"], ", ".join(REACH)))
        if j.get("rule", "none") not in RULE:
            fail('job "%s": "rule" is one of %s' % (j["name"], ", ".join(RULE)))
        if j.get("wrong") not in WRONG:
            fail('job "%s": "wrong" (what a mistake costs) is one of %s' % (j["name"], ", ".join(WRONG)))
        j["rule"] = j.get("rule", "none")
        j["checked"] = bool(j.get("checked"))
        j["weekly"] = bool(j.get("weekly"))
    m["unused"] = [str(u) for u in (m.get("unused") or [])]
    yes = str(m.get("their_yes") or "").strip()
    if len(yes) < 2 or "<" in yes:
        fail('no reading yet: the map needs "their_yes", the person\'s own words saying the map you showed them is right. '
             'Show them every line first, with anything they did not say marked as your guess, and wait for their answer.')
    return m


def way_to_start(job):
    if job["wrong"] == "little":
        return "a ready-made agent you rent: the fastest start, and a mistake here costs little"
    if job["wrong"] == "some":
        return ("a ready-made agent with 'ask me first' switched on for anything it sends, or an open one you run "
                "yourself if you want to choose its model and the day it updates")
    return ("keep it by hand or in a chat for now; when you hand it over, its rule must live in code, in an agent "
            "built for this job, never only in words")


def reading(m, seen):
    jobs = m["jobs"]
    steps = [{"job": j["name"], "step": WHO[j["who"]], "is": STEP_WORDS[WHO[j["who"]]]} for j in jobs]
    top = max(s["step"] for s in steps)
    weight, moves = [], []
    if m["unused"]:
        weight.append("%d thing%s connected or installed that you say you do not use" % (len(m["unused"]), "" if len(m["unused"]) == 1 else "s"))
        moves.append({"move": "take away", "what": ", ".join(m["unused"]),
                      "why": "until it is taken away, what is connected and never used still gets read, still updates and can still act",
                      "how": "remove or switch off each one; nothing you use changes"})
    for a in (seen or {}).get("apps", []):
        over = [i["file"] for i in a["instructions"] if i.get("past_the_app_default_limit")]
        if a.get("heavy") or over:
            weight.append("%s reads %s characters of standing instructions before every answer" % (a["app"], format(a["read_before_every_answer"], ",")))
            moves.append({"move": "shorten", "what": "the standing instructions of %s" % a["app"],
                          "why": ("part of %s is past the size the app reads by default, so the end may never be read" % ", ".join(over)) if over
                                 else "everything in them is read again before every answer, used or not",
                          "how": "nothing is lost: the meaning of every rule is kept and what every answer needs stays; the rest moves to where it is read when its job comes up"})
    order = lambda j: (WRONG.index(j["wrong"]) * -1, min([RISKY.index(r) for r in j["reach"] if r in RISKY] or [9]))
    risky = sorted([j for j in jobs if set(j["reach"]) & set(RISKY) and WHO[j["who"]] >= 2], key=order)
    for j in [j for j in risky if j["rule"] in ("none", "words")]:
        can = " and ".join(r for r in RISKY if r in j["reach"])
        weight.append('"%s" can %s, and its rule lives %s' % (j["name"], can, "nowhere" if j["rule"] == "none" else "only in words"))
        moves.append({"move": "move the rule up", "what": j["name"],
                      "why": "it can %s, and a rule in words is a request: the day it is not followed, nothing stops it" % can,
                      "how": "make it a setting first (ask me before it can %s); for what must never happen, code: no way to do it at all" % can})
    for j in [j for j in jobs if WHO[j["who"]] >= 3 and not j["checked"]]:
        weight.append('"%s" runs by itself and nobody checks it' % j["name"])
        moves.append({"move": "add a check", "what": j["name"],
                      "why": "it acts while you are away, and a mistake is found only when someone is hurt by it",
                      "how": "one look a week at what it did, or one check made from the last mistake, run every time"})
    for j in [j for j in risky if j["rule"] == "setting" and j["wrong"] == "a lot" and WHO[j["who"]] >= 3]:
        moves.append({"move": "move the rule up", "what": j["name"],
                      "why": "it acts by itself where a mistake costs a lot, and a setting can be changed by an update you did not choose",
                      "how": "put the rule in code: the agent has no way to do the thing at all"})
    hand = sorted([j for j in jobs if WHO[j["who"]] <= 1], key=lambda j: (not j["weekly"], WRONG.index(j["wrong"])))
    if top <= 1:
        for j in hand[:3]:
            moves.append({"move": "hand over first", "what": j["name"],
                          "why": ("it comes back every week" if j["weekly"] else "it is yours to choose") + ", and a mistake costs " + j["wrong"],
                          "how": way_to_start(j),
                          "before_it_starts": "name the one thing it must never do by itself, and put that rule in a setting, not in a sentence"})
    if not moves:
        moves.append({"move": "stay where you are", "what": "your setup",
                      "why": "nothing unused, nothing heavy, every job that can send, pay or delete has its rule in a setting or in code, and what runs by itself is checked",
                      "how": "run this again in a month, or when you add a job"})
    explained = any(WHO[j["who"]] >= 3 for j in jobs)
    ask = []
    if (seen or {}).get("runs_by_itself", {}).get("starts_an_ai_tool") and not explained:
        ask.append("this computer starts an AI tool by itself, and no job on the map runs by itself: which job is that?")
    return {"where_you_stand": {"step": top, "of": 4, "is": STEP_WORDS[top],
                                "ladder": ["%d: %s" % (i, w) for i, w in enumerate(STEP_WORDS)]},
            "per_job": steps, "what_weighs": weight, "next_moves": moves[:3], "more_moves_waiting": max(0, len(moves) - 3),
            "still_to_ask": ask}


def keep_places():
    return [KEEP, os.path.join(os.getcwd(), "my-ai-setup")]


def last_saved():
    """The newest kept reading, from either place a reading can be kept."""
    rows = []
    for place in keep_places():
        try:
            with open(os.path.join(place, "record.jsonl"), encoding="utf-8") as f:
                rows += [json.loads(l) for l in f if l.strip()]
        except (OSError, ValueError):
            continue
    return max(rows, key=lambda r: str(r.get("date"))) if rows else None


def summary(seen):
    return {a["app"]: {"characters": a["read_before_every_answer"], "connected_tools": a["connected_tools"],
                       "skills": len(a["skills"])} for a in (seen or {}).get("apps", [])}


def changed(m, seen, now):
    old = last_saved()
    if not old:
        return {"first_time": True}
    out = {"first_time": False, "since": old.get("date"), "changes": []}
    a, b = old["reading"]["where_you_stand"], now["where_you_stand"]
    if a["step"] != b["step"]:
        out["changes"].append("you moved from step %d (%s) to step %d (%s)" % (a["step"], a["is"], b["step"], b["is"]))
    before = {j["name"]: j for j in old.get("jobs", [])}
    for j in m["jobs"]:
        o = before.pop(j["name"], None)
        if o is None:
            out["changes"].append('new job: "%s"' % j["name"])
        else:
            said = {"who": lambda v: STEP_WORDS[WHO.get(v, 0)], "rule": lambda v: RULE_WORDS.get(v, str(v)),
                    "checked": lambda v: "checked" if v else "not checked"}
            for k, label in (("who", "who does it"), ("rule", "where its rule lives"), ("checked", "who checks it")):
                if o.get(k) != j.get(k):
                    out["changes"].append('"%s": %s went from %s to %s' % (j["name"], label, said[k](o.get(k)), said[k](j.get(k))))
    out["changes"] += ['job gone: "%s"' % n for n in before]
    was, cur = old.get("seen", {}), summary(seen)
    for app in sorted(set(was) | set(cur)):
        w, c = was.get(app), cur.get(app)
        if not w or not c:
            out["changes"].append("%s: %s" % (app, "new on this computer" if c else "no longer found"))
            continue
        if w["characters"] != c["characters"]:
            out["changes"].append("%s: standing instructions went from %s to %s characters" % (app, format(w["characters"], ","), format(c["characters"], ",")))
        add, gone = sorted(set(c["connected_tools"]) - set(w["connected_tools"])), sorted(set(w["connected_tools"]) - set(c["connected_tools"]))
        if add:
            out["changes"].append("%s: newly connected: %s" % (app, ", ".join(add)))
        if gone:
            out["changes"].append("%s: no longer connected: %s" % (app, ", ".join(gone)))
    done = [x["move"] + ": " + x["what"] for x in old["reading"]["next_moves"]
            if x["move"] != "stay where you are" and (x["move"], x["what"]) not in [(y["move"], y["what"]) for y in now["next_moves"]]]
    if done:
        out["changes"].append("moves from last time that no longer come up: " + "; ".join(done))
    return out


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "look":
        print(json.dumps(look(), indent=1, ensure_ascii=False))
        return 0
    if cmd in ("read", "changed", "save"):
        m = the_map()
        seen = None if "--no-look" in argv else look()      # --no-look: the map alone, where this computer is not the person's
        now = reading(m, seen)
        if cmd == "read":
            print(json.dumps(now, indent=1, ensure_ascii=False))
        elif cmd == "changed":
            print(json.dumps(changed(m, seen, now), indent=1, ensure_ascii=False))
        else:
            day = datetime.date.today().isoformat()
            row = json.dumps({"date": day, "jobs": m["jobs"], "unused": m["unused"], "seen": summary(seen), "reading": now}, ensure_ascii=False) + "\n"
            for place in keep_places():                     # the home folder first; the working folder where the app may not write there
                try:
                    os.makedirs(place, exist_ok=True)
                    with open(os.path.join(place, "record.jsonl"), "a", encoding="utf-8") as f:
                        f.write(row)
                except OSError:
                    continue
                print(json.dumps({"kept_in": short(place), "record": "record.jsonl",
                                  "write_the_page_as": short(os.path.join(place, "setup-%s.md" % day))}, indent=1))
                return 0
            fail("could not keep the reading: neither %s nor a folder my-ai-setup here can be written. Nothing was kept." % short(KEEP))
        return 0
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
