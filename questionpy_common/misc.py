from enum import IntEnum
from typing import Optional, Union


class SizeUnit(IntEnum):
    # pylint: disable=invalid-name
    B = 1
    KiB = 1024
    MiB = 1024 * KiB
    GiB = 1024 * MiB
    TiB = 1024 * GiB

    @classmethod
    def from_unit_prefix(cls, unit_prefix: str) -> 'SizeUnit':
        if unit_prefix == '':
            return cls.B
        unit = f"{unit_prefix.upper()}iB"
        return cls[unit]


class SizeUnitSI(IntEnum):
    B = 1
    KB = 1000
    MB = 1000 * KB
    GB = 1000 * MB
    TB = 1000 * GB

    @classmethod
    def from_unit_prefix(cls, unit_prefix: str) -> 'SizeUnitSI':
        if unit_prefix == '':
            return cls.B
        unit = f"{unit_prefix.upper()}B"
        return cls[unit]


class Size(int):
    """Size class for easier byte representation."""

    def __new__(cls, value: Union[int, float, str], unit: Union[SizeUnit, SizeUnitSI] = SizeUnit.B) -> 'Size':
        if isinstance(value, int):
            return super().__new__(cls, value * unit)
        if isinstance(value, float):
            return super().__new__(cls, round(value * unit.value))
        if isinstance(value, str):
            return super().__new__(cls, round(float(value) * unit.value))
        raise TypeError(f"Cannot convert {type(value)} to Size.")

    def __init__(self, _value: Union[int, float, str], _unit: Union[SizeUnit, SizeUnitSI] = SizeUnit.B):
        self._string: Optional[str] = None

    @classmethod
    def from_string(cls, string: str) -> 'Size':
        """
        Convert a string to a Size object.

        :param string: String to convert.
        :return: Size object.
        """

        # IEC: 1 KiB = 1024 B; SI: 1 KB = 1000 B
        iec_format = True
        unit_prefix = ''

        # Remove whitespace and lowercase the string.
        sanitized = string.rstrip().lower()

        # Remove the unit from the string.
        if sanitized.endswith('ib'):
            sanitized = sanitized[:-2]
        elif sanitized.endswith('b'):
            iec_format = False
            sanitized = sanitized[:-1]

        # Check unit prefix and return the correct value.
        try:
            if sanitized.endswith(('k', 'm', 'g', 't')):
                unit_prefix = sanitized[-1:]
                sanitized = sanitized[:-1]
            if iec_format:
                return Size(sanitized, SizeUnit.from_unit_prefix(unit_prefix))
            return Size(sanitized, SizeUnitSI.from_unit_prefix(unit_prefix))
        except (ValueError, KeyError) as e:
            raise ValueError(f"Could not convert '{string}'") from e

    def convert_to(self, unit: Union[SizeUnit, SizeUnitSI]) -> float:
        """
        Convert to given unit.

        :param unit: Unit to convert to.
        :return: Converted value.
        """

        return self / unit

    def __str__(self) -> str:
        if self._string:
            return self._string

        absolute = abs(self)

        if absolute < SizeUnit.KiB:
            self._string = f'{int(self)} {SizeUnit.B.name}'
        elif absolute < SizeUnit.MiB:
            self._string = f'{self.convert_to(SizeUnit.KiB):.2f} {SizeUnit.KiB.name}'
        elif absolute < SizeUnit.GiB:
            self._string = f'{self.convert_to(SizeUnit.MiB):.2f} {SizeUnit.MiB.name}'
        elif absolute < SizeUnit.TiB:
            self._string = f'{self.convert_to(SizeUnit.GiB):.2f} {SizeUnit.GiB.name}'
        else:
            self._string = f'{self.convert_to(SizeUnit.TiB):.2f} {SizeUnit.TiB.name}'

        return self._string

    def __repr__(self) -> str:
        return f'Size({self})'
