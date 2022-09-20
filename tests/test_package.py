from typing import List

from aiohttp.test_utils import TestClient
from pydantic import parse_obj_as

from questionpy_server.api.models import PackageInfo


async def test_package(client: TestClient) -> None:
    res = await client.request("GET", "/packages/test")

    assert res.status == 200
    data = await res.json()
    assert parse_obj_as(PackageInfo, data)


async def test_packages(client: TestClient) -> None:
    res = await client.request("GET", "/packages")

    assert res.status == 200
    data = await res.json()
    assert parse_obj_as(List[PackageInfo], data)
