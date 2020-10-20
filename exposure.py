"""
Created by Akrivi Chatzidaki
Last updated 2020/09/19: added the exposure to geojson option
"""
import numpy
import itertools
import pandas as pd
from geopy import distance
from readinput import read_json
from outputs import exposure2geojson, exposure2geojson_withoutgeomertytags
import validators



def valid_exposure(exposure, site_mtdata, check_dupl=True, generate_geojson=True):
    """
    validates the exposure model provided by the user
    :param exposure: exposure model as read from the json file
    :param site_mtdata: metadata of the exposure model
    :param check_dupl: if true we check for duplicate asset names/groups
    :param generate_geojson: if true the geojson file is generated
    """
    # required keys defined for the exposure category
    rqd_exp_cat_keys = ['category', 'description', 'conversions']
    # required keys for the assets
    rqd_asset_keys = ['asset_name', 'number', 'taxonomy', 'asset_type', 'location', 'cost']
    # required keys for the groups
    rqd_group_keys = ['group_name', 'group_type', 'location', 'assets']
    # required keys for the asssets of the groups
    rqd_groupasset_keys = ['asset_name', 'number', 'taxonomy', 'cost']

    # validate that the entries of the exposure model have the appropriate fromat, as defined by the validators
    for key, data in exposure['ExposureModel'].items():
        validators.valid_data(data, key=key)

    # exposure categories
    exp_categories = set()
    assets = set()
    groups = set()
    for exp_cat in exposure['ExposureModel']['exposure_categories']:
        # validate that the required keys have been defined fro the exposure model
        for key in rqd_exp_cat_keys:
            assert key in exp_cat.keys(), '%s is mandatory for exposure category %s' % (key, exp_cat['category'])
        category = exp_cat['category']
        if check_dupl and category in exp_categories:
            raise Exception('duplicate category in the exposure model %s' % category)
        exp_categories.add(category)

        # validate that the costs have been defined properly, without any missing data
        try:
            assert 'cost' in exp_cat['conversions']['costTypes'].keys(), 'cost should be defined in the costTypes of exposure category %s' % exp_cat['category']
            assert 'unit' in exp_cat['conversions']['costTypes']['cost'].keys(), 'unit is mandatory for cost, check exposure category %s' % exp_cat['category']
            assert 'ref_year' in exp_cat['conversions']['costTypes']['cost'].keys(), 'ref_year is mandatory for cost, check exposure category %s' % exp_cat['category']
        except KeyError:
            raise KeyError('the costTypes, cost, unit and ref_year are mandatory for the exposure model %s' % exp_cat['category'])
        # additional keys
        add_keys = {}
        if 'tagNames' in exp_cat.keys():
            add_keys.update({'tags': len(validators.validators['tagNames'](exp_cat['tagNames']))})

        if 'assets' in exp_cat.keys():
            for asset in exp_cat['assets']:
                validators.valid_asset(asset, site_mtdata, rqd_asset_keys, add_keys, rqd_exp_cat_keys)
                asset_name = asset['asset_name']
                if check_dupl and asset_name in assets:
                    raise Exception('duplicate asset name in the exposure model %s' % asset_name)
                assets.add(asset_name)

        if 'groups' in exp_cat.keys():
            for group in exp_cat['groups']:
                for key in rqd_group_keys:
                    assert key in group.keys(), '%s is mandatory for exposure category %s' % (key, group['group_name'])

                # valid group location
                validators.valid_location(group, 'group_type', site_mtdata, generate_geojson)

                # check fro duplicate group entries
                group_name = group['group_name']
                if check_dupl and group_name in groups:
                    raise Exception('duplicate asset name in the exposure model %s' % group_name)
                groups.add(group_name)

                for asset in group['assets']:
                    validators.valid_asset(asset, site_mtdata, rqd_groupasset_keys, add_keys, rqd_exp_cat_keys)
                    asset_name = asset['asset_name']
                    if check_dupl and asset_name in assets:
                        raise Exception('duplicate asset name in the exposure model %s' % asset_name)
                    assets.add(asset_name)
        assert ('assets' in exp_cat.keys()) or ('groups' in exp_cat.keys()), ('assets or groups (of assets) are mandatory for exposure category %s' % exp_cat['category'])
        print('valid exposure! :)')
    return exposure

def read_exposure_model(exposure_fname, site_mtdata, save_geojson=True):
    """
    reads the exposure model and stores all the assets found inside it. The asset category each asset belongs to is
    added in the tags (not used, neither exported but it can be for filtering purposes)
    :param exposure_fname: path and name of the exposure file
    :param site_mtdata4valid: site metadata for validating the exposure model
    :param save_geojson: if True the exposure will be saved as geojson
    :return assets: returns the assets found in the exposure model
    """
    # read the exposure json file
    exp = read_json(exposure_fname)

    exposure = valid_exposure(exp, site_mtdata, check_dupl=True, generate_geojson=True)
    if save_geojson:
        expfname = exposure_fname.split('.')[-2].split('\\')[-1]
        expfname = ('.').join((expfname, 'geojson'))
        import os
        fpath = os.path.dirname(exposure_fname)
        exposure2geojson_withoutgeomertytags(exposure, expfname, fpath= fpath )

        exposure2geojson(exp, expfname)
    # get the assets of the exposure model
    assets = {}
    for data in exp['ExposureModel']['exposure_categories']:
        category = data['category']
        tagNames = ' '.join([data['tagNames'], 'exposure_category'])
        for asset_data in data['assets']:
            asset_name = asset_data['asset_name']
            try:
                asset_data['tags'].append(category)
            except AttributeError:
                if isinstance(asset_data['tags'], str):
                    asset_data['tags'] = [asset_data['tags'],category]
            except KeyError:
                # no tags for this asset
                asset_data.update({'tags': [category]})
            asset_data.pop('asset_name')
            assets.update({asset_name: asset_data})
    return assets



def get_assets_by_taxonomy(assets, taxonomy):
    """
    gets the assets from the exposure model that belong to the given taxonomy
    :param assets: assets stored in the exposure model
    :param taxonomy: taxonomy used for filtering the assers
    :returns: dictionary with the asset name and the data for this asset
    """
    for asset_name, asset_data in assets.items():
        if asset_data['taxonomy'] == taxonomy:
            yield {asset_name: asset_data}



def find_asset_sid(location, asset_type):
    """
    finds the site id of the given asset from the data stored in the exposure model
    :param location: asset's location
    :param asset_type: type of the asset. Three options are available: area, point, linear.
    :return: the site ID that defines the hazard for the given asset
    """
    if asset_type.lower() == 'point':
        # for point assets we can either define directly the site ID where the asset is located
        # or for assets for which "we would draw a line on a map" such as the bridges we can define the
        # site IDs of the beginning and the end of this line. The hzrd_ctrl_pnt can be used to define the site
        # id whose IM value will be used for the asset. If it's not defined, then the first point of the sid list
        # will be obtained
        if len(location['sid']) == 1:
            site_id = location['sid']
        else:
            try:
                site_id = location['hzrd_ctrl_pnt']
            except KeyError:
                try:
                    site_id = int(location['sid'])
                except TypeError:
                    site_id = numpy.sort(location['sid'])[0]

    elif asset_type.lower() == 'area':
        site_id = location['hzrd_ctrl_pnt']
    return site_id


def exposure_by_taxonomy(exp_assets, cons_for_hazard, imfield_data, hazard2exppoints_consistency, site_mtdata=None, max_allowable_dist=None):
    """
    gets only the assets that belong to the taxonomies defined in the consequence model
    :param exp_assets: assets of the exposure model
    :param cons_for_hazard: consequences for the hazard that is examined
    :param imfield_data: im field data
    :param hazard2exppoints_consistency: if True then the site IDs of the exposure model are consistent to these of the
                                        hazard. If False they are not
    :param site_mtdata: site IDs, lon and lat of the hazard points. This is needed only if hazard2exppoints_consistency=False
    :param max_allowable_dist: maximum allowable distance between the site of the asset and the hazard that can be used
                                if hazard2exppoints_consistency is False
    :return: the assets of the exposure model that belong to the taxonomies defined in the cosequence files
    """
    assets_by_taxonomy = {}

    imfield_sites = imfield_data.get('sitecol')
    imfield_sites_coords = pd.DataFrame({'lat': imfield_sites['lat'], 'lon': imfield_sites['lon']})
    imfield_site = list(zip(imfield_sites_coords['lat'], imfield_sites_coords['lon']))
    # maximum allowable distance to match an asset to the hazard
    for tax_key in cons_for_hazard:
        assets_by_taxonomy.update({tax_key: {}})
        # loop over each taxonomy
        # find the assets of the exposure model that belong to this taxonomy
        # find the intensity measure type for the given asset taxonomy
        assets = get_assets_by_taxonomy(exp_assets, tax_key)
        for asset in assets:
            asset_name = list(asset.keys())[0]
            sid = find_asset_sid(asset[asset_name]['location'], asset[asset_name]['asset_type'])
            if hazard2exppoints_consistency is False:
                coords_idx = (site_mtdata['site_id'] == sid)
                assert len(site_mtdata['site_id'][coords_idx]) == 1, 'check site id of asset %s ' % asset_name
                lon = site_mtdata['lon'][coords_idx][0]
                lat = site_mtdata['lat'][coords_idx][0]
                # Creating 2 sample dataframes with 10 and 5 rows of lat, long columns respectively
                asset_site_coords = pd.DataFrame({'lat': [lat], 'lon': [lon]})
                # Zip the 2 columns to get (lat, lon) tuples for target in df1 and point in df2
                asset_site = list(zip(asset_site_coords['lat'], asset_site_coords['lon']))
                # Prexposure_by_taxonomyoduct function in itertools does a cross product between the 2 iteratables
                # You should get things of the form ( ( lat, lon), (lat, lon) ) where 1st is target, second is point. Feel free to change the order if needed
                product = list(itertools.product(imfield_site, asset_site))
                # starmap(function, parameters) maps the distance function to the list of tuples. Later you can use i.miles for conversion
                geo_dist = [i.km for i in itertools.starmap(distance.distance, product)]
                min_dist_idx = min(range(len(geo_dist)), key=geo_dist.__getitem__)
                assert geo_dist[
                           min_dist_idx] < max_allowable_dist, 'the closest hazard point to asset %s is more than %skm away' % (
                asset_name, str(max_allowable_dist))
                hazard_sid = imfield_sites['sids'][min_dist_idx]
            else:
                try:
                    hazard_sid = int(sid)
                except TypeError:
                    hazard_sid = sid[0]
                    assert isinstance(hazard_sid, int), "check asset's %s sid" % asset
            asset[asset_name]['location'].update({'hazard_sid': hazard_sid})
            assets_by_taxonomy[tax_key].update({asset_name: asset[asset_name]})
    return assets_by_taxonomy


