
# Design Documents & Slide Decks

This directory contains design documents and presentation slide decks
for the vLLM CPU performance evaluation project.
## Available Decks

| File | Description |
|------|-------------|
| [full-testing-deck.md](full-testing-deck.md) | Full testing methodology (Marp source; ~37 slides) |

Marp sources are **excluded from the MkDocs site build** (front matter would
conflict). Preview or export with Marp CLI as below. CI → GitHub Pages HTML
publish can be added later once the deck layout is stable.
## Rendering Slides with Marp

Slide decks use [Marp](https://marp.app/) (Markdown Presentation Ecosystem).
Each slide is separated by `---`. The deck includes Marp front matter
(`marp: true`, `size: 16:9`, compact table styles).

**Prerequisites:** Node.js >= 18

All commands use `npx` — nothing is installed into the repo.

### Live preview (recommended — check slide fit)

```bash
npx @marp-team/marp-cli@4 docs/design/full-testing-deck.md --server
```

Open the URL Marp prints, then step through slides. Dense tables should fit
without vertical clipping at 16:9.

### Render to HTML

```bash
npx @marp-team/marp-cli@4 docs/design/full-testing-deck.md -o /tmp/slides.html
open /tmp/slides.html
```

### Export to PDF

```bash
npx @marp-team/marp-cli@4 docs/design/full-testing-deck.md -o /tmp/slides.pdf
```

### Render all decks in this directory

```bash
npx @marp-team/marp-cli@4 docs/design/*.md -o /tmp/
```

> **Note:** Output files go to `/tmp` so they are not committed to the repo.
> The `node_modules/` directory is gitignored in case `npx` creates a local
> cache. Pin `@marp-team/marp-cli@4` for reproducible builds.
