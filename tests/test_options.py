from io import BytesIO
from pathlib import Path

from aiohttp import FormData
from aiohttp.test_utils import TestClient

from questionpy_common.elements import OptionsFormDefinition

from tests.conftest import get_file_hash


package = Path('./tests/test_data/package.qpy')
package_hash = get_file_hash(package)

method = 'POST'
url = f'packages/{package_hash}/options'

path = Path('./tests/test_data/question_state/')
question_state = (path / 'question_state.json').read_text()
question_state_request = (path / 'main.json').read_text()


async def test_optional_question_state(client: TestClient) -> None:
    # Even though the question state is optional, it
    # ...is still required to be valid JSON.
    res = await client.request(method, url, json="{not_valid!}")
    assert res.status == 400

    # ...should return the status code 404 with 'question_state_not_found: True'.
    res = await client.request(method, url, json=question_state_request)
    res_data = await res.json()
    assert res_data == {"package_not_found": True, "question_state_not_found": True}

    # ...should return the status code 200 if a package is provided and question_state_hash is empty.
    with package.open('rb') as file:
        payload = FormData()
        payload.add_field('main', '{"question_state_hash": "", "context": null}')
        payload.add_field('package', file, filename=package.name)

        res = await client.request(method, url, data=payload)

    assert res.status == 200
    res_data = await res.json()
    OptionsFormDefinition(**res_data)

    # ...should return 404 with 'question_state_not_found: True' if question_state_hash does not exist and is not empty.
    with package.open('rb') as file:
        payload = FormData()
        payload.add_field('main', '{"question_state_hash": "not_valid", "context": null}')
        payload.add_field('package', file, filename=package.name)

        res = await client.request(method, url, data=payload)

    assert res.status == 404
    res_data = await res.json()
    assert res_data == {"package_not_found": False, "question_state_not_found": True}


async def test_no_package(client: TestClient) -> None:
    payload = FormData()
    payload.add_field('main', question_state_request)
    payload.add_field('question_state', question_state)
    payload.add_field('ignore', BytesIO())  # Additional fields get ignored.

    res = await client.request(method, url, data=payload)

    assert res.status == 404
    res_data = await res.json()
    assert res_data == {"package_not_found": True, "question_state_not_found": False}


async def test_data_gets_cached(client: TestClient) -> None:
    with package.open('rb') as file:
        payload = FormData()
        payload.add_field('main', question_state_request)
        payload.add_field('question_state', question_state)
        payload.add_field('package', file, filename=package.name)

        res = await client.request(method, url, data=payload)

    assert res.status == 200
    reference = await res.json()
    OptionsFormDefinition(**reference)

    # Package and question state should be stored in cache.
    res = await client.request(method, url, json=question_state_request)
    assert res.status == 200
    res_data = await res.json()
    assert res_data == reference

    payload = FormData()
    payload.add_field('main', question_state_request)
    payload.add_field('ignore', BytesIO())  # Additional fields get ignored.
    res = await client.request(method, url, data=payload)
    assert res.status == 200
    res_data = await res.json()
    assert res_data == reference
