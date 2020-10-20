# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (C) 2015-2019 GEM Foundation

# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.

"""
Compatibility layer for Python 2 and 3. Mostly copied from six and future,
but reduced to the subset of utilities needed by GEM. This is done to
avoid an external dependency.
"""
import math
import builtins
import numpy

def decode(val):
    """
    Decode an object assuming the encoding is UTF-8.

    :param: a unicode or bytes object
    :returns: a unicode object
    """
    if isinstance(val, (list, tuple, numpy.ndarray)):
        return [decode(v) for v in val]
    elif isinstance(val, str):
        # it was an already decoded unicode object
        return val
    else:
        # assume it is an encoded bytes object
        return val.decode('utf-8')

