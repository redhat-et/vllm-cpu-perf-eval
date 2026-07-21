---
layout: default
title: Design & Slides
---

## Design Documents & Slide Decks

This directory contains design documents and presentation slide decks
for the vLLM CPU performance evaluation project.

### Available Decks

| File | Description |
|------|-------------|
| [full-testing-deck.md](full-testing-deck.md) | Complete testing methodology overview |

### Rendering Slides with Marp

Slide decks use [Marp](https://marp.app/) (Markdown Presentation Ecosystem).
Slides are separated by `---` in the markdown source.

**Prerequisites:** Node.js >= 18

All commands use `npx` — nothing is installed into the repo.

#### Render to HTML

```bash
npx @marp-team/marp-cli docs/design/full-testing-deck.md -o /tmp/slides.html
open /tmp/slides.html
```

#### Live-reload server (auto-refreshes on save)

```bash
npx @marp-team/marp-cli docs/design/full-testing-deck.md --server
```

#### Export to PDF

```bash
npx @marp-team/marp-cli docs/design/full-testing-deck.md -o /tmp/slides.pdf
```

#### Render all decks in this directory

```bash
npx @marp-team/marp-cli docs/design/ -o /tmp/
```

> **Note:** Output files go to `/tmp` so they are not committed to the repo.
> The `node_modules/` directory is gitignored in case `npx` creates a local
> cache.
