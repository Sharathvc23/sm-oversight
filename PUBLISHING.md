# Publishing sm-oversight to PyPI

`sm-oversight` publishes via **PyPI Trusted Publishing** — no API tokens. You tell
PyPI once that this repo's `release.yml` workflow may publish; after that, pushing
a version tag builds and uploads automatically.

## One-time setup (≈5 minutes — this is the part only you can do)

1. Sign in to PyPI (the same account that publishes the rest of the `sm-*` family).
2. Go to **https://pypi.org/manage/account/publishing/** → "Add a pending
   publisher" (use *pending*, because the `sm-oversight` project doesn't exist on
   PyPI yet — the first publish creates it).
3. Fill the form with **exactly** these values:

   | Field | Value |
   |-------|-------|
   | PyPI Project Name | `sm-oversight` |
   | Owner | `Sharathvc23` |
   | Repository name | `sm-oversight` |
   | **Workflow name** | `release.yml`  ← just the filename |
   | Environment name | *(leave blank)* |

That's it. No secret is created or stored anywhere.

## Releasing (every time, after setup)

```bash
# bump `version` in pyproject.toml (+ sm_oversight/__init__.py __version__)
# and update CHANGELOG, commit, then:
git tag v0.1.0
git push origin v0.1.0
```

The `release` workflow builds the sdist + wheel, runs `twine check`, and uploads
to PyPI over OIDC. Watch it under the repo's **Actions** tab. Within a minute,
`pip install sm-oversight` works for everyone.

## Notes

- The tag (`v0.1.0`) and `version` in `pyproject.toml` must match.
- The wheel ships the vendored `sm_arp/` (see `VENDORED.md`) — no external
  git dependency at install time; `twine check` covers both packages.
- Dry run anytime, no upload: `python -m build && python -m twine check dist/*`.
- Publishing to PyPI lets downstream packages (e.g. the
  `sm-dissociation-receipt[oversight]` extra) depend on this one as a normal
  pinned dependency instead of a git checkout.
