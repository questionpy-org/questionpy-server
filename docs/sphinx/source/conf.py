# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'QuestionPy Server'
copyright = '2023, innoCampus'
author = 'innoCampus'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'recommonmark',
    'sphinx_markdown_tables'
]

templates_path = ['_templates']
exclude_patterns = []

language = 'en'

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_material'
html_theme_options = {
    'nav_title': 'QuestionPy',
    'globaltoc_depth': 2,
    'color_primary': 'indigo',
    'color_accent': 'amber'
}
html_sidebars = {
    "**": ["globaltoc.html", "localtoc.html", "searchbox.html"]
}

html_static_path = ['_static']

