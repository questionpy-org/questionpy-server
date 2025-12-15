#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import inspect
import logging
import sys
from abc import ABC, abstractmethod
from importlib import import_module, resources
from importlib.resources.abc import Traversable
from pathlib import Path
from types import ModuleType
from zipfile import ZipFile

from questionpy_common import PackageNamespaceAndShortName
from questionpy_common.api.package import QPyPackageInterface
from questionpy_common.constants import DIST_DIR, MANIFEST_FILENAME
from questionpy_common.environment import (
    Environment,
    Package,
    PackageNotInitializedError,
    PackageNotLoadedError,
    PackageState,
)
from questionpy_common.manifest import DistStaticQPyDependency, Manifest
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

    def __init__(self, manifest: Manifest) -> None:
        self._manifest = manifest

        self._main_module: ModuleType | None = None
        self._interface: QPyPackageInterface | None = None
        self._dependencies: dict[PackageNamespaceAndShortName, ImportablePackage] = {}

    @property
    def manifest(self) -> Manifest:
        return self._manifest

    @property
    def state(self) -> PackageState:
        if self._interface is not None:
            return PackageState.INITIALIZED
        if self._main_module is not None:
            return PackageState.LOADED
        return PackageState.OPENED

    @property
    def dependencies(self) -> dict[PackageNamespaceAndShortName, "ImportablePackage"]:
        return self._dependencies

    @property
    def interface(self) -> QPyPackageInterface:
        if not self._interface:
            raise PackageNotInitializedError
        return self._interface

    @abstractmethod
    def load(self) -> None:
        """Import the package's main module."""

    @abstractmethod
    def init(self, env: Environment) -> None:
        """Executes the package's `init` function.

        `load` must have been called beforehand.
        """

    @abstractmethod
    def resolve_static_dependency(self, nssn: PackageNamespaceAndShortName) -> PackageLocation:
        pass


class RegularPackage(ImportablePackage):
    """Implementation using a package dist directory, which might be run directly or extracted from a zip package."""

    def __init__(self, path: Path, manifest: Manifest) -> None:
        super().__init__(manifest)
        self.path = path

    def get_path(self, path: str) -> Traversable:
        return self.path.joinpath(path)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.path})"

    __str__ = __repr__

    def resolve_static_dependency(self, nssn: PackageNamespaceAndShortName) -> PackageLocation:
        dep = next(
            (
                dep
                for dep in self.manifest.dependencies.qpy
                if isinstance(dep, DistStaticQPyDependency)
                and dep.namespace == nssn.namespace
                and dep.short_name == nssn.short_name
                for dep in self.manifest.dependencies.qpy
            ),
            None,
        )
        if not dep:
            msg = f"Package '{self.manifest.nssn}' does not provide static dependency '{nssn}'."
            raise RuntimeError(msg)

        dep_dist_path = (
            self.path / "dependencies" / "qpy" / f"{dep.namespace}-{dep.short_name}-{dep.version}" / DIST_DIR
        )
        if not dep_dist_path.exists():
            msg = (
                f"Package '{self.manifest.nssn}' lists static dependency '{nssn}', but '{dep_dist_path}' is not "
                f"present."
            )
            raise RuntimeError(msg)

        return DirPackageLocation(dep_dist_path)

    def load(self) -> None:
        for new_path in (
            str(self.path / "dependencies" / "site-packages"),
            str(self.path / "python"),
        ):
            if new_path not in sys.path:
                sys.path.insert(0, new_path)

        if self.manifest.entrypoint:
            self._main_module = import_module(
                f"{self.manifest.namespace}.{self.manifest.short_name}.{self.manifest.entrypoint}"
            )
        else:
            self._main_module = import_module(f"{self.manifest.namespace}.{self.manifest.short_name}")

    def init(self, env: Environment) -> None:
        if not self._main_module:
            raise PackageNotLoadedError

        if not hasattr(self._main_module, "init"):
            raise NoInitFunctionError(self._main_module, "init")

        signature = inspect.signature(self._main_module.init)
        self._interface = self._main_module.init(*(self, env)[: len(signature.parameters)])


class FunctionBasedPackage(ImportablePackage):
    """A package consisting only of its init function. Intended mostly for unit tests.

    ``sys.path`` must already be set up so that :attr:`module_name` is resolvable.
    """

    def __init__(self, module_name: str, function_name: str, manifest: Manifest) -> None:
        super().__init__(manifest)
        self.module_name = module_name
        self.function_name = function_name

    def get_path(self, path: str) -> Traversable:
        return resources.files(self.module_name).joinpath(path)

    def load(self) -> None:
        self._main_module = import_module(self.module_name)

    def init(self, env: Environment) -> None:
        if not self._main_module:
            raise PackageNotLoadedError

        init_function = getattr(self._main_module, self.function_name, None)
        if not init_function:
            raise NoInitFunctionError(self._main_module, self.function_name)

        signature = inspect.signature(init_function)
        self._interface = init_function(*(self, env)[: len(signature.parameters)])

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.module_name, self.function_name})"

    __str__ = __repr__

    def resolve_static_dependency(self, nssn: PackageNamespaceAndShortName) -> PackageLocation:
        raise NotImplementedError


def _package_dir(worker_home: Path, manifest: Manifest) -> Path:
    slug = f"{manifest.namespace}-{manifest.short_name}-{manifest.version}"
    package_dir = worker_home / "packages" / slug
    if package_dir.exists():
        msg = f"A package with slug '{slug}' has already been loaded or is in the process of being loaded."
        raise RuntimeError(msg)
    return package_dir


def open_qpy_package(location: PackageLocation, worker_home: Path) -> ImportablePackage:
    """Turn a pure :class:`PackageLocation` into an :class:`ImportablePackage` which can be imported and executed."""
    if isinstance(location, FunctionPackageLocation):
        return FunctionBasedPackage(location.module_name, location.function_name, location.manifest)

    if isinstance(location, ZipPackageLocation):
        # Unpack the dist part of the ZIP into the package dir.
        with ZipFile(location.path) as zip_file:
            manifest = Manifest.model_validate_json(zip_file.read(f"{DIST_DIR}/{MANIFEST_FILENAME}"))
            package_dir = _package_dir(worker_home, manifest)
            package_dir.mkdir(parents=True)

            dist_prefix = f"{DIST_DIR}/"
            for info in zip_file.infolist():
                if info.filename.startswith(dist_prefix):
                    zip_file.extract(info, package_dir)

        _log.debug("Unpacked package '%s' to '%s'.", location.path, package_dir)

        return RegularPackage(package_dir / DIST_DIR, manifest)

    if isinstance(location, DirPackageLocation):
        manifest = Manifest.model_validate_json((location.path / MANIFEST_FILENAME).read_text())
        package_dir = _package_dir(worker_home, manifest)
        package_dir.parent.mkdir(parents=True, exist_ok=True)
        package_dir.symlink_to(location.path)
        return RegularPackage(package_dir, manifest)

    msg = f"Unknown package location: '{location}'"
    raise ValueError(msg)
