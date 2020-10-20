"""
all functions needed to create the outputs are stored here
Created by Akrivi Chatzidaki
Last updated 2020/09/19: added the exposure to geojson option
Last updated 2020/09/23: saves also the png images for the most frequent damage state per asset and the recovery
                         realization
Last updated 2020/10/20 by AC: added the transparancy option in the colors.txt file that is used to color the geotiff
                                images. Now this can work for non-rectangular ground motion fields!
"""

import json
import numpy
from collections import Counter
from time import sleep
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pathlib
import os
import glob
from consequences import find_cons_idx
import valid
from validators import valid_location

#results path
main_path = pathlib.Path(__file__).parent.absolute()
results_path = os.path.join(main_path, 'Results')
# make the directory if it does not exist.
try:
    os.makedirs(results_path)
except FileExistsError:
    # if this folder exists, then delete all entries stored in it (they come from another analysis)
    files = glob.glob(results_path+'\*')
    for f in files:
        os.remove(f)


def plt_collapse_map(ds_per_asset, exposure, eid):
    """
    plot collapse map for the most frequent damage state per asset among no collapse, demolition and collapse
    :param ds_per_asset: damage states per asset
    :param exposure: exposure model (that is used to get the geometry for the assets)
    :param eid: event id for which the collapse map is displayed (used to annotate the figures)
    """
    fig = plt.figure()
    for asset in ds_per_asset.keys():
        if ds_per_asset[asset] == 'collapse':
            c = 'k'
        elif ds_per_asset[asset] == 'demolition':
            c = 'r'
        else:
            c = 'g'
        # find the location of the asset
        coords = exposure[asset]['location']['geometry']['coordinates']
        if exposure[asset]['location']['geometry']['type'] == 'LineString':
            lon = [coords[i][0] for i in range(len(coords))]
            lat = [coords[i][1] for i in range(len(coords))]
            plt.plot(lon, lat, c=c)
        elif exposure[asset]['location']['geometry']['type'].lower() == 'point':
            plt.plot(coords[0], coords[1], marker="o", c=c)
        else:
            raise ('area assets not supported yet')

        black_patch = mpatches.Patch(color='k', label='collapse')
        red_patch = mpatches.Patch(color='red', label='demolition')
        green_patch = mpatches.Patch(color='green', label='no collapse')
        plt.legend(handles=[black_patch, red_patch, green_patch])
        plt.title('Collapse map (most frequent DS), seismic event No %s' % eid)
        plt.xlabel('Longitude (degrees)')
        plt.ylabel('Latitude (degrees)')
    plt.show()

def collapse_map2geojson(ds_per_asset, exposure, eid, site_mtdata, plot_collapse_map=True, fpath=results_path):
    """
    converts the collapse map to geojson to help antonis easily plot it
    :param ds_per_asset: damage state per asset
    :param exposure: assets of the exposure model
    :param eid: event ID for which the results are plotted
    :param site_mtdata: metadata of the sites
    :param plot_collapse_map: if True the collapse map is also plotted
    :param fpath: path where the geojson file will be stored
    :returns: a file named 'CollapseMap_'+ hazard +'_eid' + str(eid) + '.geojson' in the fpath
    """
    features_all = []
    colors = ["#000000", "#ff0000", "#2da80b"]
    damage_state_name = ["collapse", "demolition", "no collapse"]
    for asset in ds_per_asset.keys():
        # find the index of the damage state in the damage_state_name
        try:
            idx = damage_state_name.index(ds_per_asset[asset])
        except ValueError:
            if ds_per_asset[asset] == 'no damage' or ds_per_asset[asset] == 'slight' or ds_per_asset[asset] =='moderate':
                idx = 2
            elif ds_per_asset[asset] == 'extensive':
                idx = 1
            else:
                raise ValueError('check the global damage state names of the assets, unrecognized %s for asset %s' %(ds_per_asset[asset], asset))
        # get the color for this asset
        color = colors[idx]
        # find th geometry for the given asset by combining site_mtdata with the exposure model
        valid_location(exposure[asset], 'asset_type', site_mtdata, generate_geojson = True)

       # for linear assets:
        if exposure[asset]['location']['geometry']['type'] == 'LineString':
            features = {"type": "Feature", "properties": {"name": asset, "stroke": color, "stroke-width": 5,
                                                          "damage state": ds_per_asset[asset]},
                        'geometry': exposure[asset]['location']['geometry']}

        elif exposure[asset]['location']['geometry']['type'] == 'Point':
            features = {"type": "Feature", "properties": {"name": asset, "marker-color": color,
                                                          "damage state": ds_per_asset[asset]},
                        'geometry': exposure[asset]['location']['geometry']}
        else:
            features = {"type": "Feature", "properties": {"name": asset, "damage state": ds_per_asset[asset]},
                                'geometry': exposure[asset]['location']['geometry']}

        features_all.append(features)
    geojson_dict = {"type": "FeatureCollection", "features": features_all}
    #fname = 'CollapseMap_'+ hazard +'_eid' + str(eid) + '.geojson'
    fname = 'CollapseMap.geojson'
    fullfname = os.path.join(fpath, fname)
    # write the results in a json file
    with open(fullfname, 'w') as fp:
        json.dump(geojson_dict, fp)

    if plot_collapse_map:
        plt_collapse_map(ds_per_asset, exposure, eid)


# - - - - - - - - recovery realizations - - -  - - -

def recovery_rlz2json(results, hazard, eid, rlz_id, asset_name, maxspeed, speed_limit_units, time_units, save_output=True, plot_rlz=True, fpath=results_path):
    """
    plot/store data on a recovery realizations for a given asset and event
    :param results: consequences
    :param hazard: hazard that is examined
    :param eid: event id for which the realization is plotted
    :param rlz_id: id of the realization that will be shown ( index = id-1)
    :param asset_name: name of the asset for which the realization will be displayed
    :param maxspeed: maximum allowable speed limit per lane
    :param time_units: units of time (e.g. days)
    :param speed_limit_units: units for the speed limit (e.g. km/h)
    :return  file named hazard + '_eid' + str(eid) + '_' + asset_name + '_recovery_rlz_' + str(rlz_id) + '.json' in the
            fpath
            Update 2020/09/23: name: realization so that it can be generic
    """
    recovery_rlz = results[str(eid)][asset_name]['global']['recovery'][rlz_id-1]
    tevent = 10.
    maxspeed= float(maxspeed)

    time = []
    for idx, s1 in enumerate(recovery_rlz['time']):
        if idx == 0:
            time.append(float(recovery_rlz['time'][idx])+tevent)
        elif idx == len(recovery_rlz['time'])-1:
            time.append(float(recovery_rlz['time'][idx])+tevent)
        else:
            time.append(float(recovery_rlz['time'][idx]) + tevent)
            time.append(float(recovery_rlz['time'][idx]) + tevent)
    time.insert(0, tevent)
    time.insert(0, 0)
    time.append(max(time))
    time.append(max(time) + 5)
    recovery_out = {
        "figure_data": {"description": 'recovery realization %s for asset %s, %s event No %s' % (rlz_id, asset_name, hazard, eid),
         "type": "linear",
         "data":[],
         "labels": {"x": "time (" + time_units+ ")",
                    "y": "maximum allowable speed limit (" + speed_limit_units + ")"},
         "legend": []}}

    # figure preparation
    linetype = ['-', '--']
    plt.figure()
    plt.xlabel('time (' + time_units + ")")
    plt.ylabel('maximum allowable speed limit per lane (' + speed_limit_units + ")")

    for i, rec in enumerate(recovery_rlz['speed_limit']):
        speed = []
        for idx, s1 in enumerate(rec['speed_limit']):
            if idx == 0:
                speed.append(float(rec['speed_limit'][idx +1 ]))
            elif idx != len(rec['speed_limit'])-1:
                    speed.append(float(rec['speed_limit'][idx]))
                    speed.append(float(rec['speed_limit'][idx+1]))
            else:
                speed.append(float(rec['speed_limit'][idx]))

        speed.insert(0, maxspeed)
        speed.insert(0, maxspeed)
        speed.append(maxspeed)
        speed.append(maxspeed)
        plt.plot(time, speed, linetype[i], label='speed limit - lane ' + str(rec['lane']))
        plt.legend(loc="upper left")

        recovery_out['figure_data']['data'].append({"x": time,
                                "y": speed})
        recovery_out['figure_data']['legend'].append('lane ' + str(rec['lane']))




    if save_output:
        # write the results in a json file
        #fname = hazard + '_eid' + str(eid) + '_' + asset_name + '_recovery_rlz_' + str(rlz_id) + '.json'
        fname = 'recovery_rlz'
        fullfname = os.path.join(fpath, fname)
        with open(fullfname+'.json', 'w') as fp:
           json.dump(recovery_out, fp)

        # updated 2020/09/23 also saves the png file
        plt.savefig(fullfname + '.png')

    if plot_rlz:
        plt.show()


def find_ds_per_asset_and_event(results, eid, asset_glob_ds_desc, hazard, save_output=True, plot_most_frequent_ds=True, fpath=results_path):
    """
    find and print/save data on the most frequent damage state per asset for event id eid

    """
    ds_per_asset = {}
    name = []
    n_occur = []
    ds_occur = []
    ds_name = []
    for asset, cons in results[str(eid)].items():
        # find the global damage state for the asset. The format is similar for Tier I and
        # Tier II assets thus this will work for both of them
        b = Counter(cons['global']['damage_state']).most_common(1)
        name.append(asset)
        n_occur.append(b[0][1])
        ds_occur.append(b[0][0])
        idx = find_cons_idx( asset_glob_ds_desc[asset]['damage_states'], 'id', ''.join(['DS', str(b[0][0])]))
        asset_ds_name = asset_glob_ds_desc[asset]['damage_states'][idx]['description']
        ds_name.append(asset_ds_name)
        ds_per_asset.update({asset: asset_ds_name})

    # bar plot preparation

    plt.figure()
    bar = plt.bar(name, n_occur)
    plt.xlabel("Assets")
    plt.ylabel("Number of occurrences")
    plt.title("Μost frequent damage state per asset, %s event No %s" % (hazard, eid))
    #plt.xticks(rotation=45)
    # Add x, y gridlines
    plt.grid(b=True, color='grey', linestyle='-', linewidth=0.5, alpha=0.5)
    # Add annotation to bars
    for idx, rect in enumerate(bar):
        height = rect.get_height()
        plt.text(rect.get_x() + rect.get_width() / 2.0, height, '%s' % ds_name[idx], ha='center', va='bottom')
    print('done0')

    if plot_most_frequent_ds:
        plt.show()

    if save_output:
        # save the output in json file
        outdir = {"figure_data": {"description": "most frequent damage state per asset, %s event No %s" % (hazard, eid),
                                        "type": "bar",
                                        "data": [],
                                        "labels": {"x": "assets",
                                                   "y": "number of occurences"},
                                        "legend": []}}
        for idx, rect in enumerate(bar):
            height = rect.get_height()
            outdir['figure_data']['data'].append({"x": name[idx],
                        "y": float(height)})
            outdir['figure_data']['legend'].append(ds_name[idx])

        # write the results in a json file
        #fname = 'MostFrequentDSperAsset_'+ hazard + '_eid' + str(eid) + '.json'
        fname = 'MostFrequentDSperAsset'
        fullfname = os.path.join(fpath, fname)
        with open(fullfname + '.json', 'w') as fp:
            json.dump(outdir, fp)

        plt.savefig(fullfname +'.png')

    return ds_per_asset




# ############################ IM FIELDS ##########################################################
def plot_im_field(eid, imfield_data, hazard, plot_gmf=True, fpath=results_path, save_output=True, grid_siteid=100000):
    """
    plot the IM field as well as the location of the rupture for the given event ID
    :params eid: event ID for which you want to plot the IM field
    :params imfield_data: data of the IM fields
    :params hazard: hazard that is examined
    :params plot_gmf: if True then the IM field is also displayed
    :params fpath: path where the results will be stored
    :params save_output: if true the output will be stored in a file named
                        'IMfield_' + hazard + '_eid' + str(eid) + '_'+ im_type +'.tiff'
                        that can be found in the fpath
    :param grid_siteid: max site ID that is used to indicate the grid


    """
    # load the details of the events
    events_info = imfield_data.get('events')
    im_fields = imfield_data.get('gmf_data').get('data')
    ruptures_info = imfield_data.get('ruptures')
    imfields_sitecol = imfield_data.get('sitecol')
    im_type = numpy.array(imfield_data.get('gmf_data').get('imts')).item()

    # find the source id for this event
    events_rupID_idx = (events_info['id'] == eid)
    assert len(numpy.nonzero(events_rupID_idx[0])[0]) != 0, 'cannot find this event ID in the ground motion fields'
    # find the rupture ID for this event
    events_rupID = events_info['rup_id'][events_rupID_idx]
    # get the lon-lat and magnitude for the given event
    # find the rupture index
    rup_idx = (ruptures_info['id'] == events_rupID)
    # find min, max lon and lat for the rupture
    mag = ruptures_info['mag'][rup_idx][0]

    # find where the event data are stored in the IM fields
    im_field_event_id = (im_fields['eid'] == eid)
    # find the site IDs for this event
    sites = im_fields['sid'][im_field_event_id]

    test_idx = numpy.nonzero(numpy.in1d(numpy.array(imfields_sitecol)['sids'], sites))[0]
    test_lat = numpy.array(imfields_sitecol)['lat'][test_idx]
    test_lon = imfields_sitecol['lon'][test_idx]
    test_sites = imfields_sitecol['sids'][test_idx]
    assert (test_sites == sites).all(), 'the whay the ground motion field is treated for ploting needs to be fixed!'

    test_im_idx = numpy.nonzero(numpy.in1d(im_fields['sid'][im_field_event_id], sites))[0]
    test_im = im_fields['gmv'][im_field_event_id]
    test_im = numpy.concatenate(test_im, axis=0)

    if save_output:

        sid_idx = (sites < grid_siteid)
        lats = test_lat[sid_idx]
        lons = test_lon[sid_idx]

        from osgeo import gdal
        from osgeo import osr
        from scipy import interpolate

        #fname = 'IMfield_' + hazard + '_' + str(eid) +  '_'+ im_type + '_nocolor.tiff'
        fname = 'IMfield_' + hazard + '_nocolor.tiff'
        fullfname = os.path.join(fpath, fname)

        lon2 = numpy.linspace(min(lons), max(lons), num=len(numpy.unique(lons))*20)
        lat2 = numpy.linspace(min(lats), max(lats), num=len(numpy.unique(lats))*10)
        lon, lat = numpy.meshgrid(lon2, lat2)
        array = interpolate.griddata((test_lon, test_lat), test_im, (lon, lat), method='cubic')

        # write the geotiff file
        xmin, ymin, xmax, ymax = [lon.min(), lat.min(), lon.max(), lat.max()]
        nrows, ncols = numpy.shape(array)
        xres = (xmax - xmin) / float(ncols)
        yres = (ymax - ymin) / float(nrows)
        geotransform = (xmin, xres, 0, ymax, 0, -yres)
        output_raster = gdal.GetDriverByName('GTiff').Create(fullfname, ncols, nrows, 1,
                                                             gdal.GDT_Float32)  # Open the file
        output_raster.SetGeoTransform(geotransform)  # Specify its coordinates
        srs = osr.SpatialReference()  # Establish its coordinate encoding
        srs.ImportFromEPSG(4326)  # This one specifies WGS84 lat long.
        output_raster.SetProjection(srs.ExportToWkt())  # Exports the coordinate system to the file
        array = numpy.flipud(array) # not to be inverted to the y axis
        output_raster.GetRasterBand(1).WriteArray(array)  # Writes my array to the raster
        output_raster.FlushCache()


        # whrite the file with the geotiff colors
        # max value of the data
        max_val = max(test_im)
        min_val = min(test_im)
        import math
        x = numpy.linspace(min_val, max_val, num=7, endpoint=True)
        fullfile_colors = os.path.join(results_path, 'colors.txt')
        # write the txt data with the colors
        with open(fullfile_colors, "w") as f:
            # update 2020/10/20 by AC: added the 4th column that indicates the transparancy and the last line that is
            # used for empty values
            line1 = "%s black 255" % str(math.floor(x[0] * 1000) / 1000)
            line2 = "%0.3f blue 255" % x[1]
            line3 = "%0.3f cyan 255" % x[2]
            line4 = "%0.3f green 255" % x[3]
            line5 = "%0.3f yellow 255" % x[4]
            line6 = "%0.3f orange 255" % x[5]
            line7 = "%s red 255" % str(math.ceil(x[6] * 1000) / 1000)
            line8 = "%s yellow 0" % str(math.ceil(x[6] * 1000) / 1000 + 50)
            f.write('{}\n{}\n{}\n{}\n{}\n{}\n{}\n{}\n'.format(line1, line2, line3, line4, line5, line6, line7, line8))


        # change the color of the geotiff
        import subprocess
        #fname2 = 'IMfield_' + hazard + '_eid' + str(eid) + '_'+ im_type +'.tiff'
        fname2 = 'IMfield_' + hazard + '.tiff'
        fullfname_final = os.path.join(fpath, fname2)
        # update 2020/10/20 by AC: added alpha factor to modify the transarency of the geotiff colors:)
        cmd = "gdaldem color-relief  -alpha " + fullfname \
                    + ' ' + fullfile_colors + ' ' + fullfname_final
        subprocess.check_call(cmd, shell=True)
        while fullfname_final not in glob.glob(fpath + '\*'):
            sleep(0.5)
        try:
            os.remove(fullfname)
        except PermissionError:
            pass
        try:
            os.remove(fullfile_colors)
        except PermissionError:
            pass

    if plot_gmf is True:
        max_val = max(test_im)
        min_val = min(test_im)
        if len(numpy.unique(test_im)) == 1:
            levels = numpy.linspace(0, min_val + min_val, num=10)
        else:
            levels = numpy.linspace(min_val, max_val, num=10)
        fig2, ax2 = plt.subplots()
        cm = plt.cm.get_cmap('jet')
        tcf = ax2.tricontourf(test_lon, test_lat, test_im, cmap=cm, levels=levels)
        #tcf = ax2.contourf(lon, lat , array, 1, cmap=cm )
        fig2.colorbar(tcf, label=im_type)
        # plot a star at the location of the rupture
        ax2.plot(ruptures_info['hypo'][rup_idx][0][0], ruptures_info['hypo'][rup_idx][0][1], '*', color='r')
        ax2.set_title("%s event No %s, M = %s" % (hazard.capitalize(), eid, mag))
        ax2.set_xlabel('longitude (degrees)')
        ax2.set_ylabel('latitude (degrees)')


def exposure2geojson(exposure, fname, fpath=results_path):
    """
    saves the exposure model as a geojson file
    :param exposure: exposure model
    :param fname: name of the output file
    :param fpath: path where the output will be stored
    :returns: the output file
    """
    # initialize colors
    colors = ["#250", "#050", "#2a10ea", "#bf09d7", "#bf09d7", "#b1db1a", "#1adb91", "#691a93", "#3a7892", "#f58300",
              "#7d7368", "#127341", "#ed0202"]

    features_all = []

    i = 0
    groups = []
    group_colors = []
    # loop over the assets in the exposure model and generate the geojson file
    for exp_data in exposure['ExposureModel']['exposure_categories']:
        category_name = exp_data['category']
        try:
            tagNames = valid.namelist(exp_data['tagNames'])
        except KeyError:
            tagNames = []
        for asset_data in exp_data['assets']:
            asset_name = asset_data['asset_name']
            tag = asset_data['tags'][0]
            if tag not in groups:
                i = i + 1
                color = colors[i]
                groups.append(tag)
                group_colors.append(color)
            else:
                idx = groups.index(tag)
                color = group_colors[idx]

            # for linear assets:
            if asset_data['location']['geometry']['type'] == 'LineString':
                features = {"type": "Feature", "properties": {"name": asset_name,
                                                              "stroke": color, "stroke-width": 5,
                                                              tagNames[0]: asset_data['tags'][0],
                                                              'exposure_category': category_name},
                            'geometry': asset_data['location']['geometry']}

            elif asset_data['location']['geometry']['type'] == 'Point':
                features = {"type": "Feature", "properties": {"name": asset_name,
                                                              "marker-color": color,
                                                              tagNames[0]: asset_data['tags'][0],
                                                              'exposure_category': category_name},
                            'geometry': asset_data['location']['geometry']}

            else:
                features = {"type": "Feature", "properties": {"name": asset_name,
                                                              tagNames[0]: asset_data['tags'][0],
                                                              'exposure_category': category_name},
                            'geometry': asset_data['location']['geometry']}
            if tag == 'pavement':
                features_all.insert(0, features)
            else:
                features_all.append(features)

    geojson_dict = {"type": "FeatureCollection", "features": features_all}

     # write the results in a json file
    fname = os.path.join(fpath, fname)
    with open(fname, 'w') as fp:
        json.dump(geojson_dict, fp)


def exposure2geojson_withoutgeomertytags(exposure, fname, fpath):
    """
    saves the exposure model as a geojson file
    :param exposure: exposure model
    :param fname: name of the output file
    :param fpath: path where the output will be stored
    :returns: the output file
    """
    # initialize colors
    colors = ["#250", "#050", "#2a10ea", "#bf09d7", "#bf09d7", "#b1db1a", "#1adb91", "#691a93", "#3a7892", "#f58300",
              "#7d7368", "#127341", "#ed0202"]

    features_all = []

    i = 0
    groups = []
    group_colors = []
    # loop over the assets in the exposure model and generate the geojson file
    for exp_data in exposure['ExposureModel']['exposure_categories']:
        category_name = exp_data['category']
        try:
            tagNames = valid.namelist(exp_data['tagNames'])
        except KeyError:
            tagNames = []

        if 'assets' in exp_data.keys():
            for asset_data in exp_data['assets']:
                asset_name = asset_data['asset_name']
                tag = asset_data['tags'][0]
                if tag not in groups:
                    i = i + 1
                    color = colors[i]
                    groups.append(tag)
                    group_colors.append(color)
                else:
                    idx = groups.index(tag)
                    color = group_colors[idx]

                # for linear assets:
                if asset_data['location']['geometry']['type'] == 'LineString':
                    features = {"type": "Feature", "properties": {"name": asset_name,
                                                                  "stroke": color, "stroke-width": 5,
                                                                  tagNames[0]: asset_data['tags'][0],
                                                                  'exposure_category': category_name},
                                'geometry': asset_data['location']['geometry']}

                elif asset_data['location']['geometry']['type'] == 'Point':
                    features = {"type": "Feature", "properties": {"name": asset_name,
                                                                  "marker-color": color,
                                                                  tagNames[0]: asset_data['tags'][0],
                                                                  'exposure_category': category_name},
                                'geometry': asset_data['location']['geometry']}

                else:
                    features = {"type": "Feature", "properties": {"name": asset_name,
                                                                  tagNames[0]: asset_data['tags'][0],
                                                                  'exposure_category': category_name},
                                'geometry': asset_data['location']['geometry']}
                if tag == 'pavement':
                    features_all.insert(0, features)
                else:
                    features_all.append(features)

        if 'groups' in exp_data.keys():
            for group_data in exp_data['groups']:
                group_name = group_data['group_name']

                i = i + 1
                color = colors[i]
                groups.append(tag)
                group_colors.append(color)

                # for linear assets:
                if group_data['location']['geometry']['type'] == 'LineString':
                    features = {"type": "Feature", "properties": {"name": group_name,
                                                                  "stroke": color, "stroke-width": 5,
                                                                  tagNames[0]: asset_data['tags'][0],
                                                                  'exposure_category': category_name},
                                'geometry': group_data['location']['geometry']}

                elif group_data['location']['geometry']['type'] == 'Point':
                    features = {"type": "Feature", "properties": {"name": group_name,
                                                                  "marker-color": color,
                                                                  tagNames[0]: group_data['tags'][0],
                                                                  'exposure_category': category_name},
                                'geometry': group_data['location']['geometry']}

                else:
                    features = {"type": "Feature", "properties": {"name": group_name,
                                                                  'exposure_category': category_name},
                                'geometry': group_data['location']['geometry']}
                if tag == 'pavement':
                    features_all.insert(0, features)
                else:
                    features_all.append(features)

    geojson_dict = {"type": "FeatureCollection", "features": features_all}

     # write the results in a json file
    fname = os.path.join(fpath, fname)
    with open(fname, 'w') as fp:
        json.dump(geojson_dict, fp)