# Hack / Utilities

Developer utilities and helper scripts.

## Scripts

### preview-site.sh

Preview the GitHub Pages site locally using Docker.

**Usage:**
```bash
# From project root
./hack/preview-site.sh

# With custom port
./hack/preview-site.sh --port 4001

# Help
./hack/preview-site.sh --help
```

**What it does:**
- Detects Docker or Podman
- Runs Jekyll in a container with GitHub Pages gems
- Serves the site at http://localhost:PORT
- Supports live reload for markdown changes

**Configuration:**
- Uses Jekyll config from `.github-pages/_config.yml`
- Builds site from project root
- Excludes `automation/` directory (Ansible/Jinja2 templates)

See [.github-pages/README.md](../.github-pages/README.md) for more details.

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
