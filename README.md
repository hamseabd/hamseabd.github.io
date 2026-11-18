# hamseabd.github.io

Personal blog. Built with [Hugo](https://gohugo.io) and the [PaperMod](https://github.com/adityatelange/hugo-PaperMod) theme. Deployed to GitHub Pages via GitHub Actions.

## Local development

```bash
# Preview locally with drafts
hugo server --buildDrafts

# Build production
hugo --minify
```

## Verify

```bash
# Build as the deploy does, check every internal link, asset, and #anchor,
# and confirm drafts stay out of the published build (Python 3.12, stdlib only)
scripts/verify.sh

# The checker's own tests
python3.12 -m venv .venv && .venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest scripts
```

## Add a new post

```bash
hugo new content posts/<slug>.md
```

Edit `content/posts/<slug>.md`, set `draft: false` when ready, push to main. GitHub Actions builds and deploys automatically.

## Theme

PaperMod is included as a git submodule in `themes/PaperMod`. To update:

```bash
git submodule update --remote --merge
```
