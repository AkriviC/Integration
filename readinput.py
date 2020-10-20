import json


def read_json(fname):
    # read a json file
    try:
        with open(fname) as f:
            data = json.load(f)
    except TypeError:
        raise TypeError('unable to read the file %s ' % fname)
    return data
