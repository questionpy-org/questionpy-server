#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from io import BytesIO
from pathlib import Path
from posixpath import dirname

from aiohttp import FormData
from aiohttp.test_utils import TestClient
from questionpy_common.elements import OptionsFormDefinition

from tests.conftest import get_file_hash

PACKAGE = Path(dirname(__file__)) / "test_data" / "package" / "package_1.qpy"
PACKAGE_HASH = get_file_hash(PACKAGE)

METHOD = 'POST'
URL = f'packages/{PACKAGE_HASH}/options'

path = Path(dirname(__file__)) / "test_data" / "question_state"
QUESTION_STATE = (path / 'question_state.json').read_text()
QUESTION_STATE_REQUEST = (path / 'main.json').read_text()


async def test_optional_question_state(client: TestClient) -> None:
    # Even though the question state is optional, the body is still required to be valid JSON.
    res = await client.request(METHOD, URL, data=b"{not_valid!}", headers={"Content-Type": "application/json"})
    assert res.status == 400


async def test_no_package(client: TestClient) -> None:
    payload = FormData()
    payload.add_field('main', QUESTION_STATE_REQUEST)
    payload.add_field('question_state', QUESTION_STATE)
    payload.add_field('ignore', BytesIO())  # Additional fields get ignored.

    res = await client.request(METHOD, URL, data=payload)

    assert res.status == 404
    res_data = await res.json()
    assert res_data == {"what": "PACKAGE"}


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

    payload = FormData()
    payload.add_field('main', QUESTION_STATE_REQUEST)
    payload.add_field('question_state', QUESTION_STATE)
    payload.add_field('ignore', BytesIO())  # Additional fields get ignored.
    res = await client.request(METHOD, URL, data=payload)
    assert res.status == 200
    res_data = await res.json()
    assert res_data == reference
