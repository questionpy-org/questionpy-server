from pathlib import Path
from typing import Optional

from .cache import FileLimitLRU


class PackageNotFound(Exception):
    pass


class PackageCollector:
    def __init__(self, local_dir: Optional[str], cache: FileLimitLRU):
        self._cache = cache
        self._local_dir: Optional[Path]

        if local_dir:
            self._local_dir = Path(local_dir)
            self._local_dir.mkdir(exist_ok=True)
        else:
            self._local_dir = None

    def contains(self, package_hash: str) -> bool:
        """
        Checks if package with the passed hash exists.

        :param package_hash: hash value of the package
        :return: path to the package
        """

        if self._local_dir and (self._local_dir / (package_hash + '.qpy')).is_file():
            return True
        return self._cache.contains(package_hash)

    def get(self, package_hash: str) -> Path:
        """
        Returns path of a package if it exists.

        TODO: Change search logic.

        :param package_hash: hash value of the package
        :return: path to the package
        """

        # check local dir
        if self._local_dir is not None:
            local_path = self._local_dir / (package_hash + '.qpy')
            if local_path.is_file():
                return local_path

        # check cache
        try:
            return self._cache.get(package_hash)
        except FileNotFoundError:
            pass

        # TODO: check repos

        raise PackageNotFound(f'Package with hash {package_hash} was not found.')
