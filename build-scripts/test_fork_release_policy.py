#!/usr/bin/env python3
import base64
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

POLICY = Path(__file__).with_name("fork-release-policy.py")
REPOSITORY = "Kenja-mc/Cataclysm-BN"
PACKAGES = (
    "BrightNightsOverhaul-windows-x64.zip",
    "BrightNightsOverhaul-linux-x64.tar.gz",
)
START = "2026-11-05T01:00:00Z"
UPLOADED = "2026-11-05T01:01:00Z"
END = "2026-11-05T01:02:00Z"
FAKE_GH = """#!/usr/bin/env python3
import base64
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit, parse_qs
state_path = Path(os.environ["RELEASE_FIXTURE"])
state = json.loads(state_path.read_text())
endpoint = next(arg for arg in sys.argv if arg.startswith("repos/"))
path = endpoint.removeprefix("repos/Kenja-mc/Cataclysm-BN/")
parsed = urlsplit(path)
path = parsed.path
query = parse_qs(parsed.query)
if "--method" in sys.argv:
    assert sys.argv[sys.argv.index("--method") + 1] == "PATCH"
    assert path.startswith("releases/") and path.split("/")[-1].isdigit()
    payload = json.load(sys.stdin)
    state["writes"].append({"path": path, "payload": payload})
    release = next(item for item in state["releases"] if str(item["id"]) == path.split("/")[-1])
    release.update(payload)
    state_path.write_text(json.dumps(state))
    print(json.dumps(release))
elif path.startswith("releases/assets/"):
    sys.stdout.buffer.write(base64.b64decode(state["bytes"][path.split("/")[-1]]))
elif path == "releases":
    page = int(query.get("page", [1])[0])
    print(json.dumps(state["releases"][(page - 1) * 100:page * 100]))
elif path.startswith("releases/") and path.endswith("/assets"):
    print(json.dumps(state["assets"][path.split("/")[1]]))
elif path.startswith("releases/"):
    print(json.dumps(next(item for item in state["releases"] if str(item["id"]) == path.split("/")[-1])))
elif path.startswith("git/ref/tags/"):
    tag = path.removeprefix("git/ref/tags/")
    print(json.dumps(state["refs"][tag]))
elif path.startswith("git/tags/"):
    print(json.dumps(state["tag_objects"][path.split("/")[-1]]))
elif path.startswith("actions/runs/") and path.endswith("/jobs"):
    run_id = path.split("/")[2]
    page = int(query.get("page", [1])[0])
    print(json.dumps({"jobs": state["jobs"][run_id][(page - 1) * 100:page * 100]}))
elif path.startswith("actions/runs/"):
    print(json.dumps(state["runs"][path.split("/")[-1]]))
else:
    raise RuntimeError(path)
"""


def step(name, conclusion="success"):
    return {"name": name, "status": "completed", "conclusion": conclusion}


def job(name, sha, names):
    return {
        "name": name,
        "head_sha": sha,
        "run_attempt": 1,
        "status": "completed",
        "conclusion": "success",
        "steps": [step(name) for name in names],
        "started_at": START,
        "completed_at": END,
    }


class ReleasePolicyCLI(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "checkout"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Release policy fixture")
        self.git("config", "user.email", "release-policy@example.invalid")
        (self.repo / "upstream.txt").write_text("upstream\n")
        self.git("add", ".")
        self.git("commit", "-m", "upstream fixture")
        self.git("tag", "v99.0.0")
        (self.repo / "CHANGELOG-OVERHAUL.md").write_text("fork\n")
        self.git("add", ".")
        self.git("commit", "-m", "stable fixture")
        self.stable_sha = self.git("rev-parse", "HEAD")
        self.git("tag", "v0.1.0")
        (self.repo / "candidate.txt").write_text("candidate\n")
        self.git("add", ".")
        self.git("commit", "-m", "candidate fixture")
        self.sha = self.git("rev-parse", "HEAD")
        self.git("tag", "v0.1.1")
        (self.repo / "newer.txt").write_text("newer main\n")
        self.git("add", ".")
        self.git("commit", "-m", "newer fixture")
        self.newer_sha = self.git("rev-parse", "HEAD")
        self.remote = self.root / "origin.git"
        subprocess.run(
            ["git", "clone", "--bare", str(self.repo), str(self.remote)],
            capture_output=True,
            check=True,
        )
        self.git("remote", "add", "origin", str(self.remote))
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "gh").write_text(FAKE_GH)
        (self.bin / "gh").chmod(0o755)
        self.fixture = self.root / "api.json"
        self.selection = self.root / "selection.json"
        self.output = self.root / "outputs"
        self.env = dict(
            os.environ,
            PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
            RELEASE_FIXTURE=str(self.fixture),
            GITHUB_REPOSITORY=REPOSITORY,
            GITHUB_RUN_ID="20",
            GITHUB_RUN_ATTEMPT="1",
            GITHUB_OUTPUT=str(self.output),
            CANDIDATE_SHA=self.sha,
        )
        self.state = {
            "writes": [],
            "releases": [
                {
                    "id": 1,
                    "tag_name": "v0.1.0",
                    "draft": False,
                    "prerelease": False,
                    "published_at": START,
                },
                {
                    "id": 2,
                    "tag_name": "v0.1.1",
                    "draft": False,
                    "prerelease": True,
                    "published_at": END,
                },
            ],
            "assets": {"2": []},
            "bytes": {},
            "refs": {},
            "tag_objects": {},
            "runs": {},
            "jobs": {},
        }
        self.ref("v0.1.0", self.stable_sha)
        self.ref("v0.1.1", self.sha)
        for run_id, path, sha, event in [
            (10, ".github/workflows/fork-release.yml", self.sha, "push"),
            (20, ".github/workflows/fork-promote.yml", self.newer_sha, "schedule"),
        ]:
            self.state["runs"][str(run_id)] = {
                "id": run_id,
                "path": path,
                "head_sha": sha,
                "head_branch": "main",
                "event": event,
                "status": "completed" if run_id == 10 else "in_progress",
                "conclusion": "success" if run_id == 10 else None,
                "run_attempt": 1,
                "repository": {"full_name": REPOSITORY},
                "head_repository": {"full_name": REPOSITORY},
            }
        self.state["jobs"]["10"] = [
            job(
                "build / Windows MSVC",
                self.sha,
                [
                    "Build test executable (desktop)",
                    "Run sharded tests (desktop)",
                    "Upload packaged build artifact",
                ],
            ),
            job(
                "build / Linux Tiles",
                self.sha,
                [
                    "Build test executable (desktop)",
                    "Run sharded tests (desktop)",
                    "Validate all mod data (Linux)",
                    "Upload packaged build artifact",
                ],
            ),
            job(
                "updater-test / Windows updater",
                self.sha,
                ["Update test (Windows PowerShell 5.1)", "Update test (PowerShell 7)"],
            ),
            job("publish", self.sha, ["Package", "Publish"]),
        ]
        self.state["jobs"]["20"] = [
            job(
                f"e2e / Fork end-to-end suite (curses shard {index}/8)",
                self.newer_sha,
                [
                    "Verify the pinned E2E commit",
                    "Check game fixture lifetimes",
                    "Run the fork end-to-end suite",
                ],
            )
            for index in range(8)
        ]
        package_directory = self.root / "packages"
        package_directory.mkdir()
        for name in PACKAGES:
            contents = (name + " immutable package bytes\n").encode()
            (package_directory / name).write_bytes(contents)
            (package_directory / (name + ".sha256")).write_text(
                f"{hashlib.sha256(contents).hexdigest()}  {name}\n"
            )
        self.save()
        manifest_env = dict(self.env, GITHUB_RUN_ID="10")
        subprocess.run(
            [
                sys.executable,
                str(POLICY),
                "manifest",
                "--tag",
                "v0.1.1",
                "--sha",
                self.sha,
                "--directory",
                str(package_directory),
            ],
            cwd=self.repo,
            env=manifest_env,
            capture_output=True,
            check=True,
        )
        for index, path in enumerate(sorted(package_directory.iterdir()), 100):
            self.asset(index, path.name, path.read_bytes())
        self.save()

    def git(self, *args):
        return subprocess.check_output(
            ["git", *args], cwd=self.repo, stderr=subprocess.DEVNULL, text=True
        ).strip()

    def ref(self, tag, sha):
        self.state["refs"][tag] = {
            "ref": "refs/tags/" + tag,
            "object": {"type": "commit", "sha": sha},
        }

    def asset(self, identity, name, contents):
        self.state["bytes"][str(identity)] = base64.b64encode(contents).decode()
        self.state["assets"]["2"].append(
            {
                "id": identity,
                "name": name,
                "size": len(contents),
                "digest": "sha256:" + hashlib.sha256(contents).hexdigest(),
                "state": "uploaded",
                "created_at": UPLOADED,
                "updated_at": UPLOADED,
                "uploader": {"login": "github-actions[bot]"},
            }
        )

    def save(self):
        self.fixture.write_text(json.dumps(self.state))

    def invoke(self, command, success=True):
        self.save()
        args = (
            ["--output", str(self.selection)]
            if command == "select"
            else ["--selection", str(self.selection)]
            if command == "promote"
            else []
        )
        result = subprocess.run(
            [sys.executable, str(POLICY), command, *args],
            cwd=self.repo,
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(json.loads(self.fixture.read_text())["writes"], [])
        return result

    def select(self):
        self.invoke("select")
        return json.loads(self.selection.read_text())

    def replace_asset_bytes(self, name, contents):
        asset = next(
            asset for asset in self.state["assets"]["2"] if asset["name"] == name
        )
        self.state["bytes"][str(asset["id"])] = base64.b64encode(contents).decode()
        asset["size"] = len(contents)
        asset["digest"] = "sha256:" + hashlib.sha256(contents).hexdigest()

    def add_newer_candidate(self, pending=False):
        release_id, run_id = 3, 11
        self.ref("v0.1.2", self.newer_sha)
        self.state["releases"].append(
            {
                "id": release_id,
                "tag_name": "v0.1.2",
                "draft": False,
                "prerelease": True,
                "published_at": "2026-11-05T02:00:00Z",
            }
        )
        self.state["runs"][str(run_id)] = dict(
            self.state["runs"]["10"], id=run_id, head_sha=self.newer_sha
        )
        if pending:
            self.state["runs"][str(run_id)].update(
                status="in_progress", conclusion=None
            )
        self.state["jobs"][str(run_id)] = copy.deepcopy(self.state["jobs"]["10"])
        for entry in self.state["jobs"][str(run_id)]:
            entry["head_sha"] = self.newer_sha
        self.state["assets"][str(release_id)] = copy.deepcopy(self.state["assets"]["2"])
        for asset in self.state["assets"][str(release_id)]:
            old_id = asset["id"]
            asset["id"] += 1000
            contents = base64.b64decode(self.state["bytes"][str(old_id)])
            if asset["name"] == "release-manifest.json":
                manifest = json.loads(contents)
                manifest.update(tag="v0.1.2", sha=self.newer_sha, run_id=run_id)
                contents = (json.dumps(manifest) + "\n").encode()
            self.state["bytes"][str(asset["id"])] = base64.b64encode(contents).decode()
            asset["size"] = len(contents)
            asset["digest"] = "sha256:" + hashlib.sha256(contents).hexdigest()

    def test_selects_newest_completed_candidate_not_newest_pending(self):
        self.add_newer_candidate(pending=True)
        self.assertEqual(self.select()["tag"], "v0.1.1")
        self.state["runs"]["11"].update(status="completed", conclusion="success")
        self.assertEqual(self.select()["tag"], "v0.1.2")

    def test_invalid_sidecar_is_rejected_even_with_matching_api_and_manifest_hashes(
        self,
    ):
        name = PACKAGES[0] + ".sha256"
        contents = ("0" * 64 + "  " + PACKAGES[0] + "\n").encode()
        self.replace_asset_bytes(name, contents)
        asset = next(
            asset
            for asset in self.state["assets"]["2"]
            if asset["name"] == "release-manifest.json"
        )
        manifest = json.loads(base64.b64decode(self.state["bytes"][str(asset["id"])]))
        manifest["files"][name] = hashlib.sha256(contents).hexdigest()
        self.replace_asset_bytes(
            "release-manifest.json", (json.dumps(manifest) + "\n").encode()
        )
        self.invoke("select", success=False)

    def test_cancelled_promotion_run_or_different_e2e_input_retains_stable(self):
        self.select()
        self.state["runs"]["20"].update(status="completed", conclusion="cancelled")
        self.invoke("promote", success=False)
        self.state["runs"]["20"].update(status="in_progress", conclusion=None)
        self.env["CANDIDATE_SHA"] = self.newer_sha
        self.invoke("promote", success=False)

    def test_every_deterministic_e2e_shard_is_required(self):
        self.select()
        original = copy.deepcopy(self.state)
        for index in range(8):
            with self.subTest(missing_shard=index):
                self.state = copy.deepcopy(original)
                self.state["jobs"]["20"].pop(index)
                self.invoke("promote", success=False)

    def test_failure_in_any_deterministic_e2e_shard_retains_stable(self):
        self.select()
        original = copy.deepcopy(self.state)
        for index in range(8):
            with self.subTest(failed_shard=index):
                self.state = copy.deepcopy(original)
                self.state["jobs"]["20"][index]["conclusion"] = "failure"
                self.invoke("promote", success=False)

    def test_duplicate_shard_cannot_replace_missing_shard(self):
        self.select()
        self.state["jobs"]["20"][-1]["name"] = self.state["jobs"]["20"][0]["name"]
        self.invoke("promote", success=False)

    def test_promotes_same_existing_assets(self):
        candidate = self.select()
        self.assertEqual(candidate["sha"], self.sha)
        before_assets = copy.deepcopy(self.state["assets"])
        self.invoke("promote")
        after = json.loads(self.fixture.read_text())
        self.assertFalse(after["releases"][1]["prerelease"])
        self.assertEqual(after["assets"], before_assets)
        self.assertEqual(after["bytes"], self.state["bytes"])
        self.assertEqual(
            after["writes"],
            [
                {
                    "path": "releases/2",
                    "payload": {"prerelease": False, "make_latest": "true"},
                }
            ],
        )

    def test_next_version_ignores_upstream_and_reserves_existing_candidates(self):
        self.assertEqual(self.invoke("next-version").stdout.strip(), "v0.1.2")
        self.git("tag", "v0.1.2")
        self.git("push", "origin", "refs/tags/v0.1.2")
        self.assertEqual(self.invoke("next-version").stdout.strip(), "v0.1.3")

    def test_exact_annotated_tag_resolves_and_promotes(self):
        self.state["refs"]["v0.1.1"]["object"] = {"type": "tag", "sha": "a" * 40}
        self.state["tag_objects"]["a" * 40] = {
            "object": {"type": "commit", "sha": self.sha}
        }
        self.select()
        self.invoke("promote")

    def test_missing_or_extra_asset_refuses_selection(self):
        original = copy.deepcopy(self.state)
        for change in ("missing", "extra"):
            with self.subTest(change=change):
                self.state = copy.deepcopy(original)
                if change == "missing":
                    self.state["assets"]["2"].pop()
                else:
                    self.asset(999, "unexpected.zip", b"extra")
                self.invoke("select", success=False)

    def test_actual_asset_bytes_and_sidecars_are_verified(self):
        self.state["bytes"]["100"] = base64.b64encode(b"corrupt").decode()
        self.invoke("select", success=False)

    def test_changed_tag_after_e2e_refuses_promotion(self):
        self.select()
        self.ref("v0.1.1", self.newer_sha)
        self.invoke("promote", success=False)

    def test_prefix_tag_response_is_not_exact_tag(self):
        self.state["refs"]["v0.1.1"]["ref"] = "refs/tags/v0.1.10"
        self.invoke("select", success=False)

    def test_changed_asset_metadata_after_e2e_refuses_promotion(self):
        self.select()
        self.state["assets"]["2"][0]["id"] = 999
        self.state["bytes"]["999"] = self.state["bytes"]["100"]
        self.invoke("promote", success=False)

    def test_failure_skip_cancel_timeout_of_each_required_gate_is_closed(self):
        self.select()
        original = copy.deepcopy(self.state)
        for jobs_key, job_index, step_index in [
            ("10", 0, 1),
            ("10", 1, 1),
            ("10", 1, 2),
            ("10", 2, 0),
            ("20", 0, 2),
        ]:
            for conclusion in ("failure", "skipped", "cancelled", "timed_out"):
                with self.subTest(
                    run=jobs_key, job=job_index, step=step_index, conclusion=conclusion
                ):
                    self.state = copy.deepcopy(original)
                    self.state["jobs"][jobs_key][job_index]["steps"][step_index][
                        "conclusion"
                    ] = conclusion
                    self.invoke("promote", success=False)

    def test_green_agentic_workflow_is_not_e2e_proof(self):
        self.select()
        self.state["runs"]["20"]["path"] = ".github/workflows/fork-playtest.yml"
        self.invoke("promote", success=False)

    def test_untrusted_or_different_sha_build_is_not_evidence(self):
        original = copy.deepcopy(self.state)
        for field, value in [
            ("head_sha", self.newer_sha),
            ("path", ".github/workflows/matrix.yml"),
            ("event", "pull_request"),
            ("run_attempt", 2),
            ("head_repository", {"full_name": "attacker/Cataclysm-BN"}),
        ]:
            with self.subTest(field=field):
                self.state = copy.deepcopy(original)
                self.state["runs"]["10"][field] = value
                self.invoke("select", success=False)

    def test_pending_candidate_is_not_selected(self):
        self.state["runs"]["10"]["status"] = "in_progress"
        self.state["runs"]["10"]["conclusion"] = None
        self.invoke("select")
        self.assertFalse(self.selection.exists())
        self.assertIn("selected=false", self.output.read_text())

    def test_newer_stable_while_e2e_runs_refuses_stale_promotion(self):
        self.select()
        self.ref("v0.1.2", self.newer_sha)
        self.state["releases"].append(
            {
                "id": 3,
                "tag_name": "v0.1.2",
                "draft": False,
                "prerelease": False,
                "published_at": END,
            }
        )
        self.invoke("promote", success=False)

    def test_newer_stable_version_even_on_older_commit_blocks_downgrade(self):
        self.select()
        self.ref("v0.2.0", self.stable_sha)
        self.state["releases"][0]["tag_name"] = "v0.2.0"
        self.invoke("promote", success=False)

    def test_selected_commit_removed_from_main_refuses_promotion(self):
        self.select()
        self.git(
            "--git-dir=" + str(self.remote),
            "update-ref",
            "refs/heads/main",
            self.stable_sha,
        )
        self.invoke("promote", success=False)

    def test_no_candidate_retains_stable_without_error(self):
        self.state["releases"] = self.state["releases"][:1]
        self.invoke("select")
        self.assertFalse(self.selection.exists())
        self.assertEqual(json.loads(self.fixture.read_text())["writes"], [])


if __name__ == "__main__":
    unittest.main()
