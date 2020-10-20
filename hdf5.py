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

import csv
import ast
import itertools
import numpy
import h5py
import inspect
from python3compat import decode


vbytes = h5py.special_dtype(vlen=bytes)
vstr = h5py.special_dtype(vlen=str)
vuint8 = h5py.special_dtype(vlen=numpy.uint8)
vuint16 = h5py.special_dtype(vlen=numpy.uint16)
vuint32 = h5py.special_dtype(vlen=numpy.uint32)
vfloat32 = h5py.special_dtype(vlen=numpy.float32)
vfloat64 = h5py.special_dtype(vlen=numpy.float64)


def decode_array(values):
    """
    Decode the values which are bytestrings.
    """
    out = []
    for val in values:
        try:
            out.append(val.decode('utf8'))
        except AttributeError:
            out.append(val)
    return out

def parse_comment(comment):
    """
    Parse a comment of the form
    `investigation_time=50.0, imt="PGA", ...`
    and returns it as pairs of strings:

    >>> parse_comment('''path=('b1',), time=50.0, imt="PGA"''')
    [('path', ('b1',)), ('time', 50.0), ('imt', 'PGA')]
    """
    names, vals = [], []
    if comment.startswith('"'):
        comment = comment[1:-1]
    pieces = comment.split('=')
    for i, piece in enumerate(pieces):
        if i == 0:  # first line
            names.append(piece.strip())
        elif i == len(pieces) - 1:  # last line
            vals.append(ast.literal_eval(piece))
        else:
            val, name = piece.rsplit(',', 1)
            vals.append(ast.literal_eval(val))
            names.append(name.strip())
    return list(zip(names, vals))

def build_dt(dtypedict, names):
    """
    Build a composite dtype for a list of names and dictionary
    name -> dtype with a None entry corresponding to the default dtype.
    """
    lst = []
    for name in names:
        try:
            dt = dtypedict[name]
        except KeyError:
            dt = dtypedict[None]
        lst.append((name, vstr if dt is str else dt))
    return numpy.dtype(lst)


class ArrayWrapper(object):
    """
    A pickleable and serializable wrapper over an array, HDF5 dataset or group
    """
    @classmethod
    def from_(cls, obj, extra='value'):
        if isinstance(obj, cls):  # it is already an ArrayWrapper
            return obj
        elif inspect.isgenerator(obj):
            array, attrs = (), dict(obj)
        elif hasattr(obj, '__toh5__'):
            return obj
        elif hasattr(obj, 'attrs'):  # is a dataset
            array, attrs = obj[()], dict(obj.attrs)
            shape_descr = attrs.get('shape_descr', [])
            for descr in map(decode, shape_descr):
                attrs[descr] = list(attrs[descr])
        else:  # assume obj is an array
            array, attrs = obj, {}
        return cls(array, attrs, (extra,))

    def __init__(self, array, attrs, extra=('value',)):
        vars(self).update(attrs)
        self._extra = tuple(extra)
        if len(array):
            self.array = array

    def __iter__(self):
        if hasattr(self, 'array'):
            return iter(self.array)
        else:
            return iter(vars(self).items())

    def __len__(self):
        if hasattr(self, 'array'):
            return len(self.array)
        else:
            return len(vars(self))

    def __getitem__(self, idx):
        if isinstance(idx, str) and idx in self.__dict__:
            return getattr(self, idx)
        return self.array[idx]

    def __toh5__(self):
        arr = getattr(self, 'array', ())
        return arr, self.to_dict()

    def __fromh5__(self, array, attrs):
        self.__init__(array, attrs)

    def __repr__(self):
        if hasattr(self, 'shape_descr'):
            assert len(self.shape) == len(self.shape_descr), (
                self.shape_descr, self.shape)
            lst = ['%s=%d' % (descr, size)
                   for descr, size in zip(self.shape_descr, self.shape)]
            return '<%s(%s)>' % (self.__class__.__name__, ', '.join(lst))
        return '<%s%s>' % (self.__class__.__name__, self.shape)

    @property
    def dtype(self):
        """dtype of the underlying array"""
        return self.array.dtype

    @property
    def shape(self):
        """shape of the underlying array"""
        return self.array.shape if hasattr(self, 'array') else ()


    def sum_all(self, *tags):
        """
        Reduce the underlying array by summing on the given dimensions
        """
        tag2idx = {tag: i for i, tag in enumerate(self.shape_descr)}
        array = self.array.sum(axis=tuple(tag2idx[tag] for tag in tags))
        attrs = vars(self).copy()
        attrs['shape_descr'] = [tag for tag in self.shape_descr
                                if tag not in tags]
        return self.__class__(array, attrs)

    def to_table(self):
        """
        Convert an ArrayWrapper with shape (D1, ..., DN) and attributes
        T1, ..., TN which are list of tags of lenghts D1, ... DN into
        a table with rows (tag1, ... tagN, extra1, ... extraM) of maximum
        length D1 * ... * DN. Zero values are discarded.

        >>> from pprint import pprint
        >>> dic = dict(shape_descr=['taxonomy', 'occupancy'],
        ...            taxonomy=['RC', 'WOOD'],
        ...            occupancy=['RES', 'IND', 'COM'])
        >>> arr = numpy.zeros((2, 3))
        >>> arr[0, 0] = 2000
        >>> arr[0, 1] = 5000
        >>> arr[1, 0] = 500
        >>> aw = ArrayWrapper(arr, dic)
        >>> pprint(aw.to_table())
        [('taxonomy', 'occupancy', 'value'),
         ('RC', 'RES', 2000.0),
         ('RC', 'IND', 5000.0),
         ('WOOD', 'RES', 500.0)]
        >>> pprint(aw.sum_all('taxonomy').to_table())
        [('occupancy', 'value'), ('RES', 2500.0), ('IND', 5000.0)]
        >>> pprint(aw.sum_all('occupancy').to_table())
        [('taxonomy', 'value'), ('RC', 7000.0), ('WOOD', 500.0)]
        """
        shape = self.shape
        tup = len(self._extra) > 1
        if tup:
            if shape[-1] != len(self._extra):
                raise ValueError(
                    'There are %d extra-fields but %d dimensions in %s' %
                    (len(self._extra), shape[-1], self))
        shape_descr = tuple(decode(d) for d in self.shape_descr)
        fields = shape_descr + self._extra
        out = []
        tags = []
        idxs = []
        for i, tagname in enumerate(shape_descr):
            values = getattr(self, tagname)
            if len(values) != shape[i]:
                raise ValueError(
                    'The tag %s with %d values is inconsistent with %s'
                    % (tagname, len(values), self))
            tags.append(decode_array(values))
            idxs.append(range(len(values)))
        for idx, values in zip(itertools.product(*idxs),
                               itertools.product(*tags)):
            val = self.array[idx]
            if tup:
                if val.sum():
                    out.append(values + tuple(val))
            elif val:
                out.append(values + (val,))
        return [fields] + out

    def to_dict(self):
        """
        Convert the public attributes into a dictionary
        """
        return {k: v for k, v in vars(self).items()
                if k != 'array' and not k.startswith('_')}


# NB: it would be nice to use numpy.loadtxt(
#  f, build_dt(dtypedict, header), delimiter=sep, ndmin=1, comments=None)
# however numpy does not support quoting, and "foo,bar" would be split :-(
def read_csv(fname, dtypedict={None: float}, renamedict={}, sep=','):
    """
    :param fname: a CSV file with an header and float fields
    :param dtypedict: a dictionary fieldname -> dtype, None -> default
    :param renamedict: aliases for the fields to rename
    :param sep: separator (default comma)
    :return: a structured array of floats
    """
    attrs = {}
    with open(fname, encoding='utf-8-sig') as f:
        while True:
            first = next(f)
            if first.startswith('#'):
                attrs = dict(parse_comment(first.strip('#,\n')))
                continue
            break
        header = first.strip().split(sep)
        try:
            rows = [tuple(row) for row in csv.reader(f)]
            arr = numpy.array(rows, build_dt(dtypedict, header))
        except KeyError:
            raise KeyError('Missing None -> default in dtypedict')
        except Exception as exc:
            raise Exception('%s: %s' % (fname, exc))
    if renamedict:
        newnames = []
        for name in arr.dtype.names:
            new = renamedict.get(name, name)
            newnames.append(new)
        arr.dtype.names = newnames
    return ArrayWrapper(arr, attrs)
