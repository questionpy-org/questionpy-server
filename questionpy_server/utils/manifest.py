#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import asyncio
from pathlib import Path
from typing import Annotated
from zipfile import BadZipFile, ZipFile

from pydantic import PlainSerializer, PlainValidator, ValidationError
from semver import VersionInfo as _Version

from questionpy_common.constants import DIST_DIR, MANIFEST_FILENAME, MAX_MANIFEST_SIZE
from questionpy_common.error import QPyBaseError
from questionpy_common.manifest import Manifest

type SemVer = Annotated[_Version, PlainValidator(_Version.parse), PlainSerializer(_Version.__str__)]


class ComparableManifest(Manifest):
    version: SemVer  # type: ignore[assignment]


class ManifestError(QPyBaseError):
    pass


def _read_manifest_sync(package_path: Path) -> ComparableManifest:
    try:
        with ZipFile(package_path) as zip_file, zip_file.open(f"{DIST_DIR}/{MANIFEST_FILENAME}") as manifest_file:
            buffer = manifest_file.read(MAX_MANIFEST_SIZE + 1)

            if len(buffer) > MAX_MANIFEST_SIZE:
                msg = f"Manifest is too large. Maximal size is {MAX_MANIFEST_SIZE.human_readable()}."
                raise ManifestError(msg)

            return ComparableManifest.model_validate_json(buffer)
    except BadZipFile as e:
        msg = f"Could not read manifest from package: {e}"
        raise ManifestError(msg) from e
    except KeyError as e:
        # ZipFile.open raises a KeyError if the file does not exist.
        msg = "Manifest is missing."
        raise ManifestError(msg) from e
    except ValidationError as e:
        msg = f"Manifest is invalid: {e}"
        raise ManifestError(msg) from e


async def read_manifest(package_path: Path) -> ComparableManifest:
    """Reads the manifest from a zipped package.

    Raises:
        ManifestError: if the manifest could not be read, is too large, or is invalid
    """
    return await asyncio.to_thread(_read_manifest_sync, package_path)
