#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from hashlib import sha256
from io import BytesIO
from unittest.mock import Mock

import pytest
from aiohttp import FormData
from aiohttp.pytest_plugin import AiohttpClient
from aiohttp.test_utils import TestClient
from pydantic import TypeAdapter

from questionpy_server.collector.local_collector import LocalCollector
from questionpy_server.models import PackageVersionInfo, PackageVersionsInfo
from questionpy_server.utils.manifest import ComparableManifest
from questionpy_server.web.app import QPyServer
from tests.conftest import PACKAGE
from tests.test_data.factories import ManifestFactory


@pytest.mark.parametrize(
    "packages",
    [
        # No packages.
        {},
        # One package.
        {"ns1": {"0.1.0"}},
        # Two packages.
        {"ns1": {"0.1.0"}, "ns2": {"0.1.0"}},
        # Multiple versions.
        {"ns1": {"1.0.0", "0.0.1"}, "ns2": {"1.0.0", "0.1.0", "0.0.1"}},
        # Multiple versions, unsorted.
        {"ns1": {"0.0.1", "1.0.0"}, "ns2": {"0.1.0", "0.0.1", "1.0.0"}},
    ],
)
async def test_packages(qpy_server: QPyServer, aiohttp_client: AiohttpClient, packages: dict[str, set[str]]) -> None:
    async def add_package_version(server: QPyServer, manifest: ComparableManifest) -> None:
        package_hash = sha256((manifest.short_name + manifest.namespace + str(manifest.version)).encode()).hexdigest()
        await server.package_collection._indexer.register_package(package_hash, manifest, Mock(spec=LocalCollector))

    manifests: dict[str, dict[str, ComparableManifest]] = {}
    for namespace, versions in packages.items():
        for version in versions:
            expected_manifest = ManifestFactory.build(namespace=namespace, short_name=namespace, version=version)
            manifests.setdefault(namespace, {})[version] = expected_manifest
            await add_package_version(qpy_server, expected_manifest)

    client = await aiohttp_client(qpy_server.web_app)
    res = await client.request("GET", "/packages")

    # Assert that a valid list of PackageVersionsInfo is returned.
    assert res.status == 200
    data = await res.json()
    package_versions_infos: list[PackageVersionsInfo] = TypeAdapter(list[PackageVersionsInfo]).validate_python(data)

    assert len(package_versions_infos) == len(packages)

    actual_namespaces = []

    # Iterate over all actual packages.
    for package_versions_info in package_versions_infos:
        actual_package_info = package_versions_info.manifest
        actual_versions = [version.version for version in package_versions_info.versions]
        # Assert that each package version is available and in the correct order.
        assert actual_versions == sorted(packages[actual_package_info.namespace], reverse=True)
        # Assert that the actual package info is a subset of the manifest of the latest package version.
        actual_package_info_items = actual_package_info.model_dump().items()
        latest_manifest_items = manifests[actual_package_info.namespace][actual_versions[0]].model_dump().items()
        assert (
            actual_package_info_items <= latest_manifest_items
        ), "Actual package info was not derived from the latest package version."

        actual_namespaces.append(actual_package_info.namespace)

    # Assert that every expected package is returned.
    assert set(actual_namespaces) == packages.keys()


async def test_extract_info(client: TestClient) -> None:
    with PACKAGE.path.open("rb") as file:
        payload = FormData()
        payload.add_field("package", file)

        res = await client.request("POST", "/package-extract-info", data=payload)

    assert res.status == 201
    data = await res.json()
    PackageVersionInfo.model_validate(data)


async def test_extract_info_faulty(client: TestClient) -> None:
    # Request without package in payload.
    payload = FormData()
    payload.add_field("ignore", BytesIO())

    res = await client.request("POST", "/package-extract-info", data=payload)

    assert res.status == 400
    assert res.reason == "PackageMissingWithoutHashError"
