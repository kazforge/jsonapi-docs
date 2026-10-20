"""Build the portal from Core and Spring GitHub Release documentation assets."""

import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import quote

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
BUILD = ROOT / "build"
BUILD_DOCS = BUILD / "docs"
MKDOCS = ROOT / "mkdocs.yml"
LABEL = re.compile(r"docs-source-sha=([a-f0-9]{40});software-tag-sha=([a-f0-9]{40})")
VERSION = re.compile(r"v(\d+)\.(\d+)\.(\d+)")
REVISION = re.compile(r"docs-site-r([1-9][0-9]*)\.tar\.gz")


def gh(*args):
    return subprocess.check_output(["gh", *args], text=True)


def api_items(endpoint):
    # JSON lines work with older gh versions too, without --slurp.
    return [json.loads(line) for line in gh(
        "api", "--paginate", endpoint, "--jq", ".[] | @json"
    ).splitlines()]


def tag_sha(repo, tag):
    obj = json.loads(gh("api", f"repos/{repo}/git/ref/tags/{tag}"))["object"]
    if obj["type"] == "tag":
        obj = json.loads(gh("api", f"repos/{repo}/git/tags/{obj['sha']}"))["object"]
    if obj["type"] != "commit":
        raise ValueError(f"Invalid tag: {repo} {tag}")
    return obj["sha"]


def require_ancestor(repo, base, head):
    comparison = json.loads(gh("api", f"repos/{repo}/compare/{base}...{head}?per_page=1"))
    if comparison["status"] not in ("ahead", "identical"):
        raise ValueError(f"Unverified docs provenance: {repo}: {base} is not an ancestor of {head}")


def select_asset(repo, tag, assets, main_sha):
    revisions = {}
    for asset in assets:
        name = asset["name"]
        if not name.startswith("docs-site"):
            continue
        revision = REVISION.fullmatch(name)
        if name == "docs-site.tar.gz":
            number = 0
        elif revision:
            number = int(revision[1])
        else:
            raise ValueError(f"Malformed docs revision: {repo} {tag}: {name}")
        if number in revisions:
            raise ValueError(f"Duplicate docs revision: {repo} {tag}: {name}")
        revisions[number] = asset
    if not revisions:
        return None
    if 0 not in revisions:
        raise ValueError(f"Missing original docs-site.tar.gz: {repo} {tag}")
    if not VERSION.fullmatch(tag):
        raise ValueError(f"Invalid software version: {repo} {tag}")
    software_sha = tag_sha(repo, tag)
    sources = set()
    original_source = None
    for number, asset in sorted(revisions.items()):
        label = LABEL.fullmatch(asset.get("label") or "")
        if not label or label[2] != software_sha:
            raise ValueError(f"Unverified docs asset: {repo} {tag}: {asset['name']}")
        source = label[1]
        if source in sources:
            raise ValueError(f"Duplicate docs source: {repo} {tag}: {asset['name']}: {source}")
        sources.add(source)
        # Originals may be prepared after the software release (Core 0.4.0).
        # All sources must descend from that release and be on the reviewed
        # default-branch history. Revisions must also include the original source.
        require_ancestor(repo, original_source or software_sha, source)
        require_ancestor(repo, source, main_sha)
        if number == 0:
            original_source = source
    return revisions[max(revisions)]


def releases(repo):
    branch = json.loads(gh("api", f"repos/{repo}"))["default_branch"]
    main_sha = json.loads(gh("api", f"repos/{repo}/commits/{quote(branch, safe='')}"))["sha"]
    found = []
    for release in api_items(f"repos/{repo}/releases?per_page=100"):
        if release["draft"] or release["prerelease"]:
            continue
        tag = release["tag_name"]
        version = VERSION.fullmatch(tag)
        # Release responses include the assets; only the release list is paginated.
        asset = select_asset(repo, tag, release["assets"], main_sha)
        if asset is None:
            continue
        if not version or any(tag == existing[1] for existing in found):
            raise ValueError(f"Unverified docs asset: {repo} {tag}")
        found.append((tuple(map(int, version.groups())), tag, asset))
    return [(tag, asset) for _, tag, asset in sorted(found, reverse=True)]


def download_asset(repo, tag, asset, destination):
    # Download by the verified asset ID, not a name that could be replaced
    # between listing metadata and downloading the archive.
    with destination.open("wb") as output:
        subprocess.run(["gh", "api", f"repos/{repo}/releases/assets/{asset['id']}",
                        "-H", "Accept: application/octet-stream"], stdout=output, check=True)
    if asset.get("digest"):
        with destination.open("rb") as archive:
            digest = "sha256:" + hashlib.file_digest(archive, "sha256").hexdigest()
        if digest != asset["digest"]:
            raise ValueError(f"Docs asset digest mismatch: {repo} {tag}: {asset['name']}")
    print(f"{repo} {tag}: {asset['name']} ({asset['label']})")


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


def load_topics(product, version, target, legacy=False):
    manifest = target / "nav.yml"
    if legacy and not manifest.is_file() and (product, version) == ("core", "0.4.0"):
        manifest = DOCS / "core" / "nav.yml"
    if manifest.is_file():
        raw = yaml.safe_load(manifest.read_text())
        (target / "nav.yml").unlink(missing_ok=True)
    elif legacy and (product, version) == ("spring", "0.1.0"):
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
        latest[product] = versions[0][0][1:]
        version_nav = []
        version_links = []
        for tag, asset in versions:
            version = tag[1:]
            target = BUILD_DOCS / product / version
            target.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory() as tmp:
                archive_path = Path(tmp) / asset["name"]
                download_asset(repo, tag, asset, archive_path)
                with tarfile.open(archive_path, "r:gz") as archive:
                    archive.extractall(target, filter="data")
            if not (target / "index.md").is_file():
                raise ValueError(f"Missing index.md: {repo} {tag}")
            for name in ("robots.txt", "llms.txt"):
                (target / name).unlink(missing_ok=True)
            version_nav.append({version: load_topics(
                product, version, target, legacy=asset["name"] == "docs-site.tar.gz"
            )})
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
