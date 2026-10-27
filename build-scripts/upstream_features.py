#!/usr/bin/env python3
"""File one deduplicated issue per upstream feature and keep a tracker for everything else.

Upstream is read-only: every upstream request is a GET, and a write to it is refused before `gh`
runs. The target repository gets one issue per clear upstream feature, identified by the upstream
PR reference (`(#NNNNN)`) and grouped by it, so several commits of one feature share a ticket; PRs
merged with merge commits map their branch commits to the same PR. A feature is a non-merge commit
whose subject is a conventional `feat:`/`feature:` commit outside the `balance` scope, which the
fork rules reject wholesale. Every other new commit stays in the tracker checklist for manual
classification, later commits for a closed feature issue are listed there too, and commits the fork
already merged are skipped. Closing the tracker stops reporting without failing the workflow.

All writes carry stable markers, so partial failures and reruns never duplicate an issue, a comment
or a checklist row. The checkpoint advances one batch at a time, only after that batch's issues and
rows exist, so a failure keeps the work that already landed. The tracker's CI-owned intro is
refreshed in place, leaving human edits alone.
"""
import argparse
import contextlib
import hashlib
import html
import io
import json
import re
import subprocess
import time

UPSTREAM = "cataclysmbn/Cataclysm-BN"
TRACKER = "<!-- overhaul-upstream-feature-watch -->"
TRACKER_INTRO_START = "<!-- upstream-watch:intro -->"
TRACKER_INTRO_END = "<!-- /upstream-watch:intro -->"
TRACKER_INTRO = (
    "CI files one issue per clear upstream feature, labelled `upstream-candidate`, and lists every "
    "other new commit here for manual classification. Later commits for a closed feature are listed "
    "here too, so a rejected feature never hides new work. Mark adopted or rejected candidates; CI "
    "never overwrites those decisions or ports code. Close this tracker to stop reporting.\n")
LEGACY_TRACKER_INTROS = (
    "CI appends all new upstream commits as review checklists. Mark adopted or rejected candidates "
    "in their report; CI never overwrites those decisions or ports code. Close this tracker to stop "
    "reporting.",
    "CI files one issue per clear upstream feature and lists every other new commit here for manual "
    "classification. Mark adopted or rejected candidates; CI never overwrites those decisions or "
    "ports code. Close this tracker to stop reporting.",
)
CHECKPOINT = re.compile(r"<!-- upstream-checkpoint:([0-9a-f]{40}) -->")
FEATURE_MARKER = re.compile(
    r"^[ \t]*<!-- upstream-feature:([a-z0-9][a-z0-9-]{0,118}) -->[ \t]*$", re.M)
COMMIT_MARKER = re.compile(r"<!-- upstream-commit:([0-9a-f]{40}) -->")
FEATURE_COMMIT_MARKER = re.compile(r"<!-- upstream-feature-commit:([0-9a-f]{40}) -->")
FEATURE_LINK_MARKER = re.compile(r"<!-- upstream-feature-link:([a-z0-9][a-z0-9-]{0,118}) -->")
COMMIT_LINK = re.compile(r"https://github\.com/" + re.escape(UPSTREAM) + r"/commit/([0-9a-f]{40})")
FEATURE_SUBJECT = re.compile(
    r"^(?P<kind>feat|feature)(?:\((?P<scope>[^()\s]{1,40})\))?(?P<breaking>!)?:[ \t]+(?P<title>\S.*)$",
    re.I,
)
PR_REF = re.compile(r"\(#(?P<pr>[0-9]{1,7})\)\s*$")
MERGE_SUBJECT = re.compile(r"^Merge pull request #(?P<pr>[0-9]{1,7}) from ", re.I)
SHA = re.compile(r"[0-9a-f]{40}")
LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")
ISSUE_URL = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/[0-9]+")
REPO = "Kenja-mc/Cataclysm-BN"
REPO_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
CANDIDATE_LABEL = "upstream-candidate"
BLOCKED_SCOPES = {"balance"}

BODY_BUDGET = 58000       # GitHub stops at 65536 characters per comment.
COMPARE_LIMIT = 250       # The compare endpoint returns at most 250 commits per response.
MAX_COMMIT_PAGES = 40
# Checkpoint granularity: each batch of commits is fully written before the checkpoint moves,
# and a run stops after this many batches or issues so a backfill stays inside rate limits and
# the next run resumes from the checkpoint.
BATCH_COMMITS = 20
MAX_BATCHES = 10
MAX_NEW_ISSUES = 25
RETRY_MARKERS = ("rate limit", "http 403", "http 429", "abuse detection")


def api(endpoint, *, data=None, method="GET", paginate=False):
    """Run one `gh api` call. Upstream is never written; throttling is retried."""
    if method != "GET" and endpoint.split("?", 1)[0].startswith(f"repos/{UPSTREAM}/"):
        raise ValueError("Refusing to change the upstream repository")
    command = ["gh", "api", "--hostname", "github.com", "--method", method, endpoint]
    if paginate:
        command += ["--paginate", "--slurp"]
    if data is not None:
        command += ["--input", "-"]
    payload = None if data is None else json.dumps(data)
    result = None
    for attempt in range(4):
        result = subprocess.run(command, input=payload, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            break
        if attempt == 3 or not any(word in result.stderr.lower() for word in RETRY_MARKERS):
            raise RuntimeError(f"gh api {method} {endpoint} failed: {result.stderr.strip()[:500]}")
        time.sleep(2 ** attempt)
    if result is None or not result.stdout.strip():
        raise ValueError(f"Empty response from {endpoint}")
    return json.loads(result.stdout)


def plain(value, limit):
    """Collapse untrusted text, name PR refs and drop mention and issue-reference sigils."""
    text = "".join(ch for ch in str(value) if ch.isprintable() or ch in "\t\n\r ")
    text = " ".join(text.split())[:limit].strip()
    text = re.sub(r"\(#([0-9]{1,7})\)", r"(PR \1)", text)
    text = re.sub(r"(?<![A-Za-z0-9])@(?=[A-Za-z0-9])", "", text)
    return re.sub(r"#(?=[0-9])", "", text)


def escape(value):
    return html.escape(str(value), quote=True).replace("`", "&#96;")


def safe(value, limit=300):
    return escape(plain(value, limit))


def commit_url(sha):
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise ValueError("Invalid upstream commit SHA")
    return f"https://github.com/{UPSTREAM}/commit/{sha}"


def safe_issue_url(url):
    if not isinstance(url, str) or not ISSUE_URL.fullmatch(url):
        raise ValueError("Unexpected issue URL in an API response")
    return url


def commit_subject(commit):
    message = (commit.get("commit") or {}).get("message") if isinstance(commit, dict) else None
    if not isinstance(message, str):
        raise ValueError("Malformed upstream commit")
    return message.partition("\n")[0].strip()


def feature_slug(scope, title):
    key = " ".join(f"{scope}:{title}".lower().split())
    readable = re.sub(r"[^a-z0-9]+", "-", key).strip("-")[:60].strip("-") or "feature"
    return f"{readable}-{hashlib.sha256(key.encode()).hexdigest()[:12]}"


def feature_from_commit(commit, pr_map=None):
    """Return the clear feature this commit declares, or None for manual classification."""
    if not isinstance(commit, dict) or not isinstance(commit.get("sha"), str) \
            or not SHA.fullmatch(commit["sha"]):
        raise ValueError("Invalid upstream commit SHA")
    subject = commit_subject(commit)
    if len(commit.get("parents") or []) > 1:
        return None  # A merge repeats the branch commits; classify the commits themselves.
    match = FEATURE_SUBJECT.match(subject)
    if not match:
        return None
    scope = (match.group("scope") or "").strip()
    if BLOCKED_SCOPES & {part.strip().lower() for part in re.split(r"[/,]", scope)}:
        return None  # Balance work is rejected wholesale by the fork rules.
    title = " ".join(match.group("title").split())
    pr = ""
    pr_match = PR_REF.search(title)
    if pr_match:
        pr = pr_match.group("pr")
        title = title[:pr_match.start()].strip()
    if not pr and pr_map:
        pr = str(pr_map.get(commit["sha"], ""))
    if not pr.isdigit():
        pr = ""
    if not title:
        return None
    author = (commit.get("author") or {}).get("login") or ""
    return {
        "sha": commit["sha"],
        "scope": scope,
        "title": title,
        "pr": pr,
        "key": f"pr-{pr}" if pr else feature_slug(scope, title),
        "breaking": bool(match.group("breaking")),
        "subject": subject,
        "author": author if LOGIN.fullmatch(author) else "",
    }


def classify(commits, merged=(), pr_map=None):
    """Split a range into feature candidates, uncertain commits and already-merged commits."""
    features, uncertain, already = [], [], []
    for commit in commits:
        feature = feature_from_commit(commit, pr_map)
        if commit["sha"] in merged:
            already.append(commit)
        elif feature is None:
            uncertain.append(commit)
        else:
            features.append(feature)
    return features, uncertain, already


def group_features(features):
    groups = {}
    for feature in features:
        groups.setdefault(feature["key"], []).append(feature)
    return groups


def chunked(items, size):
    return [items[index:index + size] for index in range(0, len(items), size)]


def compare_range(base, head, api=api):
    """Return the compare payload and every page of commits, rejecting incomplete or duplicate pages."""
    for ref in (base, head):
        if not isinstance(ref, str) or not SHA.fullmatch(ref):
            raise ValueError("Invalid comparison ref")
    pages = api(f"repos/{UPSTREAM}/compare/{base}...{head}?per_page=100", paginate=True)
    if not isinstance(pages, list) or not pages or not isinstance(pages[0], dict):
        raise ValueError("Empty comparison response")
    total = pages[0].get("total_commits")
    if not isinstance(total, int) or total < 0:
        raise ValueError("Missing comparison commit count; checkpoint not advanced")
    commits = []
    for page in pages:
        page_commits = page.get("commits") if isinstance(page, dict) else None
        if not isinstance(page_commits, list):
            raise ValueError("Malformed comparison page; checkpoint not advanced")
        commits.extend(page_commits)
    shas = [commit.get("sha") if isinstance(commit, dict) else None for commit in commits]
    if len(commits) > total or len(set(shas)) != len(commits):
        raise ValueError("Incomplete or duplicate comparison pages; checkpoint not advanced")
    return pages[0], commits


def collect_commits(base, head, api=api):
    """Return every commit from base to head, walking history past the compare cap if needed."""
    payload, commits = compare_range(base, head, api=api)
    if payload.get("status") not in ("ahead", "identical"):
        raise ValueError("Upstream ancestry changed; review the checkpoint rather than skipping commits")
    total = payload["total_commits"]
    if len(commits) < total:
        if total <= COMPARE_LIMIT:
            raise ValueError("Incomplete comparison pages; checkpoint not advanced")
        commits = walk_commits(base, head, total, api=api)
    if commits and commits[-1].get("sha") != head:
        raise ValueError("Comparison did not end at the upstream head; checkpoint not advanced")
    return commits


def walk_commits(base, head, total, api=api):
    """Read oldest-first commits from the head history when compare truncated at its cap."""
    commits, seen = [], set()
    for page in range(1, MAX_COMMIT_PAGES + 1):
        batch = api(f"repos/{UPSTREAM}/commits?sha={head}&per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ValueError("Malformed commit page; checkpoint not advanced")
        if not batch:
            break
        for commit in batch:
            if not isinstance(commit, dict) or not isinstance(commit.get("sha"), str) \
                    or not SHA.fullmatch(commit["sha"]):
                raise ValueError("Invalid upstream commit SHA")
            if commit["sha"] == base:
                commits.reverse()
                if len(commits) != total:
                    raise ValueError("Commit walk disagrees with the comparison; checkpoint not advanced")
                return commits
            if commit["sha"] in seen:
                raise ValueError("Duplicate commits in the upstream walk; checkpoint not advanced")
            seen.add(commit["sha"])
            commits.append(commit)
    raise ValueError("Upstream walk did not reach the checkpoint; checkpoint not advanced")


def merge_pr_map(commits, api=api):
    """Map branch commits of merge-commit PRs to their PR so their features group reliably."""
    mapping = {}
    for commit in commits:
        parents = commit.get("parents") or []
        if len(parents) < 2:
            continue
        subject = commit_subject(commit)
        match = MERGE_SUBJECT.match(subject)
        pr = match.group("pr") if match else ""
        if not pr:
            pr_match = PR_REF.search(subject)
            pr = pr_match.group("pr") if pr_match else ""
        if not pr:
            continue
        first = (parents[0] or {}).get("sha")
        second = (parents[1] or {}).get("sha")
        if not isinstance(first, str) or not SHA.fullmatch(first) \
                or not isinstance(second, str) or not SHA.fullmatch(second):
            continue
        try:
            payload, branch = compare_range(first, second, api=api)
        except ValueError:
            print(f"warning: cannot read the branch commits for upstream PR {pr}")
            continue
        if len(branch) < payload.get("total_commits", 0):
            print(f"warning: partial branch commit list for upstream PR {pr}")
        for branch_commit in branch:
            mapping.setdefault(branch_commit["sha"], pr)
    return mapping


def merged_in_range(repo, base, api=api):
    """Return commits in base..head the fork already merged, plus the fork's upstream merge base."""
    payload = api(f"repos/{repo}/compare/main...{UPSTREAM.split('/')[0]}:main?per_page=1")
    merge_base = (payload.get("merge_base_commit") or {}).get("sha") if isinstance(payload, dict) else None
    if not isinstance(merge_base, str) or not SHA.fullmatch(merge_base):
        raise ValueError("Could not read the fork's upstream merge base")
    if merge_base == base:
        return set(), merge_base
    status = api(f"repos/{UPSTREAM}/compare/{base}...{merge_base}?per_page=1")
    state = status.get("status") if isinstance(status, dict) else None
    if state in ("behind", "identical"):
        return set(), merge_base
    if state != "ahead":
        raise ValueError("Checkpoint is not on the upstream history; review the checkpoint")
    return {commit["sha"] for commit in collect_commits(base, merge_base, api=api)}, merge_base


def feature_title(commits):
    first = commits[0]
    name = f"{first['scope']}: {first['title']}" if first["scope"] else first["title"]
    return plain(f"[upstream] {name}" if name else f"[upstream] feature {first['sha'][:10]}", 200)


def feature_body(key, commits):
    first = commits[0]
    pr = next((commit["pr"] for commit in commits if commit["pr"]), "")
    author = f"`{safe(first['author'], 40)}`" if first["author"] else "unknown"
    scope = f"`{safe(first['scope'], 60)}`" if first["scope"] else "none"
    lines = [
        f"<!-- upstream-feature:{key} -->",
        "",
        f"Upstream declared this feature in commit [`{first['sha'][:10]}`]({commit_url(first['sha'])}).",
        "",
        f"- Author: {author}",
        f"- Scope: {scope}",
    ]
    if pr:
        lines.append(f"- Upstream PR: {pr}")
    lines += [
        f"- Breaking: {'yes' if first['breaking'] else 'no'}",
        "",
        "### Commits",
        "",
    ]
    for commit in commits:
        lines.append(f"- [ ] [`{commit['sha'][:10]}`]({commit_url(commit['sha'])}) "
                     f"<code>{safe(commit['subject'], 300)}</code> "
                     f"<!-- upstream-commit:{commit['sha']} -->")
    lines += [
        "",
        "Check a commit once it has been reviewed. Adopting a change stays manual; closing this "
        "issue records rejection, later commits for it are listed in the tracker instead, and the "
        "watcher will not reopen or refile it. The watcher only reads the upstream. Fork policy: "
        "keep classic controls, make optional behavior reversible, reject balance changes.",
    ]
    return "\n".join(lines) + "\n"


def feature_commit_comment(commit):
    return ("<!-- upstream-feature-commit:{sha} -->\n\n"
            "New upstream commit for this feature: [`{short}`]({url}) <code>{subject}</code>\n"
            ).format(sha=commit["sha"], short=commit["sha"][:10],
                     url=commit_url(commit["sha"]), subject=safe(commit["subject"], 300))


def report_row(commit):
    sha = commit["sha"]
    return (f"- [ ] [`{sha[:10]}`]({commit_url(sha)}) "
            f"<code>{safe(commit_subject(commit), 300)}</code> "
            f"<!-- upstream-commit:{sha} -->\n")


def feature_link_row(state):
    first = state["commits"][0]
    name = f"{first['scope']}: {first['title']}" if first["scope"] else first["title"]
    count = len(state["commits"])
    suffix = f" — {count} commit{'s' if count != 1 else ''}"
    if state.get("url"):
        row = f'- [ ] <a href="{state["url"]}">{safe(name, 120)}</a>{suffix}'
    else:
        row = f"- [ ] {safe(name, 120)}{suffix}"
    if state.get("pr"):
        row += f" — upstream PR {state['pr']}"
    if state.get("rejected"):
        row += " — rejected (issue closed)"
    return f'{row} <!-- upstream-feature-link:{state["key"]} -->\n'


def rejected_row(state, feature):
    sha = feature["sha"]
    number = f"#{state['number']}" if state.get("number") else "the feature issue"
    row = (f"- [ ] [`{sha[:10]}`]({commit_url(sha)}) "
           f"<code>{safe(feature['subject'], 300)}</code> — {number} is closed")
    return f"{row} <!-- upstream-commit:{sha} -->\n"


def report_parts(base, head, uncertain, states, reported, reported_features, rejected=()):
    pending = [commit for commit in uncertain if commit["sha"] not in reported]
    pending_features = [state for state in states.values() if state["key"] not in reported_features]
    pending_rejected = [(state, commit) for state, commit in rejected if commit["sha"] not in reported]
    if not pending and not pending_features and not pending_rejected:
        return []
    prefix = (
        f"## Upstream candidates: {base[:10]} → {head[:10]}\n\n"
        f"[Complete comparison](https://github.com/{UPSTREAM}/compare/{base}...{head})\n\n"
        "Unchecked means unreviewed, not approved. Adopt only UI, controls or duplicate-item changes; "
        "reject balance changes. Keep classic controls and make optional behavior reversible.\n\n"
    )
    sections = []
    if pending_features:
        sections.append(("### Feature issues", [feature_link_row(state) for state in pending_features]))
    if pending_rejected:
        sections.append(("### Commits for closed feature issues",
                         [rejected_row(state, commit) for state, commit in pending_rejected]))
    if pending:
        sections.append(("### Commits awaiting classification", [report_row(commit) for commit in pending]))
    bodies, body = [], prefix
    for heading, rows in sections:
        if len((body + heading).encode()) > BODY_BUDGET:
            bodies.append(body)
            body = prefix
        body += heading + "\n\n"
        for row in rows:
            if len((body + row).encode()) > BODY_BUDGET:
                bodies.append(body)
                body = prefix + heading + "\n\n"
            body += row
        body += "\n"
    bodies.append(body)
    return bodies


def owned_issues(repo, api=api):
    pages = api(f"repos/{repo}/issues?state=all&per_page=100", paginate=True)
    if not isinstance(pages, list):
        raise ValueError("Unexpected issue listing")
    owner = repo.split("/")[0].lower()
    issues = []
    for page in pages:
        for issue in page:
            if not isinstance(issue, dict) or "pull_request" in issue:
                continue
            login = ((issue.get("user") or {}).get("login") or "").lower().split("[")[0]
            if login in (owner, "github-actions"):
                issues.append(issue)
    return issues


def is_tracker(issue):
    return (issue.get("body") or "").lstrip().startswith(TRACKER)


def find_tracker(issues):
    trackers = [issue for issue in issues if is_tracker(issue)]
    if len(trackers) > 1:
        raise ValueError("Multiple upstream trackers; resolve duplicate checkpoints first")
    return trackers[0] if trackers else None


def checkpoint_of(tracker):
    checkpoints = CHECKPOINT.findall(tracker.get("body") or "")
    if len(checkpoints) != 1:
        raise ValueError("Tracker requires exactly one checkpoint")
    return checkpoints[0]


def tracker_stopped(tracker):
    return tracker is not None and tracker.get("state") != "open"


def feature_keys(body):
    """Read feature markers from their own line; inline prose cannot fake an issue."""
    return sorted(set(FEATURE_MARKER.findall(body or "")))


def find_feature_issues(issues):
    known = {}
    for issue in issues:
        login = ((issue.get("user") or {}).get("login") or "").lower()
        labels = {label.get("name") for label in issue.get("labels") or [] if isinstance(label, dict)}
        if not login.startswith("github-actions") and CANDIDATE_LABEL not in labels:
            continue  # Prose pasted into a human issue must not hijack a feature key.
        keys = feature_keys(issue.get("body"))
        if len(keys) > 1:
            raise ValueError(f"Feature issue #{issue.get('number')} records multiple features")
        for key in keys:
            if key in known:
                raise ValueError(f"Multiple issues record the feature {key}; keep one and retitle the other")
            known[key] = issue
    return known


def recorded_shas(repo, issue, api=api):
    body = issue.get("body") or ""
    shas = set(COMMIT_MARKER.findall(body)) | set(FEATURE_COMMIT_MARKER.findall(body))
    pages = api(f"repos/{repo}/issues/{issue['number']}/comments?per_page=100", paginate=True)
    if not isinstance(pages, list):
        raise ValueError("Unexpected issue comment listing")
    for page in pages:
        for comment in page:
            text = comment.get("body") or ""
            shas |= set(COMMIT_MARKER.findall(text))
            shas |= set(FEATURE_COMMIT_MARKER.findall(text))
    return shas


def tracker_marks(repo, tracker, api=api):
    """Return the commit SHAs and feature keys already recorded in tracker comments by CI."""
    commits, features = set(), set()
    owner = repo.split("/")[0].lower()
    pages = api(f"repos/{repo}/issues/{tracker['number']}/comments?per_page=100", paginate=True)
    if not isinstance(pages, list):
        raise ValueError("Unexpected tracker comment listing")
    for page in pages:
        for comment in page:
            if not isinstance(comment, dict):
                continue
            login = ((comment.get("user") or {}).get("login") or "").lower().split("[")[0]
            if login not in (owner, "github-actions"):
                continue
            body = comment.get("body") or ""
            commits |= set(COMMIT_MARKER.findall(body))
            commits |= set(COMMIT_LINK.findall(body))  # rows from before per-commit markers
            features |= set(FEATURE_LINK_MARKER.findall(body))
    return commits, features


def ensure_label(repo, api=api):
    pages = api(f"repos/{repo}/labels?per_page=100", paginate=True)
    if not isinstance(pages, list):
        raise ValueError("Unexpected label listing")
    names = {label.get("name") for page in pages for label in page if isinstance(label, dict)}
    if CANDIDATE_LABEL in names:
        return
    api(f"repos/{repo}/labels", method="POST", data={
        "name": CANDIDATE_LABEL, "color": "0e8a16",
        "description": "Filed by CI from an upstream BN feature commit"})


def tracker_intro_block():
    return f"{TRACKER_INTRO_START}\n{TRACKER_INTRO}{TRACKER_INTRO_END}"


def refresh_tracker_body(body):
    """Replace the CI-owned intro with the current text, leaving human edits untouched."""
    managed = tracker_intro_block()
    if TRACKER_INTRO_START in body and TRACKER_INTRO_END in body:
        return re.sub(re.escape(TRACKER_INTRO_START) + r".*?" + re.escape(TRACKER_INTRO_END),
                      lambda _: managed, body, count=1, flags=re.S)
    for legacy in LEGACY_TRACKER_INTROS:
        if legacy in body:
            return body.replace(legacy, managed, 1)
    return body


def refresh_tracker(repo, tracker, apply=True, api=api):
    """Bring an existing tracker's CI prose up to date without touching the checkpoint or notes."""
    endpoint = f"repos/{repo}/issues/{tracker['number']}"
    current = api(endpoint)
    if not isinstance(current, dict):
        raise ValueError("Unexpected tracker response")
    body = current.get("body") or ""
    updated = refresh_tracker_body(body)
    if updated == body:
        return False
    if apply:
        api(endpoint, method="PATCH", data={"body": updated})
        print("Refreshed the tracker description for the feature-issue workflow")
    else:
        print("DRY RUN would refresh the tracker description")
    return True


def ensure_tracker(repo, tracker, base, api=api):
    if tracker is not None:
        return tracker
    body = (f"{TRACKER}\n\n<!-- upstream-checkpoint:{base} -->\n\n{tracker_intro_block()}\n")
    created = api(f"repos/{repo}/issues", method="POST", data={
        "title": "Upstream BN feature candidates", "body": body})
    if not isinstance(created, dict) or not isinstance(created.get("number"), int):
        raise ValueError("Tracker creation returned no number")
    return created


def ensure_feature_issues(repo, features, known, api=api, apply=True):
    """Create or extend exactly one issue per feature. `known` is updated as issues are created."""
    states = {}
    for key, commits in group_features(features).items():
        issue = known.get(key)
        state = {"key": key, "commits": commits, "number": None, "url": None,
                 "pr": next((commit["pr"] for commit in commits if commit["pr"]), ""),
                 "rejected": False, "created": False, "new_commits": []}
        if issue is not None:
            state["number"] = issue.get("number")
            state["url"] = safe_issue_url(issue.get("html_url"))
            state["rejected"] = issue.get("state", "open") != "open"
        if state["rejected"]:
            recorded = recorded_shas(repo, issue, api=api)
            state["new_commits"] = [commit["sha"] for commit in commits
                                    if commit["sha"] not in recorded]
            states[key] = state
            continue
        if issue is None:
            state["created"] = True
            if apply:
                created = api(f"repos/{repo}/issues", method="POST", data={
                    "title": feature_title(commits),
                    "body": feature_body(key, commits),
                    "labels": [CANDIDATE_LABEL]})
                if not isinstance(created, dict) or not isinstance(created.get("number"), int):
                    raise ValueError("Feature issue creation returned no number")
                known[key] = created
                state["number"] = created["number"]
                state["url"] = safe_issue_url(created.get("html_url"))
            states[key] = state
            continue
        recorded = recorded_shas(repo, issue, api=api)
        for commit in commits:
            if commit["sha"] in recorded:
                continue
            state["new_commits"].append(commit["sha"])
            if apply:
                api(f"repos/{repo}/issues/{state['number']}/comments", method="POST",
                    data={"body": feature_commit_comment(commit)})
            recorded.add(commit["sha"])
        states[key] = state
    return states


def advance_checkpoint(repo, tracker, base, head, api=api):
    endpoint = f"repos/{repo}/issues/{tracker['number']}"
    current = api(endpoint)
    if not isinstance(current, dict):
        raise ValueError("Unexpected tracker response; checkpoint not advanced")
    body = refresh_tracker_body(current.get("body") or "")
    if CHECKPOINT.findall(body) != [base]:
        raise ValueError("Checkpoint changed during reporting; saved reports must be reviewed before advancing")
    updated, count = CHECKPOINT.subn(f"<!-- upstream-checkpoint:{head} -->", body)
    if count != 1:
        raise ValueError("Missing or ambiguous tracker checkpoint; reports saved but checkpoint not advanced")
    if updated != body:
        api(endpoint, method="PATCH", data={"body": updated})


def pending_rejected(states):
    """Commits for closed feature issues that are not recorded yet, for the tracker."""
    rows = []
    for state in states.values():
        if not state["rejected"]:
            continue
        new = set(state["new_commits"])
        rows.extend((state, commit) for commit in state["commits"] if commit["sha"] in new)
    return rows


def publish(repo, tracker, base, head, commits, known, merged=(), pr_map=None, api=api, apply=True):
    """File issues and tracker rows; each completed batch advances the checkpoint."""
    if not apply:
        if tracker is None:
            print("DRY RUN would create the tracker issue")
            reported, reported_features = set(), set()
        else:
            reported, reported_features = tracker_marks(repo, tracker, api=api)
        features, uncertain, skipped = classify(commits, merged, pr_map)
        states = ensure_feature_issues(repo, features, known, api=api, apply=False)
        for state in states.values():
            if state["created"]:
                print(f"DRY RUN would create issue: {feature_title(state['commits'])}")
            for sha in state["new_commits"]:
                if state["rejected"]:
                    print(f"DRY RUN would list commit {sha[:10]} in the tracker "
                          f"(feature issue #{state['number']} is closed)")
                else:
                    print(f"DRY RUN would add commit {sha[:10]} to feature issue #{state['number']}")
        bodies = report_parts(base, head, uncertain, states, reported, reported_features,
                              pending_rejected(states))
        for body in bodies:
            print(body)
        print(f"DRY RUN: {len(commits)} commit(s), {len(states)} feature issue(s), "
              f"{len(skipped)} already merged, {len(bodies)} report comment(s); "
              f"checkpoint {base} → {head}; no writes")
        return

    tracker = ensure_tracker(repo, tracker, base, api=api)
    ensure_label(repo, api=api)
    batches = chunked(commits, BATCH_COMMITS)
    created, skipped_total, processed, current = 0, 0, 0, base
    for index, batch in enumerate(batches):
        if index >= MAX_BATCHES or created >= MAX_NEW_ISSUES:
            break
        end = batch[-1]["sha"]
        features, uncertain, skipped = classify(batch, merged, pr_map)
        skipped_total += len(skipped)
        states = ensure_feature_issues(repo, features, known, api=api)
        created += sum(1 for state in states.values() if state["created"])
        reported, reported_features = tracker_marks(repo, tracker, api=api)
        bodies = report_parts(current, end, uncertain, states, reported, reported_features,
                              pending_rejected(states))
        for body in bodies:
            api(f"repos/{repo}/issues/{tracker['number']}/comments", method="POST",
                data={"body": body})
        advance_checkpoint(repo, tracker, current, end, api=api)
        current, processed = end, processed + len(batch)
    print(f"Checkpoint {base} → {current}; {created} new feature issue(s); "
          f"{skipped_total} already merged")
    if processed < len(commits):
        print(f"{len(commits) - processed} commit(s) remain for the next run")
    print(tracker.get("html_url") or "")


BASE, HEAD = "a" * 40, "b" * 40


def commit(sha_char, subject, *, parents=1, author="octocat"):
    return raw_commit(sha_char * 40, subject, parents=parents, author=author)


def raw_commit(sha, subject, *, parents=1, author="octocat"):
    return {"sha": sha, "commit": {"message": subject + "\n\nbody"},
            "parents": [{"sha": "0" * 40} for _ in range(parents)], "author": {"login": author}}


class FakeGitHub:
    """Offline stand-in for the `gh api` calls the watcher makes."""

    def __init__(self, *, compare=None, walk=None, fail_when=None):
        self.calls = []
        self.issues = []
        self.comments = {}
        self.labels = []
        self.compare = compare or {"status": "identical", "total_commits": 0, "commits": []}
        self.compares = {}
        self.fork_compare = {"status": "diverged", "merge_base_commit": {"sha": BASE}}
        self.walk = walk or []
        self.fail_when = fail_when
        self._next = 1

    def issue(self, body, *, title="issue", state="open", login="github-actions[bot]"):
        number = self._next
        self._next += 1
        record = {"number": number, "title": title, "body": body, "state": state,
                  "html_url": f"https://github.com/{REPO}/issues/{number}",
                  "user": {"login": login}, "labels": []}
        self.issues.append(record)
        self.comments[number] = []
        return record

    def tracker(self, base):
        return self.issue(f"{TRACKER}\n\n<!-- upstream-checkpoint:{base} -->\n",
                          title="Upstream BN feature candidates")

    def find(self, number):
        return next(issue for issue in self.issues if issue["number"] == number)

    def __call__(self, endpoint, *, data=None, method="GET", paginate=False):
        self.calls.append((method, endpoint))
        if self.fail_when and self.fail_when(method, endpoint):
            raise RuntimeError("simulated API failure")
        if endpoint.startswith(f"repos/{REPO}/compare/"):
            assert endpoint == f"repos/{REPO}/compare/main...cataclysmbn:main?per_page=1"
            return self.fork_compare
        if endpoint.startswith(f"repos/{UPSTREAM}"):
            assert method == "GET", "the watcher must never write to upstream"
            if "/compare/" in endpoint:
                refs = endpoint.split("/compare/", 1)[1].split("?", 1)[0]
                payload = self.compares.get(refs, self.compare)
                if paginate:
                    return payload if isinstance(payload, list) else [payload]
                return payload[0] if isinstance(payload, list) else payload
            if endpoint.startswith(f"repos/{UPSTREAM}/commits/"):
                return {"sha": endpoint.split("?", 1)[0].rsplit("/", 1)[1]}
            page = int((re.search(r"[?&]page=(\d+)", endpoint) or [0, 1])[1])
            return self.walk[page - 1] if page <= len(self.walk) else []
        escaped = re.escape(REPO)
        if method == "GET" and endpoint == f"repos/{REPO}/issues?state=all&per_page=100":
            return [self.issues]
        if method == "GET" and endpoint == f"repos/{REPO}/labels?per_page=100":
            return [self.labels]
        if method == "POST" and endpoint == f"repos/{REPO}/labels":
            self.labels.append(data)
            return data
        match = re.fullmatch(rf"repos/{escaped}/issues/(\d+)/comments\?per_page=100", endpoint)
        if method == "GET" and match:
            return [self.comments[int(match.group(1))]]
        if method == "POST" and endpoint == f"repos/{REPO}/issues":
            return self.issue(data["body"], title=data["title"])
        match = re.fullmatch(rf"repos/{escaped}/issues/(\d+)/comments", endpoint)
        if method == "POST" and match:
            number = int(match.group(1))
            comment = {"body": data["body"], "user": {"login": "github-actions[bot]"}}
            self.comments.setdefault(number, []).append(comment)
            return comment
        match = re.fullmatch(rf"repos/{escaped}/issues/(\d+)", endpoint)
        if match:
            record = self.find(int(match.group(1)))
            if method == "GET":
                return record
            if method == "PATCH":
                record.update(data)
                return record
        raise AssertionError(f"unexpected request {method} {endpoint}")


def watch(fake, apply=True):
    """Run the main flow against the fake API."""
    issues = owned_issues(REPO, api=fake)
    tracker = find_tracker(issues)
    if tracker_stopped(tracker):
        return
    known = find_feature_issues(issues)
    base = checkpoint_of(tracker) if tracker is not None else BASE
    if base == HEAD:
        return
    if tracker is not None:
        refresh_tracker(REPO, tracker, apply=apply, api=fake)
    merged, _ = merged_in_range(REPO, base, api=fake)
    commits = collect_commits(base, HEAD, api=fake)
    pr_map = merge_pr_map(commits, api=fake)
    publish(REPO, tracker, base, HEAD, commits, known, merged, pr_map, api=fake, apply=apply)


def check_classification():
    a = commit("a", "feat(ui): add a readable box (#10730)")
    a2 = commit("b", "feat(ui): tighten the readable box (#10730)")
    b = commit("c", "feat!: replace the old box (#10731)")
    c = commit("d", "feat: plain feature")
    balance = commit("e", "feat(balance): rebuff the box (#10720)")
    mixed = commit("f", "feat(balance,ui): rebuff the box")
    merge = commit("1", "feat: merge from a branch", parents=2)
    fix = commit("2", "fix(UI): repair the box (#10732)")
    prose = commit("3", "Add a readable box")
    features, uncertain, already = classify([a, a2, b, c, balance, mixed, merge, fix, prose])
    assert [item["title"] for item in features] == [
        "add a readable box", "tighten the readable box", "replace the old box", "plain feature"]
    assert features[0]["scope"] == "ui" and features[0]["pr"] == "10730"
    assert features[0]["key"] == "pr-10730" == features[1]["key"]
    assert features[2]["breaking"] is True and features[3]["scope"] == ""
    assert len(group_features(features[:2])) == 1
    assert uncertain == [balance, mixed, merge, fix, prose] and already == []
    assert feature_slug("ui", "Add a  readable box") == feature_slug("UI", "add a readable box")
    assert feature_slug("", "add a readable box") != feature_slug("ui", "add a readable box")
    assert len(feature_slug("x", "y" * 500)) <= 120
    assert feature_from_commit(commit("4", "feat: (#123)")) is None
    assert classify([commit("5", "feat: (#123)")])[0] == []
    mapped = commit("7", "feat: load sound volumes as decibel units")
    features, _, _ = classify([mapped], pr_map={mapped["sha"]: "9377"})
    assert features[0]["key"] == "pr-9377" and features[0]["pr"] == "9377"
    assert classify([mapped])[0][0]["key"] != "pr-9377"
    for broken in ({"sha": "nope", "commit": {"message": "feat: x"}}, "text",
                   {"sha": "a" * 40}, {"sha": "a" * 40, "commit": {}}):
        try:
            classify([broken])
        except ValueError:
            pass
        else:
            raise AssertionError("malformed commits must raise")


def check_untrusted_text():
    hostile = commit("c", "feat(ui): <script>alert(1)</script> @evil #13 `tick` "
                          "<!-- upstream-checkpoint:" + "0" * 40 + " --> (#999)")
    feature = feature_from_commit(hostile)
    title = feature_title([feature])
    assert "\n" not in title and "\t" not in title
    assert "evil" in title and "@evil" not in title and "#13" not in title
    assert len(feature_title([feature] * 5)) <= 200
    body = feature_body(feature["key"], [feature])
    assert "<script>" not in body and "&lt;script&gt;" in body and "&#96;" in body
    assert f"<!-- upstream-feature:{feature['key']} -->" in body
    assert body.count("<!--") == 2  # the feature marker plus the one commit marker
    row = report_row(hostile)
    assert "<script>" not in row and row.count("<!--") == 1 and "@evil" not in row
    state = {"key": "pr-9", "commits": [feature], "number": 7, "pr": "999",
             "url": "https://github.com/Kenja-mc/Cataclysm-BN/issues/7", "rejected": False}
    link = feature_link_row(state)
    assert "issues/7" in link and "<script>" not in link
    try:
        safe_issue_url("https://evil.example/issues/1")
    except ValueError:
        pass
    else:
        raise AssertionError("foreign issue URLs must be rejected")
    try:
        api(f"repos/{UPSTREAM}/issues", method="POST", data={"title": "x"})
    except ValueError:
        pass
    else:
        raise AssertionError("upstream writes must be refused")
    assert feature_keys("prose <!-- upstream-feature:quoted --> more\n") == []
    assert feature_keys("note\n\n<!-- upstream-feature:kept -->\n") == ["kept"]
    assert plain("ping @evil, mail a@b.c, see owner/repo#123", 100) == \
        "ping evil, mail a@b.c, see owner/repo123"


def check_comparison():
    base, head = "f" * 40, "e" * 40
    commits = [{"sha": head, "commit": {"message": "feat: newest"},
                "parents": [{"sha": "0" * 40}], "author": {"login": "octocat"}}]
    commits += [{"sha": f"{index:040x}", "commit": {"message": f"feat: {index}"},
                 "parents": [{"sha": "0" * 40}], "author": {"login": "octocat"}}
                for index in range(258, -1, -1)]
    assert len(commits) == 260
    fake = FakeGitHub(compare={"status": "ahead", "total_commits": 260, "commits": commits[:250]},
                      walk=[commits[0:100], commits[100:200], commits[200:] + [{"sha": base}]])
    result = collect_commits(base, head, api=fake)
    assert [item["sha"] for item in result] == [item["sha"] for item in reversed(commits)]
    small = [commit("1", "feat: one"), commit("e", "fix: two")]
    fake = FakeGitHub(compare={"status": "ahead", "total_commits": 2, "commits": small})
    assert collect_commits(base, head, api=fake) == small
    pages = [{"status": "ahead", "total_commits": 3, "commits": [commit("1", "feat: one")]},
             {"commits": [commit("2", "fix: two"), commit("e", "chore: three")]}]
    result = collect_commits(base, head, api=FakeGitHub(compare=pages))
    assert [item["sha"] for item in result] == ["1" * 40, "2" * 40, head], \
        "every comparison page must be collected"
    duplicate = [pages[0], {"commits": [commit("1", "feat: one"), commit("e", "chore: three")]}]
    try:
        collect_commits(base, head, api=FakeGitHub(compare=duplicate))
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate commits across pages must fail")
    broken = [
        FakeGitHub(compare={"status": "diverged", "total_commits": 0, "commits": []}),
        FakeGitHub(compare={"status": "ahead", "commits": small}),
        FakeGitHub(compare={"status": "ahead", "total_commits": 2, "commits": [small[0], small[0]]}),
        FakeGitHub(compare={"status": "ahead", "total_commits": 3, "commits": small}),
        FakeGitHub(compare={"status": "ahead", "total_commits": 260, "commits": commits[:250]},
                   walk=[commits[:100]]),
        FakeGitHub(compare={"status": "ahead", "total_commits": 2, "commits": small},
                   fail_when=lambda method, endpoint: True),
    ]
    for fake in broken:
        try:
            collect_commits(base, head, api=fake)
        except (ValueError, RuntimeError):
            pass
        else:
            raise AssertionError("unsafe comparison must not advance a checkpoint")
    for ref in ("nope", "a" * 39, None):
        try:
            collect_commits(ref, head, api=FakeGitHub())
        except ValueError:
            pass
        else:
            raise AssertionError("invalid comparison refs must raise")


def check_reporting():
    base, head = "a" * 40, "b" * 40
    uncertain = [raw_commit(f"{index:040x}", "fix: " + "界" * 300) for index in range(300)]
    bodies = report_parts(base, head, uncertain, {}, set(), set())
    assert all(len(body.encode()) <= BODY_BUDGET for body in bodies)
    assert sum(body.count("<!-- upstream-commit:") for body in bodies) == 300
    assert sum(body.count("- [ ]") for body in bodies) == 300
    assert report_parts(base, head, [], {}, set(), set()) == []
    reported = {item["sha"] for item in uncertain}
    assert report_parts(base, head, uncertain, {}, reported, set()) == []
    closed = feature_from_commit(commit("d", "feat(ui): a closed box (#8)"))
    closed_state = {"key": "pr-8", "commits": [closed], "number": 42, "pr": "8",
                    "rejected": True, "new_commits": [closed["sha"]],
                    "url": "https://github.com/Kenja-mc/Cataclysm-BN/issues/42"}
    bodies = report_parts(base, head, [], {}, set(), set(), [(closed_state, closed)])
    assert len(bodies) == 1 and "closed feature issues" in bodies[0]
    assert "#42 is closed" in bodies[0]
    assert f"<!-- upstream-commit:{closed['sha']} -->" in bodies[0]
    assert report_parts(base, head, [], {}, {closed["sha"]}, set(),
                        [(closed_state, closed)]) == []
    feature = feature_from_commit(commit("c", "feat(ui): add a box (#7)"))
    states = {feature["key"]: {"key": feature["key"], "commits": [feature], "number": 7,
                               "pr": "7", "rejected": False,
                               "url": "https://github.com/Kenja-mc/Cataclysm-BN/issues/7"}}
    bodies = report_parts(base, head, [], states, set(), set())
    assert len(bodies) == 1 and "Feature issues" in bodies[0] and "issues/7" in bodies[0]
    assert "upstream PR 7" in bodies[0]
    assert report_parts(base, head, [], states, set(), {feature["key"]}) == []
    assert feature_body(feature["key"], [feature]).count("<!-- upstream-commit:") == 1
    assert "(PR 7)" in feature_body(feature["key"], [feature])
    fake = FakeGitHub()
    legacy = fake.tracker(BASE)
    old = f"- [ ] [x](https://github.com/{UPSTREAM}/commit/{'c' * 40})\n"
    fake.comments[legacy["number"]].append({"body": old, "user": {"login": "github-actions[bot]"}})
    commits, features = tracker_marks(REPO, legacy, api=fake)
    assert "c" * 40 in commits and features == set(), "old-format rows must stay deduplicated"


def sample_commits():
    return [
        commit("1", "feat(ui): add a readable box (#10730)"),
        commit("2", "feat(ui): tighten the readable box (#10730)"),
        commit("9", "feat(mods): make civilians hate feral players (#10721)"),
        commit("3", "fix: repair the box"),
        commit("4", "chore: update the box comment"),
        commit("b", "Update the box"),
    ]


def sample(fake):
    fake.compare = {"status": "ahead", "total_commits": 6, "commits": sample_commits()}
    return fake


def feature_issues(fake):
    return [issue for issue in fake.issues if "<!-- upstream-feature:" in issue["body"]]


def check_publish():
    fake = sample(FakeGitHub())
    fake.tracker(BASE)
    watch(fake)
    created = feature_issues(fake)
    assert len(created) == 2, "one issue per distinct feature"
    grouped = next(issue for issue in created if "readable box" in issue["title"])
    assert grouped["body"].count("<!-- upstream-commit:") == 2
    assert fake.find(1)["body"].count("checkpoint:" + HEAD) == 1
    assert len(fake.comments[1]) == 1
    assert fake.comments[1][0]["body"].count("<!-- upstream-commit:") == 3
    assert all(method == "GET" for method, endpoint in fake.calls if UPSTREAM in endpoint)

    before = (len(fake.issues), [len(value) for value in fake.comments.values()])
    # Simulate a crash before the checkpoint advanced: issues and rows are already recorded.
    fake.find(1)["body"] = fake.find(1)["body"].replace(
        f"<!-- upstream-checkpoint:{HEAD} -->", f"<!-- upstream-checkpoint:{BASE} -->")
    watch(fake)
    after = (len(fake.issues), [len(value) for value in fake.comments.values()])
    assert before == after, "reruns must not duplicate issues or comments"
    assert CHECKPOINT.findall(fake.find(1)["body"]) == [HEAD]
    watch(fake)
    assert after == (len(fake.issues), [len(value) for value in fake.comments.values()])

    fake = sample(FakeGitHub())
    fake.tracker(BASE)
    with contextlib.redirect_stdout(io.StringIO()) as quiet:
        watch(fake, apply=False)
    assert "DRY RUN would create issue" in quiet.getvalue()
    assert len(fake.issues) == 1 and all(method == "GET" for method, _ in fake.calls)

    check_merged_gate()
    check_cross_batch()
    check_backfill_cap()
    check_partial_failure()
    check_listing_guards()


def check_cross_batch():
    """A feature split across batches keeps one issue and gains a commit comment."""
    global BATCH_COMMITS
    original = BATCH_COMMITS
    BATCH_COMMITS = 1
    try:
        fake = sample(FakeGitHub())
        fake.tracker(BASE)
        watch(fake)
    finally:
        BATCH_COMMITS = original
    issues = feature_issues(fake)
    assert len(issues) == 2
    grouped = next(issue for issue in issues if "readable box" in issue["title"])
    assert grouped["body"].count("<!-- upstream-commit:") == 1
    assert len(fake.comments[grouped["number"]]) == 1
    assert "<!-- upstream-feature-commit:" in fake.comments[grouped["number"]][0]["body"]
    assert CHECKPOINT.findall(fake.find(1)["body"]) == [HEAD]


def check_backfill_cap():
    """A capped run stops at a batch boundary and the next run drains the rest."""
    global BATCH_COMMITS, MAX_NEW_ISSUES
    original = (BATCH_COMMITS, MAX_NEW_ISSUES)
    commits = sample_commits()
    fake = sample(FakeGitHub())
    fake.tracker(BASE)
    BATCH_COMMITS, MAX_NEW_ISSUES = 1, 1
    try:
        watch(fake)
    finally:
        BATCH_COMMITS, MAX_NEW_ISSUES = original
    assert CHECKPOINT.findall(fake.find(1)["body"]) == [commits[0]["sha"]]
    assert len(feature_issues(fake)) == 1

    fake.compares[f"{commits[0]['sha']}...{BASE}"] = {
        "status": "behind", "total_commits": 0, "commits": []}
    fake.compare = {"status": "ahead", "total_commits": 5, "commits": commits[1:]}
    watch(fake)
    assert CHECKPOINT.findall(fake.find(1)["body"]) == [HEAD]
    assert len(feature_issues(fake)) == 2


def check_merged_gate():
    commits = sample_commits()
    fake = FakeGitHub()
    fake.tracker(BASE)
    fake.compare = {"status": "ahead", "total_commits": 6, "commits": commits}
    fake.fork_compare = {"status": "diverged", "merge_base_commit": {"sha": commits[1]["sha"]}}
    fake.compares[f"{BASE}...{commits[1]['sha']}"] = {
        "status": "ahead", "total_commits": 2, "commits": commits[:2]}
    watch(fake)
    issues = feature_issues(fake)
    assert len(issues) == 1 and issues[0]["title"].endswith("feral players"), \
        "merged feature commits get no issue"
    report = fake.comments[1][0]["body"]
    assert f"<!-- upstream-commit:{commits[0]['sha']} -->" not in report
    assert f"<!-- upstream-commit:{commits[1]['sha']} -->" not in report, \
        "already-merged commits are not listed"
    assert f"[`{commits[0]['sha'][:10]}`]" not in report
    assert "already merged" not in report

    before = [len(value) for value in fake.comments.values()]
    fake.find(1)["body"] = fake.find(1)["body"].replace(
        f"<!-- upstream-checkpoint:{HEAD} -->", f"<!-- upstream-checkpoint:{BASE} -->")
    watch(fake)
    assert [len(value) for value in fake.comments.values()] == before, \
        "a rerun must not repeat rows or feature links"
    assert CHECKPOINT.findall(fake.find(1)["body"]) == [HEAD]

    global BATCH_COMMITS
    original = BATCH_COMMITS
    BATCH_COMMITS = 1
    try:
        fake = FakeGitHub()
        fake.tracker(BASE)
        fake.compare = {"status": "ahead", "total_commits": 6, "commits": commits}
        fake.fork_compare = {"status": "diverged", "merge_base_commit": {"sha": commits[1]["sha"]}}
        fake.compares[f"{BASE}...{commits[1]['sha']}"] = {
            "status": "ahead", "total_commits": 2, "commits": commits[:2]}
        watch(fake)
    finally:
        BATCH_COMMITS = original
    bodies = [comment["body"] for comment in fake.comments[1]]
    assert len(bodies) == 4, "merged-only batches post no comment"
    assert all(f"<!-- upstream-commit:{commits[0]['sha']} -->" not in body
               and f"<!-- upstream-commit:{commits[1]['sha']} -->" not in body for body in bodies)

    fake = FakeGitHub()
    fake.fork_compare = {"status": "diverged", "merge_base_commit": {"sha": HEAD}}
    fake.compares[f"{BASE}...{HEAD}"] = {"status": "diverged", "total_commits": 0, "commits": []}
    try:
        merged_in_range(REPO, BASE, api=fake)
    except ValueError:
        pass
    else:
        raise AssertionError("a checkpoint off the upstream history must stop the run")


def check_partial_failure():
    state = {"creations": 0}

    def fail_second_creation(method, endpoint):
        if method == "POST" and endpoint == f"repos/{REPO}/issues":
            state["creations"] += 1
            return state["creations"] == 2
        return False

    fake = sample(FakeGitHub())
    fake.tracker(BASE)
    fake.fail_when = fail_second_creation
    try:
        watch(fake)
    except RuntimeError:
        pass
    else:
        raise AssertionError("a partial feature-issue failure must abort the run")
    assert CHECKPOINT.findall(fake.find(1)["body"]) == [BASE]
    assert len(feature_issues(fake)) == 1

    fake.fail_when = None
    watch(fake)
    assert len(feature_issues(fake)) == 2 and len(fake.comments[1]) == 1
    assert CHECKPOINT.findall(fake.find(1)["body"]) == [HEAD]

    fake = sample(FakeGitHub())
    fake.tracker(BASE)
    fake.fail_when = lambda method, endpoint: method == "POST" and "/comments" in endpoint
    try:
        watch(fake)
    except RuntimeError:
        pass
    else:
        raise AssertionError("a tracker comment failure must abort the run")
    assert CHECKPOINT.findall(fake.find(1)["body"]) == [BASE]
    fake.fail_when = None
    watch(fake)
    assert len(fake.comments[1]) == 1, "rerun must not repeat recorded checklist rows"
    assert CHECKPOINT.findall(fake.find(1)["body"]) == [HEAD]

    fake = sample(FakeGitHub())
    fake.tracker(BASE)
    fake.fail_when = lambda method, endpoint: method == "PATCH"
    try:
        watch(fake)
    except RuntimeError:
        pass
    else:
        raise AssertionError("a checkpoint failure must abort the run")
    assert CHECKPOINT.findall(fake.find(1)["body"]) == [BASE]
    fake.fail_when = None
    watch(fake)
    assert len(feature_issues(fake)) == 2 and len(fake.comments[1]) == 1
    assert CHECKPOINT.findall(fake.find(1)["body"]) == [HEAD]


def check_listing_guards():
    fake = FakeGitHub()
    tracker = fake.tracker(BASE)
    recorded = commit("7", "feat(ui): a box (#999)")
    fresh = commit("b", "feat(ui): another box (#999)")
    closed = fake.issue(
        f"<!-- upstream-feature:pr-999 -->\n\n<!-- upstream-commit:{recorded['sha']} -->\n",
        state="closed")
    fake.compare = {"status": "ahead", "total_commits": 2, "commits": [recorded, fresh]}
    watch(fake)
    assert closed["state"] == "closed"
    assert len(fake.comments[closed["number"]]) == 0, "a closed feature issue stays closed"
    report = fake.comments[tracker["number"]][0]["body"]
    assert f"<!-- upstream-commit:{fresh['sha']} -->" in report, \
        "later commits for a closed feature remain in the tracker"
    assert f"#{closed['number']} is closed" in report
    assert f"<!-- upstream-commit:{recorded['sha']} -->" not in report
    assert "rejected (issue closed)" in report
    assert CHECKPOINT.findall(tracker["body"]) == [HEAD]

    fake.find(1)["body"] = fake.find(1)["body"].replace(
        f"<!-- upstream-checkpoint:{HEAD} -->", f"<!-- upstream-checkpoint:{BASE} -->")
    before = [len(value) for value in fake.comments.values()]
    watch(fake)
    assert [len(value) for value in fake.comments.values()] == before, \
        "a rejected commit is recorded once"

    try:
        find_feature_issues([feature_issues(fake)[0], dict(feature_issues(fake)[0], number=99)])
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate feature issues must be resolved by hand")
    assert find_feature_issues([fake.issue("prose <!-- upstream-feature:quoted --> more\n")]) == {}
    pasted = fake.issue("<!-- upstream-feature:pr-999 -->\n", login="Kenja-mc")
    assert find_feature_issues([pasted]) == {}, "prose pasted into a human issue is ignored"
    try:
        find_feature_issues([fake.issue("<!-- upstream-feature:a -->\n<!-- upstream-feature:b -->\n")])
    except ValueError:
        pass
    else:
        raise AssertionError("an issue with two feature markers must fail")
    assert find_tracker([fake.issue(f"Notes about {TRACKER} usage\n")]) is None

    fake.issue(TRACKER + "\n<!-- upstream-checkpoint:" + BASE + " -->\n")
    try:
        find_tracker(owned_issues(REPO, api=fake))
    except ValueError:
        pass
    else:
        raise AssertionError("two trackers must be resolved by hand")

    closed_tracker = FakeGitHub()
    record = closed_tracker.tracker(BASE)
    record["state"] = "closed"
    found = find_tracker(owned_issues(REPO, api=closed_tracker))
    assert found is record and tracker_stopped(found)
    assert checkpoint_of(found) == BASE
    calls = len(closed_tracker.calls)
    watch(closed_tracker)
    assert closed_tracker.calls[calls:] == [("GET", f"repos/{REPO}/issues?state=all&per_page=100")], \
        "a closed tracker stops before any upstream request"
    assert closed_tracker.comments[record["number"]] == []

    assert owned_issues(REPO, api=FakeGitHub()) == []
    foreign = FakeGitHub()
    foreign.issue("foreign", login="someone")
    foreign.issue("pr", login="github-actions[bot]")["pull_request"] = {}
    assert owned_issues(REPO, api=foreign) == []


def check_merge_grouping():
    merge = {"sha": "a" * 40, "commit": {"message": "Merge pull request #9377 from x/y"},
             "parents": [{"sha": "1" * 40}, {"sha": "2" * 40}], "author": {"login": "octocat"}}
    branch = [raw_commit("3" * 40, "feat: load sound volumes as decibel units"),
              raw_commit("4" * 40, "refactor: tidy the loader (#9377)")]
    fake = FakeGitHub()
    fake.compares[f"{'1' * 40}...{'2' * 40}"] = {
        "status": "diverged", "total_commits": 2, "commits": branch}
    mapping = merge_pr_map([merge], api=fake)
    assert mapping == {"3" * 40: "9377", "4" * 40: "9377"}
    features, uncertain, _ = classify(branch, pr_map=mapping)
    assert len(features) == 1 and features[0]["key"] == "pr-9377"
    assert features[0]["title"] == "load sound volumes as decibel units"
    assert classify([merge], pr_map=mapping)[0] == []

    named = {"sha": "5" * 40, "commit": {"message": "refactor: tidy tools (#9380)"},
             "parents": [{"sha": "1" * 40}, {"sha": "6" * 40}], "author": {"login": "octocat"}}
    fake.compares[f"{'1' * 40}...{'6' * 40}"] = {
        "status": "diverged", "total_commits": 1,
        "commits": [raw_commit("7" * 40, "feat: add a tool")]}
    assert merge_pr_map([named], api=fake) == {"7" * 40: "9380"}

    own = raw_commit("8" * 40, "feat: other thing (#1111)")
    features, _, _ = classify([own], pr_map={"8" * 40: "9377"})
    assert features[0]["key"] == "pr-1111", "a commit's own PR reference wins"


def check_tracker_intro():
    legacy_body = (f"{TRACKER}\n\n<!-- upstream-checkpoint:{BASE} -->\n\n"
                   + LEGACY_TRACKER_INTROS[0] + "\n")
    refreshed = refresh_tracker_body(legacy_body)
    assert TRACKER_INTRO_START in refreshed and TRACKER_INTRO_END in refreshed
    assert LEGACY_TRACKER_INTROS[0] not in refreshed
    assert CHECKPOINT.findall(refreshed) == [BASE]
    assert refresh_tracker_body(refreshed) == refreshed
    human = legacy_body.replace("Close this tracker to stop reporting.", "Keep this open for me.")
    assert refresh_tracker_body(human) == human, "human prose is preserved"
    managed = (f"{TRACKER}\n\n<!-- upstream-checkpoint:{BASE} -->\n\n"
               f"{tracker_intro_block()}\n\nHuman note\n")
    updated = refresh_tracker_body(managed)
    assert updated.endswith("Human note\n") and "Human note" in updated
    assert LEGACY_TRACKER_INTROS[0] not in updated

    fake = FakeGitHub()
    record = fake.issue(legacy_body, login="Kenja-mc")
    assert refresh_tracker(REPO, record, api=fake)
    assert TRACKER_INTRO_START in record["body"]
    assert CHECKPOINT.findall(record["body"]) == [BASE]
    calls = len(fake.calls)
    assert refresh_tracker(REPO, record, api=fake) is False
    assert not any(method != "GET" for method, _ in fake.calls[calls:])


def check_multibatch_rows():
    global BATCH_COMMITS
    original = BATCH_COMMITS
    BATCH_COMMITS = 1
    try:
        fake = sample(FakeGitHub())
        fake.tracker(BASE)
        watch(fake)
    finally:
        BATCH_COMMITS = original
    rows = [sha for comment in fake.comments[1]
            for sha in COMMIT_MARKER.findall(comment["body"])]
    uncertain = {entry["sha"] for entry in sample_commits() if feature_from_commit(entry) is None}
    assert sorted(rows) == sorted(uncertain), "each uncertain commit is reported once"
    before = [len(value) for value in fake.comments.values()]
    fake.find(1)["body"] = fake.find(1)["body"].replace(
        f"<!-- upstream-checkpoint:{HEAD} -->", f"<!-- upstream-checkpoint:{BASE} -->")
    watch(fake)
    assert [len(value) for value in fake.comments.values()] == before
    assert CHECKPOINT.findall(fake.find(1)["body"]) == [HEAD]


def self_check():
    with contextlib.redirect_stdout(io.StringIO()):
        check_classification()
        check_untrusted_text()
        check_comparison()
        check_reporting()
        check_merge_grouping()
        check_tracker_intro()
        check_publish()
        check_multibatch_rows()
    print("PASS feature classification, PR grouping (including merge commits), deduplication, "
          "safe text, merge gate, closed-feature fallback, stop switch, tracker intro migration, "
          "paginated comparison, partial-failure checkpoints and upstream read-only guard")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default="Kenja-mc/Cataclysm-BN")
    parser.add_argument("--initial-ref", default="a27f19d",
                        help="last upstream merge, used only until the tracker has a checkpoint")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if not REPO_PATTERN.fullmatch(args.repo):
        parser.error("--repo must be owner/repository")
    if args.repo.lower() == UPSTREAM.lower():
        parser.error("refusing to write watcher reports to the upstream repository")
    if not re.fullmatch(r"[0-9a-f]{7,40}", args.initial_ref):
        parser.error("--initial-ref must be an upstream commit SHA")
    issues = owned_issues(args.repo)
    tracker = find_tracker(issues)
    if tracker_stopped(tracker):
        print("Upstream tracker is closed; reporting stopped until it is reopened")
        return
    known = find_feature_issues(issues)
    refreshed = False
    if tracker is not None:
        base = checkpoint_of(tracker)
        refreshed = refresh_tracker(args.repo, tracker, apply=not args.dry_run)
    else:
        resolved = api(f"repos/{UPSTREAM}/commits/{args.initial_ref}")
        base = resolved.get("sha") if isinstance(resolved, dict) else None
        if not isinstance(base, str) or not SHA.fullmatch(base):
            raise ValueError("Could not resolve the starting checkpoint")
    resolved = api(f"repos/{UPSTREAM}/commits/main")
    head = resolved.get("sha") if isinstance(resolved, dict) else None
    if not isinstance(head, str) or not SHA.fullmatch(head):
        raise ValueError("Could not resolve the upstream head")
    if head == base:
        if not args.dry_run and refreshed:
            print(f"Upstream unchanged at {head}; tracker description refreshed")
        else:
            print(f"Upstream unchanged at {head}; no writes")
        return
    merged, merge_base = merged_in_range(args.repo, base)
    commits = collect_commits(base, head)
    pr_map = merge_pr_map(commits)
    print(f"{len(commits)} commit(s) after {base[:10]} (fork merge base {merge_base[:10]})")
    publish(args.repo, tracker, base, head, commits, known, merged, pr_map,
            apply=not args.dry_run)


if __name__ == "__main__":
    main()
