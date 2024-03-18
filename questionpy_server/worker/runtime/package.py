#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import inspect
import json
import sys
import zipfile
from abc import ABC, abstractmethod
from functools import cached_property
from importlib import import_module, resources
from importlib.abc import Traversable
from pathlib import Path
from types import ModuleType
from typing import cast
from zipfile import ZipFile

from questionpy_common.api.qtype import BaseQuestionType
from questionpy_common.constants import MANIFEST_FILENAME
from questionpy_common.environment import Environment, Package, set_qpy_environment
from questionpy_common.manifest import Manifest
from questionpy_server.worker.runtime.package_location import (
    DirPackageLocation,
    FunctionPackageLocation,
    PackageLocation,
    ZipPackageLocation,
)


class NoInitFunctionError(Exception):
    def __init__(self, module: ModuleType) -> None:
        super().__init__(f"The module '{module.__name__}' contains no 'init' function")


class ImportablePackage(ABC, Package):
    """Adds methods needed for loading and running the package to :class:`Package`."""

    @abstractmethod
    def setup_imports(self) -> None:
        """Modifies ``sys.path`` to include the package's python code."""

    def init_as_main(self, env: Environment) -> BaseQuestionType:
        """Imports the package's entrypoint and executes its ``init`` function.

        :meth:`setup_imports` should be called beforehand to allow the import.
        """
        set_qpy_environment(env)

        main_module: ModuleType
        if self.manifest.entrypoint:
            main_module = import_module(
                f"{self.manifest.namespace}.{self.manifest.short_name}.{self.manifest.entrypoint}"
            )
        else:
            main_module = import_module(f"{self.manifest.namespace}.{self.manifest.short_name}")

        if not hasattr(main_module, "init") or not callable(main_module.init):
            raise NoInitFunctionError(main_module)

        signature = inspect.signature(main_module.init)
        if len(signature.parameters) == 0:
            return main_module.init()

        return main_module.init(env)


class ZipBasedPackage(ZipFile, ImportablePackage):
    """A 'regular', zip-formatted QuestionPy package."""

    def __init__(self, path: Path):
        super().__init__(path, "r")
        self.path = path

    @cached_property
    def manifest(self) -> Manifest:
        """Load QuestionPy manifest from package."""
        data = json.loads(self.read(MANIFEST_FILENAME))
        return Manifest.model_validate(data)

    def get_path(self, path: str) -> Traversable:
        # Intuitively, a path beginning with '/' should be absolute within the package, but ZipFile behaves differently.
        path = path.lstrip("/")

        # According to the docs, zipfile.Path implements Traversable.
        return cast(Traversable, zipfile.Path(self, path))

    def setup_imports(self) -> None:
        for new_path in str(self.path / "dependencies/site-packages"), str(self.path / "python"):
            if new_path not in sys.path:
                sys.path.insert(0, new_path)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.path})"

    __str__ = __repr__


class DirBasedPackage(ImportablePackage):
    """A package's source directory to be used directly."""

    def __init__(self, path: Path, manifest: Manifest) -> None:
        self.path = path
        self._manifest = manifest

    @property
    def manifest(self) -> Manifest:
        return self._manifest

    def get_path(self, path: str) -> Traversable:
        return self.path.joinpath(path)

    def setup_imports(self) -> None:
        new_path = str(self.path / "python")
        if new_path not in sys.path:
            sys.path.insert(0, new_path)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.path})"

    __str__ = __repr__


class FunctionBasedPackage(ImportablePackage):
    """A package consisting only of its init function. Intended mostly for unit tests.

    ``sys.path`` must already be set up so that :attr:`module_name` is resolvable.
    """

    def __init__(self, module_name: str, function_name: str, manifest: Manifest) -> None:
        self.module_name = module_name
        self.function_name = function_name
        self._manifest = manifest

    @property
    def manifest(self) -> Manifest:
        return self._manifest

    def get_path(self, path: str) -> Traversable:
        return resources.files(self.module_name).joinpath(path)

    def setup_imports(self) -> None:
        # Nothing to do.
        pass

    def init_as_main(self, env: Environment) -> BaseQuestionType:
        set_qpy_environment(env)

        main_module = import_module(self.module_name)
        init_function = getattr(main_module, self.function_name, None)
        if not init_function or not callable(init_function):
            raise NoInitFunctionError(main_module)

        signature = inspect.signature(init_function)
        if len(signature.parameters) == 0:
            return init_function()

        return init_function(env)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.module_name, self.function_name})"

    __str__ = __repr__


def load_package(location: PackageLocation) -> ImportablePackage:
    """Turn a pure :class:`PackageLocation` into an :class:`ImportablePackage` which can be imported and executed."""
    if isinstance(location, ZipPackageLocation):
        return ZipBasedPackage(location.path)
    if isinstance(location, DirPackageLocation):
        return DirBasedPackage(location.path, location.manifest)
    if isinstance(location, FunctionPackageLocation):
        return FunctionBasedPackage(location.module_name, location.function_name, location.manifest)

    msg = f"Unknown package location: '{location}'"
    raise ValueError(msg)
