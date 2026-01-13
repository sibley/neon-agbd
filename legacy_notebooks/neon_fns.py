import numpy as np
import pandas as pd
from shapely.geometry import Point
import geopandas as gpd 
import logging
from typing import List
import os, glob, subprocess, requests
import pickle
import os, glob, subprocess, requests
import pickle
from osgeo import gdal
import rasterio as rio
from rasterio.merge import merge
from rasterio.plot import show
# import georasters as gr
import numpy as np
import pandas as pd
from math import floor, ceil
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
import seaborn as sns
from shapely.geometry import Point
import neonutilities as nu
import geopandas as gpd 
import logging
from typing import List



from neonutilities.aop_download import validate_dpid,validate_site_format,validate_neon_site
from neonutilities.helper_mods.api_helpers import get_api
from neonutilities import __resources__
from neonutilities.helper_mods.api_helpers import get_api#, download_file
from neonutilities.helper_mods.metadata_helpers import convert_byte_size
# from neonutilities.get_issue_log import get_issue_log
# from neonutilities.citation import get_citation

from neonutilities.aop_download import *

pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)

def make_veg_gdf(veg_dict: dict) -> gpd.GeoDataFrame:
	"""
	Takes the vegetation structure dict, finds the unique reference points,
	pulls their spatial reference information using the NEON "locations" API,
	and computes the location of individual stems.

	Notes:
	1. Stems without a pointID are discarded.
	2. If the points don't all belong to the same utm zone, the function will return a failure.  
	3. If the georeferencing point cannot be found via the API, all associated stems will be discarded. 

	Parameters:
	veg_dict (pd.DataFrame): DataFrame containing 'easting' and 'northing' columns.

	Returns:
	The original dict with the spatial ref information added. 
	"""

	# Set up a session with retries
	session = requests.Session()
	retries = Retry(
		total=5,                # Total retry attempts
		backoff_factor=0.5,     # Wait time between retries: 0.5, 1, 2, 4, etc.
		status_forcelist=[500, 502, 503, 504],  # Retry on these HTTP status codes
	)
	adapter = HTTPAdapter(max_retries=retries)
	session.mount('http://', adapter)
	session.mount('https://', adapter)

	# Pull out the "mapping and tagging" dataframe
	veg_map_all = veg_dict["vst_mappingandtagging"]

	# Filter out points that have no pointID and reindex.
	veg_map = veg_map_all.loc[veg_map_all["pointID"] != ""]
	veg_map = veg_map.reindex()

	# Create a unique identifier for each point
	veg_map["points"] = veg_map["namedLocation"] + "." + veg_map["pointID"]

	# Make a list of the unique points 
	veg_points = list(set(list(veg_map["points"])))

	# Loop every point, pull the spatial ref info, and store in lists
	valid_points = []
	easting = []
	northing = []
	coord_uncertainty = []
	elev_uncertainty = []
	utm_zone = []
	for i in veg_points:
		# vres = requests.get("https://data.neonscience.org/api/v0/locations/"+i)
		vres = session.get("https://data.neonscience.org/api/v0/locations/"+i)
		vres_json = vres.json()
		if not vres_json.get("data"):
			continue
		valid_points.append(i)
		easting.append(vres_json["data"]["locationUtmEasting"])
		northing.append(vres_json["data"]["locationUtmNorthing"])
		props = pd.DataFrame.from_dict(vres_json["data"]["locationProperties"])
		cu = props.loc[props["locationPropertyName"]=="Value for Coordinate uncertainty"]["locationPropertyValue"]
		if cu.empty:
			cu = np.nan
		else: 
			cu = cu[cu.index[0]]
		coord_uncertainty.append(cu)	
		eu = props.loc[props["locationPropertyName"]=="Value for Elevation uncertainty"]["locationPropertyValue"]
		if eu.empty:
			# eu = pd.Series([np.nan])
			eu = np.nan
		else:
			eu = eu[eu.index[0]]
		elev_uncertainty.append(eu)
		utm_zone.append(32600+int(vres_json["data"]["locationUtmZone"]))

	# Create a dataframe with the spatial info of the reference points
	pt_dict = dict(points=valid_points, 
	easting=easting,
	northing=northing,
	coordinateUncertainty=coord_uncertainty,
	elevationUncertainty=elev_uncertainty,
	utm_zone = utm_zone)

	pt_df = pd.DataFrame.from_dict(pt_dict)
	pt_df.set_index("points", inplace=True)

	# Add the reference info to the veg map
	veg_map = veg_map.join(pt_df, 
	on="points", 
	how="inner")

	# Compute the Easting of each stem 
	veg_map["stemEasting"] = (veg_map["easting"]
	+ veg_map["stemDistance"]
	* np.sin(veg_map["stemAzimuth"]
	* np.pi / 180))

	# Compute the Northing of each stem
	veg_map["stemNorthing"] = (veg_map["northing"]
	+ veg_map["stemDistance"]
	* np.cos(veg_map["stemAzimuth"]
	* np.pi / 180))

	# Compute the stem uncertainties
	veg_map["stemCoordinateUncertainty"] = veg_map["coordinateUncertainty"] + 0.6
	veg_map["stemElevationUncertainty"] = veg_map["elevationUncertainty"] + 1.5

	# Test that all points are in the same UTM zone
	if len(set(veg_map["utm_zone"])) != 1:
		raise ValueError("Points in the veg map are in different UTM zones! Rectify before proceeding.")	
	else:
		# Define the crs
		crs = f"EPSG:{veg_map['utm_zone'].values[0]}"
		print(f"veg_map converted to gdf with crs {crs}")

		# Create list of shapely points for the gdf 	
		geometry = [Point(xy) for xy in zip(veg_map["stemEasting"], veg_map["stemNorthing"])]

		# Convert veg_map to a gdf 
		veg_map = gpd.GeoDataFrame(veg_map, crs=crs, geometry=geometry)

		veg_dict["vst_apparentindividual"].set_index("individualID", inplace=True)
		veg_gdf = veg_map.join(veg_dict["vst_apparentindividual"],
		on="individualID",
		how="inner",
		lsuffix="_MAT",
		rsuffix="_AI")

		return veg_gdf


def filter_veg_gdf(veg_gdf: gpd.GeoDataFrame,
				require_dbh:bool = True,
				single_bole:bool = True,	
				only_most_recent:bool = True) -> gpd.GeoDataFrame:
	"""
	Filters down a vegetation gdf to just the trees, with options to 
	1. drop trees without a dbh measurement,
	2. keep only single bole trees,
	3. keep only the most recent measurement of each tree.

	Returns the filtered gdf.
	"""

    # Filter to only trees that have a dbh value
	if require_dbh:
		veg_gdf = veg_gdf.loc[~veg_gdf["stemDiameter"].isna()]	

	# Drop duplicated measurements 
	dupe_test_cols = ['date_AI','individualID','scientificName','taxonID','family',
					'growthForm','plotID_AI','pointID','stemDiameter',
					'maxBaseCrownDiameter','stemEasting','stemNorthing']
	veg_gdf = veg_gdf.drop_duplicates(subset = dupe_test_cols)

	# Cut down to just the tree growth forms 
	tree_gdf = veg_gdf[veg_gdf['growthForm'].str.contains('tree|sapling', regex=True)]

	# Cut down to just single bole trees
	if single_bole:
		tree_gdf = tree_gdf[(tree_gdf['growthForm']=='single bole tree')]

	# Convert 'date_AI' to datetime if it's not already
	tree_gdf.loc[:, 'date_AI'] = pd.to_datetime(tree_gdf['date_AI'])

	# Sort the DataFrame by 'individualID' and 'date_AI' in descending order
	tree_gdf = tree_gdf.sort_values(by=['individualID', 'date_AI'], ascending=[True, False])

	# Keep only the most recent entry for each 'individualID'
	if only_most_recent:
		tree_gdf = tree_gdf.drop_duplicates(subset='individualID', keep='first')
		
	return tree_gdf
 

def nu_list_available_dates(dpid:str, site:str) -> pd.DataFrame:

    """
		NOTE: This is an internal hack of the original function to return a dataframe instead of printing
        
        nu_list_available_dates displays the available releases and dates for a given product and site
        --------
         Inputs:
             dpid: the data product code (eg. 'DP3.30015.001' - CHM)
             site: the 4-digit NEON site code (eg. 'JORN')
        --------
        Returns:
        prints the Release Tag (or PROVISIONAL) and the corresponding available dates (YYYY-MM) for each tag
    --------
        Usage:
        --------
        >>> list_available_dates('DP3.30015.001','JORN')
        RELEASE-2025 Available Dates: 2017-08, 2018-08, 2019-08, 2021-08, 2022-09

        >>> list_available_dates('DP3.30015.001','HOPB')
        PROVISIONAL Available Dates: 2024-09
        RELEASE-2025 Available Dates: 2016-08, 2017-08, 2019-08, 2022-08

        >>> list_available_dates('DP1.10098.001','HOPB')
        ValueError: There are no data available for the data product DP1.10098.001 at the site HOPB.
    """
    product_url = "https://data.neonscience.org/api/v0/products/" + dpid
    response = get_api(api_url=product_url)  # add input for token?

    # raise value error and print message if dpid isn't formatted as expected
    validate_dpid(dpid)

    # raise value error and print message if site is not a 4-letter character
    site = site.upper()  # make site upper case (if it's not already)
    validate_site_format(site)

    # raise value error and print message if site is not a valid NEON site
    validate_neon_site(site)

    # check if product is active
    if response.json()["data"]["productStatus"] != "ACTIVE":
        raise ValueError(
            f"NEON {dpid} is not an active data product. See https://data.neonscience.org/data-products/{dpid} for more details."
        )

    # get available releases & months:
    for i in range(len(response.json()["data"]["siteCodes"])):
        if site in response.json()["data"]["siteCodes"][i]["siteCode"]:
            available_releases = response.json()["data"]["siteCodes"][i][
                "availableReleases"
            ]

    # display available release tags (including provisional) and dates for each tag
    try:
        availables_list = []
        for entry in available_releases:
            release = entry["release"]
            available_months_str = ", ".join(entry["availableMonths"])
            available_months = [x.strip() for x in available_months_str.split(',')]
            for available_month in available_months:
                availables_list.append({'status':release,'date':available_month})
        available_df = pd.DataFrame(availables_list)
        return(available_df)
    except UnboundLocalError:
        # if the available_releases variable doesn't exist, this error will show up:
        # UnboundLocalError: local variable 'available_releases' referenced before assignment
        raise ValueError(
            f"There are no NEON data available for the data product {dpid} at the site {site}."
        )
    
def nu_aop_file_names(
			dpid:str,
	site:str,
	year:int,
	token="",
	include_provisional=True,
	check_size=False,
	savepath=None) -> List:
	"""returns names of files in the specified AOP data product, site, and year. 
	   changes the standard NEON paths to the local paths if savepath specified. """

	# raise value error and print message if dpid isn't formatted as expected
	validate_dpid(dpid)

	# raise value error and print message if dpid isn't formatted as expected
	validate_aop_dpid(dpid)

	# raise value error and print message if field spectra data are attempted
	check_field_spectra_dpid(dpid)

	# raise value error and print message if site is not a 4-letter character
	site = site.upper()  # make site upper case (if it's not already)
	validate_site_format(site)

	# raise value error and print message if site is not a valid NEON site
	validate_neon_site(site)

	# raise value error and print message if year input is not valid
	year = str(year)  # cast year to string (if it's not already)
	validate_year(year)

	# if token is an empty string, set to None
	if token == "":
		token = None

	# query the products endpoint for the product requested
	response = get_api("https://data.neonscience.org/api/v0/products/" + dpid, token)

	# exit function if response is None (eg. if no internet connection)
	if response is None:
		logging.info("No response from NEON API. Check internet connection")

	# check that token was used
	if token and "x-ratelimit-limit" in response.headers:
		check_token(response)
		# if response.headers['x-ratelimit-limit'] == '200':
		#     print('API token was not recognized. Public rate limit applied.\n')

	# get the request response dictionary
	response_dict = response.json()

	# error message if dpid is not an AOP data product
	check_aop_dpid(response_dict, dpid)

	# replace collocated site with the AOP site name it's published under
	site = get_shared_flights(site)

	# get the urls for months with data available, and subset to site & year
	site_year_urls = get_site_year_urls(response_dict, site, year)

	# error message if nothing is available
	if len(site_year_urls) == 0:
		logging.info(
			f"There are no NEON {dpid} data available at the site {site} in {year}.\nTo display available dates for a given data product and site, use the function list_available_dates()."
		)
		# print("There are no data available at the selected site and year.")

	# get file url dataframe for the available month urls
	file_url_df, releases = get_file_urls(site_year_urls, token=token)

	# get the number of files in the dataframe, if there are no files to download, return
	if len(file_url_df) == 0:
		# print("No data files found.")
		logging.info("No NEON data files found.")
		# return

	# NOTE: provisional filtering has been silenced for now. 
	# if 'PROVISIONAL' in releases and not include_provisional:
	# if include_provisional:
	# 	# log provisional included message
	# 	# logging.info(
	# 	# 	"Provisional NEON data are included. To exclude provisional data, use input parameter include_provisional=False."
	# 	# )
	# else:
	# 	# log provisional not included message and filter to the released data
	# 	# logging.info(
	# 	#     "Provisional data are not included. To download provisional data, use input parameter include_provisional=True.")
	# 	file_url_df = file_url_df[file_url_df["release"] != "PROVISIONAL"]
	# 	if len(file_url_df) == 0:
	# 		logging.info(
	# 			"NEON Provisional data are not included. To download provisional data, use input parameter include_provisional=True."
	# 		)

	num_files = len(file_url_df)
	if num_files == 0:
		logging.info(
			"No NEON data files found. Available data may all be provisional. To download provisional data, use input parameter include_provisional=True."
		)
		# return

	# get the total size of all the files found
	download_size_bytes = file_url_df["size"].sum()
	# print(f'download size, bytes: {download_size_bytes}')
	download_size = convert_byte_size(download_size_bytes)
	# print(f'download size: {download_size}')

	# report data download size and ask user if they want to proceed
	if check_size:
		if (
			input(
				f"Continuing will download {num_files} NEON data files totaling approximately {download_size}. Do you want to proceed? (y/n) "
			)
			.strip()
			.lower()
			!= "y"
		):  # lower or upper case 'y' will work
			print("Download halted.")
			# return

	# Make the list of files as they should appear on the local file system and return 
	files = list(file_url_df["url"])
	if savepath is not None:
		files = [f"{savepath.rstrip('/')}/{fi.lstrip('https://storage.googleapis.com')}" for fi in files]
	return files 