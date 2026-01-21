# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os
import sys
from datetime import datetime
from pathlib import Path


# -- Path setup --------------------------------------------------------------
# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.


BASE_ROOT = Path(__file__).parent.parent.resolve()
major_paths = (
    os.fspath(BASE_ROOT / proj)
    for proj in (
        "manager",
        "orchestrator",
        "router",
        "shell",
    )
)
sys.path = [*major_paths, *sys.path]

# -- Project information -----------------------------------------------------

project = "Director4"
copyright = f"2020-{datetime.now().year}, Sysadmins at TJ CSL"
author = "Sysadmins at TJ CSL"

# TODO: enable sphinxcontrib_django after all dependencies are merged into one Pipfile
# django_settings = "director.settings"


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.extlinks",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "myst_parser",
    # "sphinxcontrib_django"
]

add_function_parentheses = False

# Automatically generate stub pages when using the .. autosummary directive
autosummary_generate = True

# controls whether functions documented by the autofunction directive
# appear with their full module names
add_module_names = False

# napoleon settings
napoleon_numpy_docstring = False  # force google
napoleon_include_special_with_doc = False

napoleon_custom_sections = [
    ("Special", "params_style"),
]

templates_path = ["_templates"]
exclude_patterns = []

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master/", None),
    "django": (
        "https://docs.djangoproject.com/en/stable/",
        "https://docs.djangoproject.com/en/stable/_objects/",
    ),
}

extlinks = {
    "issue": ("https://github.com/tjcsl/director4/issues/%s", "issue %s"),
    "pr": ("https://github.com/tjcsl/director4/pull/%s", "pr #%s"),
}
# warn hardcoded links
extlinks_detect_hardcoded_links = True

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#

html_theme = "furo"

# use |br| for linebreak
rst_prolog = """
.. |br| raw:: html

  <br/>
"""

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

html_theme_options = {
    "source_repository": "https://github.com/tjcsl/director4/",
    "source_branch": "main",
    "source_directory": "docs/source/",
    "light_logo": "logo-full-black.svg",
    "dark_logo": "logo-full-white.svg",
    "sidebar_hide_name": True,
    "light_css_variables": {
        "color-content-foreground": "#000000",
        "color-background-primary": "#ffffff",
        "color-background-border": "#ffffff",
        "color-sidebar-background": "#f8f9fb",
        "color-brand-content": "#1c00e3",
        "color-brand-primary": "#192bd0",
        "color-link": "#c93434",
        "color-link--hover": "#5b0000",
        "color-inline-code-background": "#f6f6f6;",
        "color-foreground-secondary": "#000",
    },
    "dark_css_variables": {
        "color-content-foreground": "#ffffffd9",
        "color-background-primary": "#131416",
        "color-background-border": "#303335",
        "color-sidebar-background": "#1a1c1e",
        "color-brand-content": "#2196f3",
        "color-brand-primary": "#007fff",
        "color-link": "#51ba86",
        "color-link--hover": "#9cefc6",
        "color-inline-code-background": "#262626",
        "color-foreground-secondary": "#ffffffd9",
    },
}
html_title = "Director4"

# This specifies any additional css files that will override the theme's
html_css_files = []
