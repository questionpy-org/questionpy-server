from io import BytesIO
from pathlib import Path

from aiohttp import FormData
from aiohttp.test_utils import TestClient

from questionpy_common.elements import OptionsFormDefinition

from tests.conftest import get_file_hash


PACKAGE = Path('./tests/test_data/package.qpy')
PACKAGE_HASH = get_file_hash(PACKAGE)

METHOD = 'POST'
URL = f'packages/{PACKAGE_HASH}/options'

path = Path('./tests/test_data/question_state/')
QUESTION_STATE = (path / 'question_state.json').read_text()
QUESTION_STATE_REQUEST = (path / 'main.json').read_text()


async def test_optional_question_state(client: TestClient) -> None:
    # Even though the question state is optional, it
    # ...is still required to be valid JSON.
    res = await client.request(METHOD, URL, json="{not_valid!}")
    assert res.status == 400

    # ...should return the status code 404 with 'question_state_not_found: True'.
    res = await client.request(METHOD, URL, json=QUESTION_STATE_REQUEST)
    res_data = await res.json()
    assert res_data == {"package_not_found": True, "question_state_not_found": True}

    # ...should return the status code 200 if a package is provided and question_state_hash is empty.
    with PACKAGE.open('rb') as file:
        payload = FormData()
        payload.add_field('main', '{"question_state_hash": "", "context": null}')
        payload.add_field('package', file, filename=PACKAGE.name)

        res = await client.request(METHOD, URL, data=payload)

    assert res.status == 200
    res_data = await res.json()
    OptionsFormDefinition(**res_data)

    # ...should return 404 with 'question_state_not_found: True' if question_state_hash does not exist and is not empty.
    with PACKAGE.open('rb') as file:
        payload = FormData()
        payload.add_field('main', '{"question_state_hash": "not_valid", "context": null}')
        payload.add_field('package', file, filename=PACKAGE.name)

        res = await client.request(METHOD, URL, data=payload)

    assert res.status == 404
    res_data = await res.json()
    assert res_data == {"package_not_found": False, "question_state_not_found": True}


async def test_no_package(client: TestClient) -> None:
    payload = FormData()
    payload.add_field('main', QUESTION_STATE_REQUEST)
    payload.add_field('question_state', QUESTION_STATE)
    payload.add_field('ignore', BytesIO())  # Additional fields get ignored.

    res = await client.request(METHOD, URL, data=payload)

    assert res.status == 404
    res_data = await res.json()
    assert res_data == {"package_not_found": True, "question_state_not_found": False}


async def test_data_gets_cached(client: TestClient) -> None:
    with PACKAGE.open('rb') as file:
        payload = FormData()
        payload.add_field('main', QUESTION_STATE_REQUEST)
        payload.add_field('question_state', QUESTION_STATE)
        payload.add_field('package', file, filename=PACKAGE.name)

        res = await client.request(METHOD, URL, data=payload)

    assert res.status == 200
    reference = await res.json()
    OptionsFormDefinition(**reference)

    # Package and question state should be stored in cache.
    res = await client.request(METHOD, URL, json=QUESTION_STATE_REQUEST)
    assert res.status == 200
    res_data = await res.json()
    assert res_data == reference

    payload = FormData()
    payload.add_field('main', QUESTION_STATE_REQUEST)
    payload.add_field('ignore', BytesIO())  # Additional fields get ignored.
    res = await client.request(METHOD, URL, data=payload)
    assert res.status == 200
    res_data = await res.json()
    assert res_data == reference
