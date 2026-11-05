#!/usr/bin/env python3
"""board.py: the scoreboard for which-ai-for-my-jobs. Plain Python 3.8+, no installs, nothing leaves this computer.

The winner is decided here by fixed rules, never by the assistant's impression:
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

    board.py add  --job J [--version v1] --app A --model M --effort E [--effort-rank N] --try N --right yes|no|missing|void
                  [--seconds S] [--tokens T] [--cost-usd C] [--round quick|confirm] [--note TEXT]
    board.py show [--need 3 | --need inbox=3,invoices=10] [--misses 0 | --misses 1 | --misses captions=1,email=1] [--json]
                  [--all-versions]
    board.py tested                      every setting already tested, with the date, so a new model is easy to spot

Records live in ./which-ai/results.jsonl (or WHICH_AI_HOME). One line per try. Nothing is ever overwritten.
"""
import argparse
import datetime
import json
import os
import statistics
import sys

HOME = os.environ.get("WHICH_AI_HOME") or os.path.join(os.getcwd(), "which-ai")
LOG = os.path.join(HOME, "results.jsonl")


def load():
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


def add(a):
    if a.right not in ("yes", "no", "missing", "void"):
        sys.exit("--right must be yes, no, missing or void (void: a setup fault on our side, kept and never counted)")
    if a.right == "void" and not a.note:
        sys.exit("a void try needs --note saying what went wrong in the setup")
    os.makedirs(HOME, exist_ok=True)
    rows = load()
    for r in rows:
        if (r["job"], r["version"], key(r), r["try"]) == (a.job, a.version, (a.app, a.model, a.effort), a.try_n):
            sys.exit("try %d of %s on %s is already recorded: tries are never replaced, add the next number"
                     % (a.try_n, a.job, name((a.app, a.model, a.effort))))
    r = {"date": datetime.date.today().isoformat(), "job": a.job, "version": a.version, "app": a.app, "model": a.model,
         "effort": a.effort, "effort_rank": a.effort_rank, "try": a.try_n, "right": a.right, "seconds": num(a.seconds),
         "tokens": num(a.tokens), "cost_usd": num(a.cost_usd), "round": a.round, "note": a.note or ""}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("recorded: %s, %s try %d, %s" % (a.job, name((a.app, a.model, a.effort)), a.try_n, a.right))


def summarise(rows, need, misses=None):
    misses = misses or {"*": 0}
    jobs = sorted({(r["job"], r["version"]) for r in rows})
    S = {}
    void = [r for r in rows if r.get("right") == "void"]
    rows = [r for r in rows if r.get("right") != "void"]
    for r in rows:
        s = S.setdefault(key(r), {"jobs": {}, "secs": [], "tok": [], "usd": [], "rank": r.get("effort_rank"), "dates": set()})
        j = s["jobs"].setdefault((r["job"], r["version"]), {"right": 0, "wrong": 0, "missing": 0})
        j[r["right"] if r["right"] == "missing" else ("right" if r["right"] == "yes" else "wrong")] += 1
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
    if a.bar is not None and a.bar < 1:
        # the old share bar: turned into wrong tries allowed per job, and said plainly when it allows none
        for j in sorted({(r["job"], r["version"]) for r in rows}):
            misses.setdefault(j[0], int((1 - a.bar) * for_job(need, j) + 1e-9))
        print("NOTE: a bar of %d%% is read as wrong tries allowed per job (%s). Say it with --misses instead."
              % (round(a.bar * 100), ", ".join("%s %d" % (k, v) for k, v in misses.items() if k != "*")), file=sys.stderr)
    jobs, S, void = summarise(rows, need, misses)
    p = picks(jobs, S, misses, need)
    if a.json:
        print(json.dumps({"jobs": ["%s (%s)" % j for j in jobs], "need": {j[0]: for_job(need, j) for j in jobs},
                          "settings": {name(k): {"passed": ["%s (%s)" % j for j in s["passed"]], "share_right": round(s["share"], 3),
                                                 "middle_seconds": s["mid_secs"], "middle_tokens": s["tok_avg"], "middle_usd": s["usd_avg"],
                                                 "meets_your_bar": ["%s (%s)" % j for j in s["at_bar"]],
                                                 "not_finished": ["%s (%s)" % j for j in s["thin"]]} for k, s in S.items()},
                          "best": [name(k) for k in p["best"]], "best_value": [name(k) for k in p["value"]],
                          "value_basis": p["value_basis"], "value_bar": p.get("bar", ""), "per_job": {j: [name(k) for k in v] for j, v in p["per_job"].items()},
                          "set_aside": ["%s %s try %s: %s" % (r["job"], name(key(r)), r["try"], r.get("note", "")) for r in void],
                          "older_versions_set_aside": old_versions,
                          "notes": p["notes"]}, indent=1, ensure_ascii=False))
        return
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
        print("  for %s: %s" % (j, " = ".join(name(k) for k in v) or "no setting passed it"))
    for n in p["notes"]:
        print("NOTE: " + n)
    for r in void:
        print("SET ASIDE (setup fault, not counted): %s, %s try %s: %s" % (r["job"], name(key(r)), r["try"], r.get("note", "")))
    if old_versions:
        print("OLDER VERSIONS SET ASIDE (their checks were corrected, never mixed with the newest): %s" % ", ".join(old_versions))
    print("\nA small personal test, not proof. Important work still needs a person to check it.")


def tested(a):
    seen = {}
    for r in load():
        k = key(r)
        seen[k] = max(seen.get(k, ""), r.get("date", ""))
    for k in sorted(seen):
        print("%s  last tested %s" % (name(k), seen[k]))


def main():
    ap = argparse.ArgumentParser(description="the scoreboard for which-ai-for-my-jobs")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("--job", required=True); p.add_argument("--version", default="v1")
    p.add_argument("--app", required=True); p.add_argument("--model", required=True); p.add_argument("--effort", required=True)
    p.add_argument("--effort-rank", type=int, default=None, help="0 for the lowest effort the provider documents")
    p.add_argument("--try", dest="try_n", type=int, required=True); p.add_argument("--right", required=True)
    p.add_argument("--seconds"); p.add_argument("--tokens"); p.add_argument("--cost-usd")
    p.add_argument("--round", default="confirm", choices=("quick", "confirm")); p.add_argument("--note")
    s = sub.add_parser("show"); s.add_argument("--need", default="3", help="tries a job needs: 3, or per job: invoices=10")
    s.add_argument("--misses", default="0", help="wrong tries the best value pick may have per job: 0, 1, or captions=1,email=1")
    s.add_argument("--json", action="store_true")
    s.add_argument("--all-versions", action="store_true", help="also count older versions of a job, each as its own job")
    s.add_argument("--bar", type=float, default=None, help="old form, a share of tries; read as --misses per job")
    sub.add_parser("tested")
    a = ap.parse_args()
    {"add": add, "show": show, "tested": tested}[a.cmd](a)


if __name__ == "__main__":
    main()
