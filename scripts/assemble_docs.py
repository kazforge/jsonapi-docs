"""Build the portal from Core and Spring GitHub Release documentation assets."""

import json
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
PRODUCTS = {"core": "kazforge/jsonapi-java", "spring": "kazforge/jsonapi-java-spring"}
LABEL = re.compile(r"docs-source-sha=([a-f0-9]{40});software-tag-sha=([a-f0-9]{40})")
VERSION = re.compile(r"v(\d+)\.(\d+)\.(\d+)")


def gh(*args):
    return subprocess.check_output(["gh", *args], text=True)


def tag_sha(repo, tag):
    obj = json.loads(gh("api", f"repos/{repo}/git/ref/tags/{tag}"))["object"]
    if obj["type"] == "tag":
        obj = json.loads(gh("api", f"repos/{repo}/git/tags/{obj['sha']}"))["object"]
    if obj["type"] != "commit":
        raise ValueError(f"Invalid tag: {repo} {tag}")
    return obj["sha"]


def releases(repo):
    pages = json.loads(gh("api", "--paginate", "--slurp", f"repos/{repo}/releases?per_page=100"))
    found = []
    for release in (r for page in pages for r in page):
        if release["draft"] or release["prerelease"]:
            continue
        assets = [a for a in release["assets"] if a["name"] == "docs-site.tar.gz"]
        if not assets:
            continue
        tag = release["tag_name"]
        version = VERSION.fullmatch(tag)
        label = LABEL.fullmatch(assets[0].get("label") or "")
        if len(assets) != 1 or not version or not label or label[2] != tag_sha(repo, tag):
            raise ValueError(f"Unverified docs asset: {repo} {tag}")
        found.append((tuple(map(int, version.groups())), tag))
    return [tag for _, tag in sorted(found, reverse=True)]


def main():
    home = ["---", "title: Overview", "---", "", "# JSON:API for Java", "", "Published documentation:", ""]
    llms = ["# JSON:API for Java", "", "> Published Core and Spring guides.", ""]
    for product, repo in PRODUCTS.items():
        label = "Core library" if product == "core" else "Spring integration"
        versions = releases(repo)
        if not versions:
            raise ValueError(f"No published docs assets: {repo}")
        home.append(f"- [{label}]({product}/index.md)")
        landing = [f"# {label}", "", f"[Source on GitHub](https://github.com/{repo})", "",
                   "## Documentation versions", "",
                   '<div class="version-picker">',
                   f'<label for="{product}-version">Version</label>',
                   f'<select id="{product}-version" onchange="if (this.value) location.href = this.value">',
                   '  <option value="" selected disabled>Choose a version</option>']
        for tag in versions:
            version = tag[1:]
            target = DOCS / product / version
            target.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory() as tmp:
                subprocess.run(["gh", "release", "download", tag, "-R", repo,
                                "-p", "docs-site.tar.gz", "-D", tmp], check=True)
                with tarfile.open(Path(tmp) / "docs-site.tar.gz", "r:gz") as archive:
                    archive.extractall(target, filter="data")
            if not (target / "index.md").is_file():
                raise ValueError(f"Missing index.md: {repo} {tag}")
            for name in ("robots.txt", "llms.txt"):
                (target / name).unlink(missing_ok=True)
            landing.append(f'  <option value="{version}/">{version}</option>')
            llms.append(f"- [{label} {version}]({product}/{version}/)")
        landing.extend(["</select>", "</div>"])
        (DOCS / product / "index.md").write_text("\n".join(landing) + "\n")
    (DOCS / "index.md").write_text("\n".join(home) + "\n")
    (DOCS / "llms.txt").write_text("\n".join(llms) + "\n")


if __name__ == "__main__":
    main()
