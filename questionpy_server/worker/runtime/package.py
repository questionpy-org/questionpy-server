import json
import sys
from functools import cached_property
from importlib import import_module
from pathlib import Path
from types import ModuleType
from zipfile import ZipFile

from questionpy_common.manifest import Manifest
from questionpy_common.qtype import OptionsFormDefinition, BaseQuestionType


class QPyPackage(ZipFile):
    def __init__(self, path: Path):
        super().__init__(path, "r")
        self.path = path
        self.setup_import()

    @cached_property
    def manifest(self) -> Manifest:
        """Load QuestionPy manifest from package."""
        data = json.loads(self.read("qpy_manifest.json"))
        return Manifest.parse_obj(data)

    def setup_import(self) -> None:
        """Set up the import system that it is able to import the python code of the package."""
        sys.path = [str(self.path / "python"), str(self.path / "dependencies/site-packages"), *sys.path]


class QPyMainPackage(QPyPackage):
    def __init__(self, path: Path):
        """This is the main QPy package within this worker. Import and execute the entry point (module)."""
        super().__init__(path)
        self.main_module: ModuleType = import_module(self.manifest.entrypoint)
        if self.main_module.QuestionType.implementation is None:
            raise QuestionTypeImplementationNotFoundError(self.manifest.short_name)
        self.qtype_instance: BaseQuestionType = self.main_module.QuestionType.implementation(manifest=self.manifest)

    def get_options_form_definition(self) -> OptionsFormDefinition:
        return self.qtype_instance.get_options_form_definition()


class QuestionTypeImplementationNotFoundError(Exception):
    def __init__(self, package_name: str):
        super().__init__(f"The package {package_name} does not contain an implementation of QuestionType")
