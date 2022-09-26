import typing as _typing

from pydantic import BaseModel as _BaseModel


class _Labelled(_BaseModel):
    label: str


class _Named(_BaseModel):
    name: str


class StaticTextElement(_Labelled):
    kind: _typing.Literal["static_text"] = "static_text"
    text: str


class TextInputElement(_Labelled, _Named):
    kind: _typing.Literal["input"] = "input"
    required: bool = False
    default: _typing.Optional[str] = None
    placeholder: _typing.Optional[str] = None


class CheckboxElement(_Named):
    kind: _typing.Literal["checkbox"] = "checkbox"
    left_label: _typing.Optional[str] = None
    right_label: _typing.Optional[str] = None
    required: bool = False
    selected: bool = False


class CheckboxGroupElement(_BaseModel):
    kind: _typing.Literal["checkbox_group"] = "checkbox_group"
    checkboxes: list[CheckboxElement]


class Option(_BaseModel):
    label: str
    value: str
    selected: bool = False


class RadioGroupElement(_Labelled, _Named):
    kind: _typing.Literal["radio_group"] = "radio_group"
    options: list[Option]
    required: bool = False


class SelectElement(_Labelled, _Named):
    kind: _typing.Literal["select"] = "select"
    multiple: bool = False
    options: list[Option]
    required: bool = False


class HiddenElement(_Named):
    kind: _typing.Literal["hidden"] = "hidden"
    value: str


class GroupElement(_Labelled, _Named):
    kind: _typing.Literal["group"] = "group"
    elements: list["FormElement"]


class FormElement(_BaseModel):
    __root__: _typing.Union[
        StaticTextElement, TextInputElement, CheckboxElement, CheckboxGroupElement,
        RadioGroupElement, SelectElement, HiddenElement, GroupElement
    ]


GroupElement.update_forward_refs()


class FormSection(_BaseModel):
    header: str
    elements: list[FormElement] = []


class OptionsFormDefinition(_BaseModel):
    general: list[FormElement] = []
    sections: list[FormSection] = []
