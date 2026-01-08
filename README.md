# neon-agbd

This repository houses functions that are used to compute aboveground biomass density using (1) field survey plot data and (2) lidar data from the AOP (aerial observation platform). These functions are specific to the NEON database structure. 


## 1.  Survey plot data

### 1.1 The datasets

#### 1.1.1 Veg structure data (DP1.10098.001)

Most of the relevant data for a given site will be contained in the dictionary returned by running the retrieval function nu.load_by_product. 

```python
import neonUtilities as nu

veg_dict = nu.load_by_product(dpid="DP1.10098.001", 
                              site="SJER", 
                              package="basic", 
                              release="RELEASE-2025",
                              check_size=False)
```

where dpid is the data product ID (will always be DP1.10098.001 for this exercise), the site is a 4 digit site code (SJER = San Joaquin Experimental Range in this example), and all other arguments can be left as defaults. a successful run of `nu.load_by_product` results in a dictionary containing several data objects.  

The current list of DPIDs that have been downloaded are: 

```python
dpids= ['DELA','LENO','TALL','BONA','DEJU','HEAL','SRER','SJER','SOAP',
              'TEAK','CPER','NIWO','RMNP','DSNY','OSBS','JERC','PUUM','KONZ',
              'UKFS','SERC','HARV','UNDE','BART','JORN','DCFS','NOGP','WOOD',
              'GUAN','LAJA','GRSM','ORNL','CLBJ','MOAB','ONAQ','BLAN','MLBS',
              'SCBI','ABBY','WREF','STEI','TREE','YELL']
```

Which were retrieved and saved as pickle files using `./notebooks/dl_dp1.ipynb`. The .pkl files can be found in `./data/DP1.10098/` and are identified by site ID. all .pkl contain all available years as of 2025-11-01. 

More information about the data can be found in the the snippet below from the NEON website and in the official documentation for this product found in the pdf and markdown files in `./docs/DP1.10098/`.

```
Queries for this data product return data from the user-specified date range for the vst_perplotperyear, vst_apparentindividual, vst_non-woody, and vst_shrubgroup tables. For the vst_mappingandtagging table, queries ignore the user-specified date range and return all records for each user-selected site regardless of the user-specified date, due to the fact that individuals may be tagged and mapped in a year prior to the user-selected sampling event. Data are provided in monthly download files; queries including any part of a month will return data from the entire month. In the vst_perplotperyear table, there should be one record per plotID per eventID, and data in this table describe the presence/absence and sampling area of woody and non-woody growth forms. The vst_mappingandtagging table contains at least one record per individualID, and provides data that are invariant through time, including tagID, taxonID, and mapped location (if applicable). Duplicates in vst_mappingandtagging may exist at the individualID level if errors have been corrected after ingest of the original record; in this instance, users are advised to use the most recent record for a given individualID. The vst_apparentindividual table contains at least one record per individualID per eventID, and includes growth form, structure and plant status data that may be linked to vst_mappingandtagging records via the individualID; records may also be linked to vst_perplotperyear via the plotID and eventID fields in order to generate plot-level estimates of biomass and productivity. The vst_non-woody table contains one record per individualID per eventID, and contains growth form, structure and status data that may be linked to vst_perplotperyear data via the plotID and eventID fields. The vst_shrubgroup table contains a minimum of one record per groupID per plotID per eventID; multiple records with the same groupID may exist if a given shrub group comprises more than one taxonID. Data provided in the vst_shrubgroup table allow calculation of live and dead volume per taxonID within each shrub group, and records may be linked with the vst_perplotperyear table via the plotID and eventID fields.

For all tables, duplicates may exist where protocol and/or data entry aberrations have occurred; users should check data carefully for anomalies before joining tables. For the vst_apparentindividual table, the combination of the eventID x individualID x tempStemID fields should be unique. The tempStemID field is used to uniquely identify the stems within a multi-stem individual within a sampling event, but the identity of these stems is not tracked from year-to-year; individuals with a single stem are assigned a tempStemID of 1. Taxonomic IDs of species of concern have been 'fuzzed'; see data package readme files for more information.

If taxonomic determinations have been updated for any records in the tables vst_mappingandtagging or vst_non-woody, past determinations are archived in the vst_identificationHistory table, where the archived determinations are linked to current records using identificationHistoryID.
```

#### 1.1.2 Tree biomass estimates - NEONForestAGB

NEONForestAGB is a dataset derived from the Veg structure data described in section 1.1.1. Jeff Atkins et al. systematically applied allometric equations to every DBH measurement for every possible combination of `individualID` and survey date that is present in the DP1.10098.001 database. 

In this dataset there are three rows for every combination of individualID and survey date. Each row is the same except for the allometry that was used to compute AGB (aboveground biomass). The allometry used is indicated in the `allometry` column of the 10 csv files that represent the full NEONForestAGB database (named `NEONForestAGBv2_partXX.csv`). Allometry values are either "AGBJenkins", "AGBChojnacky", or "AGBAnnighofer". 

For more information about this dataset, how it was made, or what it's proerties are, see the documentation in `./docs/NEONForestAGB/`, the metadata file, the master taxon list, and all of the files for the AGB database in `./data/NEONForestAGB/` 


### 1.2 Deriving plot-level AGB for each sampling campaign

The `DP1.10098.001` and `NEONForestAGB` datasets are used in tandem to create plot-level estimates of AGB. 

First it is helpful to understand the nature of the plots. At each NEON TOS (Terrestrial Observation Site), there are both `Distributed` plots (up to n=20), the locations of which are chosen to proportionally represent the landcover types of the site, and `Tower` plots (n = 20 in forests, n = 30 in non-woody sites), which are located within the airshed of the flux tower. For more information, see the docs folder. 

The family of functions in the .py files in /src/ work together to execute the following workflow, which ultimately results in AGB estimates for a given NEON TOS site, by survey plot and survey campaign (year).   

For the TOS site: 

1. Open the DP1.10098 .pkl file for the specified siteID (4-character site code). 

2. Read in and concatenate all NEONForestAGBv2 csvs. Filter to the specified siteID. 

3. Cut the NEONForestAGB dataframe down to just the columns `['individualID','date','allometry','AGB']`. Pivot using an index of `['individualID','date']` so that each allometry types become columns and the values are the values from the AGB column. Join the NEONForestAGB dataframe to the `vst_apparentindividual` dataframe in the DP1 dict on the individualID and date columns. For any rows in vst_apparentindividual that do not have a corresponging entry in NEONForestAGB, fill in the allometry columns with NA. Now all available biomass estimates have been added to the table of the raw measurement information.

3. Make a list of all unique combinations of plotID and year in the DP1 data, where the year is obtained from the final 4 characters of the eventID. 

4. Begin looping through plotIDs and calculating the necessary information to be able to estimate whole-plot biomass. 

Per plotID: 

1. Create a list of all of the unique `individualIDs` from the `vst_apparentindividual` table that fall within the plot. We want all individuals, not just those for a given sampling year, because we will be implementing logic to fill in information for missing entries. From here foreward we can refer to this dataframe as vst_ai. 

2. Conduct any gap filling that is necessary for each individualID. If there is missing data for a given allometry type for a given survey year, and there are at least 2 observations for that individual and allometry type from other years, estimate the missing observation using a linear fit. If only 1 observation is available, use that same value as a gap filler (assumption: no growth). If no observations are available, leave all as NA. 

3. Divide up all of the vst_ai df into "small_woody", "tree" categories. 
- To be in the "tree" category, an individual must have a `growthForm` within the set `['single bole tree','multi-bole tree','small tree']` and have a `stemDiameter` equal to or greater than 10cm. 
- To be in the "small_woody" category, an individual must be in the set `['small_tree','sapling','single shrub', 'small shrub']` and have a `stemDiameter` of less than 10cm. 

4. For each year, sum the biomass for all trees, and divide by the area of the plot. The area of each plot can be obtained from [FILL THIS IN]. Store this as the "tree" biomass for the plot. 

5. For each year, sum the small_woody biomass and divided by the number of measured individuals to get an average biomass. Then multiply this by the total number of small_woody individuals that exist in the plot to get the "small_woody" biomass total for the plot. Divide by the plot area to get the biomass density.  

The results of 4 and 5 should be stored in a data frame with columns showing the siteID, plotID, eventYear, the biomass totals for each category type (trees and small_woody) and for each of the 3 allometry types that are present, the n of trees, the n of measured small_woody, and the n of total small_woody in the site (total of 12 columns). 

This will be the output of the workflow. 



## 2. AOP data 

This is an area of active research and will be updated at a later time. 


2. Begin looping survey years, beginning with the first. 