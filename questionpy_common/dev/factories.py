#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import random

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory as _ModelFactory

import questionpy_common.elements as _elements


class StaticTextElementFactory(_ModelFactory):
    __model__ = _elements.StaticTextElement


class TextInputElementFactory(_ModelFactory):
    __model__ = _elements.TextInputElement


class CheckboxElementFactory(_ModelFactory):
    __model__ = _elements.CheckboxElement


class CheckboxGroupElementFactory(_ModelFactory):
    __model__ = _elements.CheckboxGroupElement


class OptionFactory(_ModelFactory):
    __model__ = _elements.Option


class RadioGroupElementFactory(_ModelFactory):
    __model__ = _elements.RadioGroupElement


class SelectElementFactory(_ModelFactory):
    __model__ = _elements.SelectElement


class HiddenElementFactory(_ModelFactory):
    __model__ = _elements.HiddenElement


def _one_of_each_element() -> list[_elements.FormElement]:
    # This used to work without a custom factory method, but doesn't anymore.
    # Maybe the same bug as https://github.com/litestar-org/polyfactory/issues/317?
    one_of_each = [
        factory.build()
        for factory in (
            StaticTextElementFactory,
            TextInputElementFactory,
            CheckboxElementFactory,
            CheckboxGroupElementFactory,
            RadioGroupElementFactory,
            SelectElementFactory,
            HiddenElementFactory,
        )
    ]
    random.shuffle(one_of_each)
    return one_of_each


class GroupElementFactory(_ModelFactory):
    __model__ = _elements.GroupElement

    elements = Use(_one_of_each_element)


class FormSectionFactory(_ModelFactory):
    __model__ = _elements.FormSection

    elements = Use(_one_of_each_element)


class OptionsFormDefinitionFactory(_ModelFactory):
    __model__ = _elements.OptionsFormDefinition

    general = Use(_one_of_each_element)
    sections = Use(lambda: [FormSectionFactory.build()])
