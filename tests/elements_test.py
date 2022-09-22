from typing import Type

import pytest
from pydantic import BaseModel
from pydantic_factories import ModelFactory

from questionpy_common.dev.factories import StaticTextElementFactory, TextInputElementFactory, CheckboxElementFactory, \
    CheckboxGroupElementFactory, OptionFactory, RadioGroupElementFactory, SelectElementFactory, HiddenElementFactory, \
    GroupElementFactory, FormElementFactory, FormSectionFactory, FormFactory
from questionpy_common.elements import StaticTextElement, TextInputElement, CheckboxElement, CheckboxGroupElement, \
    Option, RadioGroupElement, SelectElement, HiddenElement, GroupElement, FormElement, FormSection, Form


@pytest.mark.parametrize("factory, model", (
    [StaticTextElementFactory, StaticTextElement],
    [TextInputElementFactory, TextInputElement],
    [CheckboxElementFactory, CheckboxElement],
    [CheckboxGroupElementFactory, CheckboxGroupElement],
    [OptionFactory, Option],
    [RadioGroupElementFactory, RadioGroupElement],
    [SelectElementFactory, SelectElement],
    [HiddenElementFactory, HiddenElement],
    [GroupElementFactory, GroupElement],
    [FormElementFactory, FormElement],
    [FormSectionFactory, FormSection],
    [FormFactory, Form]
))
def test_factory_builds_valid_model(factory: ModelFactory, model: Type[BaseModel]) -> None:
    fake_model = factory.build()
    assert type(fake_model) == model  # pylint: disable=unidiomatic-typecheck


@pytest.mark.parametrize("factory, model", (
    [StaticTextElementFactory, StaticTextElement],
    [TextInputElementFactory, TextInputElement],
    [CheckboxElementFactory, CheckboxElement],
    [CheckboxGroupElementFactory, CheckboxGroupElement],
    [OptionFactory, Option],
    [RadioGroupElementFactory, RadioGroupElement],
    [SelectElementFactory, SelectElement],
    [HiddenElementFactory, HiddenElement],
    [GroupElementFactory, GroupElement],
    [FormElementFactory, FormElement],
    [FormSectionFactory, FormSection],
    [FormFactory, Form]
))
def test_ignore_additional_properties(factory: ModelFactory, model: Type[BaseModel]) -> None:
    data = factory.build().dict()
    created_model = model(**data, additional_properties='test')
    assert not hasattr(created_model, 'additional_properties')
