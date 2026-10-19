"""Build the portal from Core and Spring GitHub Release documentation assets."""

import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
BUILD = ROOT / "build"
BUILD_DOCS = BUILD / "docs"
MKDOCS = ROOT / "mkdocs.yml"
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


def prefix_nav(items, prefix, target):
    if isinstance(items, str):
        resolved = (target / items).resolve()
        if not resolved.is_relative_to(target.resolve()) or not resolved.is_file():
            raise ValueError(f"Invalid nav target: {prefix}/{items}")
        return f"{prefix}/{items}"
    if isinstance(items, list):
        return [prefix_nav(i, prefix, target) for i in items]
    if isinstance(items, dict):
        return {k: prefix_nav(v, prefix, target) for k, v in items.items()}
    raise ValueError(f"Invalid nav entry: {items}")


def load_topics(product, version, target):
    manifest = target / "nav.yml"
    if not manifest.is_file() and (product, version) == ("core", "0.4.0"):
        manifest = DOCS / "core" / "nav.yml"
    if manifest.is_file():
        raw = yaml.safe_load(manifest.read_text())
        (target / "nav.yml").unlink(missing_ok=True)
    elif (product, version) == ("spring", "0.1.0"):
        # This immutable snapshot predates nav.yml; retain MkDocs' file ordering.
        raw = ["index.md"] + sorted(p.name for p in target.glob("*.md") if p.name != "index.md")
    else:
        raise ValueError(f"Missing product-owned nav.yml: {product} {version}")
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"Expected a nonempty navigation list: {product} {version}")
    first = raw[0]
    if isinstance(first, dict) and len(first) == 1:
        first = next(iter(first.values()))
    if first != "index.md":
        raise ValueError(f"Navigation must start with index.md: {product} {version}")
    return prefix_nav(raw, f"{product}/{version}", target)


def main():
    config = yaml.safe_load(MKDOCS.read_text())
    products = config["extra"]["products"]
    shutil.rmtree(BUILD_DOCS, ignore_errors=True)
    shutil.copytree(DOCS, BUILD_DOCS)
    (BUILD_DOCS / "core" / "nav.yml").unlink(missing_ok=True)
    nav = [{"Overview": "index.md"}]
    latest = {}
    llms = [f"# {config['site_name']}", "", f"> {config['site_description']}", ""]
    for product, meta in products.items():
        repo = meta["repo"]
        versions = releases(repo)
        if not versions:
            raise ValueError(f"No published docs assets: {repo}")
        latest[product] = versions[0][1:]
        version_nav = []
        version_links = []
        for tag in versions:
            version = tag[1:]
            target = BUILD_DOCS / product / version
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
            version_nav.append({version: load_topics(product, version, target)})
            version_links.append(f"- [{version}]({version}/index.md)")
            llms.append(f"- [{meta['title']} {version}]({product}/{version}/)")
        version_nav.append({"Releases": f"{product}/index.md"})
        nav.append({meta["title"]: version_nav})
        index_md = BUILD_DOCS / product / "index.md"
        index_md.write_text(index_md.read_text().rstrip() + "\n\n" + "\n".join(version_links) + "\n")
    home_md = BUILD_DOCS / "index.md"
    home = home_md.read_text()
    for product, version in latest.items():
        home = home.replace("{" + product + "}", version)
    home_md.write_text(home)
    (BUILD_DOCS / "llms.txt").write_text("\n".join(llms) + "\n")
    (BUILD / "mkdocs.yml").write_text(yaml.safe_dump({
        "INHERIT": "../mkdocs.yml",
        "docs_dir": "docs",
        "site_dir": "../site",
        "theme": {"custom_dir": "../overrides"},
        "nav": nav,
    }, sort_keys=False))


if __name__ == "__main__":
    main()
