#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from abc import abstractmethod
from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol

from questionpy_common.manifest import PackageFile

if TYPE_CHECKING:
    from questionpy_common.api.qtype import QuestionTypeInterface


class BasePackageInterface(Protocol):
    @abstractmethod
    def get_static_files(self) -> Mapping[str, PackageFile]:
        pass


class LibraryPackageInterface(BasePackageInterface, Protocol):
    pass


type QPyPackageInterface = LibraryPackageInterface | QuestionTypeInterface
