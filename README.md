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

## 2. AOP data 

This is an area of active research and will be updated at a later time. 