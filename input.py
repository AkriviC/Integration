"""
downloads input files from the Middleware
Created by Akrivi Chatzidaki
"""
import os
import h5py
import numpy

from exposure import read_exposure_model
from consequences import get_consequences
import hdf5
from readinput import read_json
from validators import validators




def initialize_files(fnames, infiles_path):
    """
    file initialization: if the files are not stored in the infiles_path they will
    be downloaded from the Middleware (only for files that do not exist in the folder)
    :param file_id_names: ids of the names to be downloaded
    :param infiles_path: path where the files will be stored
    :return: the file names + paths
    """
    fname2download = []
    for fname in fnames.keys():
        fullfname = os.path.join(infiles_path, fnames[fname])
        if not os.path.isfile(fullfname):
            fname2download.append(fnames[fname].split('.')[0])
        fnames[fname] = fullfname

    if len(fname2download) > 0:
        # download the files
        raise ImportError('files %s cannot be found in the input folder' % fname2download)
    return fnames

def load_exposure_mtdata(fname):
    # read the sites file
    exp_mtdata = hdf5.read_csv(fname,
                               {'lon': numpy.float32, 'lat': numpy.float, 'site_id': numpy.uint32, None: str},
                               sep=',').array
    return exp_mtdata


def load_input_files(fnames, hazard, exp2geojson=True):
    """
    loads the input files and stores the data in variables
    :param fnames: file names + paths to be loaded (dictionary with keys:['exp_fname'], ['imfields_fname'], ['cons_fname'])
    :param hazard: type of the hazard that is examined. It is used for filtering the consequences
    :param exp2geojson: if True the exposure model will be saved as geojson
    :return exp_assets: assets found in the exposure model
            imfield_data: im field dataset
            cons: consequences for all asset taxonomies of interest
            exp_mtdata: site mtdata for the exposure model (export only if sites_fname is key in the fnames dictionart)
    """
    # read the sites file
    exp_mtdata = load_exposure_mtdata(fnames['sites_fname'])
    # get the assets from the exposure model
    exp_assets = read_exposure_model(fnames['exp_fname'], exp_mtdata, save_geojson=exp2geojson)
    # read the ground motion fields
    ftype = fnames['imfields_fname'].split('.')[-1]
    if ftype == 'h5' or ftype == 'hdf5':
        imfield_data = h5py.File(fnames['imfields_fname'], 'r')
    else:
        raise ImportError('unknown %s type of the input IM filed, only h5 and hdf5 are supprted' %ftype)

    # read consequence files
    cons = get_consequences(fnames['cons_fnames'], hazard)

    return exp_assets, imfield_data, cons, exp_mtdata



def read_inputparamsforfiltering(fpath, fname, hazard):
    """
    reads the input parameters that are stored in the input_params.json file and will be used for filtering the
    events. For the seismic hazard, the required parameters are:
    1. min_magnitude: minimum magnitude of the seismic event
    2. max_magnitude: maximum magnitude of the seismic event
    3. min_distance: minimum distance of the earthquake's hypocenter to the location defined in the ref_coords
    4. max_distance: maximum distance of the earthquake's hypocenter to the location defined in the ref_coords
    5. ref_coords: coordinates of the reference point from which the distance is computed
    returns: the imput parameters. If any of them is not defined in the inputs file, then it is set as None
    """
    if hazard == "seismic":
        req_params = ['min_magnitude', 'max_magnitude', 'min_distance', 'max_distance', 'ref_coords', 'IM_threshold']
        input_params =  dict([(key, []) for key in req_params])
        # define the full path + name of the file
        fullfile = os.path.join(fpath, fname)
        # load the input file
        params = read_json(fullfile)
        for req_param in req_params:
            if req_param not in params:
                input_params[req_param] = None
            elif params[req_param] == 'None':
                input_params[req_param] = None
            else:
                input_params[req_param] = params[req_param]
        return input_params
    else:
        raise Exception('only seismic hazard is supported')



def read_inputparamsforplotting(fpath, fname):
    """
    reads the parameters that are needed for plotting the events
    :param fpath: path where the file with the input parameters is stored
    :param fname: name of the file where the input parameters are stored
    """
    # required parameters:
    # eventID: ID of the event
    # asset_name: name of the asset
    # realization_id: id of the recovery realization to be shown
    req_params = ['event_id', 'asset_name', 'realization_id']
    input_params = dict([(key, []) for key in req_params])
    # define the full path + name of the file
    fullfile = os.path.join(fpath, fname)
    # load the input file
    params = read_json(fullfile)
    for req_param in req_params:
        if req_param not in params:
            input_params[req_param] = None
        else:
            input_params[req_param] = params[req_param]
    return input_params




def read_IMvalue_type(fpath, fname):
    """
    reads the IM value and the type of the IM
    :param fpath: path where the file with the input parameters is stored
    :param fname: name of the file where the input parameters are stored
    """
    # required parameters:
    # IMtype: type of the IM
    # IMvalue: value of the IM
    req_params = ['IM_type', 'IM_value', 'magnitude', "rupture_lon", "rupture_lat"]
    input_params = dict([(key, []) for key in req_params])
    # define the full path + name of the file
    fullfile = os.path.join(fpath, fname)
    # load the input file
    params = read_json(fullfile)
    for req_param in req_params:
        if req_param not in params:
            raise Exception("%s must be defined in the %s file" % (req_params, fname))
        else:
            input_params[req_param] = validators[req_param](params[req_param])

    return input_params['IM_type'], input_params['IM_value'],  input_params['magnitude'], input_params["rupture_lon"], input_params["rupture_lat"]


def IMvalue2IMfield(IMtype, IMvalue, magnitude, rupture_lon, rupture_lat, site_mtdata, outfname):
    """
    convert an IM value to an .h5 file where the ground motion field is stored as well as the location ofthe rupture
    :param IMtype: type of the IM e.g. PGA
    :param IMvalue: IM value to be assumed constant for all points
    :param site_mtdata: sites to be included in the ground motion field
    :param rup_location: a dictionary with 'lon' and 'lat' of the rupture location. If it is empty then the rupture
                            is assumed to be located at the central point of the site_mtdata file
    :param outfname: name of the output file where the ground motion fields will be stored
    """
    #events
    events_dtype = numpy.dtype([('id', '<u4'), ('rup_id', '<u4'), ('rlz_id', '<u2'), ('year', '<u2'), ('ses_id', '<u2') ])
    # event id = 1, realization, rupture, ses = 1
    events = numpy.ones(1, events_dtype)

    ruptures_dtype = numpy.dtype([('id', '<u4'), ('serial', '<u4'), ('srcidx', '<u2'), ('grp_id', '<u2'), ('code', 'u1'), ('n_occ', '<u2'),
             ('mag', '<f4'), ('rake', '<f4'), ('occurrence_rate', '<f4'), ('minlon', '<f4'), ('minlat', '<f4'),
             ('maxlon', '<f4'), ('maxlat', '<f4'), ('hypo', '<f4', (3,)), ('gidx1', '<f4'), ('gidx2', '<f4'),
             ('sx', '<f4'), ('sy', '<f4'), ('e0', '<f4'), ('e1', '<f4')])
    ruptures = numpy.ones(1, ruptures_dtype)
    ruptures['mag'] = magnitude
    ruptures['rake'] = numpy.nan
    ruptures['minlon'] = rupture_lon
    ruptures['maxlon'] = rupture_lon
    ruptures['minlat'] = rupture_lat
    ruptures['maxlat'] = rupture_lat
    ruptures['hypo'] = [rupture_lon, rupture_lat, numpy.nan]
    ruptures['gidx1'] = numpy.nan
    ruptures['gidx2'] = numpy.nan
    ruptures['sx'] = numpy.nan
    ruptures['sy'] = numpy.nan
    ruptures['e0'] = numpy.nan
    ruptures['e1'] = numpy.nan


    site_col_dtype = numpy.dtype([('sids', '<u4'), ('lon', '<f8'), ('lat', '<f8'), ('depth', '<f8'), ('vs30', '<f8'), ('vs30measured', '?')])
    site_col = numpy.zeros(len(site_mtdata['lon']), site_col_dtype)
    site_col['lon'] = site_mtdata['lon']
    site_col['lat'] = site_mtdata['lat']
    site_col['sids'] = site_mtdata['site_id']
    site_col['depth'] = numpy.nan
    site_col['vs30'] = numpy.nan
    site_col['vs30measured'] = numpy.nan

    # ground motion field data
    gmf_dtype = numpy.dtype([('sid', '<u4'), ('eid', '<u4'), ('gmv', '<f4', (1,))])
    gmf = numpy.zeros(len(site_mtdata['site_id']), gmf_dtype)
    gmf['sid'] = site_mtdata['site_id']
    gmf['eid'] = 1
    gmf['gmv'] = IMvalue

    # gmf types
    gmf_type_dtype = numpy.dtype('O')
    gmf_type = numpy.zeros(1, gmf_type_dtype)
    gmf_type = IMtype

    # generates the IM field dataset
    hf = h5py.File(outfname, 'w')
    hf.create_dataset('events', data=events)
    hf.create_dataset('ruptures', data=ruptures)
    hf.create_dataset('sitecol', data=site_col)
    gmf_data_hf = hf.create_group('gmf_data')
    gmf_data_hf.create_dataset('data', data=gmf)
    gmf_data_hf.create_dataset('imts', data=gmf_type)
