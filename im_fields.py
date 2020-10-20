"""
Created by Akrivi Chatzidaki
"""


import numpy


def filter_events_by_imvalue(consequences, imfield_data, exp_assets, events_filtering_method=1, IM_threshold=None):
    """
    filter the events and obtain the event IDs for the events for which a IM value has been computed
    for the site of interest if events_filtering_method =1 or for those that produce an acceleration value higher
    than the IM_threshold at any asset of interest if events_filtering_method =2
    :param consequences: consequences for a given hazard
    :param imfield_data: data for the IM fields as read through the hdf5 file
    :param exp_assets: assets found in the exposure model
    :param events_filtering_method: 1 if the events that do not produce acceleration values at any asset of interets are filtered out
                                    2 if the events that do nor prodece IM value higher than the IM threshold at any location
                                    of interest are filtered out
    :param IM_thershold: threshold of the IM used to filter out the events. Needed only if events_filtering_method is
                        used
    :returns events_of_interest: event IDs for the events of interest
    """
    # load the ground motion field data
    im_fields = imfield_data.get('gmf_data').get('data')
    im_type = numpy.array(imfield_data.get('gmf_data').get('imts')).item()

    # check that IM_threshold is not defined for events_filtering_method = 1
    if events_filtering_method == 1 and IM_threshold:
        raise Warning ('IM_threshold is not taken into account for filtering the events since events_filtering_method = 1')
    events_of_interest = set()
    for tax_key in consequences:
        # loop over each taxonomy
        # find the assets of the exposure model that belong to this taxonomy
        # find the intensity measure type for the given asset taxonomy
        imt = consequences[tax_key]['im_type']
        # check that this IM is the same as the one provided in the IM fields
        assert imt.lower() == im_type.lower(), ('the IM type of the IM fields should be the same with this of the assets')
        for asset_name, asset in exp_assets[tax_key].items():
            # find the site id of the asset
            sid = asset['location']['hazard_sid']
            if events_filtering_method == 1:
                # find all the events for the given site
                idx_events = (im_fields['sid'] == int(sid))
                events = im_fields['eid'][idx_events]
            elif events_filtering_method == 2:
                idx_events = (im_fields['sid'] == int(sid))
                events1 = im_fields['eid'][idx_events]
                if len(events1) == 0:
                    pass
                im_values = im_fields['gmv'][idx_events]
                idx_imthreshold = (im_values[:, 0] >= IM_threshold)
                events = events1[idx_imthreshold]
            [events_of_interest.add(event) for event in events]
    assert len(events_of_interest) > 0, ('all events are filtered out')
    return events_of_interest


def fiter_imfield_data(imfield_data, events_of_interest):
    """
    filters the data stored in the hdf5 file and keeps only data for the events of interest
    :param imfield_data: data of the IM fields as stored in the hdf5 file\
    :param events_of_interest: events of interest for which we will store the data of the IM fields
    :returns :
    """
    # get the data that link the event IDs with the rupture IDs
    event_mtdata = imfield_data.get('events')
    # find the rupture IDs for the given event IDs
    ruptures_of_interest_idx = [list(event_mtdata['id']).index(eid) for eid in events_of_interest]
    # filtered events
    filtered_event_mtdata = event_mtdata[sorted(ruptures_of_interest_idx)]
    # find the metadata for the ruptures of interest
    rupture_mtdata = imfield_data.get('ruptures')
    ruptures_info_idx = [list(rupture_mtdata['id']).index(rupid) for rupid in filtered_event_mtdata['rup_id']]
    # filter the rupture mtdata
    filtered_rupture_mtdata = numpy.array(rupture_mtdata)[sorted(ruptures_info_idx)]

    return filtered_event_mtdata, filtered_rupture_mtdata


def filter_events(imfield_data, cons_for_hazard, exp_assets, min_mag=4.0, max_mag=None, IM_threshold=0.01, min_dist=None, max_dist=None, ref_coords={}):
    """
    this function filters the events based on the minimum magnitude, the maximum magnitude, the minimum distance
    the maximum distance (optional) and the lower IM threshold value for any of the assets
    :param imfield_data:
    :param cons:
    :param exp_assets:
    :return:
    """
    # find the events of interest of the given demo. We have two options for this:
    # events_filtering_method = 1:  those with acceleration values >  0 for any of assets
    # events_filtering_method = 2: those with acceleration higher than a certain threshold at any of the assets
    if not IM_threshold:
        events_filtering_method = 1
    else:
        events_filtering_method = 2


    events_of_interest = filter_events_by_imvalue(cons_for_hazard, imfield_data, exp_assets, events_filtering_method, IM_threshold)

    # filter the IM fields so that they contain info only about the events of interest
    filtered_event_mtdata, filtered_rupture_mtdata = fiter_imfield_data(imfield_data, events_of_interest)

    # filter the events per magnitude (optional)
    mags = filtered_rupture_mtdata['mag']
    if min_mag and max_mag:
        rup_idx = (mags >= min_mag) & (mags <= max_mag)
    elif min_mag and not max_mag:
        rup_idx = (mags >= min_mag)
    elif max_mag and not min_mag:
        rup_idx = (mags <= max_mag)
    else:
        rup_idx = (mags == mags)
    filtered_rupture_mtdata_by_mag =  filtered_rupture_mtdata[rup_idx]

    # filter the events per distance
    if min_dist or max_dist:
        assert ref_coords, 'filtering the events by distance needs also a reference point'
        cent_lon = ref_coords['lon']
        cent_lat = ref_coords['lat']

        import geopy.distance
        dist = numpy.array([geopy.distance.distance((filtered_rupture_mtdata_by_mag['hypo'][:, :2][i]), (cent_lon, cent_lat)).km
                for i in range(0, len(filtered_rupture_mtdata_by_mag['mag']))])
        if min_dist and max_dist:
            rup_idx2 = (dist >= min_dist) & (dist <= max_dist)
        elif min_dist and not max_dist:
            rup_idx2 = (dist >= min_dist)
        elif max_dist and not min_dist:
            rup_idx2 = (dist <= max_dist)
        ruptures = filtered_rupture_mtdata_by_mag['id'][rup_idx2]
    else:
        ruptures = filtered_rupture_mtdata_by_mag['id']

    # get the event IDs for the given rupture
    event_idx_ids_for_mag_dist = [list(filtered_event_mtdata['rup_id']).index(r) for r in ruptures]
    event_ids_for_mag_dist = filtered_event_mtdata['id'][event_idx_ids_for_mag_dist]

    return event_ids_for_mag_dist


