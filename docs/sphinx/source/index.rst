.. QuestionPy Server documentation master file, created by
   sphinx-quickstart on Wed Jan 11 08:23:09 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to QuestionPy Server's documentation!
=============================================

For full documentation visit  `shpinx-doc.org <https://www.sphinx-doc.org>`_ .

Commands
####################################

* :code:`sphinx-apidoc -o source/ ../../questionpy_server` - Generate markup from python code.
* :code:`make html` - Build the documentation site.
* :code:`sphinx-apidoc -h` - Print help message and exit.

Project layout
####################################

.. code-block::

    source/
         index.rst   # The documentation homepage.
         conf.py     # The configuration file.
         reference/  # Folder containing code documentation
         ...         # Other markdown pages, images and other files.

.. toctree::
   :maxdepth: 2
   :caption: Contents:
   :name: mastertoc

   tutorial.rst
   reference/modules.rst
   about.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
