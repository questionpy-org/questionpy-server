#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import asyncio
from asyncio import to_thread
from contextlib import ExitStack
from pathlib import Path
from typing import IO, Annotated, Any
from zipfile import BadZipFile, ZipFile

from pydantic import PlainSerializer, PlainValidator, ValidationError
from semver import Version

from questionpy_common.constants import DIST_DIR, MANIFEST_FILENAME, MAX_MANIFEST_SIZE
from questionpy_common.error import QPyBaseError
from questionpy_common.manifest import Manifest
from questionpy_common.package_location import (
    FunctionPackageLocation,
    PackageLocation,
    ZipPackageLocation,
)


class ManifestError(QPyBaseError):
    pass


def _read_manifest_from_file_sync(manifest_file: IO[bytes]) -> Manifest:
    try:
        buffer = manifest_file.read(MAX_MANIFEST_SIZE + 1)

        if len(buffer) > MAX_MANIFEST_SIZE:
            msg = f"Manifest is too large. Maximum size is {MAX_MANIFEST_SIZE.human_readable()}."
            raise ManifestError(msg)

        return Manifest.model_validate_json(buffer)
    except ValidationError as e:
        msg = f"Manifest is invalid: {e}"
        raise ManifestError(msg) from e


def _read_manifest_from_path_sync(manifest_path: Path) -> Manifest:
    try:
        with manifest_path.open("rb") as file:
            return _read_manifest_from_file_sync(file)
    except FileNotFoundError as e:
        msg = "Manifest is missing."
        raise ManifestError(msg) from e


def _read_manifest_from_zip_sync(package: Path | ZipFile) -> Manifest:
    try:
        with ExitStack() as stack:
            if isinstance(package, Path):
                package = stack.enter_context(ZipFile(package))

            manifest_file = stack.enter_context(package.open(f"{DIST_DIR}/{MANIFEST_FILENAME}"))

            return _read_manifest_from_file_sync(manifest_file)
    except BadZipFile as e:
        msg = f"Could not read manifest from package: {e}"
        raise ManifestError(msg) from e
    except KeyError as e:
        # ZipFile.open raises a KeyError if the file does not exist.
        msg = "Manifest is missing."
        raise ManifestError(msg) from e


async def read_manifest_from_zip(package: Path | ZipFile) -> Manifest:
    """Reads the manifest from a zipped package.

    Raises:
        ManifestError: if the manifest could not be read, it is too large or is invalid
    """
    return await asyncio.to_thread(_read_manifest_from_zip_sync, package)


async def read_manifest_from_location(location: PackageLocation) -> Manifest:
    if isinstance(location, ZipPackageLocation):
        return await read_manifest_from_zip(location.path)
    if isinstance(location, FunctionPackageLocation):
        return Manifest(**location.manifest.model_dump())

    manifest_path = location.path / MANIFEST_FILENAME
    return await to_thread(_read_manifest_from_path_sync, manifest_path)


def _maybe_parse_version(value: Any) -> Any:
    if isinstance(value, Version):
        return value
    if isinstance(value, str):
        return Version.parse(value)
    return value


type ParsableSemverVersion = Annotated[
    Version, PlainValidator(_maybe_parse_version, json_schema_input_type=str), PlainSerializer(Version.__str__)
]
