"""
- - - - - - - - - - - - - - - - -  IMPACT ASSESSMENT TOOL - - - - - - - - - - - - - - - - - - - - -
This code is a very simple one that can be used for estimating the consequences on a scenario basis. Specifically,
for each scenario, the consequences are determined for all assets that are vulnerable to the specific type of hazard.
Typically, assets that belong to the same taxonomy are not expected to experience the same consequences for a given
event thus the consequences should be randomly rearranged (if we assume that correlation = 0).
Updated 2020/09/11 by Akrivi Chatzidaki so that it can read the new input file, save the outputs in json, geotiff and geojson files,
                    and load the input files from middleware
Updated 2020/09/19 by Akrivi Chatzidaki: added the option of hazard2exppoints_consistency for the HYPERION case where
                                         the site IDs of the exposure and the IM fields are not consistent. We assume
                                         that the gmfs are following a grid
Updated 2020/10/20 by AC: modify it so that it can also be used for Infrastress

"""
import pathlib
import os
from consequences import get_consequences_by_event_all_assets
from outputs import find_ds_per_asset_and_event, collapse_map2geojson, plot_im_field
from input import initialize_files, load_input_files, load_exposure_mtdata
from exposure import exposure_by_taxonomy
from input import read_inputparamsforplotting, read_IMvalue_type, IMvalue2IMfield

if __name__ =='__main__':
    demo_name = 'Motoroil'
    hazard = 'seismic'

    # Added 2020/10/20 by AC:
    # In INFRASTRESS the IM values of the ground motion field are constant for all locations of interest, so we added
    # a pre-processing phase to convert this IM value to an .h5 file with the ground motion field so that the set of
    # files prepared for PANOPTIS can be used without problems. There is no need in this case to filter the events since
    # only one will be generated (thus we only need to run the ImpactAssessment tool)
    # The input IM type and IM value is assumed to be stored in a file named: input_params_IMfield.json
    # I added this flag to be set to True if this process should be followed
    IMvlaues2gmf = True


    # --------- INITIALIZE FILES: download input files if they don't exist ---------
    # initialization step: download and rename the files from the middleware if they do not exist
    # in the InputFiles folder
    main_path = pathlib.Path(__file__).parent.absolute()
    infiles_path = os.path.join(main_path, 'InputFiles')
    fnames = {"exp_fname": demo_name + '_exposure.json',
              "sites_fname":  demo_name + '_exposure_mtdata.csv',
              "cons_fnames": demo_name+'_consequences.json',
              "imfields_fname": demo_name +'_'+hazard +'_IMfields_00.h5'}



if IMvlaues2gmf:
    # load the values of the ground motion field
    IMtype, IMvalue, magnitude, rupture_lon, rupture_lat = read_IMvalue_type(infiles_path, 'input_params_IMfield.json')
    # load the sites file (this is done here and in the following section, but it doesnt matter since
    # it is fast. We can change it if needed
    site_mtdata = load_exposure_mtdata(os.path.join(infiles_path, fnames['sites_fname']))
    # create the h5 file with the ground motion fields
    IMvalue2IMfield(IMtype, IMvalue, magnitude, rupture_lon, rupture_lat, site_mtdata, os.path.join(infiles_path, fnames["imfields_fname"]))



# load the input parameters needed for plotting the outputs
inputs = read_inputparamsforplotting(infiles_path, 'input_params_plotting.json')



# --------- FILE INITIALIZATION ---------
# it downloads the files from Middleware if they do not exist in the infiles_path folder
fnames = initialize_files(fnames, infiles_path)

# --------- LOAD INPUT FILES ---------
exp_assets, imfield_data, cons, site_mtdata = load_input_files(fnames, hazard, exp2geojson=True)

# --------- LOAD THE CONSEQUENCES AND GET THE ASSETS FOR THE TAXONOMIES DEFINED IN THE CONS FILES ---------
cons_for_hazard = cons['consequences_by_hazard'][hazard]
exp_by_taxonomy = exposure_by_taxonomy(exp_assets, cons_for_hazard, imfield_data, hazard2exppoints_consistency=True)




# --------- PLOT THE IM FIELD FOR AN EVENT ---------
# here the first event is selected
eid = inputs['event_id']

plot_im_field(eid, imfield_data, hazard, plot_gmf=True, save_output=True)


# --------- GET THE CONSEQUENCES PER ASSET FOR THE SELECTED EVENT ---------
# get consequences by asset for this event
cons_mtdata = cons['consequences_mtdata']
results, asset_ds_description = get_consequences_by_event_all_assets(eid, imfield_data, cons_for_hazard, cons_mtdata, exp_by_taxonomy)


# --------- FIND THE MOST FREQUENT DAMAGE STATE PER ASSET FOR THE SELECTED EVENT ---------
# find the most frequent damage state per asset & plot it
ds_per_asset = find_ds_per_asset_and_event(results, eid, asset_ds_description, hazard, save_output=True, plot_most_frequent_ds=False)


# --------- PLOT THE COLLAPSE MAP FOR THE SELECTED EVENT ---------
# plot collapse map or create geojson output
collapse_map2geojson(ds_per_asset, exp_assets, eid, site_mtdata, plot_collapse_map=True)

