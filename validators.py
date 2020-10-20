"""

"""
import numpy
import valid

validators = {
    'IM_type': valid.IM_type,
    'IM_value': valid.positivefloat,
    "rupture_lon":	valid.longitude,
    "rupture_lat": valid.latitude,
    'magnitude': valid.positivefloat,
    'asset_name': valid.asset_name,
    'group_name': valid.asset_name,
    'description': valid.utf8_not_empty,
    'taxonomy': valid.asset_name,
    'number_value': valid.compose(valid.positivefloat, valid.nonzero),
    'number_unit': valid.unit,
    'asset_type': valid.Choice('point', 'area', 'linear', 'Point', 'Area', 'Linear'),
    'group_type': valid.Choice('area'),
    'location_sid': valid.positiveint_or_list,
    'location_type': valid.Choice('individual', 'start_end', 'boundaries'),
    'tags': valid.namelist,
    'cost_type': valid.Choice('total', 'per_asset'),
    'cost_unit': valid.utf8,
    'cost_ref_year': valid.positiveint,
    'cost_value': valid.compose(valid.positivefloat, valid.nonzero),
    'location_hzrd_ctrl_pnt': valid.positiveint,
    'time_unit': valid.utf8,
    'figures': valid.namelist,
    'location_orient': valid.float_,
    'category': valid.utf8,
    'tagNames': valid.namelist,
    'id': valid.exposure_id,
    'dir': valid.positiveint
}



def valid_data(data, key=''):
    """
    validates that the input data are of the rigght format
    """
    # the names of the following keys will be composed to be validated
    comp_names = ['number', 'cost', 'time', 'location']

    if isinstance(data, dict):
        for key, dt in data.items():
            if key == 'dirs':
                # update the validator with the dirs found in the metadata of the file
                dirs = [dirs_dt['dir'] for dirs_dt in dt]
                validators.update({'dir': valid.Choice(dirs)})
                valid_data(dt, key)
            elif key in comp_names:
                dt2 = dt.copy()
                for d in dt.keys():
                    dt2['_'.join((key, d))] = dt2.pop(d)
                valid_data(dt2, key)
            else:
                valid_data(dt, key)
    elif isinstance(data, list):
        for dt in data:
            valid_data(dt)
    else:
        if key == '':
            # we have a list of values
            pass
        else:
            validators[key](data)



def valid_location(asset, type_tag, site_mtdata, generate_geojson):
        # check that the asset type and the location types are consistent
        if asset[type_tag].lower() == 'point':
            try:
                assert asset['location']['type'] == 'individual' or asset['location']['type'] == 'start_end', (
                    'for point assets the location sitds can be individual or start_end, not boundaries. Check asset %s' %
                    asset['asset_name'])
            except KeyError:
                pass

        if asset[type_tag].lower() == 'linear':
            try:
                assert (asset['location']['type'] == 'individual' or asset['location']['type'] == 'start_end'), (
                    'for linear assets the location sitds can be individual or start_end, not boundaries. Check asset %s' %
                    asset['asset_name'])
            except KeyError:
                raise Exception('location type is mandatory for linear assets, check %s' % asset['asset_name'])
        if asset[type_tag].lower() == 'area':
            assert asset['location']['type'] == 'boundaries', (
                    'for area assets the location sid type must be boundaries. Check asset %s' % asset['asset_name'])
            assert 'hzrd_ctrl_pnt' in asset[
                'location'].keys(), 'the hazard control point is mandatory for area assets, check %s ' % asset['asset_name']

        if not isinstance(asset['location']['sid'], int) and len(asset['location']['sid']) > 1:
            assert set(['sid', 'type']).issubset(asset['location']), (
                    'location sid and type are mandatory for asset %s' % asset['asset_name'])

            # check that the sites have been defined in the site mtdata file
            idx = [numpy.nonzero(site_mtdata['site_id'] == sid)[0][0] for sid in asset['location']['sid']]
            assert len(idx) == len(asset['location']['sid']), (
                    'the site ids of asset %s must also exist in the site metadata file' % asset['asset_name'])

            if asset['location']['type'] == 'start_end':
                assert len(asset['location']['sid']) <= 2, (
                        'for start_end location type two site ids must be defined, not more. Check asset %s' % asset[
                        'asset_name'])

                if generate_geojson:
                    idx2 = [numpy.nonzero((site_mtdata['site_id'] >= min(asset['location']['sid'])) & (site_mtdata['site_id'] <= max(asset['location']['sid'])))]
                    idx = idx2[0][0]
                    assert len(idx) >= 2, 'check asset %s site ids' % asset['asset_name']
                    coordinates = [[(float(site_mtdata['lon'][i])), (float(site_mtdata['lat'][i]))] for i in idx]
                    asset['location'].update({'geometry': {"type": "LineString",
                                                            "coordinates": coordinates}})


            elif asset['location']['type'] == 'boundaries':
                assert len(asset['location']['sid']) > 2, (
                        'for start_end location type two site ids must be defined, not more. Check asset %s' % asset[
                        'asset_name'])
                if generate_geojson:
                    idx.append(idx[0])
                    coordinates = [[[(float(site_mtdata['lon'][i])), (float(site_mtdata['lat'][i]))] for i in idx]]
                    asset['location'].update({'geometry': {"type": "Polygon",
                                                            "coordinates": coordinates}})

            elif asset['location']['type'] == 'individual':
                if generate_geojson:
                    coordinates = [[(float(site_mtdata['lon'][i])), (float(site_mtdata['lat'][i]))] for i in idx]
                    asset['location'].update({'geometry': {"type": "LineString",
                                                            "coordinates": coordinates}})

        else:
            if isinstance(asset['location']['sid'], list) and len(asset['location']['sid']):
                sid = asset['location']['sid'][0]
            else:
                sid = asset['location']['sid']
            idx = numpy.nonzero(site_mtdata['site_id'] == asset['location']['sid'])
            assert len(idx) == 1, (
                    'the site ids of asset %s must also exist in the site metadata file' % asset['asset_name'])
            if generate_geojson:
                coordinates = [(float(site_mtdata['lon'][idx][0])), (float(site_mtdata['lat'][idx][0]))]
                asset['location'].update({'geometry': {"type": "Point",
                                                        "coordinates": coordinates}})



def valid_asset(asset, site_mtdata, rqd_keys, add_keys, rqd_exp_cat_keys):
    assert set(rqd_keys).issubset(asset.keys()), ('the %s are mandatory tags for asset %s ' % (rqd_exp_cat_keys, asset['asset_name']))
    assert set(['value', 'unit']).issubset(asset['number']), (
                'number unit and value are mandatory for asset %s' % asset['asset_name'])
    assert set(['type', 'value']).issubset(asset['cost']), (
                'cost type and value are mandatory for asset %s' % asset['asset_name'])
    if 'tags' in add_keys.keys():
        assert 'tags' in asset.keys(), 'tags are mandatory for asset %s belonging to an exposure category with tagNames' % \
                                       asset['asset_name']
        if not isinstance(asset['tags'], list):
            assert 1 == add_keys['tags'], (
                    'one tag must be defined for each tagName, check asset %s' % asset['asset_name'])
        else:
            assert len(asset['tags']) == add_keys['tags'], (
                    'one tag must be defined for each tagName, check asset %s' % asset['asset_name'])

    if 'location' in rqd_keys:
        valid_location(asset, 'asset_type', site_mtdata, generate_geojson=True)

