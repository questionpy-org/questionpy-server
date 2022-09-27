"""
The runtime is the entry point of a QuestionPy worker and provides the low-level API between worker and
application server. It is responsible for setting up the sandbox, reading the QuestionPy package files
and it invokes the functions provided by the higher-level questionpy library.
"""
