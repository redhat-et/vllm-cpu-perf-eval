"""Map MkDocs edit links to real repository paths (symlink-aware)."""

from __future__ import annotations


def on_page_context(context, page, config, nav):
    if not config.repo_url:
        return

    src = page.file.src_uri
    repo_path = "documentation/index.md" if src == "index.md" else src
    page.edit_url = f"{config.repo_url.rstrip('/')}/edit/main/{repo_path}"
