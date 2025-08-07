#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import json
from io import BytesIO
from unittest.mock import patch

import pytest
from aiohttp import FormData
from aiohttp.test_utils import TestClient
from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import BaseModel

from questionpy_common.elements import (
    CheckboxElement,
    FormSection,
    GroupElement,
    HiddenElement,
    Option,
    OptionsFormDefinition,
    RadioGroupElement,
    SelectElement,
    StaticTextElement,
    TextInputElement,
)
from questionpy_server.collector import PackageCollection
from questionpy_server.hash import calculate_hash
from questionpy_server.models import RequestErrorCode
from tests.conftest import package_dir, test_data_path

from .factories import (
    CheckboxElementFactory,
    FormSectionFactory,
    GroupElementFactory,
    HiddenElementFactory,
    OptionFactory,
    OptionsFormDefinitionFactory,
    RadioGroupElementFactory,
    SelectElementFactory,
    StaticTextElementFactory,
    TextInputElementFactory,
)

_PACKAGE = package_dir / "package_1.qpy"
_PACKAGE_HASH = calculate_hash(_PACKAGE)

_METHOD = "POST"
_URL = f"packages/{_PACKAGE_HASH}/options"

_QUESTION_STATE = (test_data_path / "question_state" / "question_state.json").read_text()
_REQUEST_MAIN = json.dumps({"context": "tests"})


async def test_should_validate_main_body_when_question_state_is_not_given(client: TestClient) -> None:
    with patch.object(PackageCollection, "get"):
        # Even though the question state is optional, the body is still required to be valid JSON.
        res = await client.request(_METHOD, _URL, data=b"{not_valid!}", headers={"Content-Type": "application/json"})
        assert res.status == 422
        res_data = await res.json()
        assert res_data == {
            "error_code": RequestErrorCode.INVALID_REQUEST.value,
            "temporary": False,
            "reason": "Invalid JSON body",
        }


async def test_no_package(client: TestClient) -> None:
    payload = FormData()
    payload.add_field("main", _REQUEST_MAIN)
    payload.add_field("question_state", _QUESTION_STATE)
    payload.add_field("ignore", BytesIO())  # Additional fields get ignored.

    res = await client.request(_METHOD, _URL, data=payload)

    assert res.status == 404
    res_data = await res.json()
    assert {"error_code": RequestErrorCode.PACKAGE_NOT_FOUND.value, "temporary": False}.items() <= res_data.items()


async def test_data_gets_cached(client: TestClient) -> None:
    with _PACKAGE.open("rb") as file:
        payload = FormData()
        payload.add_field("main", _REQUEST_MAIN)
        payload.add_field("question_state", _QUESTION_STATE)
        payload.add_field("package", file, filename=_PACKAGE.name)

        res = await client.request(_METHOD, _URL, data=payload)

    assert res.status == 200
    reference = await res.json()
    OptionsFormDefinition(**reference)

    payload = FormData()
    payload.add_field("main", _REQUEST_MAIN)
    payload.add_field("question_state", _QUESTION_STATE)
    payload.add_field("ignore", BytesIO())  # Additional fields get ignored.
    res = await client.request(_METHOD, _URL, data=payload)
    assert res.status == 200
    res_data = await res.json()
    assert res_data == reference


@pytest.mark.parametrize(
    ("factory", "model"),
    [
        (StaticTextElementFactory, StaticTextElement),
        (TextInputElementFactory, TextInputElement),
        (CheckboxElementFactory, CheckboxElement),
        (OptionFactory, Option),
        (RadioGroupElementFactory, RadioGroupElement),
        (SelectElementFactory, SelectElement),
        (HiddenElementFactory, HiddenElement),
        (GroupElementFactory, GroupElement),
        (FormSectionFactory, FormSection),
        (OptionsFormDefinitionFactory, OptionsFormDefinition),
    ],
)
def test_factory_builds_valid_model(factory: ModelFactory, model: type[BaseModel]) -> None:
    fake_model = factory.build()
    assert isinstance(fake_model, model)


@pytest.mark.parametrize(
    ("factory", "model"),
    [
        (StaticTextElementFactory, StaticTextElement),
        (TextInputElementFactory, TextInputElement),
        (CheckboxElementFactory, CheckboxElement),
        (OptionFactory, Option),
        (RadioGroupElementFactory, RadioGroupElement),
        (SelectElementFactory, SelectElement),
        (HiddenElementFactory, HiddenElement),
        (GroupElementFactory, GroupElement),
        (FormSectionFactory, FormSection),
        (OptionsFormDefinitionFactory, OptionsFormDefinition),
    ],
)
def test_ignore_additional_properties(factory: ModelFactory, model: type[BaseModel]) -> None:
    data = factory.build().model_dump()
    created_model = model(**data, additional_property="test")
    assert not hasattr(created_model, "additional_property")
