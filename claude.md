# Claude Notes for neon-agbd

This file contains notes for future sessions working with this codebase.

## Code Structure

The `/src/` directory contains four Python modules:

1. **data_loader.py** - Functions for loading and preparing data
   - `load_dp1_data()` - Load DP1.10098.001 pickle files
   - `load_neon_forest_agb()` - Load and concatenate NEONForestAGB CSVs
   - `load_plot_areas()` - Load plot polygon data from GeoJSON
   - `pivot_agb_by_allometry()` - Convert long to wide format for AGB
   - `merge_agb_with_apparent_individual()` - Join AGB with vst_apparentindividual

2. **gap_filling.py** - Functions for filling missing biomass values
   - Uses linear interpolation when 2+ observations exist
   - Uses constant fill when 1 observation exists
   - Leaves NA when 0 observations exist

3. **biomass_calculator.py** - Functions for computing plot-level biomass
   - Categorizes individuals as 'tree', 'small_woody', or 'other'
   - Trees: growthForm in [single bole tree, multi-bole tree, small tree] AND stemDiameter >= 10cm
   - Small woody: growthForm in [small tree, sapling, single shrub, small shrub] AND stemDiameter < 10cm

4. **main.py** - Main workflow orchestration
   - `compute_site_biomass()` - Process a single site
   - `compute_all_sites_biomass()` - Process multiple sites

## Key Data Considerations

### eventID Format
The eventID format is `vst_SITE_YYYY` (e.g., 'vst_SJER_2015'). The year is extracted from the last 4 characters.

### NEONForestAGB Allometry Types
Three allometry types are available:
- **AGBJenkins** - Based on Jenkins et al. 2003
- **AGBChojnacky** - Based on Chojnacky et al. 2014
- **AGBAnnighofer** - May have many NaN values depending on site/species

### Plot Areas
Plot areas are obtained from the GeoJSON file. Common sizes:
- 400 m² (20m x 20m)
- 1600 m² (40m x 40m)

### Biomass Units
- NEONForestAGB provides individual tree AGB in **kg** (kilograms)
- Output biomass density is reported in **Mg/ha** (megagrams per hectare, equivalent to tonnes per hectare)
- Conversion factor: `KG_TO_MG = 1/1000`

### Small Woody Calculation
The small_woody biomass calculation accounts for unmeasured individuals:
1. Calculate average biomass from measured individuals
2. Multiply by total count of small_woody individuals
3. Divide by plot area

When no measured individuals exist, the biomass is reported as NaN (not 0).

## Known Issues / Edge Cases

1. **Same-year duplicate observations**: Fixed by using mean value instead of linear regression when all observations are from the same year.

2. **Missing plot areas**: Some plots may not have entries in the GeoJSON file. These are skipped with a warning.

3. **AGBAnnighofer NaN values**: For many sites/species, this allometry type returns NaN values. This is expected behavior from the NEONForestAGB dataset.

## Usage Example

```python
from src.main import compute_site_biomass, compute_all_sites_biomass, ALL_SITES

# Single site
results = compute_site_biomass('SJER')

# Multiple sites
results = compute_all_sites_biomass(['SJER', 'HARV', 'TALL'])

# All available sites
results = compute_all_sites_biomass(ALL_SITES)
```

## Output Format

The output DataFrame has 13 columns:
- siteID, plotID, year, plotArea_m2
- tree_AGBJenkins, tree_AGBChojnacky, tree_AGBAnnighofer (Mg/ha)
- n_trees
- small_woody_AGBJenkins, small_woody_AGBChojnacky, small_woody_AGBAnnighofer (Mg/ha)
- n_small_woody_total, n_small_woody_measured

## Questions for User

1. **Small woody understanding**: The current implementation assumes that small_woody individuals without stemDiameter measurements are counted but not included in the average biomass calculation. This matches the README description.

## Future Improvements

- Add support for vst_shrubgroup data (currently not used)
- Add support for vst_non-woody data (currently not used)
- Add more sophisticated gap-filling methods (e.g., species-specific growth curves)
- Add validation checks for data quality flags
