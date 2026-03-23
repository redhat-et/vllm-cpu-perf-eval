# GitHub Pages Configuration

This directory contains the Jekyll configuration for generating GitHub Pages documentation.

## Structure

```
.github-pages/
├── _config.yml    # Jekyll configuration
├── Gemfile        # Ruby dependencies (github-pages gem)
└── README.md      # This file

(project root)/
└── index.md       # Landing page for GitHub Pages site
```

## Local Preview

The preview script (`hack/preview-site.sh`) provides an easy way to test the GitHub Pages site locally before deploying.

### Quick Start

```bash
# Start the preview server (auto-detects Docker/Podman)
./hack/preview-site.sh --port 4001

# Force a specific container runtime
CONTAINER_RUNTIME=podman ./hack/preview-site.sh --port 4001

# Stop the preview server
./hack/preview-site.sh --stop
```

Then open **<http://localhost:4001>** in your browser.

### Preview Script Features

- **Auto-detects** Docker or Podman (or force via `CONTAINER_RUNTIME` environment variable)
- **Installs** GitHub Pages gems automatically (first run takes 2-3 minutes)
- **Live reload** - Changes to markdown/CSS reload automatically
- **Custom port** - Use `--port` to avoid conflicts (default: 4000)
- **Easy stop** - Use `--stop` to cleanly shut down the server

### Container Runtime Selection

By default, the script auto-detects Docker or Podman. To force a specific runtime:

```bash
# Use Podman
export CONTAINER_RUNTIME=podman
./hack/preview-site.sh --port 4001

# Or inline
CONTAINER_RUNTIME=podman ./hack/preview-site.sh --port 4001

# Use Docker explicitly
CONTAINER_RUNTIME=docker ./hack/preview-site.sh --port 4001
```

### First Run

The first time you run the preview, it will:

1. Pull the `jekyll/jekyll:latest` Docker image (~500MB)
2. Install the `github-pages` gem and all dependencies (~2-3 minutes)
3. Build the site from your markdown files
4. Start a local web server

**Subsequent runs are much faster** as gems are cached.

### Making Changes

The server watches for changes and automatically rebuilds:

**Markdown changes** (docs, tests, models):
- Edit any `.md` file
- Save the file
- Browser auto-refreshes (live reload)

**Configuration changes** (`_config.yml`):
- Stop the server: `./hack/preview-site.sh --stop`
- Restart: `./hack/preview-site.sh --port 4001`
- Configuration changes require a restart

**CSS/Layout changes**:
- Changes to `assets/css/custom.css` reload automatically
- Changes to `_layouts/` or `_includes/` reload automatically
- Use hard refresh (Cmd+Shift+R / Ctrl+Shift+R) to clear browser cache

### Troubleshooting

**Port already in use:**
```bash
# Use a different port
./hack/preview-site.sh --port 8080
```

**Container won't start:**
```bash
# Stop any existing containers
./hack/preview-site.sh --stop

# Or manually
docker stop jekyll-preview
docker rm jekyll-preview
```

**Changes not showing:**
```bash
# Hard refresh in browser
# Mac: Cmd+Shift+R
# Windows/Linux: Ctrl+Shift+R

# Or restart the server
./hack/preview-site.sh --stop
./hack/preview-site.sh --port 4001
```

**Gems installation fails:**
```bash
# Clear the bundle cache
rm -rf .github-pages/vendor/
./hack/preview-site.sh --port 4001
```

### Manual Docker Usage

If you prefer to run Docker commands directly:

```bash
# From project root
docker run --rm -it \
  -v "$PWD:/srv/jekyll:Z" \
  -p 4001:4000 \
  -e JEKYLL_ENV=development \
  -w /srv/jekyll/.github-pages \
  jekyll/jekyll:latest \
  sh -c "bundle install --path vendor/bundle && bundle exec jekyll serve --config _config.yml --watch --force_polling --host 0.0.0.0"
```

Then open <http://localhost:4001> in your browser.

## Configuration Details

### Jekyll Source Directory

The site is built from the **project root** (`source: ..` in `_config.yml`), which allows Jekyll to access:
- `index.md` - Landing page
- `docs/` - Documentation
- `models/` - Model information
- `tests/` - Test suite documentation
- `README.md` - Repository README

### Excluded Directories

**IMPORTANT**: The `automation/` directory is excluded because it contains Ansible playbooks with Jinja2 templates that conflict with Jekyll's Liquid templating engine.

```yaml
exclude:
  - automation/**/*  # Contains Jinja2 templates
  - results
  - utils
  - hack
  - .github-pages
```

## GitHub Pages Deployment

### Option 1: Deploy from `github-pages` Branch (Current)

You're currently on the `github-pages` branch. To deploy:

1. Push to the `github-pages` branch:
   ```bash
   git push origin github-pages
   ```

2. Configure repository Settings → Pages:
   - Source: `Deploy from a branch`
   - Branch: `github-pages`
   - Folder: `/ (root)`

### Option 2: Deploy from `main` Branch `/docs` Folder

Alternatively, you could publish from the `docs/` folder on the main branch:

1. Move `.github-pages/` contents to `docs/`:
   ```bash
   # Move Jekyll configuration and dependencies
   mv .github-pages/_config.yml docs/
   mv .github-pages/Gemfile docs/

   # Move Jekyll layouts and includes
   mv .github-pages/_layouts docs/
   mv .github-pages/_includes docs/

   # Move custom assets
   mv .github-pages/assets docs/

   # Move or copy the landing page
   mv index.md docs/
   ```

2. Update `_config.yml` source path:
   ```yaml
   # Change from:
   source: ..
   # To:
   source: .
   ```

3. Configure GitHub Pages:
   - Go to repository Settings → Pages
   - Source: `Deploy from a branch`
   - Branch: `main`
   - Folder: `/docs`

## Theme

The site uses the **Cayman** theme via `remote_theme`:

```yaml
remote_theme: pages-themes/cayman@v0.2.0
```

This is compatible with GitHub Pages and doesn't require the theme gem to be installed locally.

## Advanced Troubleshooting

### Port Already in Use

If port 4000 is already in use (e.g., by LiteLLM), use a different port:

```bash
./hack/preview-site.sh --port 4001
```

### Liquid Syntax Errors

If you see errors about Liquid syntax in Ansible files, ensure `automation/` is in the exclude list in `_config.yml`.

### Theme Not Found

The site uses `remote_theme` which is fetched from GitHub. Ensure you have internet connectivity and the `jekyll-remote-theme` plugin is listed in `_config.yml`.

## Initial Setup

The first time you run the preview, it will:
1. Download the Jekyll Docker image (~500MB)
2. Install the `github-pages` gem and dependencies (~2-3 minutes)
3. Build the site
4. Start the server

Subsequent runs will be much faster as gems are cached in the container volume.
