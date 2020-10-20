"""
contains all the functions that are needed for reading and processing the consequence functions
Created by Akrivi Chatzidaki
"""
import numpy
import random

from readinput import read_json
F32 = numpy.float32
I32 = numpy.int32
S32 = numpy.dtype('U25')


def read_consequences(fname):
    """
    reads the consequence file and stores the data
    :param fname: file name + path of the consequence file to be loaded
    :returns:   cons: consequences
                cons_mt_data: metedata for the consequences
    """
    consequences = read_json(fname)
    # store the metadata of the consequence files
    try:
        cons_mtdata = consequences['mtdata']
    except KeyError:
        raise Exception('not metadata available in %s' % fname)
    try:
        cons = consequences['consequences_by_taxonomy']
    except KeyError:
        raise Exception('consequence file %s not properly defined, or missing consequences' % fname)
    return cons, cons_mtdata



def cons_by_hazard(consequences, hazard, check_dupl=True):
    """
    get the consequences for the given hazard. Steps:
    1. check for duplicate consequence entries
    2. group the consequences by hazard type
    3. obtain the consequences for the given hazard
    :param consequences:
    """
    taxo_refs = set()
    for idx, cons in enumerate(consequences):
        try:
            taxonomy = cons['asset_taxonomy']
        except KeyError:
            raise Exception('check asset taxonomies in the consequence file')

        # check if duplicate asset taxonmies exist in the consequence file
        if check_dupl and taxonomy in taxo_refs:
            raise Exception('duplicate asset taxonomy %s in the consequence file' % taxonomy)
        taxo_refs.add(taxonomy)

    # get consequences by hazard
    if isinstance(hazard, str):
        hazard = [hazard]
    cons_by_hazard = {}
    [cons_by_hazard.update({haz: {}}) for haz in set(hazard)]
    for i, cons in enumerate(consequences):
        cons2 = cons.copy()
        del cons2['asset_taxonomy']
        del cons2['hazard_type']
        try:
            cons_by_hazard[cons['hazard_type']].update({cons['asset_taxonomy']: cons2})
        except KeyError:
            # not interested about this hazard
            pass
    return cons_by_hazard



def get_consequences(fname, hazard):
    """
    get the consequences stored in the file named fname for the hazard defined in the function
    :param fname: path and name of the file where the consequences are stored
    :param hazard: hazard that is used for filtering the consequences
    :return consequences: dictionary with fields:
                    'consequences_by_hazard': where the consequences for the given hazard are stored for all asset
                                            taxonomies related to this hazard
                    'consequences_mtdata': metadata stored in the cosequence file
    """
    consequences, cons_mtdata = read_consequences(fname)

    # post-process the consequences
    consequences_by_hazard = cons_by_hazard(consequences, hazard, check_dupl=True)
    consequences = {}
    consequences.update({'consequences_by_hazard': consequences_by_hazard})
    consequences.update({'consequences_mtdata': cons_mtdata})
    return consequences



def get_cons_imlevels(consequences):
    """
    get the IM level for which the consequences have been computed for the given im_type. Herein the consequences
    for a given hazard and taxonomy are expected to be inputs of this function
    :param consequences: consequences for a given taxonomy and hazard type
    :returns imls: intensity measure levels for the given consequences
    """
    imls = numpy.zeros(len(consequences))
    for idx, cons in enumerate(consequences):
        imls[idx] = float(cons['im_level'])
    return imls



def get_consequences_by_event(events, im_values, asset_name, asset_im_levels, asset_consequences, rndnums, results):
    """
    calculates the consequences for a given event for a single asset
    :param events: id of the event(s)
    :param im_values: IM values for the events at the asset location
    :param asset_name: name of the asset that will be used to annotate the results
    :param asset_im_levels: the IM levels for which the consequences have been computed
    :param asset_consequences: a dictionary of the consequences
    :param rndnums: random numbers used for re-arranging the consequences
    :param results: dictionary to be appended with the new consequences for the given asset
    :return: event_id --> asset_name --> consequences
    """
    for ev_idx, event in enumerate(events):
        # find the index of the closest value from the im_l of the taxonomy. This is expected to work sufficiently only
        # when we have multiple stripes for the given asset. Otherwise, other tricks should be done.
        im_value = im_values[ev_idx]
        idx_closest_im = min(range(len(asset_im_levels)), key=lambda i: abs(asset_im_levels[i] - im_value.item()))
        asset_cons = asset_consequences[idx_closest_im]
        asset_cons_rrng = {}
        if len(asset_cons.keys()) > 1:
            # Tier I assets
            for i, asset_cons in enumerate(asset_cons['consequences']):
                if asset_cons['component'] != 'global':
                    asset_cons_rrng.update({asset_cons['component']: {}})
                    # re-arrange consequences for the components
                    if 'cost' in asset_cons.keys():
                        cost = [asset_cons['cost'][i] for i in rndnums]
                        asset_cons_rrng[asset_cons['component']].update({"cost": cost})

                    if 'damage_state' in asset_cons.keys():
                        damage_state = [asset_cons['damage_state'][i] for i in rndnums]
                        asset_cons_rrng[asset_cons['component']].update({"damage_state": damage_state})

                else:
                    asset_cons_rrng.update( {asset_cons['component']: {}})
                    if 'recovery' in asset_cons.keys():
                        recovery = []
                        [recovery.append(asset_cons['recovery_realizations'][kk]) for kk in rndnums]
                        asset_cons_rrng[asset_cons['component']].update({"recovery": recovery})
                    if 'cost' in asset_cons.keys():
                        cost = [asset_cons['cost'][i] for i in rndnums]
                        asset_cons_rrng[asset_cons['component']].update({"cost": cost})
                    if 'damage_state' in asset_cons.keys():
                        damage_state = [asset_cons['damage_state'][i] for i in rndnums]
                        asset_cons_rrng[asset_cons['component']].update({"damage_state": damage_state})

        else:
            asset_cons_rrng = {"global": {}}
            # Tier II assets
            if 'cost' in asset_cons['global'].keys():
                cost = [asset_cons['global']['cost'][i] for i in rndnums]
                asset_cons_rrng['global'].update({"cost": cost})

            if 'damage_state' in asset_cons['global'].keys():
                damage_state = [asset_cons['global']['damage_state'][i] for i in rndnums]
                asset_cons_rrng['global'].update({"damage_state": damage_state})

            if 'recovery' in asset_cons['global'].keys():
                recovery = {''.join(['rlz_', str(i + 1)]): asset_cons['global']['recovery'][''.join(['rlz_', str(k + 1)])]
                        for i, k in enumerate(rndnums)}
                asset_cons_rrng['global'].update({"recovery": recovery})

        # update the results with the consequences of this asset
        if str(event) in results.keys():
            results[str(event)].update({asset_name: asset_cons_rrng})
        else:
            results.update({str(event): {asset_name: asset_cons_rrng}})
    return results


def find_conss_idx(comps_data, tag, check_dupl=True):
    """
    find index where the data for the given component are stored
    :param comps_data: description of the damage states
    :param component: component for which the damage state description needs to be obtained
    :param check_dupl: True if we check the inputs for duplicate components
    :return comp_ds_descr: damage state description for the given component
    """
    dtype = numpy.dtype([(tag, S32), ('idx', I32)])
    comps_idx = numpy.zeros(len(comps_data), dtype)
    comp_refs = set()
    for i, comps in enumerate(comps_data):
        comp_name = comps[tag]
        if check_dupl and comp_name in comp_refs:
            raise Exception('duplicate component %s ' % comp_name)
        comp_refs.add(comp_name)
        comps_idx[tag][i] = comp_name
        comps_idx['idx'][i] = i
    return comps_idx


def find_cons_idx(comps_data, tag, component):
    """
    find index of the cosequences for a given component
    :param comps_data: description of the damage states
    :param tag: dictionary tag
    :param component: component name
    """
    comps_idx = find_conss_idx(comps_data, tag, check_dupl=True)
    idx = numpy.where(comps_idx[tag] == component)
    return comps_idx['idx'][idx][0]


def get_consequences_by_event_all_assets(event_id, imfield_data, cons_for_hazard, cons_mtdata, exp_assets):
    """
    calculates the consequences for one or more events and all assets associated with this event
    :param event_id: id of the event for which the consequences are computed
    :param imfield_data: dataset of the IM filed
    :param cons_for_hazard: consequences associated to the hazard of interest
    :param cons_mtdata: metatdata of the consequeces
    :param exp_assets: assets of the exposure model
    :return: result, asset_ds_description
    """

    # load the IM type and the IM values
    im_type = numpy.array(imfield_data.get('gmf_data').get('imts')).item()
    im_fields = imfield_data.get('gmf_data').get('data')
    idx_events = (im_fields['eid'] == event_id)
    im_values_all = im_fields['gmv'][idx_events]

    # generate a list of integers in the range 0-99
    Nrealizations = cons_mtdata['Nrealizations']
    nums = list(range(Nrealizations))

    # compute the consequences for each ground motion field
    results = {}
    rnd_seed = 0
    asset_ds_description = {}
    for tax_key in cons_for_hazard:
        # loop over each taxonomy
        # find the assets of the exposure model that belong to this taxonomy
        # find the intensity measure type for the given asset taxonomy
        imt = cons_for_hazard[tax_key]['im_type']
        # check that this IM is the same as the one provided in the IM fields
        assert imt.lower() == im_type.lower(), ('the IM type of the IM fields should be the same with this of the assets')
        for asset_name, asset in exp_assets[tax_key].items():
            rnd_seed = rnd_seed+1
            random.Random(rnd_seed).shuffle(nums)
            idx_sid_event = (im_fields['sid'][idx_events] == asset['location']['hazard_sid'])
            im_values = im_values_all[idx_sid_event][0]
            # find the IM levels for which the consequences are computed the given asset taxonomy
            asset_im_levels = get_cons_imlevels(cons_for_hazard[tax_key]['iml_consequences'])
            asset_consequences = cons_for_hazard[tax_key]['iml_consequences']
            results = get_consequences_by_event([event_id], im_values, asset_name, asset_im_levels, asset_consequences, nums, results)
            global_idx = find_cons_idx(cons_for_hazard[tax_key]['component_damage_state_description'], 'component', 'global')
            asset_ds_description.update({asset_name: cons_for_hazard[tax_key]['component_damage_state_description'][global_idx]})
    return results, asset_ds_description

