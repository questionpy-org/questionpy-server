import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal, TypeAlias

from pydantic import Field

from questionpy_common.environment import PackageInitFunction
from questionpy_common.manifest import Manifest


@dataclass
class ZipPackageLocation:
    """The path to a 'regular', zip-formatted QuestionPy package."""

    path: Path
    kind: Literal["zip"] = field(default="zip", init=False)

    def __str__(self) -> str:
        return str(self.path)


@dataclass
class DirPackageLocation:
    """A package's source directory to be loaded directly."""

    path: Path

    manifest: Manifest
    """The manifest to use, probably loaded from the package config.

    Since the source format of a manifest is YAML and we don't want the runtime to depend on PyYAML, the server should
    load the manifest and pass it into the worker here.
    """

    kind: Literal["dir"] = field(default="dir", init=False)

    def __str__(self) -> str:
        return str(self.path)


@dataclass
class FunctionPackageLocation:
    """A package consisting only of its init function. Intended mostly for unit tests.

    No change is made to the ``sys.path`` of the worker, so the module must already be resolvable.
    """

    module_name: str
    """The module name to load.

    Example:
        ``tests.webserver.test_page``
    """

    function_name: str

    manifest: Manifest
    """Since a function doesn't have an associated manifest file, you can specify a manifest here.

    If ``None``, a dummy manifest will be generated.
    """

    kind: Literal["module"] = field(default="module", init=False)

    def __init__(self, module_name: str, function_name: str = "init", manifest: Manifest | None = None) -> None:
        if not manifest:
            manifest = Manifest(
                short_name=function_name,
                namespace=module_name.replace(".", "_"),
                version="0.1.0-debug",
                api_version="0.1",
                author="Debug Modulovitch",
            )

        self.module_name = module_name
        self.function_name = function_name
        self.manifest = manifest

    def __str__(self) -> str:
        return f"{self.module_name}:{self.function_name}"

    @classmethod
    def from_function(
        cls, function: PackageInitFunction, manifest: Manifest | None = None
    ) -> "FunctionPackageLocation":
        """Get the module and name of the function and create a :class:`FunctionPackageLocation` targeting it."""
        if not hasattr(function, "__module__") or not hasattr(function, "__name__"):
            raise ValueError(f"Callable '{function}' is missing __module__ or __name__ attribute")

        if not hasattr(sys.modules[function.__module__], function.__name__):
            raise ValueError(
                f"Function '{function.__name__}' must be a global in module '{function.__module__}' to be "
                f"used as a package."
            )

        return cls(function.__module__, function.__name__, manifest)


PackageLocation: TypeAlias = Annotated[
    ZipPackageLocation | DirPackageLocation | FunctionPackageLocation, Field(discriminator="kind")
]
"""Identifies how to load a package.

'Loading' a package here is synonymous with creating a :class:`ImportablePackage` instance.
:class:`PackageLocation`\\ s differ from :class:`ImportablePackage`\\ s in that they are side effect-free.
For instance, in the case of a zip package, the zip file is only opened within the worker, when the
:class:`ZipBasedPackage` is created.
"""
