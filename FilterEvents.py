"""
- - - - - - - - - - - - - - - - -  Filter events - - - - - - - - - - - - - - - - - - - - -
This tool is used for filterinf the IM fields based on the parameters defined in the input_params.json file that
is stored in the Inputs folder

Updated 2020/09/11 by Akrivi Chatzidaki so that it can read the new input file, save the outputs in json, geotiff and geojson files,
                    and load the input files from middleware
Updated 2020/09/19 by Akrivi Chatzidaki: added the option of hazard2exppoints_consistency for the HYPERION case where
                                         the site IDs of the exposure and the IM fields are not consistent. We assume
                                         that the gmfs are following a grid
Updated 2020/09/23 by Akrivi: the code is split in 2 parts: filter events and impact assessment tool
"""
import pathlib
import os
from im_fields import filter_events
from input import initialize_files, load_input_files, read_inputparamsforfiltering
from exposure import exposure_by_taxonomy

if __name__ =='__main__':
    demo_name = 'Egnatia'
    hazard = 'seismic'

    # --------- INITIALIZE FILES: download input files if they don't exist ---------
    # initialization step: download and rename the files from the middleware if they do not exist
    # in the InputFiles folder
    main_path = pathlib.Path(__file__).parent.absolute()
    infiles_path = os.path.join(main_path, 'InputFiles')
    fnames = {"exp_fname": demo_name + '_exposure_simple.json',
              "sites_fname":  demo_name + '_exposure_mtdata.csv',
              "cons_fnames": demo_name+'_consequences.json',
              "imfields_fname": demo_name +'_'+hazard +'_IMfields_45.h5'}





# --------- FILE INITIALIZATION ---------
# it downloads the files from Middleware if they do not exist in the infiles_path folder
fnames = initialize_files(fnames, infiles_path)

# --------- LOAD INPUT FILES ---------
exp_assets, imfield_data, cons, site_mtdata = load_input_files(fnames, hazard, exp2geojson=True)

# --------- LOAD THE CONSEQUENCES AND GET THE ASSETS FOR THE TAXONOMIES DEFINED IN THE CONS FILES ---------
cons_for_hazard = cons['consequences_by_hazard'][hazard]
exp_by_taxonomy = exposure_by_taxonomy(exp_assets, cons_for_hazard, imfield_data, hazard2exppoints_consistency=True)

# -------- LOADS THE INPUT PARAMETERS --------
input_params = read_inputparamsforfiltering(infiles_path, 'input_params_filtering.json', hazard)


# --------- FILTER THE EVENTS ---------
# 1. min and/or max magnitude
# 2. min and/or max distance from a site whose coordinates are defined in the ref_coords entry
# 3. IM_threshold i.e. the value of the IM that should be exceeded at any asset
event_ids_for_mag_dist = filter_events(imfield_data, cons_for_hazard, exp_by_taxonomy, min_mag=input_params['min_magnitude'],
                                      max_mag=input_params['max_magnitude'], min_dist=input_params['min_distance'], max_dist=input_params['max_distance'],
                                       ref_coords=input_params['ref_coords'], IM_threshold=input_params['IM_threshold'])

# export the events
fullout_file = os.path.join(infiles_path, 'filtered_events.txt')
with open(fullout_file, 'w') as f:
    if len(event_ids_for_mag_dist) == 0:
        f.write("None\n")
    else:
        for item in event_ids_for_mag_dist:
            f.write("%s\n" % item)

