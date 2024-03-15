#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>


import pytest
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
