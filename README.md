# JSON:API for Java documentation

Shared MkDocs/Pages portal for the independently released
[Core](https://github.com/kazforge/jsonapi-java) and
[Spring](https://github.com/kazforge/jsonapi-java-spring) libraries.

Each product owns its `docs/site/` guides. This repository only hosts the
portal, assembling immutable documentation assets from product GitHub
Releases into versioned pages, navigation and discovery files automatically.

## Local build

Use Python 3.14 and the pinned dependencies. Released product docs assets
must be available on GitHub.

```sh
python -m pip install --only-binary :all: --require-hashes -r requirements.txt
GH_TOKEN="$(gh auth token)" python scripts/assemble_docs.py
mkdocs build --strict -f build/mkdocs.yml
mkdocs serve -f build/mkdocs.yml
```

Assembly writes only to ignored `build/`; generated `build/mkdocs.yml` inherits
the shared `mkdocs.yml`, builds from `build/docs/` and outputs to root `site/`
for Pages and PR previews. Homepage prose stays in `docs/index.md`;
only `{core}` and `{spring}` version placeholders are replaced
in the build copy. Assemble before running MkDocs.

Run the assembler tests with `python -m unittest discover -s tests -v`.

## Immutable documentation revisions

Each existing software Release keeps its original `docs-site.tar.gz` (revision
0). Products can append `docs-site-r1.tar.gz`, `docs-site-r2.tar.gz`, etc. to
that same Release without releasing software or opening a Portal PR. The
assembler selects the highest **numeric** revision, or the original when no
revisions exist. Software version ordering, URLs and version pickers do not
include revision numbers. The existing `docs-release-published` repository
dispatch runs the same strict MkDocs build and Pages deployment.

Every docs asset must have exactly the label
`docs-source-sha=<40 lowercase hex characters>;software-tag-sha=<40 lowercase hex characters>`.
The software SHA must match the resolved release tag commit. The docs source
must descend from that commit and be reachable from the product's default
branch; revisions must also descend from the original docs source. This allows
the existing post-release Core 0.4.0 original. Product review and publishing
own the docs-only change check and released-API compatibility; ancestry alone
does not establish semantic compatibility.

Missing originals, duplicate revisions or source SHAs, malformed `docs-site*`
names, bad labels and unverified provenance fail the build, even on an older
revision. Invalid revisions never silently fall back to another asset. Assets
are downloaded by verified ID and checked against GitHub's SHA-256 digest when
provided. All originals and revisions remain untouched on GitHub. Rebuilding
the same release metadata selects the same snapshot; rollback is a reviewed
docs revert published as the next revision, not replacement of an old asset.

Future product archives must include a `nav.yml` list with `index.md` first
(optionally labelled), followed by product-owned topic labels and paths.
Only the Core 0.4.0 original uses `docs/core/nav.yml`; only the Spring 0.1.0
original retains file-based navigation. Revisions use their product-owned
manifest. No product Markdown or discovery files are parsed for navigation.
