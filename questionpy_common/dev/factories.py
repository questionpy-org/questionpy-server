from pydantic_factories import ModelFactory as _ModelFactory

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


class GroupElementFactory(_ModelFactory):
    __model__ = _elements.GroupElement


class FormSectionFactory(_ModelFactory):
    __model__ = _elements.FormSection


class OptionsFormDefinitionFactory(_ModelFactory):
    __model__ = _elements.OptionsFormDefinition
