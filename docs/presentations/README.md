# Presentations

This directory contains presentation decks for vLLM performance evaluation results and methodology.

## Available Presentations

### 1. Embedding Models: Methodology & Results
**File:** [embedding-models-methodology-results.md](embedding-models-methodology-results.md)

**Content:**
- Test methodology and architecture
- Workload characterization
- Results analysis for 5 embedding models
- Key findings and recommendations
- Deployment best practices

**Generated from test results:**
- Platform: Intel Xeon 6975P (128 cores)
- vLLM Version: 0.18.0+rhaiv.7 (Red Hat AI Inference Server)
- Test Date: June 2-3, 2026

## Converting to Presentation Format

The markdown files use [Marp](https://marp.app/) format, which can be converted to HTML, PDF, or PPTX.

### Option 1: Using Marp CLI (Recommended)

**Install Marp CLI:**
```bash
npm install -g @marp-team/marp-cli
```

**Generate HTML (for web viewing):**
```bash
marp embedding-models-methodology-results.md -o embedding-models.html
```

**Generate PDF (for sharing):**
```bash
marp embedding-models-methodology-results.md -o embedding-models.pdf
```

**Generate PowerPoint:**
```bash
marp embedding-models-methodology-results.md -o embedding-models.pptx
```

**Live preview while editing:**
```bash
marp -w embedding-models-methodology-results.md
```

### Option 2: Using Marp for VS Code

1. Install the [Marp for VS Code extension](https://marketplace.visualstudio.com/items?itemName=marp-team.marp-vscode)
2. Open the `.md` file in VS Code
3. Click "Open Preview" or use the export options in the extension

### Option 3: Using Reveal.js (Alternative)

If you prefer reveal.js presentations:

```bash
# Install pandoc
brew install pandoc  # macOS
# or: sudo apt-get install pandoc  # Linux

# Convert to reveal.js HTML
pandoc embedding-models-methodology-results.md \
  -t revealjs \
  -s \
  -o embedding-models-reveal.html \
  -V theme=white
```

## Presentation Structure

All presentations follow this standard structure:

1. **Title & Executive Summary** - Overview and key findings
2. **Methodology** - Test architecture, workloads, metrics
3. **Test Setup** - Platform, models, configurations
4. **Results** - Data analysis and comparisons
5. **Key Findings** - Major insights and observations
6. **Recommendations** - Deployment guidance and best practices
7. **Future Work** - Next steps and open questions

## Customizing Presentations

### Themes

Marp supports several built-in themes. To change theme, edit the frontmatter:

```yaml
---
marp: true
theme: default  # Options: default, gaia, uncover
---
```

### Custom Styling

Add custom CSS in the frontmatter:

```yaml
---
marp: true
style: |
  section {
    background-color: #f0f0f0;
  }
  h1 {
    color: #cc0000;
  }
---
```

### Adding Images

Reference images relative to the markdown file:

```markdown
![Architecture Diagram](../diagrams/architecture.png)
```

## Updating Presentations

When new test results are available:

1. Extract key metrics from `results/embedding/*/test-metadata.json`
2. Update the relevant slides with new data
3. Regenerate the presentation files
4. Archive previous versions in `presentations/archive/`

## Best Practices

1. **Keep slides concise** - Max 7 bullet points per slide
2. **Use tables for data** - Better than paragraphs for metrics
3. **Include units** - Always specify ms, RPS, tokens/s, etc.
4. **Show trends** - Use before/after comparisons
5. **Highlight key findings** - Use ✅ ⚠️ ❌ emojis for quick scanning
6. **Cite sources** - Reference specific test runs/files
7. **Version presentations** - Include test date and vLLM version

## Presentation Checklist

Before sharing a presentation:

- [ ] Verify all data is from current test results
- [ ] Check that metrics have units
- [ ] Ensure model names are correct (RedHatAI namespace)
- [ ] Update platform/version information
- [ ] Test presentation rendering (HTML/PDF)
- [ ] Proofread for typos
- [ ] Add speaker notes if needed
- [ ] Export to final format

## Contributing

When adding new presentations:

1. Use the same Marp frontmatter format
2. Follow the standard structure (5-7 sections)
3. Include a summary in this README
4. Add conversion instructions if using different tools
5. Reference source data files

## Support

For questions about:
- **Marp syntax:** https://marpit.marp.app/markdown
- **Test results:** See `docs/methodology/overview.md`
- **Methodology:** See `docs/methodology/testing-phases.md`
