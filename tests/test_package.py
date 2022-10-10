from io import BytesIO
from pathlib import Path
from typing import List

from aiohttp import FormData
from aiohttp.test_utils import TestClient
from pydantic import parse_obj_as

from questionpy_server.api.models import PackageInfo
from tests.conftest import get_file_hash


async def test_get_package(client: TestClient) -> None:
    res = await client.request('GET', '/packages/test')

    assert res.status == 200
    data = await res.json()
    parse_obj_as(PackageInfo, data)


async def test_post_package(client: TestClient) -> None:
    package = Path('./tests/test_data/package.qpy')
    package_hash = get_file_hash(package)

    with package.open('rb') as file:
        payload = FormData()
        payload.add_field('package', file, filename=package.name)

        res = await client.request('POST', f'/packages/{package_hash}', data=payload)

    assert res.status == 200
    data = await res.json()
    parse_obj_as(PackageInfo, data)


async def test_post_package_faulty(client: TestClient) -> None:
    package = Path('./tests/test_data/package.qpy')
    package_hash = get_file_hash(package) + 'x'

    # Package hash is not matching the package.
    with package.open('rb') as file:
        payload = FormData()
        payload.add_field('package', file, filename=package.name)

        res = await client.request('POST', f'/packages/{package_hash}', data=payload)

    assert res.status == 400
    text = await res.text()
    assert text.startswith('Package hash does not match')

    # Request without package in payload.
    payload = FormData()
    payload.add_field('ignore', BytesIO())  # To force multipart/form-data.

    res = await client.request('POST', f'/packages/{package_hash}', data=payload)
    assert res.status == 400
    text = await res.text()
    assert text == 'No package found in multipart/form-data'


async def test_packages(client: TestClient) -> None:
    res = await client.request('GET', '/packages')

    assert res.status == 200
    data = await res.json()
    parse_obj_as(List[PackageInfo], data)
