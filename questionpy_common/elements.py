from typing import List, Literal, Union, Optional, get_args

from pydantic import BaseModel, PositiveInt
from typing_extensions import TypeGuard, TypeAlias

from questionpy_common.conditions import Condition

__all__ = ["CanHaveConditions", "StaticTextElement", "TextInputElement", "CheckboxElement", "CheckboxGroupElement",
           "Option", "RadioGroupElement", "SelectElement", "HiddenElement", "GroupElement", "RepetitionElement",
           "FormElement", "FormSection", "OptionsFormDefinition", "is_form_element"]


class _Labelled(BaseModel):
    label: str
    """Text describing the element, shown verbatim."""


class _Named(BaseModel):
    name: str
    """Name which will later identify the element in submitted form data."""


class CanHaveConditions(BaseModel):
    """Mixin class for elements which can have conditions on other elements."""
    disable_if: list[Condition] = []
    """Disable this element if any of these conditions match."""
    hide_if: list[Condition] = []
    """Hide this element if any of these conditions match."""


class StaticTextElement(_Labelled, _Named, CanHaveConditions):
    """Some static text with a label."""
    kind: Literal["static_text"] = "static_text"
    text: str


class TextInputElement(_Labelled, _Named, CanHaveConditions):
    kind: Literal["input"] = "input"
    required: bool = False
    """Require some non-empty input to be entered before the form can be submitted."""
    default: Optional[str] = None
    """Default value of the input when first loading the form. Part of the submitted form data."""
    placeholder: Optional[str] = None
    """Placeholder to show when no value has been entered yet. Not part of the submitted form data."""


class CheckboxElement(_Named, CanHaveConditions):
    kind: Literal["checkbox"] = "checkbox"
    left_label: Optional[str] = None
    """Label shown the same way as labels on other element types."""
    right_label: Optional[str] = None
    """Additional label shown to the right of the checkbox."""
    required: bool = False
    """Require this checkbox to be selected before the form can be submitted."""
    selected: bool = False
    """Default state of the checkbox."""


class CheckboxGroupElement(BaseModel):
    """Adds a 'Select all/none' button after multiple checkboxes."""
    kind: Literal["checkbox_group"] = "checkbox_group"
    checkboxes: List[CheckboxElement]


class Option(BaseModel):
    """A possible option for radio groups and drop-downs."""
    label: str
    """Text describing the option, shown verbatim."""
    value: str
    """Value which will be taken by the radio group or drop-down when this option is selected."""
    selected: bool = False
    """Default state of the option."""


class RadioGroupElement(_Labelled, _Named, CanHaveConditions):
    """Group of radio buttons, of which at most one can be selected at a time."""
    kind: Literal["radio_group"] = "radio_group"
    options: List[Option]
    """Selectable options."""
    required: bool = False
    """Require one of the options to be selected before the form can be submitted."""


class SelectElement(_Labelled, _Named, CanHaveConditions):
    """A drop-down list."""
    kind: Literal["select"] = "select"
    multiple: bool = False
    """Allow the selection of multiple options."""
    options: List[Option]
    """Selectable options."""
    required: bool = False
    """Require at least one of the options to be selected before the form can be submitted."""


class HiddenElement(_Named, CanHaveConditions):
    """An element which isn't shown to the user but still submits its fixed value."""
    kind: Literal["hidden"] = "hidden"
    value: str


class GroupElement(_Labelled, _Named, CanHaveConditions):
    """Groups multiple elements horizontally with a common label."""
    kind: Literal["group"] = "group"
    elements: List["FormElement"]


class RepetitionElement(_Named):
    """Repeats a number of elements, allowing the user to add new repetitions with the click of a button."""
    kind: Literal["repetition"] = "repetition"

    initial_elements: PositiveInt
    """Number of repetitions to show when the form is first loaded."""
    increment: PositiveInt
    """Number of repetitions to add with each click of the button."""
    button_label: Optional[str] = None
    """Label for the button which adds more repetitions, or None to use default provided by LMS."""

    elements: list["FormElement"]
    """Elements which will be repeated."""


FormElement: TypeAlias = Union[
    StaticTextElement, TextInputElement, CheckboxElement, CheckboxGroupElement,
    RadioGroupElement, SelectElement, HiddenElement, GroupElement, RepetitionElement
]

GroupElement.update_forward_refs()
RepetitionElement.update_forward_refs()


class FormSection(_Named):
    """Form section which can be expanded and collapsed."""
    header: str
    """Header to be shown at the top of the section."""
    elements: List[FormElement] = []
    """Elements contained in the section."""


class OptionsFormDefinition(BaseModel):
    general: List[FormElement] = []
    """Elements to add to the main section, after the LMS' own elements."""
    sections: List[FormSection] = []
    """Sections to add after the main section."""


def is_form_element(value: object) -> TypeGuard[FormElement]:
    # unions don't support runtime type checking through isinstance
    # this checks if value is an instance of any of the union members
    return isinstance(value, get_args(FormElement))
