from typing import Union
from unittest.mock import patch

import pytest

from questionpy_common.misc import Size, SizeUnit, SizeUnitSI

KiB = 1024  # pylint: disable=invalid-name
MiB = 1024 ** 2  # pylint: disable=invalid-name
GiB = 1024 ** 3  # pylint: disable=invalid-name
TiB = 1024 ** 4  # pylint: disable=invalid-name

KB = 1000
MB = 1000 ** 2
GB = 1000 ** 3
TB = 1000 ** 4


@pytest.mark.parametrize('size_unit, expected', [
    (SizeUnit.B, 1),
    (SizeUnit.KiB, KiB),
    (SizeUnit.MiB, MiB),
    (SizeUnit.GiB, GiB),
    (SizeUnit.TiB, TiB),

    (SizeUnitSI.B, 1),
    (SizeUnitSI.KB, KB),
    (SizeUnitSI.MB, MB),
    (SizeUnitSI.GB, GB),
    (SizeUnitSI.TB, TB),
])
def test_size_unit_si(size_unit: Union[SizeUnit, SizeUnitSI], expected: int) -> None:
    assert size_unit == expected


@pytest.mark.parametrize('size_unit, unit_prefix, expected', [
    (SizeUnit, '', SizeUnit.B),
    (SizeUnit, 'k', SizeUnit.KiB),
    (SizeUnit, 'm', SizeUnit.MiB),
    (SizeUnit, 'g', SizeUnit.GiB),
    (SizeUnit, 't', SizeUnit.TiB),

    (SizeUnitSI, '', SizeUnitSI.B),
    (SizeUnitSI, 'k', SizeUnitSI.KB),
    (SizeUnitSI, 'm', SizeUnitSI.MB),
    (SizeUnitSI, 'g', SizeUnitSI.GB),
    (SizeUnitSI, 't', SizeUnitSI.TB),
])
def test_byte_size_from_unit_prefix(size_unit: Union[SizeUnit, SizeUnitSI], unit_prefix: str,
                                    expected: Union[SizeUnit, SizeUnitSI]) -> None:

    assert size_unit.from_unit_prefix(unit_prefix) == expected
    assert size_unit.from_unit_prefix(unit_prefix.upper()) == expected


@pytest.mark.parametrize('value, unit, expected', [
    # Integers.
    (1, SizeUnit.B, 1),
    (1024, SizeUnit.B, KiB),
    (1, SizeUnit.KiB, KiB),
    (1, SizeUnit.MiB, MiB),
    (1, SizeUnit.GiB, GiB),
    (1, SizeUnit.TiB, TiB),
    (-1, SizeUnit.KiB, -KiB),

    # Floats.
    (0.4, SizeUnit.B, 0),
    (0.6, SizeUnit.B, 1),
    (1.0, SizeUnit.B, 1),
    (0.5, SizeUnit.KiB, 512),

    (-0.4, SizeUnit.B, 0),
    (-0.6, SizeUnit.B, -1),
    (-0.5, SizeUnit.KiB, -512),

    # Strings.
    ('0.4', SizeUnit.B, 0),
    ('0.6', SizeUnit.B, 1),
    ('1.5', SizeUnit.KiB, 1536),
    ('1', SizeUnit.MiB, MiB),
    ('1', SizeUnit.GiB, GiB),
    ('1', SizeUnit.TiB, TiB),

    ('+0.4', SizeUnit.B, 0),
    ('+0.6', SizeUnit.B, 1),
    ('+1.5', SizeUnit.KiB, 1536),
    ('+1', SizeUnit.MiB, MiB),
    ('+1', SizeUnit.GiB, GiB),
    ('+1', SizeUnit.TiB, TiB),

    ('-0.4', SizeUnit.B, 0),
    ('-0.6', SizeUnit.B, -1),
    ('-1.5', SizeUnit.KiB, -1536),
    ('-1', SizeUnit.MiB, -MiB),
    ('-1', SizeUnit.GiB, -GiB),
    ('-1', SizeUnit.TiB, -TiB),

    # SI units.
    (1, SizeUnitSI.B, 1),
    (1000, SizeUnitSI.B, KB),
    (1, SizeUnitSI.KB, KB),
    (1, SizeUnitSI.MB, MB),
    (1, SizeUnitSI.GB, GB),
    (1, SizeUnitSI.TB, TB),
    (-1, SizeUnitSI.KB, -KB),

    # Floats.
    (0.4, SizeUnitSI.B, 0),
    (0.6, SizeUnitSI.B, 1),
    (1.0, SizeUnitSI.B, 1),
    (0.5, SizeUnitSI.KB, 500),

    (-0.4, SizeUnitSI.B, 0),
    (-0.6, SizeUnitSI.B, -1),
    (-0.5, SizeUnitSI.KB, -500),

    # Strings.
    ('0.4', SizeUnitSI.B, 0),
    ('0.6', SizeUnitSI.B, 1),
    ('1.5', SizeUnitSI.KB, 1500),
    ('1', SizeUnitSI.MB, MB),
    ('1', SizeUnitSI.GB, GB),
    ('1', SizeUnitSI.TB, TB),

    ('+0.4', SizeUnitSI.B, 0),
    ('+0.6', SizeUnitSI.B, 1),
    ('+1.5', SizeUnitSI.KB, 1500),
    ('+1', SizeUnitSI.MB, MB),
    ('+1', SizeUnitSI.GB, GB),
    ('+1', SizeUnitSI.TB, TB),

    ('-0.4', SizeUnitSI.B, 0),
    ('-0.6', SizeUnitSI.B, -1),
    ('-1.5', SizeUnitSI.KB, -1500),
    ('-1', SizeUnitSI.MB, -MB),
    ('-1', SizeUnitSI.GB, -GB),
    ('-1', SizeUnitSI.TB, -TB),
])
def test_init(value: float, unit: SizeUnit, expected: int) -> None:
    assert Size(value, unit) == expected


@pytest.mark.parametrize('value', [
    Size(0),
    Size(-0),
    Size(+0),
    Size(0.0),
    Size(-0.0),
    Size(+0.0),
    Size('0'),
    Size('-0'),
    Size('+0'),
    Size('0.0'),
    Size('-0.0'),
    Size('+0.0')
])
def test_zero(value: Size) -> None:
    assert 0 == value


def test_incorrect_type() -> None:
    with pytest.raises(TypeError):
        Size([])  # type: ignore


@pytest.mark.parametrize('value', [
    '10,0',
    '1 00'
    '--1',
    '++1',
    '1-1',
    '1.0.0',
    'abc',
    '100abc',
    'abc100',
    'abc100abc',
    '100 abc',
    'abc 100',
    'abc 100 abc',
])
def test_incorrect_input(value: str) -> None:
    with pytest.raises(ValueError):
        Size(value)


@pytest.mark.parametrize('string, expected', [
    # Without unit.
    ('0', 0),
    ('1', 1),
    ('1.0', 1),
    ('1.4', 1),
    ('1.6', 2),
    ('1024', KiB),
    ('1024.0', KiB),
    ('1024.5', KiB),
    ('1024.6', KiB + 1),

    # With unit.
    ('1 b', 1),
    ('1 B', 1),
    ('1k', KiB),
    ('1kib', KiB),
    ('1 m', MiB),
    ('1 mib', MiB),
    ('1 G', GiB),
    ('1 giB', GiB),
    ('1 T  ', TiB),
    ('  1 tib', TiB),
    ('  1 TiB  ', TiB),

    # SI units.
    ('1kb', KB),
    ('1KB', KB),
    ('1 mb', MB),
    ('1 MB', MB),
    ('1 Gb', GB),
    ('1 gB', GB),
    ('1 TB', TB),
    ('1 tb', TB),
])
def test_from_string(string: str, expected: int) -> None:
    assert Size.from_string(string) == expected


@pytest.mark.parametrize('string', [
    '1.0.0',
    'KiB',
    '1 KiB KiB',
    '1 5',
    '1 5 MiB',
    '12 ÖiB'
    '12 Öb',
    '1 kD',
    'kib 13'
])
def test_from_string_not_valid(string: str) -> None:
    with pytest.raises(ValueError):
        Size.from_string(string)


@pytest.mark.parametrize('value, unit, expected', [
    # IEC units.
    (Size(1), SizeUnit.B, 1),
    (Size(0), SizeUnit.B, 0),
    (Size(-1), SizeUnit.B, -1),

    (Size(KiB), SizeUnit.KiB, 1),
    (Size(1, SizeUnit.KiB), SizeUnit.B, KiB),

    (Size(KiB, SizeUnit.MiB), SizeUnit.GiB, 1),
    (Size(1, SizeUnit.GiB), SizeUnit.MiB, KiB),

    (Size(KiB, SizeUnit.MiB), SizeUnit.GiB, 1),
    (Size(1, SizeUnit.GiB), SizeUnit.MiB, KiB),

    (Size(KiB, SizeUnit.GiB), SizeUnit.TiB, 1),
    (Size(1, SizeUnit.TiB), SizeUnit.GiB, KiB),

    (Size(1536, SizeUnit.MiB), SizeUnit.GiB, 1.5),
    (Size(-1.5, SizeUnit.GiB), SizeUnit.MiB, -1536),

    (Size(2, SizeUnit.MiB), SizeUnit.B, 2 * MiB),
    (Size(-2, SizeUnit.GiB), SizeUnit.B, -2 * GiB),

    # SI units.
    (Size(1), SizeUnitSI.B, 1),
    (Size(0), SizeUnitSI.B, 0),
    (Size(-1), SizeUnitSI.B, -1),

    (Size(KB), SizeUnitSI.KB, 1),
    (Size(1, SizeUnitSI.KB), SizeUnitSI.B, KB),

    (Size(KB, SizeUnitSI.MB), SizeUnitSI.GB, 1),
    (Size(1, SizeUnitSI.GB), SizeUnitSI.MB, KB),

    (Size(KB, SizeUnitSI.MB), SizeUnitSI.GB, 1),
    (Size(1, SizeUnitSI.GB), SizeUnitSI.MB, KB),

    (Size(KB, SizeUnitSI.GB), SizeUnitSI.TB, 1),
    (Size(1, SizeUnitSI.TB), SizeUnitSI.GB, KB),

    (Size(1536, SizeUnitSI.MB), SizeUnitSI.GB, 1.536),
    (Size(-1.5, SizeUnitSI.GB), SizeUnitSI.MB, -1500),

    (Size(2, SizeUnitSI.MB), SizeUnitSI.B, 2 * MB),
    (Size(-2, SizeUnitSI.GB), SizeUnitSI.B, -2 * GB),
])
def test_convert_to(value: Size, unit: SizeUnit, expected: int) -> None:
    assert pytest.approx(value.convert_to(unit)) == expected


@pytest.mark.parametrize('value, expected', [
    # IEC units.
    (Size(1), '1 B'),
    (Size(KiB), '1.00 KiB'),
    (Size(KiB, SizeUnit.KiB), '1.00 MiB'),
    (Size(KiB, SizeUnit.MiB), '1.00 GiB'),
    (Size(KiB, SizeUnit.GiB), '1.00 TiB'),
    (Size(KiB, SizeUnit.TiB), '1024.00 TiB'),

    (Size(1.5), '2 B'),
    (Size(1536), '1.50 KiB'),
    (Size(1536, SizeUnit.KiB), '1.50 MiB'),
    (Size(1536, SizeUnit.MiB), '1.50 GiB'),
    (Size(1536, SizeUnit.GiB), '1.50 TiB'),
    (Size(1536, SizeUnit.TiB), '1536.00 TiB'),

    (Size(-1.5), '-2 B'),
    (Size(-1536), '-1.50 KiB'),
    (Size(-1536, SizeUnit.KiB), '-1.50 MiB'),
    (Size(-1536, SizeUnit.MiB), '-1.50 GiB'),
    (Size(-1536, SizeUnit.GiB), '-1.50 TiB'),
    (Size(-1536, SizeUnit.TiB), '-1536.00 TiB'),

    # SI units.
    (Size(1, SizeUnitSI.KB), '1000 B'),
    (Size(1, SizeUnitSI.MB), '976.56 KiB'),
    (Size(1, SizeUnitSI.GB), '953.67 MiB'),
    (Size(1, SizeUnitSI.TB), '931.32 GiB'),

    (Size(KB, SizeUnitSI.KB), '976.56 KiB'),
    (Size(KB, SizeUnitSI.MB), '953.67 MiB'),
    (Size(KB, SizeUnitSI.GB), '931.32 GiB'),
    (Size(KB, SizeUnitSI.TB), '909.49 TiB'),
])
def test_to_str(value: Size, expected: str) -> None:
    assert str(value) == expected


def test_repr() -> None:
    with patch.object(Size, '__str__', return_value='test') as mock:
        assert repr(Size(1)) == 'Size(test)'
        mock.assert_called_once()
