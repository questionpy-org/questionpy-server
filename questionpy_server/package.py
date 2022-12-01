from pathlib import Path
from typing import Optional, TYPE_CHECKING

from questionpy_common.manifest import Manifest

from questionpy_server.api.models import PackageInfo

if TYPE_CHECKING:
    from questionpy_server.collector.abc import BaseCollector


class Package:
    hash: str
    manifest: Manifest

    _collector: 'BaseCollector'
    _info: Optional[PackageInfo]
    _path: Optional[Path]

    def __init__(self, package_hash: str, manifest: Manifest, collector: 'BaseCollector', path: Path = None):
        self.hash = package_hash
        self.manifest = manifest

        self._collector = collector
        self._info = None
        self._path = path

    def __hash__(self) -> int:
        return hash(self.hash)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Package):
            return NotImplemented
        return self.hash == other.hash

    def get_info(self) -> PackageInfo:
        if not self._info:
            self._info = PackageInfo(**self.manifest.dict(), package_hash=self.hash)
        return self._info

    async def get_path(self) -> Path:
        if not (self._path and self._path.is_file()):
            self._path = await self._collector.get_path(self)
        return self._path
