# JSON:API for Java documentation

Versioned Core library and Spring integration documentation, maintained by
KazForge. Preview hosting: <https://kazforge.github.io/jsonapi-docs/>.
No releases are approved yet. The current Core website and custom domain stay unchanged.

## Ownership

Core and Spring own their public `docs/site/` guides in `kazforge/jsonapi-java`
and `kazforge/jsonapi-java-spring`, respectively. This repository owns shared
navigation, local copies of Core's styling/logo, release pins and Pages hosting.
It copies guides at build time, never runs library code or commits copied guides.

## Local build

Use Linux x86_64 and Python 3.13 or 3.14:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --only-binary :all: --require-hashes -r requirements.txt
mkdocs build --strict
mkdocs serve
```

## Promote a release

1. Confirm Maven Central publication and a clean external consumer test. Include
   evidence, software tag and full commit SHA in a reviewed PR.
2. Set that library's version and full SHA directly in
   `.github/workflows/docs-pages.yml`. Keep the other library independent.
   For additional versions, duplicate its explicit pinned checkout/copy steps;
   retain old version pins and directories. Never use moving `main` references.
3. Add the version and its pages to standard `mkdocs.yml` navigation, and link the
   library landing page to the latest approval. Start with Core's **next** release
   or Spring's **first public** release; import no historical Core releases.
4. For local preview, check out the same SHA under `_sources/core` or
   `_sources/spring`, then copy its `docs/site/` into `docs/core/<version>/` or
   `docs/spring/<version>/`, as the workflow does. Run the strict build and inspect
   navigation, relative links, assets and search at desktop/mobile widths.
