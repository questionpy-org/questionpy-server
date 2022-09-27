from io import StringIO
from typing import Tuple

from aiohttp import FormData
from aiohttp.test_utils import TestClient

from questionpy_common.elements import OptionsFormDefinition

from questionpy_server.api.models import QuestionStateHash
from questionpy_server.factories.question_state import QuestionStateHashFactory
from tests.conftest import Packages, Package


def route(package_hash: str) -> str:
    return f'/packages/{package_hash}/options'


PKG = Packages(route)


def get_method_url_data(dataitem: Package) -> Tuple[str, str, str]:
    question_state_hash_model: QuestionStateHash = QuestionStateHashFactory.build()
    question_state_hash_model.question_state_hash = dataitem.question_state_hash
    question_state_hash_json = question_state_hash_model.json()

    return 'POST', dataitem.route, question_state_hash_json


async def test_no_package(client: TestClient) -> None:
    method, url, data = get_method_url_data(PKG.no_package)

    res = await client.request(method, url, json=data)
    assert res.status == 404

    res_data = await res.json()
    assert res_data == {"package_not_found": True, "question_state_not_found": False}

    payload = FormData()
    payload.add_field('main', data)
    payload.add_field('package', StringIO())

    res = await client.request(method, url, data=payload)

    assert res.status == 200

    res_data = await res.json()
    OptionsFormDefinition(**res_data)


async def test_no_question_state(client: TestClient) -> None:
    method, url, data = get_method_url_data(PKG.no_question_state)

    res = await client.request(method, url, json=data)
    assert res.status == 404

    res_data = await res.json()
    assert res_data == {"package_not_found": False, "question_state_not_found": True}

    payload = FormData()
    payload.add_field('main', data)
    payload.add_field('question_state', "{'test': 'hallo'}",
                      content_type='text/plain')  # To force multipart/form-data.

    res = await client.request(method, url, data=payload)

    assert res.status == 200

    res_data = await res.json()
    OptionsFormDefinition(**res_data)


async def test_no_package_and_no_question_state(client: TestClient) -> None:
    method, url, data = get_method_url_data(PKG.nothing)

    res = await client.request(method, url, json=data)
    assert res.status == 404

    res_data = await res.json()
    assert res_data == {"package_not_found": True, "question_state_not_found": True}

    # Sending everything is tested in test_complete - therefore we can skip it here.


async def test_complete(client: TestClient) -> None:
    method, url, data = get_method_url_data(PKG.complete)

    payload = FormData()
    payload.add_field('main', data)
    payload.add_field('package', StringIO())
    payload.add_field('question_state', "{'test': 'hallo'}")

    res = await client.request(method, url, data=payload)

    assert res.status == 200

    res_data = await res.json()
    OptionsFormDefinition(**res_data)
