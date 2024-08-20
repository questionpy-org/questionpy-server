#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import pytest
from aiohttp.test_utils import TestClient

from tests.conftest import PACKAGE, TestPackageFactory, TestZipPackage


@pytest.fixture
def package(package_factory: TestPackageFactory) -> TestZipPackage:
    dir_package = package_factory.to_dir_package(PACKAGE)
    dir_package.inject_static_file("static/path/to/file.pdf", b"some data")
    return package_factory.to_zip_package(dir_package)


async def test_should_get_static_file(client: TestClient, package: TestZipPackage) -> None:
    with package.path.open("rb") as package_fd:
        res = await client.post(
            f"/packages/{package.hash}/file/local/package_1/static/path/to/file.pdf", data={"package": package_fd}
        )

    assert res.status == 200
    assert res.content_type == "application/pdf"
    assert await res.read() == b"some data"


async def test_should_return_not_implemented_when_not_main_package(client: TestClient, package: TestZipPackage) -> None:
    with package.path.open("rb") as package_fd:
        res = await client.post(
            f"/packages/{package.hash}/file/some_other_ns/and_short_name/static/path/to/file.pdf",
            data={"package": package_fd},
        )

    assert res.status == 501
    assert "Static file retrieval from non-main packages is not supported yet." in await res.text()


async def test_should_return_not_found_when_file_does_not_exist(client: TestClient, package: TestZipPackage) -> None:
    with package.path.open("rb") as package_fd:
        res = await client.post(
            f"/packages/{package.hash}/file/local/package_1/static/wrong/path/to/file.pdf", data={"package": package_fd}
        )

    assert res.status == 404
