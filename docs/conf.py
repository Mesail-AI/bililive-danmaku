import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

project = "Bililive Danmaku"
author = "Ahsen17"
release = "0.1.0"
language = "zh_CN"

# Root URL of the published site, set by the Pages workflow so that
# cross-language links and Open Graph URLs stay absolute under the
# project subpath; empty for local preview served at "/".
root_url = os.environ.get("DOCS_ROOT_URL", "")

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinxcontrib.mermaid",
    "sphinxext.opengraph",
    "sphinx_tippy",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]

# docstring 为 Google 风格（Args/Raises 段），按源码顺序输出成员
napoleon_google_docstring = True
autodoc_member_order = "bysource"

html_theme = "shibuya"

html_theme_options = {
    "github_url": "https://github.com/Mesail-AI/bililive-danmaku",
}

ogp_site_url = root_url

myst_enable_extensions = ["colon_fence", "deflist", "tasklist"]

source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
exclude_patterns = ["_build"]

# Mermaid
mermaid_parallel = True
mermaid_parallel_processes = 2
