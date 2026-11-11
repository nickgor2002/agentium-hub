#!/usr/bin/env python3
"""board.py: the scoreboard for which-ai-for-my-jobs, and the keeper of its gates. Plain Python 3.8+, no installs,
nothing leaves this computer.

THE GATES. Each one is held here, at the moment it matters: the program prints exactly what to show the person, records
their yes for exactly that, and refuses to record a try that skipped a gate, saying what is missing and what to do.
    board.py card                 the profile card as saved: its marks, what is still open, what comes next (after every answer)
    board.py card ok              their ok to the card: every found part becomes settled
    board.py contenders           the AIs and settings to approve, model by model with each one's efforts
    board.py job J [--version v2] one test in full to approve: the task, its files, every check word for word
    board.py plan                 the whole plan to approve: contenders, jobs, tries, judges, time, cost
    board.py yes contenders | yes job J | yes plan      their yes, for exactly what was last printed
    board.py decide ...           the person's decision on an answer the judges did not agree on
A try is recorded only when the card is settled, the plan is approved as it stands, the contender is in it, the test is
the one they approved (a changed test is a new version, shown in full again) and the judges are the plan's.

THE WINNER is decided here by fixed rules, never by the assistant's impression:
  * a setting PASSES a job when it has at least NEED tries on that job and every one was right;
  * the person's bar for the best value pick is a number of wrong tries allowed per job (--misses), never a percentage:
    with three tries a job, "one miss in ten" cannot be seen (one miss in three is already 67%), so the person chooses
    "all three right" or "one wrong try in three is fine", or asks for ten tries on that job (--need job=10);
  * BEST (the work must be right): the setting that passes the most jobs; ties go to the higher share right, then the
    faster middle time, then the lower use; a tie that survives all of that is shown as a tie;
  * BEST VALUE: among settings that meet the person's bar on every job, the cheapest. Money only when every one of them
    reported a charge;
    otherwise tokens, said as use and not money; otherwise unknown, and the passing settings are listed by speed;
  * PER JOB: for each job, the cheapest setting that meets the person's bar on it, then the lowest effort of that model.
  * ONE VERSION PER JOB: a test whose checks were corrected becomes v2, and v1 and v2 are never mixed: the board reads
    only the newest version of each job and names the older ones it set aside (--all-versions shows them as well).
  * ONE SET OF JUDGES PER JOB: every try says who marked it (--marked-by: the judges' names, or program). When the
    counted tries of one job were marked by different judges, the board says so: a stricter judge on one group of
    answers looks exactly like a weaker model, so those tries are not compared as if one set had marked them all.
  * NO PICK WHILE A MARK WAITS: an answer the judges split on (--right split) waits for the person; until each one is
    decided the board names them and picks nothing.

    board.py add  --job J [--version v1] --app A --model M --effort E [--effort-rank N] --try N
                  --right yes|no|missing|void|split [--seconds S] [--tokens T] [--cost-usd C] [--round quick|confirm]
                  [--note TEXT] [--marked-by "judge one + judge two" | --marked-by program]
    board.py decide --job J --app A --model M --effort E --try N --right yes|no [--note TEXT]   |   decide --all-waiting no
    board.py show [--need 3 | --need inbox=3,invoices=10] [--misses 0 | --misses 1 | --misses captions=1,email=1] [--json]
                  [--all-versions]         (with no --need or --misses, the person's own line 8 of the card is used)
    board.py tested                      every setting already tested, with the date, so a new model is easy to spot

Records live in ./which-ai/ (or WHICH_AI_HOME): results.jsonl (one line per try), card.json, plan.json, approved.jsonl,
jobs/<job>/<version>/. Nothing is ever overwritten by this program.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import statistics
import sys

HOME = os.environ.get("WHICH_AI_HOME") or os.path.join(os.getcwd(), "which-ai")
LOG = os.path.join(HOME, "results.jsonl")
CARD = os.path.join(HOME, "card.json")
PLAN = os.path.join(HOME, "plan.json")
YES = os.path.join(HOME, "approved.jsonl")
ME = "python3 %s" % (sys.argv[0] if " " not in sys.argv[0] else '"%s"' % sys.argv[0])


def stop(msg):
    """A refusal: what is missing, and what to do next."""
    sys.exit("NOT YET. " + msg)


SKILL_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if os.path.realpath(HOME).startswith(SKILL_DIR + os.sep):
    stop("Their record would land inside the skill's own folder (%s), where an update of the skill deletes it. Run this "
         "from the folder they are working in: everything is then kept in which-ai/ there." % HOME)


def load_all():
    rows = []
    if os.path.exists(LOG):
        for n, line in enumerate(open(LOG, encoding="utf-8"), 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                print("line %d of results.jsonl is not readable and is skipped" % n, file=sys.stderr)
    return rows


def same_try(r, d):
    return all(r.get(k) == d.get(k) for k in ("job", "version", "app", "model", "effort", "try"))


def load():
    """Every try. A try the judges split on carries the person's decision once they made one (a later line, never an edit)."""
    rows = load_all()
    tries = [r for r in rows if not r.get("decides")]
    for d in (r for r in rows if r.get("decides")):
        for r in tries:
            if r.get("right") == "split" and same_try(r, d):
                r["right"], r["decided_by"] = d.get("right"), "person"
                r["note"] = ("%s | the person decided: %s" % (r.get("note", ""), d.get("note") or d.get("right"))).strip(" |")
    return tries


def vnum(v):
    try:
        return int(str(v).lstrip("vV"))
    except ValueError:
        return -1


def newest_only(rows):
    """Only the newest version of each job counts: once a check is corrected (v2), the old v1 is set aside, so a
    setting is never rewarded for passing an unfair old test."""
    top = {}
    for r in rows:
        j = r.get("job")
        if vnum(r.get("version")) > vnum(top.get(j, "v-1")):
            top[j] = r.get("version")
    kept = [r for r in rows if r.get("version") == top.get(r.get("job"))]
    old = sorted({"%s %s" % (r.get("job"), r.get("version")) for r in rows if r.get("version") != top.get(r.get("job"))})
    return kept, old


def key(r):
    return (r.get("app", ""), r.get("model", ""), r.get("effort", ""))


def name(k):
    return "%s / %s / %s" % k


def num(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def markers(v):
    """'Opus + gpt-sol' and 'gpt-sol, opus' are the same set of judges: one spelling for both."""
    parts = [x.strip().lower() for x in str(v or "").replace(",", "+").replace(" and ", "+").split("+")]
    return " + ".join(sorted(x for x in parts if x))


def marked_by(rows):
    """Per job, every distinct set of judges its counted tries name (tries that name none are left out)."""
    out = {}
    for r in rows:
        if r.get("right") in ("yes", "no") and markers(r.get("marked_by")):
            out.setdefault("%s (%s)" % (r["job"], r["version"]), set()).add(markers(r.get("marked_by")))
    return {j: sorted(v) for j, v in sorted(out.items())}


def per_job(spec, default):
    """'3' -> every job 3; 'email=1,captions=1' -> those jobs, the rest the default."""
    out = {"*": default}
    if spec in (None, ""):
        return out
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            j, v = part.split("=", 1)
            out[j.strip()] = int(v)
        else:
            out["*"] = int(part)
    return out


def for_job(table, job):
    return table.get(job[0], table.get("*"))


# ---------------------------------------------------------------------------------------------------------------------
# The gates: the card, the contenders, each test, the plan. What the person said yes to is kept by its fingerprint.

LINES = (("1", "Your work, and for whom"), ("2", "The jobs to test"), ("3", "The AIs you pay for or use"),
         ("4", "Your usual model, and why you stay with it"), ("5", "What to test"),
         ("6", "Your time today, and subscription only or not"),
         ("7", "For each job: what matters most, and the format its answer must follow"),
         ("8", "For the cheaper pick, per job: every try right, or one wrong try allowed"))
PARTS4 = (("model", "which model"), ("tried others", "whether you tried others, and what you did not like"),
          ("why stay", "why you stay"))
PARTS7 = (("matters", "what matters most"), ("format", "its format, or that it has none"))
CARD_HOW = """No card is saved yet. Save it as %s, filled in from what you found and what they said, then run this again:

{
 "1": {"text": "", "by": "?"},
 "2": {"jobs": {"email": "replies to customers", "captions": "captions for posts"}, "by": "?"},
 "3": {"text": "", "by": "?"},
 "4": {"model": {"text": "", "by": "?"}, "tried others": {"text": "", "by": "?"}, "why stay": {"text": "", "by": "?"}},
 "5": {"text": "", "by": "?"},
 "6": {"text": "", "by": "?"},
 "7": {"email": {"matters": {"text": "", "by": "?"}, "format": {"text": "", "by": "?"}}},
 "8": {"email": {"tries": 3, "wrong allowed": 0, "by": "?"}}
}

"by" says where each part comes from, and only you can keep it honest:
  "them"   they said it in this chat, about that line (answering its question, or writing it in their reply to the card)
  "found"  from their files, their chats, or something said in passing: it waits for their ok
  "ok"     a found part they then said ok to
  "?"      not known (leave the text empty)
A default, a guess or your own reasonable choice is never "them". Keep each text to a few of their words. Line 2 names
each job with one short word (it becomes the job's name everywhere); lines 7 and 8 have one entry per job of line 2.
Save the card again after every answer and run this again: it prints the card to show and what comes next."""


ASK = {
    "2": " If nothing names their jobs (no chats read, nothing in their files), ask: \"Describe a usual week: what do you ask "
         "your AI for?\" and turn the answer into a short list to pick from; typical jobs for their kind of work only as "
         "examples inside that question, never as jobs you found.",
    "4": " Its parts are one question, each answered in their own words. " "\"I use the default\" names the model and the "
         "reason, never whether they tried others: that part stays \"?\". \"I don't know which\" is an answer: take the "
         "model from their saved setup or the app's default and save it as found, for their ok.",
    "5": " Propose their usual model at every effort first (the cheapest win is usually the same model at a lower effort), "
         "and ask whether to add other models they can reach.",
    "6": " Suggest about half an hour, and only what their subscription already includes.",
    "7": " One question per job, two parts in their words: what matters most (always right, the tone, waiting, the bill), "
         "and the format its answer must follow (their template or house style) or that it has none.",
    "8": " Say why in one line (each setting gets three tries per job, so this is what can honestly be measured), then the "
         "choices: 1. all three tries right, on every job; 2. one wrong try in three is fine on some jobs, if it is much "
         "cheaper (which ones?); 3. a closer read on a job: ten tries there, one wrong allowed (about three times the "
         "allowance on that job); 4. something else. Never \"one miss in ten\" on three tries: one miss in three can never "
         "show it. A condition (\"one wrong is fine if it is only the "
         "style\") cannot be measured: the board counts a wrong try as wrong whatever its kind. Say so, and save that job "
         "as every try right unless they then accept any wrong try. Save each job's answer as \"tries\" (3 or 10) and "
         "\"wrong allowed\" (0 or 1): the board then uses it by itself."}


def read_json(path, what):
    try:
        return json.load(open(path, encoding="utf-8"))
    except ValueError as e:
        stop("%s is not readable (%s). Save it again as plain JSON, then run this again." % (what, e))


def read_card():
    return read_json(CARD, "card.json") if os.path.exists(CARD) else None


def card_jobs(card):
    js = ((card or {}).get("2") or {}).get("jobs") or {}
    if isinstance(js, list):
        js = {str(j): "" for j in js}
    return js if isinstance(js, dict) else {}


def bar_of(entry):
    """Line 8 for one job: (tries, wrong allowed), or None when it is not a clear answer."""
    try:
        t, w = int(entry.get("tries")), int(entry.get("wrong allowed"))
    except (TypeError, ValueError, AttributeError):
        return None
    return (t, w) if t >= 3 and 0 <= w and w * 3 <= t else None


def card_parts(card):
    """Every part of the eight lines, in order: (line, part, what it says, by, own). own: a part the card wants in
    their own words (why they stay, whether they tried others, what matters and the format of each job), settled only
    by their answer to its question, never by something found and an ok."""
    out, jobs = [], list(card_jobs(card))
    for n, _label in LINES:
        c = card.get(n) or {}
        if not isinstance(c, dict):
            c = {}
        if n == "2":
            js = card_jobs(card)
            out.append((n, "", "; ".join("%s (%s)" % (k, v) if v else k for k, v in js.items()), c.get("by", "?"), False, (n,)))
        elif n == "4":
            for k, label in PARTS4:
                p = c.get(k) if isinstance(c.get(k), dict) else {}
                out.append((n, label, str(p.get("text") or ""), p.get("by", "?"), k != "model", (n, k)))
        elif n == "7":
            for j in jobs or ["(the jobs of line 2)"]:
                for k, label in PARTS7:
                    p = (c.get(j) or {}).get(k) if isinstance(c.get(j), dict) else {}
                    p = p if isinstance(p, dict) else {}
                    out.append((n, "%s, %s" % (j, label), str(p.get("text") or ""), p.get("by", "?"), True, (n, j, k)))
        elif n == "8":
            for j in jobs or ["(the jobs of line 2)"]:
                p = c.get(j) if isinstance(c.get(j), dict) else {}
                b = bar_of(p)
                text = "" if not b else ("every one of %d tries right" % b[0] if not b[1] else
                                         "%d wrong in %d tries is fine, whatever is wrong in it" % (b[1], b[0]))
                out.append((n, j, text if p.get("by", "?") != "?" else "", p.get("by", "?"), False, (n, j)))
        else:
            out.append((n, "", str(c.get("text") or ""), c.get("by", "?"), False, (n,)))
    return out


def is_settled(part):
    return part[3] in ("them", "ok") and part[2].strip() not in ("", "?")


def card_open(card):
    """What is not settled yet, as 'line 4 (why you stay)'; empty when all eight are."""
    if card is None:
        return ["no card is saved yet"]
    out = {}
    for p in card_parts(card):
        if not is_settled(p):
            out.setdefault(p[0], []).append(p[1])
    return ["line %s%s" % (n, " (%s)" % "; ".join(x for x in v if x) if any(v) else "") for n, v in sorted(out.items())]


def card_lines(card, marks=True):
    parts, out = card_parts(card), []
    for n, label in LINES:
        mine = [p for p in parts if p[0] == n]
        def mark(p):
            if not marks:
                return ""
            if is_settled(p):
                return "   [✓ settled]"
            return "   [found, waiting for their ok]" if p[3] == "found" and p[2].strip() else "   [? not known]"
        if len(mine) == 1 and not mine[0][1]:
            out.append("%s. %s: %s%s" % (n, label, mine[0][2] or "?", mark(mine[0])))
        else:
            out.append("%s. %s:" % (n, label))
            out += ["   - %s: %s%s" % (p[1], p[2] or "?", mark(p)) for p in mine]
    return out


def need_card(doing):
    card = read_card()
    still = card_open(card)
    if still:
        stop("The profile card is not settled: %s. %s comes only after all eight lines are theirs. Run `%s card`: it "
             "shows the card and the next line to ask, one at a time." % ("; ".join(still), doing, ME))
    return card


def cmd_card(a):
    card = read_card()
    if card is None:
        print(CARD_HOW % CARD)
        return
    if a.what == "ok":
        def settle(o):
            if not isinstance(o, dict):
                return 0
            mine = 1 if o.get("by") == "found" else 0
            if mine:
                o["by"] = "ok"
            return mine + sum(settle(v) for v in o.values())
        n = settle(card)
        json.dump(card, open(CARD, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("their ok is recorded: %d found part%s now settled.\n" % (n, " is" if n == 1 else "s are"))
    still = card_open(card)
    parts = card_parts(card)
    found = [p for p in parts if p[3] == "found" and p[2].strip()]
    if not still:
        print("All eight are settled:")
        print("\n".join(card_lines(card, marks=False)))
        print("\nNEXT: open your next reply with \"All eight are settled:\" and these eight lines as a short list, in their "
              "language, before any contender. In the same reply comes the list of AIs and settings to approve: check "
              "which tools can run here, save them in plan.json, and run `%s contenders` for exactly what to show." % ME)
        return
    print("(Everything is kept in %s.)" % HOME)
    print("THE CARD as it stands. Show it after each answer, in their language (the whole card, or the lines that changed), with these marks:")
    print("\n".join(card_lines(card)))
    print("\nNOT SETTLED YET: %s" % "; ".join(still))
    if found:
        print("NEXT: the found parts wait for their ok. End the reply that shows the card with: \"Reply ok if the found lines "
              "are right, or tell me what to change. Then I will ask the ? lines one at a time.\" Nothing else comes in "
              "that reply. On their ok run `%s card ok`; what they change instead, save as \"them\"." % ME)
    else:
        first = next(p for p in parts if not is_settled(p))
        job = first[1].split(",")[0] if first[0] in ("7", "8") else ""
        group = [p[1] for p in parts if p[0] == first[0] and not is_settled(p) and p[1] and (not job or p[1].split(",")[0] == job)]
        print("NEXT: ask line %s%s as one short numbered question, \"something else\" last. Nothing else in that reply.%s"
              % (first[0], " (%s)" % "; ".join(group) if group else "", ASK.get(first[0], "")))
    print("Until all eight are settled, name no contender, no test and no plan, even if they ask to hurry or name jobs. "
          "A part is settled only by their own words about that line, or their ok to a found part: never by a default "
          "or a guess, and an answer that shows they did not understand leaves it \"?\".")


def sha_of(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def said():
    """Every line of approved.jsonl: what was printed to show, and what they said yes to."""
    out = []
    if os.path.exists(YES):
        for line in open(YES, encoding="utf-8"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def note_said(did, what, sha):
    os.makedirs(HOME, exist_ok=True)
    with open(YES, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": datetime.datetime.now().isoformat(timespec="seconds"), "did": did, "what": what, "sha": sha},
                           ensure_ascii=False) + "\n")


def yes_shas(what):
    return {r["sha"] for r in said() if r.get("did") == "yes" and r.get("what") == what}


PLAN_HOW = """Save the AIs and settings you can test as %s (the rest of the plan is added later, at the plan step):

{
 "route": "this computer",
 "contenders": [
  {"app": "claude", "model": "<a model, named as the tool's own model choice names it>", "efforts": ["low", "medium", "high"], "seen": "confirmed"},
  {"app": "codex", "model": "<another>", "efforts": ["low", "high"], "seen": "to confirm"}
 ],
 "inside": {"claude": "confirmed by them: paid extra usage is switched off", "codex": "cannot tell: credits exist, nothing shows the fallback is off"}
}

One entry per model, with the efforts THAT model really offers today, lowest first, read from the tool's own --help or
the provider's current documentation: never one shared list of efforts for every model, never a model or an effort from
memory, never an internal or system entry. "seen" is "confirmed" (in the tool's model list or --help today) or
"to confirm" (on the first try). "route" is "this computer", or "paste" when they paste each test into their own apps
(then one entry per app, with the model and mode choices it shows them).
"inside" says, for each app, how you know its tries stay inside what they allowed on line 6 (that no paid extra can be
drawn): "seen: <what the tool itself shows>", "confirmed by them: <their words about their account>", "paste: they paste
it themselves", or "cannot tell: <why>". No key being set does not prove it; never write a guess as seen.
Then run this again."""


def read_plan():
    return read_json(PLAN, "plan.json") if os.path.exists(PLAN) else None


def plan_contenders(plan):
    """The contenders as saved, checked: [(app, model, [efforts], seen)]."""
    cs = (plan or {}).get("contenders")
    if not isinstance(cs, list) or not cs:
        return None, "it names no contenders"
    out = []
    for c in cs:
        if not isinstance(c, dict) or not str(c.get("app") or "").strip() or not str(c.get("model") or "").strip():
            return None, "a contender has no app or no model"
        ef = c.get("efforts")
        if not isinstance(ef, list) or not ef or len(set(map(str, ef))) != len(ef):
            return None, "%s / %s needs its own list of efforts, lowest first, each once (a model with one setting has one)" % (c["app"], c["model"])
        if c.get("seen") not in ("confirmed", "to confirm"):
            return None, "%s / %s needs \"seen\": \"confirmed\" or \"to confirm\"" % (c["app"], c["model"])
        out.append((str(c["app"]).strip(), str(c["model"]).strip(), [str(e).strip() for e in ef], c["seen"]))
    return out, ""


INSIDE = ("seen", "confirmed by them", "paste", "cannot tell")


def inside_of(plan, cs):
    """Per app of the contenders: how its tries stay inside what they allowed. (the table, what is missing or unclear)"""
    ins = plan.get("inside") if isinstance(plan.get("inside"), dict) else {}
    apps = sorted({c[0] for c in cs})
    out = {a_: str(ins.get(a_) or "").strip() for a_ in apps}
    if plan.get("route") == "paste":
        out = {a_: v or "paste: they paste it themselves" for a_, v in out.items()}
    bad = [a_ for a_, v in out.items() if not v.lower().startswith(INSIDE)
           or (v.lower().startswith("seen") and "key" in v.lower())]     # no key being set proves nothing about paid extras
    return out, bad


def stuck(plan, cs):
    """A tool nobody can vouch for is not run, and it never ends the whole test: the ways on, for the person to choose."""
    ins, _bad = inside_of(plan, cs)
    cannot = [a_ for a_, v in ins.items() if v.lower().startswith("cannot tell")]
    if not cannot:
        return
    rest = sorted({"%s / %s" % (c[0], c[1]) for c in cs if c[0] not in cannot})
    stop("You cannot see that %s stays inside what they allowed, and they have not confirmed it (%s). So it is not run, "
         "and nothing is promised about it. It does not end the test either. Say plainly what you could and could not "
         "see, then ask one short numbered question: 1. they look in their own account and confirm that no paid extra "
         "can be drawn (say where to look); 2. that app is tested by pasting: they paste each task into it and paste the "
         "answer back; %s%d. something else. Save their answer in plan.json (\"confirmed by them: ...\", \"paste: ...\", "
         "or that app's models taken out), then run `%s contenders` again: the list as it then stands is the one they approve. "
         "If they turn every way down, say what then stays untested and end with the same question: never leave them "
         "without a next step."
         % (" and ".join(cannot), "; ".join("%s: %s" % (a_, ins[a_]) for a_ in cannot),
            "3. today goes on without it, with %s; " % ", ".join(rest) if rest else "", 4 if rest else 3, ME))


def contenders_sha(plan):
    cs, _why = plan_contenders(plan)
    return sha_of({"route": (plan or {}).get("route", ""), "contenders": cs, "inside": inside_of(plan, cs)[0] if cs else {}})


def contender_lines(cs):
    out = []
    for app in sorted({c[0] for c in cs}):
        out.append("  %s" % app)
        out += ["    - %s: %s   (%s)" % (m, ", ".join(ef), "confirmed today" if seen == "confirmed" else "to be confirmed on the first try")
                for a_, m, ef, seen in cs if a_ == app]
    return out


def cmd_contenders(a):
    card = need_card("The list of AIs and settings")
    plan = read_plan()
    cs, why = plan_contenders(plan)
    if cs is None:
        print((("plan.json is not ready: %s.\n\n" % why) if plan is not None else "") + PLAN_HOW % PLAN)
        return
    ins, bad = inside_of(plan, cs)
    if bad:
        print("plan.json is not ready: \"inside\" does not say, for %s, how its tries stay inside what they allowed.\n\n%s"
              % (", ".join(bad), PLAN_HOW % PLAN))
        return
    stuck(plan, cs)
    if len({(c[0], c[1]) for c in cs}) < 2 and not str(plan.get("one model") or "").strip():
        stop("Only one model is in this list. Lowest effort goes first, so if it passes at its lowest setting a single "
             "setting was tried and the board can only say \"too thin to choose\": they would spend their time and get no "
             "comparison. Offer a second model they can reach (another model of the same plan counts), within what line 5 "
             "allows. If they want one model only, save their words as \"one model\": \"...\" in plan.json and say plainly "
             "in the reply what the result can and cannot tell them. Then run `%s contenders` again." % ME)
    print("SHOW THIS, in their language, in one reply. Open with the card, as printed:\n")
    print("All eight are settled:")
    print("\n".join(card_lines(card, marks=False)))
    print("\nThen one line on what you checked and found (which tools are installed and signed in; for a key only whether "
          "one is set, never its value). Then the list to approve, every model with its own efforts, none grouped or left out:\n")
    print("\n".join(contender_lines(cs)))
    print("\nHow each stays inside what they allowed (say it as it is, promise nothing more):")
    print("\n".join("  %s: %s" % kv for kv in ins.items()))
    print("\nEnd with: \"These are the AIs and settings I can test for you: right?\"")
    print("On their yes run `%s yes contenders`. If the list changes later (a tool drops out, another route, a model "
          "added), change plan.json and come back here: the new list is approved again before anything goes on." % ME)
    note_said("shown", "contenders", contenders_sha(plan))


def job_dir(job, version):
    return os.path.join(HOME, "jobs", job, version)


def newest_version(job):
    base = os.path.join(HOME, "jobs", job)
    vs = [v for v in (os.listdir(base) if os.path.isdir(base) else []) if vnum(v) > 0 and os.path.isdir(os.path.join(base, v))]
    return max(vs, key=vnum) if vs else None


CHECK = re.compile(r"^\s*(\d+)[.)]\s*\[(program|judged)\]\s*(\S.*)$", re.I)
JOB_HOW = """Save the test for "%(job)s" in %(dir)s, then run this again:
  task.md    the exact request, written like their real ones. Every name, place and amount in it is invented. Every rule
             a check tests is written in the task itself.
  files/     anything the task needs, also invented (leave it out when the task needs nothing).
  checks.md  the checks a right answer must meet (three to six, plus the standing one: the answer names no person,
             company or detail that is not in the task), one per line, numbered and marked:
                 1. [program] The total is 1,240 euros.
                 2. [judged] It promises no recording: saying the session will be recorded breaks it.
             [program] for every number, date, price, total, length, heading, section and required fact; [judged] only
             for tone, kindness and "no invented promise", written as one statement that must be true and names what breaks it."""


def read_job(job, version):
    """(task text, [(name, bytes)], [(number, kind, words)], problem). The files a test is made of, as saved."""
    d = job_dir(job, version)
    tp, cp = os.path.join(d, "task.md"), os.path.join(d, "checks.md")
    if not os.path.isfile(tp) or not os.path.isfile(cp):
        return None, None, None, "task.md or checks.md is missing"
    task = open(tp, encoding="utf-8", errors="replace").read()
    files = []
    for b, _d, fs in os.walk(os.path.join(d, "files")):
        for f in sorted(fs):
            if not f.startswith("."):
                p = os.path.join(b, f)
                files.append((os.path.relpath(p, d), open(p, "rb").read()))
    files.sort()
    checks = []
    for line in open(cp, encoding="utf-8", errors="replace").read().splitlines():
        m = CHECK.match(line)
        if m:
            checks.append([m.group(1), m.group(2).lower(), m.group(3).strip()])
        elif line.strip() and checks and not line.lstrip().startswith("#"):
            checks[-1][2] += " " + line.strip()
        elif line.strip() and not line.lstrip().startswith("#"):
            return None, None, None, "checks.md has a line that is not a numbered, marked check: %r" % line.strip()[:80]
    if not task.strip():
        return None, None, None, "task.md is empty"
    if len(checks) < 3:
        return None, None, None, "checks.md holds %d marked check%s; a test needs at least three" % (len(checks), "" if len(checks) == 1 else "s")
    return task, files, checks, ""


def job_sha(task, files, checks):
    h = hashlib.sha256()
    h.update(task.encode("utf-8"))
    for n, body in files:
        h.update(b"\0" + n.encode("utf-8") + b"\0" + body)
    h.update(b"\0" + json.dumps(checks, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()[:16]


def job_state(job, version):
    """('ok' | 'missing' | 'no yes' | 'changed', sha, checks): is this test, as it is saved now, one they said yes to?"""
    task, files, checks, why = read_job(job, version)
    if task is None:
        return "missing", why, None
    sha = job_sha(task, files, checks)
    if sha in yes_shas("job %s" % job):
        return "ok", sha, checks
    return ("changed" if yes_shas("job %s %s" % (job, version)) else "no yes"), sha, checks


def cmd_job(a):
    card = need_card("A test")
    plan = read_plan()
    if contenders_sha(plan) not in yes_shas("contenders") or plan_contenders(plan)[0] is None:
        stop("The AIs and settings to test are not approved as they stand now. Tests come after that yes: run "
             "`%s contenders`, show what it prints, and record their yes." % ME)
    jobs = card_jobs(card)
    if a.job not in jobs:
        stop("\"%s\" is not a job on the card (line 2 holds: %s). Use the card's name for the job, or settle the new job "
             "on the card first." % (a.job, ", ".join(jobs)))
    version = a.version or newest_version(a.job) or "v1"
    d = job_dir(a.job, version)
    task, files, checks, why = read_job(a.job, version)
    if task is None:
        print("The test is not ready: %s.\n" % why)
        print(JOB_HOW % {"job": a.job, "dir": d})
        return
    sha = job_sha(task, files, checks)
    if sha in yes_shas("job %s" % a.job):
        print("%s %s holds exactly the task, files and checks they already said yes to: no new yes is needed. Record its "
              "tries with --version %s." % (a.job, version, version))
        return
    print("SHOW THIS, in one reply, in their language: the task and every check word for word, nothing summarised, "
          "nothing left out, and never the expected answer.")
    print("First read it once more: every name, place and amount in it is invented, their own shop, signature, company, "
          "colleagues and town included, even when they gave or asked for the real one. A real one is never put in: if "
          "they ask for it, say kindly that nothing real of theirs goes into a test, and keep the invented one.\n")
    if vnum(version) > 1:
        print("This is %s of the test \"%s\": a change to a task, a file or a check makes a new version. Show ALL of it "
              "again, not only what changed. Results of older versions are set aside and never mixed with it.\n" % (version, a.job))
    print("=== THE TASK (%s %s) ===\n%s\n" % (a.job, version, task.strip()))
    if files:
        for n, body in files:
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError:
                text = None
            if text is not None and len(text) <= 4000:
                print("=== ITS FILE %s ===\n%s\n" % (n, text.strip()))
            else:
                print("=== ITS FILE %s === (%d bytes: say what it holds, with every name, number and price in it)\n%s\n"
                      % (n, len(body), (text or "")[:1500]))
    else:
        print("=== ITS FILES === none\n")
    print("=== THE CHECKS, every one, as they will be saved and marked ===")
    for n, kind, words in checks:
        print("%s. [%s] %s" % (n, "a program checks it" if kind == "program" else "the judges mark it", words))
    if vnum(version) > 1:
        cs, _w = plan_contenders(plan)
        b = bar_of((card.get("8") or {}).get(a.job) or {}) or (3, 0)
        print("\nIts tries are new tries: up to %d more, on top of what already ran. Say so, and what it means for the time "
              "they gave, when you ask for their yes." % sum(tries_most(ef, b) for _a, _m, ef, _s in cs))
    print("\nAsk for their yes to this test. On their yes run `%s yes job %s`. After it, the task, the files and the "
          "checks never change: a change is the next version (jobs/%s/v%d/), shown here and approved before any try of it."
          % (ME, a.job, a.job, vnum(version) + 1))
    note_said("shown", "job %s %s" % (a.job, version), sha)


def plan_jobs(card):
    """[(job, newest version, tries, wrong allowed, state, has judged checks)] for every job on the card."""
    out = []
    for j in card_jobs(card):
        v = newest_version(j)
        b = bar_of((card.get("8") or {}).get(j) or {}) or (3, 0)
        st, _sha, checks = job_state(j, v) if v else ("missing", "", None)
        out.append((j, v, b[0], b[1], st, any(k == "judged" for _n, k, _w in checks or [])))
    return out


def tries_most(efforts, bar):
    """The most tries one model can need on one job: each effort once and the full tries at the one chosen; where a
    wrong try is allowed, every effort may get its full tries."""
    return len(efforts) + bar[0] - 1 if not bar[1] else len(efforts) * bar[0]


def plan_sha(plan, card):
    return sha_of({"plan": plan, "jobs": [(j, t, w) for j, _v, t, w, _s, _g in plan_jobs(card)]})


PLAN_MORE = """Add the rest of the plan to plan.json, next to "route" and "contenders", then run this again:
  "judges": ["<app / model / effort>", "<app / model / effort>"]   one capable model from each company they can reach, two at
            most, each at one effort: the same ones mark every answer, whoever wrote it. With one company only: one judge.
            Leave it [] only when no check of any job is marked [judged].
  "minutes": 25                      the time you expect, inside what they gave on line 6
  "cost": "..."                      a reported price, or "uses your subscription allowance"; unknown stays unknown
  "allowance": "..."                 their allowance or reset time, where the app shows it (may be left out)
  "clean": {"claude": "...", "codex": "..."}   per tool: that it can run clean (without their own instructions and memory)
            and by which setting from its --help, or that it cannot and every contender of that tool is kept equal"""


def plan_problem(plan, jobs):
    cs, why = plan_contenders(plan)
    if cs is None:
        return why
    if inside_of(plan, cs)[1]:
        return "\"inside\" does not say, for %s, how its tries stay inside what they allowed" % ", ".join(inside_of(plan, cs)[1])
    j = plan.get("judges")
    if not isinstance(j, list) or len(j) > 2 or any(not str(x).strip() for x in j):
        return "\"judges\" must be a list of at most two"
    if any(g for *_x, g in jobs) and not j:
        return "a job has checks the judges mark, and the plan names no judge"
    if plan.get("minutes") in (None, "") or not str(plan.get("cost") or "").strip():
        return "\"minutes\" or \"cost\" is missing"
    if plan.get("route") != "paste":
        clean = plan.get("clean") if isinstance(plan.get("clean"), dict) else {}
        miss = sorted({c[0] for c in cs} - {k for k, v in clean.items() if str(v).strip()})
        if miss:
            return "\"clean\" says nothing for %s" % ", ".join(miss)
    return ""


def cmd_plan(a):
    card = need_card("The plan")
    plan = read_plan()
    if plan is None:
        stop("There is no plan.json yet. Run `%s contenders` first: it says how to save the AIs and settings." % ME)
    jobs = plan_jobs(card)
    bad = [(j, v, st) for j, v, _t, _w, st, _g in jobs if st != "ok"]
    if bad:
        stop("Not every job on the card has a test they said yes to: %s. Every job of line 2 becomes a test before the "
             "plan: run `%s job <job>` for each, show it in full and record their yes (or, if they drop a job, take it "
             "off the card in their words first)." % ("; ".join("%s (%s)" % (j, "no test saved" if st == "missing" else
                                                                             "its test changed after their yes" if st == "changed" else "no yes yet") for j, _v, st in bad), ME))
    why = plan_problem(plan, jobs)
    if why:
        print("plan.json is not ready: %s.\n\n%s" % (why, PLAN_MORE))
        return
    cs, _w = plan_contenders(plan)
    stuck(plan, cs)
    most = sum(tries_most(ef, (t, w2)) for _a, _m, ef, _s in cs for _j, _v, t, w2, _st, _g in jobs)
    print("SHOW THIS PLAN, as one short list or table, in their language, nothing left out:\n")
    if contenders_sha(plan) in yes_shas("contenders"):
        print("Contenders: the %d models they approved, each at its own efforts, unchanged since their yes (say so; they need "
              "not be listed again)." % len(cs))
    else:
        print("Contenders, each model with its own efforts, lowest first. This list changed since their last yes to it: say "
              "what changed, and show it whole; their yes to this plan covers it:")
        print("\n".join(contender_lines(cs)))
    print("\nJobs and tries:")
    for j, v, t, w, _st, g in jobs:
        print("  - %s (%s): %d tries for each finalist, %s; %s" % (
            j, v, t, "every try right" if not w else "%d wrong try in %d is fine for the cheaper pick, whatever is wrong in it (a lower "
            "effort that misses once in the quick round still goes on to its full tries here)" % (w, t),
            "the judges mark part of it" if g else "a program checks all of it"))
    judges = [str(x).strip() for x in plan.get("judges") or []]
    if judges:
        print("\nJudges, the same for every answer, whoever wrote it: %s" % " + ".join(judges))
        if len(judges) == 1:
            print("  (one judge only: say plainly that the judge is not independent)")
    else:
        print("\nJudges: none needed, a program checks every check")
    print("\nTries: lowest effort first, so at most %d and usually far fewer. Expected time: about %s minutes. Cost: %s%s"
          % (most, plan.get("minutes"), plan.get("cost"), ". Allowance: %s" % plan["allowance"] if plan.get("allowance") else ""))
    if isinstance(plan.get("clean"), dict) and plan["clean"]:
        print("Clean sessions: %s" % "; ".join("%s: %s" % kv for kv in plan["clean"].items()))
    print("Inside what they allowed: %s" % "; ".join("%s: %s" % kv for kv in inside_of(plan, cs)[0].items()))
    print("\nAsk for their yes to this exact plan: nothing here grants permission to spend, only their yes does. On their "
          "yes run `%s yes plan`. If a contender, an effort, a judge or the route changes after it (a tool stops, a judge "
          "cannot be reached, an allowance runs out), stop, say so, change plan.json and come back here: the changed plan "
          "is approved again before another try." % ME)
    note_said("shown", "plan", plan_sha(plan, card))


def cmd_yes(a):
    card, plan = need_card("A yes"), read_plan()
    if a.kind == "job":
        if not a.job:
            stop("Say which job: `%s yes job <job>`." % ME)
        version = a.version or newest_version(a.job) or "v1"
        task, files, checks, why = read_job(a.job, version)
        if task is None:
            stop("The test of %s %s is not ready (%s): run `%s job %s`." % (a.job, version, why, ME, a.job))
        what, sha, again = "job %s %s" % (a.job, version), job_sha(task, files, checks), "job %s" % a.job
    elif a.kind == "contenders":
        what, sha, again = "contenders", contenders_sha(plan), "contenders"
    else:
        what, sha, again = "plan", plan_sha(plan, card), "plan"
    shown = [r for r in said() if r.get("did") == "shown" and r.get("what") == what]
    if not shown or shown[-1]["sha"] != sha:
        stop("%s. A yes counts only for exactly what was printed to show them: run `%s %s`, show all of it, and record "
             "their yes after they give it." % ("This was never printed to show" if not shown else
                                                "It changed since it was last printed", ME, again))
    note_said("yes", what, sha)
    if a.kind == "job":
        note_said("yes", "job %s" % a.job, sha)
    if a.kind == "plan":
        note_said("yes", "contenders", contenders_sha(plan))
    print("their yes is recorded: %s" % what)
    if a.kind == "contenders":
        print("NEXT: turn each job of the card into a test and have each approved in full: `%s job <job>`." % ME)
    elif a.kind == "job":
        left = [j for j, _v, _t, _w, st, _g in plan_jobs(card) if st != "ok"]
        print("NEXT: %s" % ("the test of %s: `%s job %s`." % (left[0], ME, left[0]) if left else
                            "its tries go on under the plan they approved; record them with --version as said above." if yes_shas("plan") else
                            "every job has its approved test. The plan and its cost: `%s plan`." % ME))
    else:
        judges = " + ".join(str(x).strip() for x in plan.get("judges") or []) or "program"
        print("NEXT: the run, lowest effort first. Prove the setup on one answer before the quick round. Record every try as "
              "it is marked, and read the record before moving on:\n  %s add --job <job> --app <app> --model <model> "
              "--effort <effort> --try 1 --right yes|no|missing|void|split --seconds 21.6 --tokens 9400 [--cost-usd 0.01] "
              "--round quick|confirm [--note \"...\"] --marked-by \"%s\"\n(--marked-by program for a job no judge marks. An answer the judges did not agree on, or one was unsure "
              "of: --right split, with each judge's reason in --note; it goes to the person.)" % (ME, judges))


def gate_add(a):
    """A try is recorded only behind every gate. Returns (version, effort rank, who marked it)."""
    card = need_card("Recording a try (and running one)")
    plan = read_plan()
    if plan is None or plan_sha(plan, card) not in yes_shas("plan"):
        stop("The plan, as it stands now, does not have their yes%s. No try runs or is recorded before it: run `%s plan`, "
             "show what it prints and record their yes." % (" (it changed after their yes)" if yes_shas("plan") else "", ME))
    cs, _why = plan_contenders(plan)
    mine = [c for c in cs if (c[0], c[1]) == (a.app, a.model)]
    if not mine or a.effort not in mine[0][2]:
        stop("%s is not in the plan they approved%s. A contender or an effort outside it needs a changed plan and a new "
             "yes: change plan.json, run `%s plan`, show it and record their yes."
             % (name((a.app, a.model, a.effort)), " (it holds %s / %s at: %s)" % (a.app, a.model, ", ".join(mine[0][2])) if mine else
                " (it holds: %s)" % ", ".join(sorted({"%s / %s" % (c[0], c[1]) for c in cs})), ME))
    newest = newest_version(a.job)
    version = a.version or newest or "v1"
    if newest and vnum(version) < vnum(newest):
        stop("%s has a %s: its tries are recorded with --version %s. Older versions are set aside, never added to." % (a.job, newest, newest))
    st, sha, checks = job_state(a.job, version)
    if st != "ok":
        stop({"missing": "There is no saved test for %(j)s %(v)s (%(s)s). Run `%(me)s job %(j)s`.",
              "no yes": "The test %(j)s %(v)s does not have their yes. Run `%(me)s job %(j)s`, show all of it and record their yes; only then its tries count.",
              "changed": "The task, a file or a check of %(j)s %(v)s changed after their yes. What they approved never changes: put "
                         "it back as it was, or save the change as the next version (jobs/%(j)s/v%(n)d/), run `%(me)s job %(j)s`, "
                         "show ALL of it and record their yes; then record tries with --version v%(n)d."}[st]
             % {"j": a.job, "v": version, "s": sha, "me": ME, "n": vnum(version) + 1})
    judged = any(k == "judged" for _n, k, _w in checks)
    who = markers(a.marked_by)
    plan_judges = markers(" + ".join(str(x) for x in plan.get("judges") or []))
    if a.right in ("yes", "no", "split"):
        if judged and who != plan_judges:
            stop("%s has checks the judges mark, and this try names %s. The plan they approved names: %s. Record it with "
                 "--marked-by \"%s\". If a judge did not mark this answer or could not be reached, that is a changed plan: "
                 "say so, change plan.json, run `%s plan` and record their yes before going on."
                 % (a.job, "\"%s\"" % who if who else "no judges", plan_judges, plan_judges, ME))
        if not judged and who not in ("", "program"):
            stop("Every check of %s is a program check, so its tries are --marked-by program." % a.job)
        if not judged:
            who = "program"
    if a.right == "split" and not judged:
        stop("split is for an answer the judges did not agree on; %s has no judged check." % a.job)
    rank = a.effort_rank if a.effort_rank is not None else mine[0][2].index(a.effort)
    for r in load():
        if (r["job"], r["version"], key(r), r["try"]) == (a.job, version, (a.app, a.model, a.effort), a.try_n):
            sys.exit("try %d of %s on %s is already recorded: tries are never replaced, add the next number"
                     % (a.try_n, a.job, name((a.app, a.model, a.effort))))
    since = max([r["at"] for r in said() if r.get("did") == "yes" and r.get("what") == "plan"] or [""])
    done = [r for r in load() if (r.get("job"), r.get("version"), r.get("app"), r.get("model")) == (a.job, version, a.app, a.model)
            and r.get("right") != "void" and str(r.get("at") or "") >= since]
    most = tries_most(mine[0][2], bar_of((card.get("8") or {}).get(a.job) or {}) or (3, 0))
    if a.right != "void" and len(done) >= most:
        stop("That would be try %d of %s / %s on %s %s since their yes to the plan, and the plan allows %d at most (each "
             "effort once and the full tries at the one chosen). More tries than they approved is a changed plan: say why "
             "they are needed, run `%s plan`, show it and record their yes." % (len(done) + 1, a.app, a.model, a.job, version, most, ME))
    return version, rank, who


def add(a):
    if a.right not in ("yes", "no", "missing", "void", "split"):
        sys.exit("--right must be yes, no, missing, void or split (void: a setup fault on our side, kept and never counted; "
                 "split: the judges did not agree or one was unsure, so the person decides)")
    if a.right == "void" and not a.note:
        sys.exit("a void try needs --note saying what went wrong in the setup")
    if a.right == "split" and not a.note:
        sys.exit("a split try needs --note with each judge's mark and reason: the person is shown them")
    version, rank, who = gate_add(a)
    os.makedirs(HOME, exist_ok=True)
    r = {"date": datetime.date.today().isoformat(), "at": datetime.datetime.now().isoformat(timespec="seconds"),
         "job": a.job, "version": version, "app": a.app, "model": a.model,
         "effort": a.effort, "effort_rank": rank, "try": a.try_n, "right": a.right, "seconds": num(a.seconds),
         "tokens": num(a.tokens), "cost_usd": num(a.cost_usd), "round": a.round, "note": a.note or "",
         "marked_by": who}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("recorded: %s, %s try %d, %s" % (a.job, name((a.app, a.model, a.effort)), a.try_n, a.right))
    if a.right == "split":
        print("It waits for the person: show them the answer in full, without its author, with each judge's reason, and "
              "record what they decide on the frozen checks with `%s decide`. No pick is named while one waits." % ME)


def waiting(rows):
    return [r for r in rows if r.get("right") == "split"]


def decide(a):
    rows = load()
    wait = waiting(rows)
    if a.all_waiting:
        if a.all_waiting != "no":
            sys.exit("--all-waiting takes only no: counting them all as wrong, the same for everyone, is the one shortcut")
        if len(wait) <= 3:
            sys.exit("only %d answer%s wait: with three or fewer, each one is shown and decided" % (len(wait), "" if len(wait) == 1 else "s"))
        pick = wait
    else:
        if a.right not in ("yes", "no"):
            sys.exit("--right must be yes or no: the person's decision on the frozen checks")
        want = {"job": a.job, "version": a.version or (newest_version(a.job) if a.job else None) or "v1", "app": a.app,
                "model": a.model, "effort": a.effort, "try": a.try_n}
        pick = [r for r in wait if same_try(r, want)]
        if not pick:
            sys.exit("no answer waits under that name. Waiting now: %s" % ("; ".join(
                "%s %s, %s try %s" % (r["job"], r["version"], name(key(r)), r["try"]) for r in wait) or "none"))
    with open(LOG, "a", encoding="utf-8") as f:
        for r in pick:
            f.write(json.dumps({"date": datetime.date.today().isoformat(), "decides": True, "job": r["job"], "version": r["version"],
                                "app": r["app"], "model": r["model"], "effort": r["effort"], "try": r["try"],
                                "right": "no" if a.all_waiting else a.right, "decided_by": "person",
                                "note": a.note or ("counted as wrong with every other waiting answer, their choice" if a.all_waiting else "")},
                               ensure_ascii=False) + "\n")
    left = len(wait) - len(pick)
    print("the person's decision is recorded for %d answer%s; %s" % (len(pick), "" if len(pick) == 1 else "s",
          "%d still wait%s" % (left, "s" if left == 1 else "") if left else "none waits: the board can pick now"))


def summarise(rows, need, misses=None):
    misses = misses or {"*": 0}
    jobs = sorted({(r["job"], r["version"]) for r in rows})
    S = {}
    void = [r for r in rows if r.get("right") == "void"]
    rows = [r for r in rows if r.get("right") != "void"]
    for r in rows:
        s = S.setdefault(key(r), {"jobs": {}, "secs": [], "tok": [], "usd": [], "rank": r.get("effort_rank"), "dates": set()})
        j = s["jobs"].setdefault((r["job"], r["version"]), {"right": 0, "wrong": 0, "missing": 0})
        # an answer still waiting for the person is not right and not wrong yet: it counts as not there
        j["missing" if r["right"] in ("missing", "split") else ("right" if r["right"] == "yes" else "wrong")] += 1
        s["dates"].add(r.get("date", ""))
        if r["right"] != "missing":
            for f, k2 in (("seconds", "secs"), ("tokens", "tok"), ("cost_usd", "usd")):
                s[k2].append(num(r.get(f)))
    for k, s in S.items():
        s["passed"] = [j for j in jobs if s["jobs"].get(j, {}).get("right", 0) >= for_job(need, j)
                       and not s["jobs"][j]["wrong"] and not s["jobs"][j]["missing"]]
        # meets the person's own bar: fully tried, nothing missing, no more wrong tries than they allowed on that job
        s["at_bar"] = [j for j in jobs if j in s["jobs"] and not s["jobs"][j]["missing"]
                       and s["jobs"][j]["right"] + s["jobs"][j]["wrong"] >= for_job(need, j)
                       and s["jobs"][j]["wrong"] <= for_job(misses, j)]
        s["thin"] = [j for j in jobs if sum(s["jobs"].get(j, {"x": 0}).values()) < for_job(need, j)]
        tried = sum(sum(v.values()) for v in s["jobs"].values())
        s["share"] = sum(v["right"] for v in s["jobs"].values()) / tried if tried else 0
        secs = [x for x in s["secs"] if x is not None]
        s["mid_secs"] = statistics.median(secs) if secs else None
        # the middle value, not the average: a first try that pays a start-up cost (a cache being built) is not typical
        s["tok_avg"] = statistics.median(s["tok"]) if s["tok"] and None not in s["tok"] else None
        s["usd_avg"] = statistics.median(s["usd"]) if s["usd"] and None not in s["usd"] else None
    return jobs, S, void


def bar_words(jobs, misses, need):
    eased = [j for j in jobs if for_job(misses, j)]
    if not eased:
        return "every try right"
    return "; ".join("%s: up to %d wrong in %d tries" % (j[0], for_job(misses, j), for_job(need, j)) for j in eased) + \
        ("; every other job: every try right" if len(eased) < len(jobs) else "")


def picks(jobs, S, misses=None, need=None):
    misses = misses or {"*": 0}
    need = need or {"*": 3}
    out = {"best": [], "value": [], "value_basis": "", "per_job": {}, "notes": []}
    if len(S) < 2:
        out["notes"].append("too thin to choose: fewer than two settings tested")
    if not S or not jobs:
        return out
    def order(k):
        s = S[k]
        return (-len(s["passed"]), -s["share"], s["mid_secs"] if s["mid_secs"] is not None else 1e18,
                s["usd_avg"] if s["usd_avg"] is not None else (s["tok_avg"] if s["tok_avg"] is not None else 1e18))
    ranked = sorted(S, key=order)
    top = order(ranked[0])
    if not S[ranked[0]]["passed"]:
        out["notes"].append("no setting passed any job on every try: no winner, only the counts")
    else:
        out["best"] = [k for k in ranked if order(k) == top]
    out["bar"] = bar_words(jobs, misses, need)
    full = [k for k in S if len(S[k]["at_bar"]) == len(jobs)]
    if not full:
        out["notes"].append("no setting met the value bar (%s): no best value overall, see the per job picks" % out["bar"])
    elif all(S[k]["usd_avg"] is not None for k in full):
        out["value_basis"] = "money (reported charge per try)"
        low = min(S[k]["usd_avg"] for k in full)
        out["value"] = sorted([k for k in full if S[k]["usd_avg"] == low], key=lambda k: S[k]["rank"] if S[k]["rank"] is not None else 99)
    elif all(S[k]["tok_avg"] is not None for k in full):
        out["value_basis"] = "use in tokens per try (use, not money: different companies count and charge differently)"
        low = min(S[k]["tok_avg"] for k in full)
        out["value"] = [k for k in full if S[k]["tok_avg"] == low]
    else:
        out["value_basis"] = "unknown: not every passing setting reported its charge or tokens; listed fastest first"
        out["value"] = sorted(full, key=lambda k: S[k]["mid_secs"] if S[k]["mid_secs"] is not None else 1e18)
    for j in jobs:
        ok = [k for k in S if j in S[k]["at_bar"]]
        def cheap(k):
            s = S[k]
            return (s["usd_avg"] if s["usd_avg"] is not None else 1e18, s["tok_avg"] if s["tok_avg"] is not None else 1e18,
                    s["rank"] if s["rank"] is not None else 99, s["mid_secs"] if s["mid_secs"] is not None else 1e18)
        if ok:
            low = min(cheap(k) for k in ok)
            out["per_job"]["%s (%s)" % j] = [k for k in ok if cheap(k) == low]
        else:
            out["per_job"]["%s (%s)" % j] = []
    return out


def card_bar():
    """The person's own line 8, as the board's --need and --misses; nothing when no settled card is saved."""
    try:
        card = json.load(open(CARD, encoding="utf-8")) if os.path.exists(CARD) else None
    except ValueError:
        card = None
    need, misses = {}, {}
    for j in card_jobs(card):
        b = bar_of(((card.get("8") or {}).get(j)) or {})
        if b:
            need[j], misses[j] = b
    return need, misses


def show(a):
    rows = load()
    if not rows:
        print("no tries recorded yet in %s" % LOG)
        return
    old_versions = []
    if not a.all_versions:
        rows, old_versions = newest_only(rows)
    need = per_job(a.need, 3)
    misses = per_job(a.misses, 0)
    cneed, cmiss = card_bar()
    if a.need is None:
        need.update(cneed)
    if a.misses is None and a.bar is None:
        misses.update(cmiss)
    if a.bar is not None and a.bar < 1:
        # the old share bar: turned into wrong tries allowed per job, and said plainly when it allows none
        for j in sorted({(r["job"], r["version"]) for r in rows}):
            misses.setdefault(j[0], int((1 - a.bar) * for_job(need, j) + 1e-9))
        print("NOTE: a bar of %d%% is read as wrong tries allowed per job (%s). Say it with --misses instead."
              % (round(a.bar * 100), ", ".join("%s %d" % (k, v) for k, v in misses.items() if k != "*")), file=sys.stderr)
    jobs, S, void = summarise(rows, need, misses)
    p = picks(jobs, S, misses, need)
    wait = waiting(rows)
    waits = ["%s %s, %s try %s: %s" % (r["job"], r["version"], name(key(r)), r["try"], r.get("note", "")) for r in wait]
    if wait:
        p.update({"best": [], "value": [], "value_basis": "", "per_job": {j: [] for j in p["per_job"]}})
        p["notes"] = ["%d answer%s the judges did not agree on wait%s for the person: no pick until each one is decided"
                      % (len(wait), "" if len(wait) == 1 else "s", "s" if len(wait) == 1 else "")]
    decided = sum(1 for r in rows if r.get("decided_by") == "person")
    who = marked_by(rows)
    for j, sets in who.items():
        if len(sets) > 1:
            p["notes"].append("%s was marked by different judges (%s): a stricter judge looks like a weaker model, so "
                              "do not compare those tries as if one set had marked them all" % (j, "; ".join(sets)))
    plan = None
    try:
        plan = json.load(open(PLAN, encoding="utf-8")) if os.path.exists(PLAN) else None
    except ValueError:
        pass
    cs = plan_contenders(plan)[0] if plan else None
    if cs and not wait:
        never = sorted({"%s / %s" % (c[0], c[1]) for c in cs} - {"%s / %s" % (k[0], k[1]) for k in S})
        if never:
            p["notes"].append("in the plan they approved but never tried: %s. Say so with the result" % ", ".join(never))
    if a.json:
        out = {"jobs": ["%s (%s)" % j for j in jobs], "need": {j[0]: for_job(need, j) for j in jobs},
               "settings": {name(k): {"passed": ["%s (%s)" % j for j in s["passed"]], "share_right": round(s["share"], 3),
                                      "middle_seconds": s["mid_secs"], "middle_tokens": s["tok_avg"], "middle_usd": s["usd_avg"],
                                      "meets_your_bar": ["%s (%s)" % j for j in s["at_bar"]],
                                      "not_finished": ["%s (%s)" % j for j in s["thin"]]} for k, s in S.items()},
               "best": [name(k) for k in p["best"]], "best_value": [name(k) for k in p["value"]],
               "value_basis": p["value_basis"], "value_bar": p.get("bar", ""), "per_job": {j: [name(k) for k in v] for j, v in p["per_job"].items()},
               "set_aside": ["%s %s try %s: %s" % (r["job"], name(key(r)), r["try"], r.get("note", "")) for r in void],
               "older_versions_set_aside": old_versions, "marked_by": who,
               "notes": p["notes"]}
        if wait or decided:
            out["waiting_for_the_person"], out["decided_by_the_person"] = waits, decided
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return
    if wait:
        print("WAITING FOR THE PERSON: %d answer%s the judges did not agree on. NO PICK IS NAMED YET." % (len(wait), "" if len(wait) == 1 else "s"))
        for w in waits:
            print("  - " + w)
        print("Show each one in full, one at a time, without its author, with each judge's reason; they decide on the frozen "
              "checks only. Record each with `%s decide --job J --app A --model M --effort E --try N --right yes|no`.%s "
              "Then run show again.\n" % (ME, " More than three wait: first say how many and ask whether to decide each "
                                              "one, or count them all as wrong, the same for everyone (`decide --all-waiting no`)." if len(wait) > 3 else ""))
    print("Jobs: %s. A job counts as passed after %s, all right.\n" % (", ".join("%s (%s)" % j for j in jobs),
          ", ".join(sorted({"%d tries" % for_job(need, j) for j in jobs}))))
    for k in sorted(S, key=lambda k: (-len(S[k]["passed"]), -S[k]["share"])):
        s = S[k]
        cells = []
        for j in jobs:
            v = s["jobs"].get(j)
            cells.append("%s %d/%d" % (j[0], v["right"], sum(v.values())) if v else "%s untested" % j[0])
        print("%-42s passed %d of %d | %s | middle %s s | tokens %s | $ %s" % (
            name(k), len(s["passed"]), len(jobs), "; ".join(cells),
            "%.0f" % s["mid_secs"] if s["mid_secs"] is not None else "?",
            "%.0f" % s["tok_avg"] if s["tok_avg"] is not None else "?",
            "%.4f" % s["usd_avg"] if s["usd_avg"] is not None else "?"))
    print()
    print("BEST (must be right): %s" % (" = ".join(name(k) for k in p["best"]) or "none"))
    print("BEST VALUE: %s%s" % (" = ".join(name(k) for k in p["value"]) or "none", " [%s]" % p["value_basis"] if p["value_basis"] else ""))
    print("  your bar for it: %s" % p.get("bar", "every try right"))
    for j, v in p["per_job"].items():
        print("  for %s: %s" % (j, " = ".join(name(k) for k in v) or ("waits for the person" if wait else "no setting passed it")))
    for j, sets in who.items():
        if len(sets) == 1:
            print("  %s marked by: %s" % (j, sets[0]))
    if decided:
        print("  answers the judges did not agree on, decided by the person: %d" % decided)
    for n in p["notes"]:
        print("NOTE: " + n)
    for r in void:
        print("SET ASIDE (setup fault, not counted): %s, %s try %s: %s" % (r["job"], name(key(r)), r["try"], r.get("note", "")))
    if old_versions:
        print("OLDER VERSIONS SET ASIDE (their checks were corrected, never mixed with the newest): %s" % ", ".join(old_versions))
    if cs:
        # a plan they approved is saved here: say, job by job, every setting that passed, so nothing told about the
        # result ("the only one that...") has to be worked out by eye
        print()
        for j in jobs:
            who_passed = [name(k) for k in sorted(S) if j in S[k]["passed"]]
            print("PASSED %s (%s), every try right: %s" % (j[0], j[1], "; ".join(who_passed) or "no setting"))
        every = load()
        kinds = {k: sum(1 for r in every if r.get("right") == k or (k == "marked" and r.get("right") in ("yes", "no"))) for k in ("marked", "void", "missing", "split")}
        at = sorted(str(r["at"]) for r in every if r.get("at"))
        span = ""
        if len(at) > 1:
            a_, b_ = datetime.datetime.fromisoformat(at[0]), datetime.datetime.fromisoformat(at[-1])
            span = "; recorded from %s to %s (%d minutes)" % (a_.strftime("%H:%M"), b_.strftime("%H:%M"), round((b_ - a_).total_seconds() / 60))
        print("THE RUN IN NUMBERS, from the record: %d tries recorded (%d marked right or wrong%s%s%s); %d settings tried%s%s."
              % (len(every), kinds["marked"], ", %d set aside for a setup fault" % kinds["void"] if kinds["void"] else "",
                 ", %d that never ran" % kinds["missing"] if kinds["missing"] else "",
                 ", %d waiting for the person" % kinds["split"] if kinds["split"] else "",
                 len({key(r) for r in every}), ", %d answers decided by the person" % decided if decided else "", span))
        print("Tell them the picks as printed above. A number about the run is one of the numbers above, never one counted by "
              "hand. A sentence of your own about the result (the only one that passed, the cheapest, the fastest, what they "
              "use today) is said only if every line above agrees with it.")
    print("\nA small personal test, not proof. Important work still needs a person to check it.")


def tested(a):
    seen = {}
    for r in load():
        k = key(r)
        seen[k] = max(seen.get(k, ""), r.get("date", ""))
    for k in sorted(seen):
        print("%s  last tested %s" % (name(k), seen[k]))


def main():
    ap = argparse.ArgumentParser(description="the scoreboard for which-ai-for-my-jobs, and the keeper of its gates")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("card", help="the profile card as saved, what is open, what comes next")
    c.add_argument("what", nargs="?", choices=("ok",), help="ok: their ok to the card, every found part becomes settled")
    sub.add_parser("contenders", help="the AIs and settings to approve")
    j = sub.add_parser("job", help="one test in full, to approve")
    j.add_argument("job"); j.add_argument("--version", default=None)
    sub.add_parser("plan", help="the whole plan, to approve")
    y = sub.add_parser("yes", help="record their yes for what was last printed")
    y.add_argument("kind", choices=("contenders", "job", "plan")); y.add_argument("job", nargs="?"); y.add_argument("--version", default=None)
    p = sub.add_parser("add")
    p.add_argument("--job", required=True); p.add_argument("--version", default=None)
    p.add_argument("--app", required=True); p.add_argument("--model", required=True); p.add_argument("--effort", required=True)
    p.add_argument("--effort-rank", type=int, default=None, help="0 for the lowest effort; read from the plan when left out")
    p.add_argument("--try", dest="try_n", type=int, required=True); p.add_argument("--right", required=True)
    p.add_argument("--seconds"); p.add_argument("--tokens"); p.add_argument("--cost-usd")
    p.add_argument("--round", default="confirm", choices=("quick", "confirm")); p.add_argument("--note")
    p.add_argument("--marked-by", default="", help="who marked this try: the plan's judges, or program; the same on every try of a job")
    d = sub.add_parser("decide", help="the person's decision on an answer the judges did not agree on")
    d.add_argument("--job"); d.add_argument("--version", default=None); d.add_argument("--app"); d.add_argument("--model")
    d.add_argument("--effort"); d.add_argument("--try", dest="try_n", type=int); d.add_argument("--right"); d.add_argument("--note")
    d.add_argument("--all-waiting", default=None, help="no: count every waiting answer as wrong, the same for everyone (more than three waiting)")
    s = sub.add_parser("show"); s.add_argument("--need", default=None, help="tries a job needs: 3, or per job: invoices=10")
    s.add_argument("--misses", default=None, help="wrong tries the best value pick may have per job: 0, 1, or captions=1,email=1")
    s.add_argument("--json", action="store_true")
    s.add_argument("--all-versions", action="store_true", help="also count older versions of a job, each as its own job")
    s.add_argument("--bar", type=float, default=None, help="old form, a share of tries; read as --misses per job")
    sub.add_parser("tested")
    a = ap.parse_args()
    {"card": cmd_card, "contenders": cmd_contenders, "job": cmd_job, "plan": cmd_plan, "yes": cmd_yes, "add": add,
     "decide": decide, "show": show, "tested": tested}[a.cmd](a)


if __name__ == "__main__":
    main()
