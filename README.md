# JSON:API for Java documentation

Versioned Core library and Spring integration documentation, maintained by
KazForge. Preview hosting: <https://kazforge.github.io/jsonapi-docs/>.
Published guides: Core **0.4.0** and Spring **0.1.0**. The current Core website
and custom domain stay unchanged until a separately approved manual cutover.

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
   library landing page to the latest approval. Update root `docs/llms.txt` with
   the published version link; import no historical Core releases.
4. For local preview, check out the same SHA under `_sources/core` or
   `_sources/spring`, then copy its `docs/site/` into `docs/core/<version>/` or
   `docs/spring/<version>/`, as the workflow does. Run the strict build and inspect
   navigation, relative links, assets and search at desktop/mobile widths.

## Discovery and legacy links

The portal owns `docs/robots.txt` and `docs/llms.txt`; MkDocs copies them to the
site root. Keep them out of versioned guides. On each approved promotion, update
`llms.txt` to list only published versions, using relative links for preview and
production. `robots.txt` allows public crawling and names the production sitemap
for use after cutover; it does not change the preview's canonical site URL.

Eight `docs/<legacy-route>/index.html` pages forward old Core links to the matching
Core 0.4.0 pages. Relative targets work under `/jsonapi-docs/` and `/`. JavaScript
preserves query strings and fragments with `location.replace`; without JavaScript,
visitors can follow the fallback link (without the original query/fragment).
These are HTTP 200 HTML pages, not HTTP 301 redirects. Keep their 0.4.0 targets
stable, including `/getting-started/`, used by the immutable Spring 0.1.0 guide.

## Manual domain cutover (separate approval required)

- [ ] Verify the preview's root, both guides, all eight legacy routes (including
  queries/fragments), navigation, assets and search on desktop/mobile. Obtain
  explicit Core/Lead PO approval for the transfer window.
- [ ] Record both repositories' Pages settings, the known-good Core deployment,
  and Cloudflare's `jsonapi` DNS record/TTL/proxy settings for rollback.
- [ ] Prepare and review a separate portal config PR setting `mkdocs.yml`
  `site_url` to `https://jsonapi.kazforge.com/` and final production discovery
  values. Merge it only during the approved transfer window.
- [ ] Transfer the custom domain from Core Pages to portal Pages and redeploy.
  Adjust Cloudflare DNS only if required; leave the Core publisher intact.
- [ ] Verify HTTPS/certificate, HTTP/default-host redirects, canonical URLs,
  sitemap/discovery files, both guides, assets/search and all eight legacy URLs,
  especially Spring's `https://jsonapi.kazforge.com/getting-started/` link.
- [ ] Only after production passes verification, open/review the separate Core
  publisher-retirement PR, preserving Core's docs build and required check.
- [ ] If verification fails, restore the original Pages domain and any changed
  DNS settings, redeploy the recorded Core deployment, and revert the portal
  config through a reviewed PR to restore preview hosting.

Search Console verification remains separate under KAZ-260.
