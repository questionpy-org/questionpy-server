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
    checkboxes: _typing.List[CheckboxElement]


class Option(_BaseModel):
    label: str
    value: str
    selected: bool = False


class RadioGroupElement(_Labelled, _Named):
    kind: _typing.Literal["radio_group"] = "radio_group"
    options: _typing.List[Option]
    required: bool = False


class SelectElement(_Labelled, _Named):
    kind: _typing.Literal["select"] = "select"
    multiple: bool = False
    options: _typing.List[Option]
    required: bool = False


class HiddenElement(_Named):
    kind: _typing.Literal["hidden"] = "hidden"
    value: str


class GroupElement(_Labelled, _Named):
    kind: _typing.Literal["group"] = "group"
    elements: _typing.List["FormElement"]


class FormElement(_BaseModel):
    __root__: _typing.Union[
        StaticTextElement, TextInputElement, CheckboxElement, CheckboxGroupElement,
        RadioGroupElement, SelectElement, HiddenElement, GroupElement
    ]


class FormSection(_BaseModel):
    header: str
    elements: _typing.List[FormElement] = []


class Form(_BaseModel):
    general: _typing.List[FormElement] = []
    sections: _typing.List[FormSection] = []
