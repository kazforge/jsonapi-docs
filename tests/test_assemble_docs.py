import hashlib
import io
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts import assemble_docs as assembler


REPO = "example/product"
TAG_SHA = "a" * 40
ORIGINAL_SHA = "b" * 40
MAIN_SHA = "f" * 40


def asset(number=0, source=ORIGINAL_SHA, software=TAG_SHA):
    return {
        "id": number + 1,
        "name": f"docs-site-r{number}.tar.gz" if number else "docs-site.tar.gz",
        "label": f"docs-source-sha={source};software-tag-sha={software}",
    }


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.tag = patch.object(assembler, "tag_sha", return_value=TAG_SHA).start()
        self.gh = patch.object(assembler, "gh", return_value='{"status": "ahead"}').start()
        self.addCleanup(patch.stopall)

    def select(self, assets, tag="v1.0.0"):
        return assembler.select_asset(REPO, tag, assets, MAIN_SHA)

    def test_original_only_and_post_release_source(self):
        original = asset()
        self.assertEqual(self.select([original]), original)
        self.gh.assert_any_call("api", f"repos/{REPO}/compare/{TAG_SHA}...{ORIGINAL_SHA}?per_page=1")
        self.gh.assert_any_call("api", f"repos/{REPO}/compare/{ORIGINAL_SHA}...{MAIN_SHA}?per_page=1")

    def test_numeric_revision_order_is_independent_of_listing_order(self):
        original, r2, r10 = asset(), asset(2, "c" * 40), asset(10, "d" * 40)
        for assets in ([r10, original, r2], [original, r2, r10], [r2, r10, original]):
            with self.subTest(assets=assets):
                self.assertEqual(self.select(assets), r10)
        self.gh.assert_any_call("api", f"repos/{REPO}/compare/{ORIGINAL_SHA}...{'d' * 40}?per_page=1")

    def test_unrelated_assets_are_ignored(self):
        self.assertIsNone(self.select([{"name": "library.jar"}]))

    def test_duplicate_original_and_revision_fail(self):
        for assets in ([asset(), asset()], [asset(), asset(1, "c" * 40), asset(1, "d" * 40)]):
            with self.subTest(assets=assets), self.assertRaisesRegex(ValueError, "Duplicate docs revision"):
                self.select(assets)

    def test_revision_requires_original(self):
        with self.assertRaisesRegex(ValueError, "Missing original"):
            self.select([asset(1)])

    def test_malformed_revision_names_fail(self):
        for name in ("docs-site-r0.tar.gz", "docs-site-r01.tar.gz", "docs-site-r-1.tar.gz",
                     "docs-site-r1.5.tar.gz", "docs-site-rx.tar.gz", "docs-site-r1.zip",
                     "docs-site-r1.tar.gz.bak", "docs-site-r١.tar.gz"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Malformed docs revision"):
                self.select([asset(), dict(asset(1), name=name)])

    def test_missing_malformed_and_conflicting_labels_fail(self):
        for label in (None, "", "docs-source-sha=bad", asset()["label"] + ";extra=x",
                      asset()["label"] + ";" + asset()["label"],
                      asset(1, "c" * 40, "e" * 40)["label"]):
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, "Unverified docs asset"):
                self.select([asset(), dict(asset(1), label=label)])

    def test_invalid_lower_revision_is_not_silently_skipped(self):
        with self.assertRaisesRegex(ValueError, "Unverified docs asset"):
            self.select([asset(), dict(asset(1), label="broken"), asset(2, "d" * 40)])

    def test_duplicate_source_labels_fail(self):
        with self.assertRaisesRegex(ValueError, "Duplicate docs source"):
            self.select([asset(), asset(1)])

    def test_unrelated_sources_and_sources_off_default_branch_fail(self):
        for responses in (["diverged"], ["ahead", "behind"],
                          ["ahead", "ahead", "behind"], ["ahead", "ahead", "ahead", "diverged"]):
            self.gh.side_effect = [json.dumps({"status": status}) for status in responses]
            with self.subTest(responses=responses), self.assertRaisesRegex(ValueError, "Unverified docs provenance"):
                self.select([asset(), asset(1, "c" * 40)])

    def test_source_at_tag_is_valid(self):
        self.gh.return_value = '{"status": "identical"}'
        self.assertEqual(self.select([asset(source=TAG_SHA)])["name"], "docs-site.tar.gz")

    def test_unknown_source_commit_fails(self):
        self.gh.side_effect = assembler.subprocess.CalledProcessError(1, "gh")
        with self.assertRaises(assembler.subprocess.CalledProcessError):
            self.select([asset()])

    def test_non_version_tag_fails(self):
        with self.assertRaisesRegex(ValueError, "Invalid software version"):
            self.select([asset()], "docs-only")


class DiscoveryTests(unittest.TestCase):
    def test_annotated_and_lightweight_tags(self):
        for obj in ({"type": "commit", "sha": TAG_SHA}, {"type": "tag", "sha": "e" * 40}):
            responses = [json.dumps({"object": obj}), json.dumps({"object": {"type": "commit", "sha": TAG_SHA}})]
            with self.subTest(obj=obj), patch.object(assembler, "gh", side_effect=responses):
                self.assertEqual(assembler.tag_sha(REPO, "v1.0.0"), TAG_SHA)

    def test_non_commit_tag_fails(self):
        with patch.object(assembler, "gh", return_value='{"object": {"type": "tree"}}'):
            with self.assertRaisesRegex(ValueError, "Invalid tag"):
                assembler.tag_sha(REPO, "v1.0.0")

    def test_paginated_json_lines(self):
        with patch.object(assembler, "gh", return_value='{"id":1}\n{"id":2}\n') as gh:
            self.assertEqual(assembler.api_items("endpoint"), [{"id": 1}, {"id": 2}])
            gh.assert_called_once_with("api", "--paginate", "endpoint", "--jq", ".[] | @json")

    def test_software_order_and_complete_asset_listing(self):
        releases = [
            {"id": n, "tag_name": tag, "draft": draft, "prerelease": prerelease}
            for n, (tag, draft, prerelease) in enumerate([
                ("v0.9.0", False, False), ("v0.10.0", False, False),
                ("v9.0.0", True, False), ("v8.0.0", False, True), ("v0.1.0", False, False),
            ])
        ]
        r10 = asset(10, "c" * 40)
        pages = [releases, [asset(), r10], [asset()], []]
        with patch.object(assembler, "api_items", side_effect=pages) as items, \
                patch.object(assembler, "tag_sha", return_value=TAG_SHA), \
                patch.object(assembler, "gh", side_effect=lambda *args: json.dumps(
                    {"default_branch": "main", "sha": MAIN_SHA, "status": "ahead"})):
            self.assertEqual(assembler.releases(REPO), [("v0.10.0", asset()), ("v0.9.0", r10)])
        self.assertEqual(items.call_count, 4)
        items.assert_any_call(f"repos/{REPO}/releases/0/assets?per_page=100")


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="docs-revisions-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_download_uses_verified_id_and_checks_digest(self):
        data = b"immutable archive"
        selected = dict(asset(2), digest="sha256:" + hashlib.sha256(data).hexdigest())
        destination = self.root / "download.tar.gz"

        def download(args, stdout, check):
            self.assertEqual(args, ["gh", "api", f"repos/{REPO}/releases/assets/3",
                                    "-H", "Accept: application/octet-stream"])
            self.assertTrue(check)
            stdout.write(data)

        with patch.object(assembler.subprocess, "run", side_effect=download):
            assembler.download_asset(REPO, "v1.0.0", selected, destination)
            self.assertEqual(destination.read_bytes(), data)
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                assembler.download_asset(REPO, "v1.0.0", dict(selected, digest="sha256:bad"), destination)

    def test_product_navigation_and_original_only_legacy_fallbacks(self):
        target = self.root / "docs"
        target.mkdir()
        (target / "index.md").write_text("# Guide\n")
        (target / "topic.md").write_text("# Topic\n")
        self.assertEqual(assembler.load_topics("spring", "0.1.0", target, legacy=True),
                         ["spring/0.1.0/index.md", "spring/0.1.0/topic.md"])
        with self.assertRaisesRegex(ValueError, "Missing product-owned nav.yml"):
            assembler.load_topics("spring", "0.1.0", target)
        core = self.root / "core"
        core.mkdir()
        (core / "nav.yml").write_text("- index.md\n- topic.md\n")
        with patch.object(assembler, "DOCS", self.root):
            self.assertEqual(assembler.load_topics("core", "0.4.0", target, legacy=True),
                             ["core/0.4.0/index.md", "core/0.4.0/topic.md"])
        (target / "nav.yml").write_text("- Start: index.md\n- Product title: topic.md\n")
        self.assertEqual(assembler.load_topics("core", "0.4.0", target),
                         [{"Start": "core/0.4.0/index.md"}, {"Product title": "core/0.4.0/topic.md"}])
        self.assertFalse((target / "nav.yml").exists())

    def test_invalid_navigation_fails(self):
        (self.root / "index.md").write_text("# Guide\n")
        for nav in ([], ["missing.md"], ["index.md", "missing.md"], ["index.md", "../outside.md"]):
            (self.root / "nav.yml").write_text(yaml.safe_dump(nav))
            with self.subTest(nav=nav), self.assertRaises(ValueError):
                assembler.load_topics("spring", "0.1.0", self.root)

    def make_archive(self, name, files):
        path = self.root / name
        with tarfile.open(path, "w:gz") as archive:
            for name, text in files.items():
                data = text.encode()
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        return path

    def test_assembly_keeps_version_urls_and_discovery_deterministic(self):
        docs = self.root / "docs"
        build = self.root / "build"
        shutil.copytree(assembler.DOCS, docs)
        original = self.make_archive("original.tar.gz", {
            "index.md": "# Original\n", "nav.yml": "- index.md\n",
        })
        revised = self.make_archive("revision.tar.gz", {
            "index.md": "# Revised\n", "topic.md": "# Topic\n",
            "nav.yml": "- Start: index.md\n- Product topic: topic.md\n",
            "robots.txt": "product robots", "llms.txt": "product llms",
        })
        original_digest = hashlib.sha256(original.read_bytes()).hexdigest()
        latest = {"core": "v0.4.0", "spring": "v0.1.0"}
        archives = {"docs-site.tar.gz": original, "docs-site-r10.tar.gz": revised}

        def download(repo, tag, selected, destination):
            shutil.copyfile(archives[selected["name"]], destination)

        def releases(repo):
            product = "spring" if repo.endswith("-spring") else "core"
            return [(latest[product], asset(10, "c" * 40)), ("v0.0.1", asset())]

        with patch.object(assembler, "DOCS", docs), patch.object(assembler, "BUILD", build), \
                patch.object(assembler, "BUILD_DOCS", build / "docs"), \
                patch.object(assembler, "releases", side_effect=releases), \
                patch.object(assembler, "download_asset", side_effect=download):
            assembler.main()
            snapshot = {str(p.relative_to(build)): p.read_bytes() for p in build.rglob("*") if p.is_file()}
            assembler.main()
            self.assertEqual(snapshot, {str(p.relative_to(build)): p.read_bytes() for p in build.rglob("*") if p.is_file()})
        config = yaml.safe_load((build / "mkdocs.yml").read_text())
        self.assertEqual(config["nav"][1]["Core"][0], {"0.4.0": [
            {"Start": "core/0.4.0/index.md"}, {"Product topic": "core/0.4.0/topic.md"},
        ]})
        self.assertIn("# Revised", (build / "docs/core/0.4.0/index.md").read_text())
        self.assertIn("# Original", (build / "docs/core/0.0.1/index.md").read_text())
        self.assertIn("core/0.4.0/", (build / "docs/llms.txt").read_text())
        self.assertNotIn("r10", str(config))
        self.assertFalse((build / "docs/core/0.4.0/robots.txt").exists())
        self.assertFalse((build / "docs/core/0.4.0/llms.txt").exists())
        self.assertEqual((build / "docs/robots.txt").read_bytes(), (docs / "robots.txt").read_bytes())
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), original_digest)


if __name__ == "__main__":
    unittest.main()
