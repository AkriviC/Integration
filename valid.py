# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2013-2019 GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake. If not, see <http://www.gnu.org/licenses/>.

"""
Validation library for the engine, the desktop tools, and anything else
"""
import re

class SimpleId(object):
    """
    Check if the given value is a valid ID.

    :param length: maximum length of the ID
    :param regex: accepted characters
    """
    def __init__(self, length, regex=r'^[\w_\-]+$'):
        self.length = length
        self.regex = regex
        self.__name__ = 'SimpleId(%d, %s)' % (length, regex)

    def __call__(self, value):
        if max(map(ord, value)) > 127:
            raise ValueError(
                'Invalid ID %r: the only accepted chars are a-zA-Z0-9_-'
                % value)
        elif len(value) > self.length:
            raise ValueError("The ID '%s' is longer than %d character" %
                             (value, self.length))
        elif re.match(self.regex, value):
            return value
        raise ValueError(
            "Invalid ID '%s': the only accepted chars are a-zA-Z0-9_-" % value)

ASSET_NAME_LENGTH = 100
MAX_ID_LENGTH = 75  # length required for some sources in US14 collapsed model
source_id = SimpleId(MAX_ID_LENGTH, r'^[\w\.\-_]+$')
IM_type = SimpleId(MAX_ID_LENGTH)
exposure_id = SimpleId(ASSET_NAME_LENGTH)

ASSET_NAME_LENGTH = 100
asset_name = SimpleId(ASSET_NAME_LENGTH)

UNIT_LENGTH = 50
unit = SimpleId(UNIT_LENGTH)


def namelist(value):
    """
    :param value: input string
    :returns: list of identifiers separated by whitespace or commas

    >>> namelist('a,b')
    ['a', 'b']
    >>> namelist('a1  b_2\t_c')
    ['a1', 'b_2', '_c']

    >>> namelist('a1 b_2 1c')
    ['a1', 'b_2', '1c']
    """
    names = value.replace(',', ' ').split()
    for n in names:
        try:
            source_id(n)
        except ValueError:
            raise ValueError('List of names containing an invalid name:'
                             ' %s' % n)
    return names




def not_empty(value):
    """
    check that the string is not all empty
    """
    if isinstance(value, int):
        pass
    elif value is None or value.strip() == '':
        raise ValueError('got an empty string')
    return value

def positivefloat(value):
    """
    :param value: input stirng
    :return: positive integer
    """
    if isinstance(value, float):
        i = value
    else:
        i = float(not_empty(value))
    if i < 0:
        raise ValueError('float %d < 0' % i)
    return i


def float_(value):
    """
    :param value: input string
    :returns: a floating point number
    """
    try:
        return float(value)
    except Exception:
        raise ValueError("'%s' is not a float" % value)

def longitude(value):
    """
    :param value: input string
    :returns: longitude float, rounded to 5 digits, i.e. 1 meter maximum

    >>> longitude('0.123456')
    0.12346
    """
    lon = round(float_(value), 5)
    if lon > 180.:
        raise ValueError('longitude %s > 180' % lon)
    elif lon < -180.:
        raise ValueError('longitude %s < -180' % lon)
    return lon


def latitude(value):
    """
    :param value: input string
    :returns: latitude float, rounded to 5 digits, i.e. 1 meter maximum

    >>> latitude('-0.123456')
    -0.12346
    """
    lat = round(float_(value), 5)
    if lat > 90.:
        raise ValueError('latitude %s > 90' % lat)
    elif lat < -90.:
        raise ValueError('latitude %s < -90' % lat)
    return lat

def utf8(value):
    """
    check that the string is utf-8. It returns an encode bytestring
    :param value:
    :return:
    """
    try:
        if isinstance(value, bytes):
            return value.decode('utf-8')
        else:
            return value
    except Exception:
        raise ValueError('not UTF-8: %r' % value)


def utf8_not_empty(value):
    """Check that the string is UTF-8 and not empty"""
    return utf8(not_empty(value))


def compose(*validators):
    """
    implement a composition of validators e.g. utf8_non_empty = compose(utf8, not_empty))
    :param vaidators:
    :return:
    """
    def composed_validator(value):
        out = value
        for validator in reversed(validators):
            out = validator(out)
        return out
    composed_validator.__name__ = 'compose(%s)' % ','.join(val.__name__ for val in validators)
    return composed_validator



def nonzero(value):
    """
    :param value: input string
    :returns: the value unchanged

    >>> nonzero('1')
    '1'
    >>> nonzero('0')
    Traceback (most recent call last):
      ...
    ValueError: '0' is zero
    """
    if float_(value) == 0:
        raise ValueError("'%s' is zero" % value)
    return value



class Choice(object):
    """
    check if the choice is valid (case sensitive)

    """
    @property
    def __name__(self):
        return 'Choice%s' % str(self.choices)

    def __init__(self, *choices):
        self.choices = choices

    def __call__(self, value):
        if value not in self.choices:
            if value not in self.choices[0]:
                raise ValueError("Got '%s', expected %s" % (value, '|'.join(self.choices)))
        return value



def positiveint(value):
    """
    :param value: input stirng
    :return: positive integer
    """
    i = not_empty(value)
    if not isinstance(i, int):
        raise ValueError('%s is not int' % i)
    elif i < 0:
        raise ValueError('int %s < 0' % i)
    return i


def positiveint_list(value):
    """
    :param value: input list of values
    :return: list of positive integers
    """
    if not isinstance(value, list):
        raise ValueError('%s is not list' % value)
    vals = [positiveint(val) for val in value]
    return vals

def positiveint_or_list(value):
    """
    :param value: input list or a single value
    :return: list of positive integers
    """
    if isinstance(value, list):
        vals = [positiveint(val) for val in value]
    else:
        vals = positiveint(value)
    return vals
