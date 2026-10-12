#!/usr/bin/env python3
"""Report every new upstream commit for human triage; never port changes automatically."""
import argparse
import html
import json
import re
import subprocess

UPSTREAM = "cataclysmbn/Cataclysm-BN"
TRACKER = "<!-- overhaul-upstream-feature-watch -->"
CHECKPOINT = re.compile(r"<!-- upstream-checkpoint:([0-9a-f]{40}) -->")
FEATURE = re.compile(r"^(feat(?:\([^)]*\))?!?:|add(?:s|ed|ing)?\b|introduc(?:e|es|ed|ing)\b|new\b)", re.I)


def api(endpoint, *, data=None, method="GET", paginate=False):
    command = ["gh", "api", "--hostname", "github.com", "--method", method, endpoint]
    if paginate:
        command += ["--paginate", "--slurp"]
    if data is not None:
        command += ["--input", "-"]
    result = subprocess.run(command, input=json.dumps(data) if data is not None else None,
                            text=True, stdout=subprocess.PIPE, check=True)
    return json.loads(result.stdout)


def commits_from_pages(pages):
    if not pages or pages[0]["status"] not in ("ahead", "identical"):
        raise ValueError("Upstream ancestry changed; review the checkpoint rather than skipping commits")
    commits = [commit for page in pages for commit in page["commits"]]
    if len(commits) != pages[0]["total_commits"] or len({c["sha"] for c in commits}) != len(commits):
        raise ValueError("Incomplete or duplicate comparison pages; checkpoint not advanced")
    return commits


def report_parts(base, head, commits):
    # ponytail: title heuristics only, add PR-label classification if manual triage becomes too noisy.
    groups = {"Likely additions": [], "Other changes requiring manual review": []}
    for commit in commits:
        sha = commit["sha"]
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Invalid upstream commit SHA")
        subject = commit["commit"]["message"].partition("\n")[0]
        label = "Likely additions" if FEATURE.match(subject) else "Other changes requiring manual review"
        title = html.escape(subject[:300]).replace("`", "&#96;")
        groups[label].append(f"- [ ] [{sha[:10]}](https://github.com/{UPSTREAM}/commit/{sha}) <code>{title}</code>\n")
    prefix = (f"## Upstream candidates: {base[:10]} → {head[:10]}\n\n"
              f"[Complete comparison](https://github.com/{UPSTREAM}/compare/{base}...{head})\n\n"
              "Unchecked means unreviewed, not approved. Adopt only UI, controls or duplicate-item changes; "
              "reject balance changes. Keep classic controls and make optional behavior reversible.\n\n")
    bodies = []
    body = prefix
    for label, rows in groups.items():
        if not rows:
            continue
        section = f"### {label}\n\n"
        body += section
        for row in rows:
            if len((body + row).encode()) > 58000:
                bodies.append(body)
                body = prefix + section
            body += row
    if commits:
        bodies.append(body)
    return [(f"<!-- upstream-report:{base}:{head}:{index} -->", body)
            for index, body in enumerate(bodies)]


def find_tracker(repo):
    pages = api(f"repos/{repo}/issues?state=all&per_page=100", paginate=True)
    owner = repo.split("/")[0].lower()
    issues = [issue for page in pages for issue in page
              if "pull_request" not in issue and TRACKER in (issue.get("body") or "")
              and (issue.get("user") or {}).get("login", "").lower() in (owner, "github-actions[bot]")]
    if len(issues) > 1:
        raise ValueError("Multiple upstream trackers; resolve duplicate checkpoints first")
    if issues and issues[0]["state"] != "open":
        raise ValueError("Upstream tracker is closed; reopen it to resume, rejected reports are not reopened")
    return issues[0] if issues else None


def publish(repo, tracker, base, head, parts):
    if tracker is None:
        tracker = api(f"repos/{repo}/issues", method="POST", data={
            "title": "Upstream BN feature candidates",
            "body": (f"{TRACKER}\n\n<!-- upstream-checkpoint:{base} -->\n\n"
                     "CI appends all new upstream commits as review checklists. Mark adopted or rejected "
                     "candidates in their report; CI never overwrites those decisions or ports code. "
                     "Close this tracker to stop reporting.\n")})
    endpoint = f"repos/{repo}/issues/{tracker['number']}"
    pages = api(f"{endpoint}/comments?per_page=100", paginate=True)
    existing = {comment.get("body") or "" for page in pages for comment in page
                if (comment.get("user") or {}).get("login", "").lower() in (repo.split('/')[0].lower(), "github-actions[bot]")}
    for marker, body in parts:
        if not any(comment.startswith(marker) for comment in existing):
            api(f"{endpoint}/comments", method="POST", data={"body": marker + "\n\n" + body})
    current = api(endpoint)
    if CHECKPOINT.findall(current.get("body") or "") != [base]:
        raise ValueError("Checkpoint changed during reporting; saved reports must be reviewed before advancing")
    body, count = CHECKPOINT.subn(f"<!-- upstream-checkpoint:{head} -->", current["body"])
    if count != 1:
        raise ValueError("Missing or ambiguous tracker checkpoint; reports saved but checkpoint not advanced")
    api(endpoint, method="PATCH", data={"body": body})
    print(tracker["html_url"])


def self_check():
    a, b = "a" * 40, "b" * 40
    first = {"sha": a, "commit": {"message": "feat(ui): add a readable box"}}
    second = {"sha": b, "commit": {"message": "Unclassified <script>alert(1)</script>"}}
    pages = [{"status": "ahead", "total_commits": 2, "commits": [first]},
             {"commits": [second]}]
    assert commits_from_pages(pages) == [first, second]
    for broken in (pages[:1], [pages[0], {"commits": [first]}],
                   [{"status": "diverged", "total_commits": 0, "commits": []}]):
        try:
            commits_from_pages(broken)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe comparison must not advance a checkpoint")
    parts = report_parts(a, b, [first, second])
    text = "".join(body for _, body in parts)
    assert f"/commit/{a}" in text and f"/commit/{b}" in text
    assert "<script>" not in text and "&lt;script&gt;" in text
    empty = report_parts(a, b, [{"sha": a, "commit": {"message": ""}}])
    assert f"/commit/{a}" in empty[0][1]
    large = [{"sha": f"{i:040x}", "commit": {"message": "feat: " + "界" * 400}}
             for i in range(300)]
    chunks = report_parts(a, b, large)
    assert all(len((marker + "\n\n" + body).encode()) < 60000 for marker, body in chunks)
    assert sum(body.count("- [ ]") for _, body in chunks) == 300
    assert report_parts(a, a, []) == []
    print("PASS upstream comparison boundaries, complete chunking and untrusted subjects")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="Kenja-mc/Cataclysm-BN")
    parser.add_argument("--initial-ref", default="a27f19d",
                        help="last upstream merge, used only until the tracker has a checkpoint")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        parser.error("--repo must be owner/repository")
    if not re.fullmatch(r"[0-9a-f]{7,40}", args.initial_ref):
        parser.error("--initial-ref must be an upstream commit SHA")
    tracker = find_tracker(args.repo)
    if tracker:
        checkpoints = CHECKPOINT.findall(tracker["body"])
        if len(checkpoints) != 1:
            raise ValueError("Tracker requires exactly one checkpoint")
        base = checkpoints[0]
    else:
        base = api(f"repos/{UPSTREAM}/commits/{args.initial_ref}")["sha"]
    head = api(f"repos/{UPSTREAM}/commits/main")["sha"]
    commits = commits_from_pages(api(f"repos/{UPSTREAM}/compare/{base}...{head}?per_page=100", paginate=True))
    parts = report_parts(base, head, commits)
    if args.dry_run:
        for marker, body in parts:
            print(marker + "\n\n" + body)
        print(f"{len(commits)} commits; {len(parts)} report parts; checkpoint {base} → {head}; no writes")
    elif parts:
        publish(args.repo, tracker, base, head, parts)
    else:
        print(f"Upstream unchanged at {head}; no writes")


if __name__ == "__main__":
    main()
