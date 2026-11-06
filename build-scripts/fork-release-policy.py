#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

REPOSITORY = "Kenja-mc/Cataclysm-BN"
WORKFLOW = ".github/workflows/fork-release.yml"
PACKAGES = (
    "BrightNightsOverhaul-windows-x64.zip",
    "BrightNightsOverhaul-linux-x64.tar.gz",
)
FILES = (*PACKAGES, *(name + ".sha256" for name in PACKAGES))
MANIFEST = "release-manifest.json"
TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")


class BuildPending(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ValueError(message)


def api(endpoint, payload=None):
    command = [
        "gh",
        "api",
        "-H",
        "X-GitHub-Api-Version: 2022-11-28",
        "-H",
        "Accept: application/vnd.github+json",
    ]
    if payload is not None:
        command += ["--method", "PATCH", "--input", "-"]
    result = subprocess.run(
        command + [f"repos/{REPOSITORY}/{endpoint}"],
        input=json.dumps(payload) if payload is not None else None,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def pages(endpoint, key=None):
    separator = "&" if "?" in endpoint else "?"
    page = 1
    while True:
        response = api(f"{endpoint}{separator}per_page=100&page={page}")
        items = response[key] if key else response
        yield from items
        if len(items) < 100:
            return
        page += 1


def resolve_tag(tag):
    require(TAG.fullmatch(tag), "Unrecognized candidate tag")
    ref = api(f"git/ref/tags/{quote(tag, safe='')}")
    require(ref["ref"] == f"refs/tags/{tag}", "Tag lookup did not return exact ref")
    obj = ref["object"]
    visited = set()
    while obj["type"] == "tag":
        require(obj["sha"] not in visited, "Cyclic annotated tag")
        visited.add(obj["sha"])
        obj = api(f"git/tags/{obj['sha']}")["object"]
    require(
        obj["type"] == "commit" and SHA.fullmatch(obj["sha"]),
        "Tag does not resolve to a commit",
    )
    return obj["sha"]


def ancestor(older, newer):
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer], check=False
    )
    require(result.returncode in (0, 1), "Unable to establish commit ancestry")
    return result.returncode == 0


def refresh_main():
    subprocess.run(
        [
            "git",
            "fetch",
            "--no-tags",
            "origin",
            "+refs/heads/main:refs/remotes/origin/main",
        ],
        check=True,
    )


def version_tuple(tag):
    match = TAG.fullmatch(tag)
    require(match is not None, "Unrecognized release version")
    return tuple(map(int, match.groups()))


def next_version():
    refresh_main()
    subprocess.run(["git", "fetch", "--tags", "origin"], check=True)
    tags = subprocess.check_output(
        ["git", "tag", "--list", "v*"], text=True
    ).splitlines()
    versions = []
    for tag in tags:
        if not TAG.fullmatch(tag):
            continue
        sha = subprocess.check_output(
            ["git", "rev-parse", f"refs/tags/{tag}^{{commit}}"], text=True
        ).strip()
        fork_commit = (
            subprocess.run(
                ["git", "cat-file", "-e", f"{sha}:CHANGELOG-OVERHAUL.md"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode
            == 0
        )
        if fork_commit and ancestor(sha, "origin/main"):
            versions.append(version_tuple(tag))
    if not versions:
        return "v0.1.0"
    major, minor, patch = max(versions)
    return f"v{major}.{minor}.{patch + 1}"


def successful_steps(job, names):
    require(
        job["status"] == "completed" and job["conclusion"] == "success",
        f"Required job failed: {job['name']}",
    )
    for name in names:
        matching = [step for step in job["steps"] if step["name"] == name]
        require(
            len(matching) == 1
            and matching[0]["status"] == "completed"
            and matching[0]["conclusion"] == "success",
            f"Required step did not succeed: {name}",
        )


def trusted_build(manifest):
    run_id, attempt = manifest["run_id"], manifest["run_attempt"]
    require(
        type(run_id) is int and type(attempt) is int and run_id > 0 and attempt > 0,
        "Invalid build run identity",
    )
    run = api(f"actions/runs/{run_id}")
    require(
        run["path"] == WORKFLOW
        and run["repository"]["full_name"] == REPOSITORY
        and run["head_repository"]["full_name"] == REPOSITORY,
        "Untrusted build workflow",
    )
    require(
        run["event"] in ("push", "workflow_dispatch")
        and run["head_branch"] in ("main", manifest["tag"]),
        "Untrusted build event/ref",
    )
    if run["status"] != "completed":
        raise BuildPending("Candidate build has not completed")
    require(
        run["status"] == "completed"
        and run["conclusion"] == "success"
        and run["run_attempt"] == attempt
        and run["head_sha"] == manifest["sha"],
        "Build evidence is not a completed successful same-SHA attempt",
    )
    jobs = list(pages(f"actions/runs/{run_id}/attempts/{attempt}/jobs", "jobs"))
    required = {
        "Windows MSVC": [
            "Build test executable (desktop)",
            "Run sharded tests (desktop)",
            "Upload packaged build artifact",
        ],
        "Linux Tiles": [
            "Build test executable (desktop)",
            "Run sharded tests (desktop)",
            "Validate all mod data (Linux)",
            "Upload packaged build artifact",
        ],
        "Windows updater": [
            "Update test (Windows PowerShell 5.1)",
            "Update test (PowerShell 7)",
        ],
        "publish": ["Package", "Publish"],
    }
    for suffix, steps in required.items():
        matching = [job for job in jobs if job["name"].split(" / ")[-1] == suffix]
        require(len(matching) == 1, f"Missing or ambiguous required job: {suffix}")
        require(
            matching[0]["head_sha"] == manifest["sha"]
            and matching[0]["run_attempt"] == attempt,
            "Job evidence SHA/attempt differs",
        )
        successful_steps(matching[0], steps)
    return next(job for job in jobs if job["name"].split(" / ")[-1] == "publish")


def download(asset, directory):
    require(
        asset["state"] == "uploaded" and asset["size"] > 0, "Incomplete release asset"
    )
    require(
        asset["uploader"]["login"] == "github-actions[bot]",
        "Release asset was not uploaded by Actions",
    )
    digest = asset.get("digest", "")
    require(
        isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", digest),
        "Missing SHA-256 asset digest",
    )
    path = directory / asset["name"]
    with path.open("wb") as stream:
        subprocess.run(
            [
                "gh",
                "api",
                "-H",
                "Accept: application/octet-stream",
                f"repos/{REPOSITORY}/releases/assets/{asset['id']}",
            ],
            stdout=stream,
            check=True,
        )
    require(path.stat().st_size == asset["size"], "Downloaded asset size differs")
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    require(digest == "sha256:" + hasher.hexdigest(), "Downloaded asset digest differs")
    return path, hasher.hexdigest()


def inspect_candidate(release):
    require(
        release["draft"] is False and release["prerelease"] is True,
        "Release is not a published prerelease",
    )
    sha = resolve_tag(release["tag_name"])
    require(ancestor(sha, "origin/main"), "Candidate is not on main ancestry")
    assets = list(pages(f"releases/{release['id']}/assets"))
    require(
        len(assets) == len(FILES) + 1
        and {asset["name"] for asset in assets} == {*FILES, MANIFEST},
        "Incomplete or unexpected release assets",
    )
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        hashes = {}
        for asset in assets:
            _, hashes[asset["name"]] = download(asset, directory)
        manifest = json.loads((directory / MANIFEST).read_text())
        require(
            manifest["schema"] == 1
            and manifest["repository"] == REPOSITORY
            and manifest["sha"] == sha
            and manifest["tag"] == release["tag_name"],
            "Manifest identity differs from tag",
        )
        require(
            manifest["files"] == {name: hashes[name] for name in FILES},
            "Manifest does not cover exact release files",
        )
        for name in PACKAGES:
            require(
                (directory / (name + ".sha256")).read_text()
                == f"{hashes[name]}  {name}\n",
                "Package SHA-256 sidecar differs",
            )
    publish = trusted_build(manifest)
    require(
        all(
            publish["started_at"] <= asset["created_at"] <= publish["completed_at"]
            for asset in assets
        ),
        "Assets were not created by the qualifying publish job",
    )
    fields = ("id", "name", "size", "digest", "created_at", "updated_at")
    return {
        "release_id": release["id"],
        "tag": release["tag_name"],
        "sha": sha,
        "run_id": manifest["run_id"],
        "run_attempt": manifest["run_attempt"],
        "published_at": release["published_at"],
        "assets": sorted(
            ({key: asset[key] for key in fields} for asset in assets),
            key=lambda asset: asset["name"],
        ),
    }


def forward_only(candidate, releases):
    for release in releases:
        if release["draft"] or release["prerelease"]:
            continue
        stable_sha = resolve_tag(release["tag_name"])
        require(
            stable_sha != candidate["sha"] and ancestor(stable_sha, candidate["sha"]),
            "Candidate would replace equal, newer, or divergent stable history",
        )
        require(
            version_tuple(candidate["tag"]) > version_tuple(release["tag_name"]),
            "Candidate version would downgrade installed updaters",
        )


def select_candidate():
    refresh_main()
    releases = list(pages("releases"))
    candidates = sorted(
        (
            release
            for release in releases
            if not release["draft"]
            and release["prerelease"]
            and TAG.fullmatch(release["tag_name"])
        ),
        key=lambda release: (release["published_at"], release["id"]),
        reverse=True,
    )
    for release in candidates:
        sha = resolve_tag(release["tag_name"])
        if not ancestor(sha, "origin/main"):
            continue
        if any(
            not stable["draft"]
            and not stable["prerelease"]
            and (
                resolve_tag(stable["tag_name"]) == sha
                or ancestor(sha, resolve_tag(stable["tag_name"]))
            )
            for stable in releases
        ):
            continue
        try:
            candidate = inspect_candidate(release)
        except BuildPending:
            continue
        forward_only(candidate, releases)
        return candidate
    return None


def verify_e2e(candidate):
    run_id = int(os.environ["GITHUB_RUN_ID"])
    attempt = int(os.environ["GITHUB_RUN_ATTEMPT"])
    run = api(f"actions/runs/{run_id}")
    require(
        run["path"] == ".github/workflows/fork-promote.yml"
        and run["head_branch"] == "main"
        and run["event"] in ("schedule", "workflow_dispatch")
        and run["repository"]["full_name"] == REPOSITORY
        and run["head_repository"]["full_name"] == REPOSITORY
        and run["run_attempt"] == attempt,
        "Untrusted promotion workflow",
    )
    require(
        run["status"] == "in_progress" and run["conclusion"] is None,
        "Promotion run is no longer active",
    )
    jobs = list(pages(f"actions/runs/{run_id}/attempts/{attempt}/jobs", "jobs"))
    expected_names = {
        f"Fork end-to-end suite (curses shard {index}/8)" for index in range(8)
    }
    matching = [job for job in jobs if job["name"].split(" / ")[-1] in expected_names]
    require(
        len(matching) == 8
        and {job["name"].split(" / ")[-1] for job in matching} == expected_names,
        "Missing or duplicate deterministic E2E shard",
    )
    for job in matching:
        require(
            job["head_sha"] == run["head_sha"] and job["run_attempt"] == attempt,
            "E2E shard belongs to another caller SHA/attempt",
        )
        successful_steps(
            job,
            [
                "Verify the pinned E2E commit",
                "Check game fixture lifetimes",
                "Run the fork end-to-end suite",
            ],
        )
    require(
        os.environ["CANDIDATE_SHA"] == candidate["sha"],
        "E2E caller SHA differs from selected candidate",
    )


def promote(candidate):
    refresh_main()
    verify_e2e(candidate)
    current = inspect_candidate(api(f"releases/{candidate['release_id']}"))
    require(
        current == candidate,
        "Candidate tag, assets, or build evidence changed while testing",
    )
    forward_only(candidate, list(pages("releases")))
    require(
        resolve_tag(candidate["tag"]) == candidate["sha"],
        "Candidate tag moved before promotion",
    )
    api(
        f"releases/{candidate['release_id']}",
        {"prerelease": False, "make_latest": "true"},
    )


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("next-version")
    manifest_parser = commands.add_parser("manifest")
    manifest_parser.add_argument("--tag", required=True)
    manifest_parser.add_argument("--sha", required=True)
    manifest_parser.add_argument("--directory", type=Path, required=True)
    select_parser = commands.add_parser("select")
    select_parser.add_argument("--output", type=Path, required=True)
    promote_parser = commands.add_parser("promote")
    promote_parser.add_argument("--selection", type=Path, required=True)
    args = parser.parse_args()
    require(
        os.environ.get("GITHUB_REPOSITORY") == REPOSITORY,
        "Policy only operates on the fork repository",
    )
    if args.command == "next-version":
        print(next_version())
    elif args.command == "manifest":
        require(
            TAG.fullmatch(args.tag) and SHA.fullmatch(args.sha),
            "Invalid candidate identity",
        )
        manifest = {
            "schema": 1,
            "repository": REPOSITORY,
            "tag": args.tag,
            "sha": args.sha,
            "run_id": int(os.environ["GITHUB_RUN_ID"]),
            "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
            "files": {
                name: hashlib.file_digest(
                    (args.directory / name).open("rb"), "sha256"
                ).hexdigest()
                for name in FILES
            },
        }
        (args.directory / MANIFEST).write_text(
            json.dumps(manifest, sort_keys=True) + "\n"
        )
    elif args.command == "select":
        candidate = select_candidate()
        if candidate is not None:
            args.output.write_text(json.dumps(candidate, sort_keys=True) + "\n")
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
            output.write(f"selected={'true' if candidate else 'false'}\n")
            if candidate:
                output.write(f"sha={candidate['sha']}\ntag={candidate['tag']}\n")
    else:
        promote(json.loads(args.selection.read_text()))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"::error::{error}", file=sys.stderr)
        sys.exit(1)
