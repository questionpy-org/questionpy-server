from io import BytesIO
from typing import List

from aiohttp import FormData
from aiohttp.test_utils import TestClient
from pydantic import parse_obj_as

from questionpy_server.api.models import PackageInfo
from tests.conftest import PACKAGES


async def test_post_package(client: TestClient) -> None:
    with PACKAGES[0].path.open('rb') as file:
        payload = FormData()
        payload.add_field('package', file)

        res = await client.request('POST', f'/packages/{PACKAGES[0].hash}', data=payload)

    assert res.status == 200
    data = await res.json()
    parse_obj_as(PackageInfo, data)


async def test_post_package_faulty(client: TestClient) -> None:
    # Package hash is not matching the package.
    with PACKAGES[0].path.open('rb') as file:
        payload = FormData()
        payload.add_field('package', file)

        res = await client.request('POST', f'/packages/{PACKAGES[0].hash + "x"}', data=payload)

    assert res.status == 400
    text = await res.text()
    assert text.startswith('Package hash does not match')

    # Request without package in payload.
    payload = FormData()
    payload.add_field('ignore', BytesIO())  # To force multipart/form-data.

    res = await client.request('POST', f'/packages/{PACKAGES[0].hash}', data=payload)
    assert res.status == 400
    text = await res.text()
    assert text == 'No package found in multipart/form-data'


async def test_packages(client: TestClient) -> None:
    res = await client.request('GET', '/packages')

    assert res.status == 200
    data = await res.json()
    parse_obj_as(List[PackageInfo], data)


async def test_extract_info(client: TestClient) -> None:
    with PACKAGES[0].path.open('rb') as file:
        payload = FormData()
        payload.add_field('package', file)

        res = await client.request('POST', '/package-extract-info', data=payload)

    assert res.status == 201
    data = await res.json()
    parse_obj_as(PackageInfo, data)


async def test_extract_info_faulty(client: TestClient) -> None:
    # Request without package in payload.
    payload = FormData()
    payload.add_field('ignore', BytesIO())

    res = await client.request('POST', '/package-extract-info', data=payload)

    assert res.status == 400
    text = await res.text()
    assert text == 'No package found in multipart/form-data'
