from typing import List, Literal, Union, Optional, get_args

from pydantic import BaseModel
from typing_extensions import TypeGuard, TypeAlias

from questionpy_common.conditions import Condition

__all__ = ["CanHaveConditions", "StaticTextElement", "TextInputElement", "CheckboxElement", "CheckboxGroupElement",
           "Option", "RadioGroupElement", "SelectElement", "HiddenElement", "GroupElement", "FormElement",
           "FormSection", "OptionsFormDefinition", "is_form_element"]


class _Labelled(BaseModel):
    label: str


class _Named(BaseModel):
    name: str


class CanHaveConditions(BaseModel):
    disable_if: list[Condition] = []
    hide_if: list[Condition] = []


class StaticTextElement(_Labelled, _Named, CanHaveConditions):
    kind: Literal["static_text"] = "static_text"
    text: str


class TextInputElement(_Labelled, _Named, CanHaveConditions):
    kind: Literal["input"] = "input"
    required: bool = False
    default: Optional[str] = None
    placeholder: Optional[str] = None


class CheckboxElement(_Named, CanHaveConditions):
    kind: Literal["checkbox"] = "checkbox"
    left_label: Optional[str] = None
    right_label: Optional[str] = None
    required: bool = False
    selected: bool = False


class CheckboxGroupElement(BaseModel):
    kind: Literal["checkbox_group"] = "checkbox_group"
    checkboxes: List[CheckboxElement]


class Option(BaseModel):
    label: str
    value: str
    selected: bool = False


class RadioGroupElement(_Labelled, _Named, CanHaveConditions):
    kind: Literal["radio_group"] = "radio_group"
    options: List[Option]
    required: bool = False


class SelectElement(_Labelled, _Named, CanHaveConditions):
    kind: Literal["select"] = "select"
    multiple: bool = False
    options: List[Option]
    required: bool = False


class HiddenElement(_Named, CanHaveConditions):
    kind: Literal["hidden"] = "hidden"
    value: str


class GroupElement(_Labelled, _Named, CanHaveConditions):
    kind: Literal["group"] = "group"
    elements: List["FormElement"]


FormElement: TypeAlias = Union[
    StaticTextElement, TextInputElement, CheckboxElement, CheckboxGroupElement,
    RadioGroupElement, SelectElement, HiddenElement, GroupElement
]

GroupElement.update_forward_refs()


class FormSection(_Named):
    header: str
    elements: List[FormElement] = []


class OptionsFormDefinition(BaseModel):
    general: List[FormElement] = []
    sections: List[FormSection] = []


def is_form_element(value: object) -> TypeGuard[FormElement]:
    # unions don't support runtime type checking through isinstance
    # this checks if value is an instance of any of the union members
    return isinstance(value, get_args(FormElement))
