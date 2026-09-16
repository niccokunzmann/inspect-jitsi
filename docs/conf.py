# inspect-jitsi documentation build configuration file
import datetime
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))  # update docs from source for livehtml

from inspect_jitsi.version import __version__  # noqa: E402

# The CLI reference (docs/reference/cli.rst) includes this file rather than
# documenting the command line interface by hand - regenerated on every
# build straight from the `inspect-jitsi` command's own `--help` output,
# the same way sphinx.ext.apidoc regenerates reference/api/ from docstrings.
_CLI_REFERENCE = HERE / "reference" / "_generated" / "cli.md"
_CLI_REFERENCE.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(  # noqa: S603
    [
        sys.executable,
        "-m",
        "typer",
        "inspect_jitsi.cli",
        "utils",
        "docs",
        "--name",
        "inspect-jitsi",
        "--output",
        str(_CLI_REFERENCE),
    ],
    check=True,
    cwd=ROOT,
)
# Demote headings by one level - the generated file starts at `#`, but it's
# included under this page's own top-level heading, not standalone.
_CLI_REFERENCE.write_text(re.sub(r"(?m)^(#+)", r"#\1", _CLI_REFERENCE.read_text()))

# The changelog (docs/reference/changelog.rst) includes this copy of the
# repository's own CHANGES.md rather than duplicating it by hand - headings
# demoted by one level for the same reason as the CLI reference above.
_CHANGELOG = HERE / "reference" / "_generated" / "changelog.md"
_CHANGELOG.parent.mkdir(parents=True, exist_ok=True)
_CHANGELOG.write_text(re.sub(r"(?m)^(#+)", r"#\1", (ROOT / "CHANGES.md").read_text()))

extensions = [
    "myst_parser",
    "notfound.extension",
    "sphinx.ext.apidoc",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",  # must be loaded after sphinx.ext.napoleon
    "sphinx_copybutton",
    "sphinx_design",
    "sphinx_reredirects",
]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
master_doc = "index"
# False positive: myst_parser checks every title in a document that
# includes MyST content, including the host RST document's own top-level
# title - which is correctly at "H1", not the "H2" it expects nested
# content to start at.
suppress_warnings = ["myst.header"]

project = "inspect-jitsi"
this_year = datetime.date.today().year  # noqa: DTZ011
copyright = f"{this_year}, Nicco Kunzmann"  # noqa: A001
release = __version__
version = release

# -- Options for HTML output -------------------------------------------------

templates_path = []
exclude_patterns = [
    "reference/api/modules.rst",
    # Included by reference/cli.rst and reference/changelog.rst respectively,
    # not standalone documents.
    "reference/_generated/cli.md",
    "reference/_generated/changelog.md",
]
html_theme = "pydata_sphinx_theme"
html_theme_options = {
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/niccokunzmann/inspect-jitsi",
            "icon": "fa-brands fa-square-github",
            "type": "fontawesome",
            "attributes": {"target": "_blank", "rel": "noopener me"},
        },
    ],
    "footer_end": ["theme-version", "sphinx-version"],
    "logo": {"text": "inspect-jitsi"},
    "navigation_with_keys": True,
    "show_nav_level": 2,
    "show_toc_level": 2,
    "secondary_sidebar_items": ["edit-this-page", "page-toc", "sourcelink"],
    "use_edit_page_button": True,
}
html_context = {
    "github_user": "niccokunzmann",
    "github_repo": "inspect-jitsi",
    "github_version": "main",
    "doc_path": "docs",
}
html_static_path = ["_static"]
pygments_style = "sphinx"
smartquotes_action = "De"

# -- linkcheck builder configuration ----------------------------------
linkcheck_ignore = [
    # Illustrative placeholder domain used throughout docstrings/examples
    # (e.g. "https://meet.example.com/SomeRoomName") - never meant to resolve.
    r"https://meet\.example\.com.*",
    # Where `make livehtml` serves locally - nothing is listening there
    # during a plain build/linkcheck run.
    r"http://127\.0\.0\.1:8000",
]
linkcheck_anchors = True
linkcheck_timeout = 5
linkcheck_retries = 1

# -- sphinx.ext.apidoc options -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/apidoc.html
apidoc_modules = [
    {
        "path": "../inspect_jitsi",
        "destination": "reference/api",
        "exclude_patterns": [
            "**/test*",
        ],
        "separate_modules": True,
        "automodule_options": {
            "members",
            "show-inheritance",
            "undoc-members",
            "private-members",
            "special-members",
        },
    }
]
autoclass_content = "both"


def _deduplicate_apidoc_package_pages(app) -> None:  # noqa: ARG001
    """Add `:no-index:` to every apidoc-generated *package* page's automodule.

    Every `__init__.py` in this project re-exports its subpackage's public
    API via `__all__` (e.g. `inspect_jitsi.JitsiConference` re-exports
    `inspect_jitsi.xmpp.conference.JitsiConference`) - autodoc honors
    `__all__` regardless of where a name is actually defined, so the package
    page and the defining submodule's page would otherwise both claim to be
    *the* documentation for the same object, which Sphinx rejects as a
    duplicate object description. The submodule page (generated separately
    by `separate_modules`) stays the canonical, indexed one; the package
    page still renders the same content for readability, just without
    competing for the cross-reference target.
    """
    api_dir = HERE / "reference" / "api"
    for rst_file in api_dir.glob("*.rst"):
        text = rst_file.read_text()
        if not re.match(r"^\S+ package\n=+\n", text):
            continue  # a "module" page (a leaf .py) - nothing to deduplicate
        patched = re.sub(
            r"(\.\. automodule:: \S+\n(?:   :\S+:\n)*)",
            lambda m: (
                m.group(1)
                if ":no-index:" in m.group(1)
                else m.group(1) + "   :no-index:\n"
            ),
            text,
        )
        if patched != text:
            rst_file.write_text(patched)


def setup(app) -> None:
    # Must run after sphinx.ext.apidoc's own `builder-inited` handler
    # (default priority 500) regenerates reference/api/ - see
    # `_deduplicate_apidoc_package_pages`.
    app.connect("builder-inited", _deduplicate_apidoc_package_pages, priority=900)


# -- sphinx.ext.autodoc options -------------------------------------------------
# private-members/special-members: every function is documented, including
# module-private helpers and dunder methods - docstrings cross-reference
# each other by fully qualified name, which needs a documented target to
# resolve, private/dunder methods included.
autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "undoc-members": True,
    "private-members": True,
    "special-members": True,
}

# -- sphinx.ext.intersphinx configuration ----------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master/", None),
}

# -- sphinx.ext.napoleon configuration ----------------------------------
napoleon_use_param = True
napoleon_google_docstring = True
napoleon_attr_annotations = True

# -- sphinx_copybutton configuration ----------------------------------
copybutton_exclude = ".linenos, .gp, .go"

# -- sphinx_reredirects configuration ----------------------------------
redirects = {
    "install": "installation.html",
    "usage": "how-to/index.html",
    "cli": "reference/cli.html",
    "development": "development/index.html",
}

man_pages = [
    (
        "index",
        "inspect-jitsi",
        "inspect-jitsi Documentation",
        ["Nicco Kunzmann"],
        1,
    )
]

htmlhelp_basename = "inspect-jitsidoc"
