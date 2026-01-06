# Vegetation structure (DP1.10098.001)

## Measurement
Taxonomic identification, state of health, stem diameter, height, crown dimensions, and mapped locations of woody and non-woody perennial vegetation.

## Collection methodology
Taxonomic identification, stem diameter, height, crown dimensions, observations of plant health and mapped location information and other measurements are recorded to enable estimation of biomass and production at multiple scales according to established allometries for the growth forms present across the NEON observatory. Data are collected with hand-held tools in the field, using standardized methods adopted from the forestry community. The temporal strategy is dependent on plot type; the full complement of tower plots is measured every 5 years, and a subset of tower plots are measured annually. Tower plots are established to overlap with the land surface that generates instrument based measurements of productivity from the surface-atmosphere exchange system. Distributed plots are measured every 5 years and provide a biomass snapshot across all vegetation types within a given NEON site.

For information about disturbances, land management activities, and other incidents that may impact data at NEON sites, see the [Site management and event reporting (DP1.10111.001)](https://data.neonscience.org/data-products/DP1.10111.001) data product.

![Image 1](https://raw.githubusercontent.com/NEONScience/NEON-quick-start-guides/9eda564cc095d3c4edfe4e19fe67ab86f4e8b04b/DP1.10098.001/Image1.jpg)  
A 20 m x 20 m Distributed or small-stature Tower base plot (left), a 40 m x 40 m large-stature Tower base plot (right), and associated subplots and nested subplots used for measuring woody and other qualifying vegetation. Subplots that are 100 meters squared and larger are labeled like 'XX_YYY', where 'XX' denotes the point that anchors the southwest corner and 'YYY' indicates the area in meters squared. Nested subplots smaller than 100 meters squared are identified like 'XX_YY_Z', where the additional 'Z' component designates the corner (black italics) in which the nested subplot is established within the 10 m x 10 m base unit.
  
## Data package contents
vst_shrubgroup: Biomass and productivity measurements of groups of shrubs  
vst_identificationHistory: Plant identification history for records where identifications have changed  
vst_apparentindividual: Biomass and productivity measurements of woody individuals  
vst_non-woody: Biomass and productivity measurements of non-herbaceous perennial plants (e.g. cacti, ferns)  
vst_perplotperyear: Per plot sampling metadata, including presence/absence of each growthForm  
vst_mappingandtagging: Mapping, identifying and tagging of individual stems for remeasurement  
variables: Description and units for each column of data in data tables  
readme: Data product description, issue log, and other metadata about the data product  
validation: Description of data validation applied at the points of collection and ingest  

## Data quality
The identificationQualifier field indicates uncertainty in taxonomic identification, and the taxonRank field indicates the specificity of the identification. For individuals monitored via dendrometer bands, the dendrometerCondition field indicates any problems with the band at the time of data collection.

For analyses that rely on precise geolocation of individuals, the coordinateUncertainty field in the vst_mappingandtagging table contains the uncertainty at the plot level; i.e., it reflects that each measurement was made somewhere within the plot. To calculate the location and uncertainty for each mapped individual, follow the instructions in the User Guide or use the geoNEON R package to perform the calculations. https://github.com/NEONScience/NEON-geolocation. To locate unmapped individuals at spatial scales finer than the plot, use the subplotID in the vst_apparentindividual or vst_non-woody tables and follow the instructions in the User Guide.

Please note that quality checks are comprehensive but not exhaustive; therefore, unknown data quality issues may exist. Users are advised to evaluate quality of the data as relevant to the scientific research question being addressed, perform data review and post-processing prior to analysis, and use the data quality information and issue logs included in download packages to aid interpretation.
  
## Standard calculations
For wrapper functions to download data from the API, and functions to merge tabular data files across sites and months, NEON provides the neonUtilities package in R and the neonutilities package in Python. See the [Download and Explore NEON Data](https://www.neonscience.org/resources/learning-hub/tutorials/download-explore-neon-data) tutorial for introductory instructions in both programming languages.

Woody vegetation measurements are designed for use in estimating plant biomass and productivity at NEON sites. Published allometries for plant biomass as it relates to height, stem diameter, taxonomic identification, and other measurements should be used to make these estimates.

To extrapolate from individual plants to the plot- or site-level, data users must account for the plot-specific use of nested subplots by growth form. Different nested subplot areas can be used within the same plot for different growth forms (i.e., different nested subplot sizes are allowed for each of shrubs/saplings/small-trees, lianas, ferns, and all 'other'), and nested subplot area can also vary from plot-to-plot for the same growth form. Thus, to calculate biomass, stem density, etc. at the plot scale, it is necessary to account for the nested subplot area by growth form per plot using nested subplot area data in the vst_perplotperyear table. Additional presence/absence data in the vst_perplotperyear table are needed to properly estimate biomass and other variables at the site-level; specifically, vst_perplotperyear records with targetTaxaPresent = "No" are the mechanism by which NEON documents plots with zero qualifying vegetation, and these zeroes are critical when generating site-scale parameter estimates.

Other data products measuring components of biomass and productivity include Non-herbaceous perennial vegetation structure (DP1.10045.001; bundled with this product from RELEASE-2022 onward), Litterfall and fine woody debris (NEON.DP1.10033), herbaceous clip harvest (NEON.DP1.10023), root biomass and chemistry (DP1.10067), coarse downed wood log surveys (NEON.DP1.10010), and coarse downed wood bulk density (NEON.DP1.10014).

Woody vegetation measurements can also be used as ground references for NEON remote sensing data. To calculate the location of each mapped individual, follow the instructions in the User Guide, or use the geoNEON R package to perform the calculations. https://github.com/NEONScience/NEON-geolocation
  
## Table joining
|Table 1|Table 2|Join by field(s)|
|------------------------|------------------------|-------------------------------|
vst_perplotperyear|vst_mappingandtagging|Join not recommended: vst\_perplotperyear and vst\_mappingand tagging represent different temporal resolution
vst_mappingandtagging|vst_apparentindividual|individualID
vst_perplotperyear|vst_apparentindividual|Join not recommended: vst_perplotperyear provides annual metadata at the plot level
vst_shrubgroup|vst_perplotperyear|Join not recommended: vst_perplotperyear provides annual metadata at the plot level
vst_shrubgroup|vst_apparentindividual|Join not recommended: vst\_shrubgroup and vst\_apparentindividual represent non-overlapping sets of plants
vst_mappingandtagging|vst_shrubgroup|Join not recommended: shrubs are not mapped
vst_shrubgroup|vst_non-woody|Join not recommended: vst\_shrubgroup and vst\_non-woody represent non-overlapping sets of plants
vst_non-woody|vst_perplotperyear|Join not recommended: vst_perplotperyear provides annual metadata at the plot level
vst_non-woody|vst_apparentindividual|Join not recommended: vst\_non-woody and vst\_apparentindividual represent non-overlapping sets of plants
vst_mappingandtagging|vst_non-woody|individualID
vst_mappingandtagging|vst_identificationHistory|identificationHistoryID
  
## Documentation
- [TOS Protocol and Procedure: VST - Measurement of Vegetation Structure](https://data.neonscience.org/api/v0/documents/NEON.DOC.000987vM)  
NEON.DOC.000987vM | 6.2 MiB | PDF  
- [TOS Standard Operating Procedure: CAC – Cactus Biomass and Handling](https://data.neonscience.org/api/v0/documents/NEON.DOC.001715vD)  
NEON.DOC.001715vD | 2.1 MiB | PDF  
- [NEON User Guide to the Vegetation Structure Data Product (NEON.DP1.10098.001)](https://data.neonscience.org/api/v0/documents/NEON_vegStructure_userGuide_vF)  
NEON_vegStructure_userGuide_vF | 1.2 MiB | PDF  

For more information on data product documentation, see:  
https://data.neonscience.org/data-products/DP1.10098.001  

## Citation
To cite data from Vegetation structure (DP1.10098.001), see citation here:  
https://data.neonscience.org/data-products/DP1.10098.001  
For general guidance in citing NEON data and documentation, see the citation guidelines page:  
https://www.neonscience.org/data-samples/guidelines-policies/citing  

## Contact Us
NEON welcomes discussion with data users! Reach out with any questions or concerns about NEON data: [Contact Us](https://www.neonscience.org/about/contact-us)
