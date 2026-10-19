# JSON:API for Java documentation

Shared MkDocs/Pages portal for the independently released
[Core](https://github.com/kazforge/jsonapi-java) and
[Spring](https://github.com/kazforge/jsonapi-java-spring) libraries.

Each product owns its `docs/site/` guides. This repository only hosts the
portal, assembling immutable `docs-site.tar.gz` assets from product GitHub
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

Future product archives must include a `nav.yml` list with `index.md` first
(optionally labelled), followed by product-owned topic labels and paths.
Core 0.4.0 alone uses `docs/core/nav.yml`; Spring 0.1.0 retains its original
file-based navigation. No product Markdown or discovery files are parsed for navigation.
