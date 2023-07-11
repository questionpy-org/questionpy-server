#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

"""
The runtime is the entry point of a QuestionPy worker and provides the low-level API between worker and
application server. It is responsible for setting up the sandbox, reading the QuestionPy package files
and it invokes the functions provided by the higher-level questionpy library.
"""
