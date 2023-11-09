#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import inspect
import json
import sys
import zipfile
from functools import cached_property
from importlib import import_module
from importlib.abc import Traversable
from pathlib import Path
from types import ModuleType
from typing import cast
from zipfile import ZipFile

from questionpy_common.environment import Environment, Package, set_qpy_environment
from questionpy_common.manifest import Manifest
from questionpy_common.qtype import BaseQuestionType


class QPyPackage(ZipFile, Package):
    def __init__(self, path: Path):
        super().__init__(path, "r")
        self.path = path
        self.setup_import()

    @cached_property
    def manifest(self) -> Manifest:
        """Load QuestionPy manifest from package."""
        data = json.loads(self.read("qpy_manifest.json"))
        return Manifest.model_validate(data)

    def setup_import(self) -> None:
        """Set up the import system that it is able to import the python code of the package."""
        sys.path = [str(self.path / "python"), str(self.path / "dependencies/site-packages"), *sys.path]

    def get_path(self, path: str) -> Traversable:
        # Intuitively, a path beginning with '/' should be absolute within the package, but ZipFile behaves differently.
        path = path.lstrip("/")

        # According to the docs, zipfile.Path implements Traversable.
        return cast(Traversable, zipfile.Path(self, path))


class QPyMainPackage(QPyPackage):
    def __init__(self, path: Path):
        """This is the main QPy package within this worker. Import and execute the entry point (module)."""
        super().__init__(path)
        self._main_module: ModuleType
        if self.manifest.entrypoint:
            self._main_module = import_module(f"{self.manifest.namespace}.{self.manifest.short_name}."
                                              f"{self.manifest.entrypoint}")
        else:
            self._main_module = import_module(f"{self.manifest.namespace}.{self.manifest.short_name}")

        if not hasattr(self._main_module, "init") or not callable(self._main_module.init):
            raise NoInitFunctionError(self._main_module)

    def init(self, env: Environment) -> BaseQuestionType:
        set_qpy_environment(env)

        signature = inspect.signature(self._main_module.init)
        if len(signature.parameters) == 0:
            return self._main_module.init()

        return self._main_module.init(env)


class NoInitFunctionError(Exception):
    def __init__(self, module: ModuleType) -> None:
        super().__init__(f"The module '{module.__name__}' contains no 'init' function")


class QuestionTypeImplementationNotFoundError(Exception):
    def __init__(self, package_name: str):
        super().__init__(f"The package {package_name} does not contain an implementation of QuestionType")
