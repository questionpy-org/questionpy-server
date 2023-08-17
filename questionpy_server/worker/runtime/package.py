#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import json
import sys
from functools import cached_property
from importlib import import_module
from pathlib import Path
from types import ModuleType
from zipfile import ZipFile

from questionpy_common.manifest import Manifest
from questionpy_common.qtype import BaseQuestionType


class QPyPackage(ZipFile):
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


class QPyMainPackage(QPyPackage):
    def __init__(self, path: Path):
        """This is the main QPy package within this worker. Import and execute the entry point (module)."""
        super().__init__(path)
        self.main_module: ModuleType = import_module(f"{self.manifest.namespace}.{self.manifest.short_name}."
                                                     f"{self.manifest.entrypoint}")
        if self.main_module.QuestionType.implementation is None:
            raise QuestionTypeImplementationNotFoundError(self.manifest.short_name)
        self.qtype_instance: BaseQuestionType = self.main_module.QuestionType.implementation(manifest=self.manifest)


class QuestionTypeImplementationNotFoundError(Exception):
    def __init__(self, package_name: str):
        super().__init__(f"The package {package_name} does not contain an implementation of QuestionType")
