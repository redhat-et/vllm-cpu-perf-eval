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

### Using the Preview Script (Recommended)

```bash
# From project root
./hack/preview-site.sh --port 4001

# Or from hack/ directory
cd hack
./preview-site.sh --port 4001
```

### Using Docker Directly

```bash
# From .github-pages/ directory
cd .github-pages
docker run --rm -it \
  -v "$PWD/..:/srv/jekyll:Z" \
  -p 4001:4000 \
  -w /srv/jekyll/.github-pages \
  jekyll/jekyll:latest \
  sh -c "bundle install && bundle exec jekyll serve --config _config.yml --host 0.0.0.0"
```

Then open http://localhost:4001 in your browser.

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
   mv .github-pages/_config.yml docs/
   mv .github-pages/Gemfile docs/
   ```

2. Update `_config.yml` to use `docs/` as source

3. Configure GitHub Pages to use `main` branch `/docs` folder

## Theme

The site uses the **Cayman** theme via `remote_theme`:

```yaml
remote_theme: pages-themes/cayman@v0.2.0
```

This is compatible with GitHub Pages and doesn't require the theme gem to be installed locally.

## Troubleshooting

### Port Already in Use

If port 4000 is already in use (e.g., by LiteLLM), use a different port:

```bash
./hack/preview-site.sh --port 4001
```

### Liquid Syntax Errors

If you see errors about Liquid syntax in Ansible files, ensure `automation/` is in the exclude list in `_config.yml`.

### Theme Not Found

The site uses `remote_theme` which is fetched from GitHub. Ensure you have internet connectivity and the `jekyll-remote-theme` plugin is listed in `_config.yml`.

## First Run

The first time you run the preview, it will:
1. Download the Jekyll Docker image (~500MB)
2. Install the `github-pages` gem and dependencies (~2-3 minutes)
3. Build the site
4. Start the server

Subsequent runs will be much faster as gems are cached in the container volume.
