# Hack / Utilities

Developer utilities and helper scripts.

## Scripts

### preview-site.sh

Preview the GitHub Pages site locally using Docker.

**Quick Start:**
```bash
# Start preview server
./hack/preview-site.sh --port 4001

# Stop preview server
./hack/preview-site.sh --stop

# Help
./hack/preview-site.sh --help
```

**Features:**
- Auto-detects Docker or Podman
- Installs GitHub Pages gems automatically
- Serves site with live reload at http://localhost:PORT
- Clean start/stop commands

**First Run:**
- Takes 2-3 minutes to install gems
- Subsequent runs are instant

**Making Changes:**
- Markdown files reload automatically
- CSS/layout changes reload automatically
- Config changes require restart

**Troubleshooting:**
```bash
# Port conflict
./hack/preview-site.sh --port 8080

# Clean restart
./hack/preview-site.sh --stop
./hack/preview-site.sh --port 4001

# Hard refresh browser (Cmd+Shift+R / Ctrl+Shift+R)
```

**See** [.github-pages/README.md](../.github-pages/README.md) for complete documentation, troubleshooting, and manual Docker usage.

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
