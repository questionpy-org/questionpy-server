#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import random
from abc import ABC
from collections.abc import Callable
from typing import Any

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory as _ModelFactory

import questionpy_common.elements as _elements
from questionpy_common import TranslatableString


class _BaseFactory(_ModelFactory, ABC):
    __is_base_factory__ = True

    @classmethod
    def get_provider_map(cls) -> dict[Any, Callable[[], Any]]:
        provider_map = super().get_provider_map()
        provider_map[TranslatableString] = provider_map[str]
        return provider_map


class StaticTextElementFactory(_BaseFactory):
    __model__ = _elements.StaticTextElement


class TextInputElementFactory(_BaseFactory):
    __model__ = _elements.TextInputElement


class CheckboxElementFactory(_BaseFactory):
    __model__ = _elements.CheckboxElement


class OptionFactory(_BaseFactory):
    __model__ = _elements.Option


class RadioGroupElementFactory(_BaseFactory):
    __model__ = _elements.RadioGroupElement


class SelectElementFactory(_BaseFactory):
    __model__ = _elements.SelectElement


class HiddenElementFactory(_BaseFactory):
    __model__ = _elements.HiddenElement


def _one_of_each_leaf_element() -> list[_elements.FormElement]:
    # This used to work without a custom factory method, but doesn't anymore.
    # Maybe the same bug as https://github.com/litestar-org/polyfactory/issues/317?
    one_of_each = [
        factory.build()
        for factory in (
            StaticTextElementFactory,
            TextInputElementFactory,
            CheckboxElementFactory,
            SelectElementFactory,
            HiddenElementFactory,
        )
    ]
    random.shuffle(one_of_each)
    return one_of_each


class GroupElementFactory(_BaseFactory):
    __model__ = _elements.GroupElement

    elements = Use(_one_of_each_leaf_element)


class FormSectionFactory(_BaseFactory):
    __model__ = _elements.FormSection

    elements = Use(_one_of_each_leaf_element)


class OptionsFormDefinitionFactory(_BaseFactory):
    __model__ = _elements.OptionsFormDefinition

    general = Use(_one_of_each_leaf_element)
    sections = Use(lambda: [FormSectionFactory.build()])
