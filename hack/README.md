# Hack / Utilities

Developer utilities and helper scripts.

## Scripts

### preview-site.sh

Preview the documentation site locally with MkDocs.

**Quick Start:**

```bash
# Start preview server (default port 8000)
./hack/preview-site.sh

# Custom port
./hack/preview-site.sh --port 4000

# Help
./hack/preview-site.sh --help
```

**First run:** installs MkDocs and Material from `requirements-docs.txt` if needed.

**Making changes:**

- Markdown edits reload automatically
- Changes to `mkdocs.yml` or theme overrides require a server restart

**Build (production check):**

```bash
python3 -m venv .venv-docs
source .venv-docs/bin/activate
pip install -r requirements-docs.txt
DISABLE_MKDOCS_2_WARNING=true mkdocs build --strict
```

Output is written to `site/`.

### strip_jekyll_for_mkdocs.py

One-time maintenance script that removes Jekyll front matter and Liquid `{% raw %}` wrappers from site markdown. Navigation is defined in `mkdocs.yml` at the repo root.

## Future Utilities

This directory is intended for:

- Development helper scripts
- Testing utilities
- Code generation tools
- Other developer conveniences

Not for:

- Production automation (use `automation/`)
- Platform setup (use `automation/platform-setup/`)
- Test execution (use `automation/test-execution/`)
