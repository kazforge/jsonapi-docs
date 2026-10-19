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
mkdocs build --strict
mkdocs serve
```
