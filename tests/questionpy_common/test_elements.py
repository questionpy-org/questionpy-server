#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from io import BytesIO

import pytest
from aiohttp import FormData
from aiohttp.test_utils import TestClient
from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import BaseModel

from questionpy_common.dev.factories import (
    CheckboxElementFactory,
    CheckboxGroupElementFactory,
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
from questionpy_common.elements import (
    CanHaveConditions,
    CheckboxElement,
    CheckboxGroupElement,
    FormSection,
    GroupElement,
    HiddenElement,
    Option,
    OptionsFormDefinition,
    RadioGroupElement,
    SelectElement,
    StaticTextElement,
    TextInputElement,
    is_form_element,
)
from tests.conftest import get_file_hash, package_dir, test_data_path

PACKAGE = package_dir / "package_1.qpy"
PACKAGE_HASH = get_file_hash(PACKAGE)

METHOD = "POST"
URL = f"packages/{PACKAGE_HASH}/options"

path = test_data_path / "question_state"
QUESTION_STATE = (path / "question_state.json").read_text()
QUESTION_STATE_REQUEST = (path / "main.json").read_text()


async def test_optional_question_state(client: TestClient) -> None:
    # Even though the question state is optional, the body is still required to be valid JSON.
    res = await client.request(METHOD, URL, data=b"{not_valid!}", headers={"Content-Type": "application/json"})
    assert res.status == 400


async def test_no_package(client: TestClient) -> None:
    payload = FormData()
    payload.add_field("main", QUESTION_STATE_REQUEST)
    payload.add_field("question_state", QUESTION_STATE)
    payload.add_field("ignore", BytesIO())  # Additional fields get ignored.

    res = await client.request(METHOD, URL, data=payload)

    assert res.status == 404
    res_data = await res.json()
    assert res_data == {"what": "PACKAGE"}


async def test_data_gets_cached(client: TestClient) -> None:
    with PACKAGE.open("rb") as file:
        payload = FormData()
        payload.add_field("main", QUESTION_STATE_REQUEST)
        payload.add_field("question_state", QUESTION_STATE)
        payload.add_field("package", file, filename=PACKAGE.name)

        res = await client.request(METHOD, URL, data=payload)

    assert res.status == 200
    reference = await res.json()
    OptionsFormDefinition(**reference)

    payload = FormData()
    payload.add_field("main", QUESTION_STATE_REQUEST)
    payload.add_field("question_state", QUESTION_STATE)
    payload.add_field("ignore", BytesIO())  # Additional fields get ignored.
    res = await client.request(METHOD, URL, data=payload)
    assert res.status == 200
    res_data = await res.json()
    assert res_data == reference


@pytest.mark.parametrize(
    ("factory", "model"),
    [
        (StaticTextElementFactory, StaticTextElement),
        (TextInputElementFactory, TextInputElement),
        (CheckboxElementFactory, CheckboxElement),
        (CheckboxGroupElementFactory, CheckboxGroupElement),
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
        (CheckboxGroupElementFactory, CheckboxGroupElement),
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


@pytest.mark.parametrize(
    "factory",
    [
        StaticTextElementFactory,
        TextInputElementFactory,
        CheckboxElementFactory,
        CheckboxGroupElementFactory,
        RadioGroupElementFactory,
        SelectElementFactory,
        HiddenElementFactory,
        GroupElementFactory,
    ],
)
def test_is_form_element_should_return_true(factory: ModelFactory) -> None:
    assert is_form_element(factory.build())


@pytest.mark.parametrize(
    "instance",
    [
        object(),
        CanHaveConditions(),
        Option(label="", value=""),
        FormSection(name="", header="", elements=[]),
        OptionsFormDefinition(),
    ],
)
def test_is_form_element_should_return_false(instance: object) -> None:
    assert not is_form_element(instance)
