# hamseabd.github.io

Personal blog. Built with [Hugo](https://gohugo.io) and the [PaperMod](https://github.com/adityatelange/hugo-PaperMod) theme. Deployed to GitHub Pages via GitHub Actions.

## Local development

```bash
# Preview locally with drafts
hugo server --buildDrafts

# Build production
hugo --minify
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
