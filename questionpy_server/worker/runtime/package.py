#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import inspect
import logging
import sys
from abc import ABC, abstractmethod
from functools import cached_property
from importlib import import_module, resources
from importlib.resources.abc import Traversable
from pathlib import Path
from types import ModuleType
from zipfile import ZipFile

from questionpy_common.api.package import QPyPackageInterface
from questionpy_common.constants import DIST_DIR, MANIFEST_FILENAME
from questionpy_common.environment import Environment, Package, PackageState
from questionpy_common.manifest import Manifest
from questionpy_server.worker.runtime.package_location import (
    DirPackageLocation,
    FunctionPackageLocation,
    PackageLocation,
    ZipPackageLocation,
)

_log = logging.getLogger(__name__)


class NoInitFunctionError(Exception):
    def __init__(self, module: ModuleType, init_function_name: str) -> None:
        super().__init__(f"The module '{module.__name__}' contains no '{init_function_name}' function")


class ImportablePackage(ABC, Package):
    """Adds methods needed for loading and running the package to :class:`Package`."""

    def __init__(self) -> None:
        self._state = PackageState.PREPARED

    @abstractmethod
    def setup_imports(self) -> None:
        """Modifies ``sys.path`` to include the package's python code."""

    def init(self, env: Environment) -> QPyPackageInterface:
        """Imports the package's entrypoint and executes its ``init`` function.

        :meth:`setup_imports` should be called beforehand to allow the import.
        """
        main_module: ModuleType
        if self.manifest.entrypoint:
            main_module = import_module(
                f"{self.manifest.namespace}.{self.manifest.short_name}.{self.manifest.entrypoint}"
            )
        else:
            main_module = import_module(f"{self.manifest.namespace}.{self.manifest.short_name}")

        self._state = PackageState.LOADED

        if not hasattr(main_module, "init") or not callable(main_module.init):
            raise NoInitFunctionError(main_module, "init")

        signature = inspect.signature(main_module.init)
        package_interface = main_module.init(*(self, env)[: len(signature.parameters)])
        self._state = PackageState.INITIALIZED
        return package_interface

    @property
    def state(self) -> PackageState:
        return self._state


class UnpackingZipBasedPackage(ImportablePackage):
    """A zip-formatted QuestionPy package which will be unpacked into a temporary directory before use."""

    def __init__(self, location: ZipPackageLocation, worker_home: Path) -> None:
        super().__init__()
        self.path = location.path
        self.hash = location.hash

        self._dir_package = self._unpack(worker_home / "packages" / self.hash)

    def _unpack(self, to_dir: Path) -> "DirBasedPackage":
        to_dir.mkdir(parents=True)
        with ZipFile(self.path) as zip_file:
            dist_prefix = f"{DIST_DIR}/"
            for info in zip_file.infolist():
                if info.filename.startswith(dist_prefix):
                    zip_file.extract(info, to_dir)

        _log.debug("Unpacked package '%s' to '%s'.", self.path, to_dir)

        return DirBasedPackage(to_dir / DIST_DIR)

    def setup_imports(self) -> None:
        self._dir_package.setup_imports()

    @property
    def manifest(self) -> Manifest:
        return self._dir_package.manifest

    def get_path(self, path: str) -> Traversable:
        return self._dir_package.get_path(path)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.path})"

    __str__ = __repr__


class DirBasedPackage(ImportablePackage):
    """A package's dist directory to be used directly."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    @cached_property
    def manifest(self) -> Manifest:
        """Load QuestionPy manifest from package."""
        manifest_path = self.path / MANIFEST_FILENAME
        return Manifest.model_validate_json(manifest_path.read_bytes())

    def get_path(self, path: str) -> Traversable:
        return self.path.joinpath(path)

    def setup_imports(self) -> None:
        for new_path in (
            str(self.path / "dependencies" / "site-packages"),
            str(self.path / "python"),
        ):
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
        super().__init__()
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

    def init(self, env: Environment) -> QPyPackageInterface:
        main_module = import_module(self.module_name)

        self._state = PackageState.LOADED

        init_function = getattr(main_module, self.function_name, None)
        if not init_function or not callable(init_function):
            raise NoInitFunctionError(main_module, self.function_name)

        signature = inspect.signature(init_function)
        package_interface = init_function(*(self, env)[: len(signature.parameters)])
        self._state = PackageState.INITIALIZED
        return package_interface

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.module_name, self.function_name})"

    __str__ = __repr__


def load_package(location: PackageLocation, worker_home: Path) -> ImportablePackage:
    """Turn a pure :class:`PackageLocation` into an :class:`ImportablePackage` which can be imported and executed."""
    if isinstance(location, ZipPackageLocation):
        return UnpackingZipBasedPackage(location, worker_home)
    if isinstance(location, DirPackageLocation):
        return DirBasedPackage(location.path)
    if isinstance(location, FunctionPackageLocation):
        return FunctionBasedPackage(location.module_name, location.function_name, location.manifest)

    msg = f"Unknown package location: '{location}'"
    raise ValueError(msg)
