# Claude Notes for neon-agbd

This file contains notes for future sessions working with this codebase.

## Code Structure

The `/src/` directory contains five Python modules:

1. **constants.py** - All hardcoded constants used across the codebase
   - `DEAD_STATUSES` - Plant status values indicating dead trees
   - `LIVE_STATUSES` - Plant status values indicating live trees
   - `TREE_GROWTH_FORMS` - Growth forms that qualify as trees
   - `SMALL_WOODY_GROWTH_FORMS` - Growth forms that qualify as small woody
   - `DIAMETER_THRESHOLD` - Diameter cutoff (10cm) for tree vs small woody
   - `ALLOMETRY_COLS` - Names of allometry columns
   - `KG_TO_MG` - Unit conversion factor

2. **data_loader.py** - Functions for loading and preparing data
   - `load_dp1_data()` - Load DP1.10098.001 pickle files
   - `load_neon_forest_agb()` - Load and concatenate NEONForestAGB CSVs
   - `load_plot_areas()` - Load plot polygon data from GeoJSON
   - `pivot_agb_by_allometry()` - Convert long to wide format for AGB
   - `merge_agb_with_apparent_individual()` - Join AGB with vst_apparentindividual

3. **gap_filling.py** - Functions for filling missing biomass values
   - Uses linear interpolation when 2+ observations exist
   - Uses constant fill when 1 observation exists
   - Leaves NA when 0 observations exist

4. **biomass_calculator.py** - Functions for computing plot-level biomass
   - Categorizes individuals as 'tree', 'small_woody', or 'other'
   - Trees: growthForm in [single bole tree, multi-bole tree, small tree] AND stemDiameter >= 10cm
   - Small woody: growthForm in [small tree, sapling, single shrub, small shrub] AND stemDiameter < 10cm

5. **main.py** - Main workflow orchestration
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

## Version 2 Features (2026-01)

### Dead Status Corrections
Trees that have a "sandwiched" dead status (alive->dead->alive pattern) are now corrected to assume the tree was alive throughout. If the dead status persists (alive->dead->dead), the tree's biomass is set to 0 for dead periods.

Dead status values (defined in `constants.py`):
- Dead, broken bole
- Downed
- Lost, burned
- Lost, fate unknown
- Lost, herbivory
- Lost, presumed dead
- Removed
- Standing dead
- No longer qualifies

Live status values (defined in `constants.py`):
- '' (empty string)
- Live
- Live, other damage
- Live, broken bole
- Live, disease damaged
- Live, insect damaged
- Live, physically damaged
- Lost, tag damaged

### Output Dictionary

The `compute_site_biomass_full()` function returns a dictionary containing both the input DP1.10098 data and computed outputs, so everything is accessible from a single file:

**Input tables (from DP1.10098 pickle):**
- `vst_apparentindividual`: Raw apparent individual measurements
- `vst_mappingandtagging`: Tree mapping and tagging data
- `vst_perplotperyear`: Plot-level metadata per year
- Plus metadata tables: `categoricalCodes_10098`, `variables_10098`, `validation_10098`, etc.

**Computed outputs:**
- `plot_biomass`: Plot-level biomass with growth metrics
- `unaccounted_trees`: Trees not included in calculations
- `individual_trees`: Individual tree measurements in long form
- `site_id`: Site identifier
- `metadata`: Processing information (settings used, counts)

### Unaccounted Trees Table
Tracks trees that couldn't be included in biomass calculations:
- `UNMEASURED`: Trees in mapping table but never measured
- `NO_ALLOMETRY`: Trees with diameter but no biomass estimates

### Individual Trees Table
Long-form table with one row per tree per survey year:
- All three allometry AGB values
- Growth rates (year-over-year and cumulative via linear regression)
- Time-invariant attributes from mapping table (scientific name, taxonID, etc.)
- Corrected dead status flag
- `gapFilling`: Indicates whether the row is 'ORIGINAL' (measured) or 'FILLED' (gap-filled)

### Gap-Filling Behavior
When `apply_gap_filling=True` (default), the following gap-filling is applied:
1. **Complete grid creation**: For each individual that ever appeared in a plot, a row is created for every year the plot was sampled
2. **Forward/backward fill of growthForm and stemDiameter**: These time-invariant attributes are filled from the nearest observation (forward fill preferred, backward fill if no previous data)
3. **Biomass interpolation**: Missing biomass values are filled using linear interpolation when 2+ observations exist, or constant fill when only 1 observation exists

The `gapFilling` column tracks whether each row was from an actual measurement ('ORIGINAL') or created by gap-filling ('FILLED').

### Growth Metrics
- `growth`: Year-over-year growth rate (Mg/ha/year)
- `growth_cumu`: Cumulative average growth from linear regression slope

### Example Script
`example_run.py` demonstrates processing a site and saving outputs as pkl and CSV files.

## Implementation Notes

### Multi-Stem Tree Handling
- Each individual can have multiple stems (rows per year with same individualID)
- For dead status: individual is alive if ANY stem is alive
- For individual tree table: biomass is summed across stems, diameter takes max value

### Growth Calculations
- Year-over-year growth: `(current_biomass - previous_biomass) / (current_year - previous_year)`
- Cumulative growth: slope from `scipy.stats.linregress(years, biomass)`
- Plot-level growth uses total biomass (tree + small_woody) with Jenkins as primary allometry
- Individual tree growth is calculated separately for each allometry type

### Unaccounted Trees Logic
- UNMEASURED: individualID exists in `vst_mappingandtagging` but not in `vst_apparentindividual`
- NO_ALLOMETRY: Tree has stemDiameter >= 10cm but no biomass from any of the three allometries
- Only trees (not small_woody) are tracked as unaccounted

### Dead Status Classification
All plant statuses are now classified as either dead or live (see `constants.py`):
- `No longer qualifies` - classified as DEAD
- `Lost, fate unknown` - classified as DEAD
- `Lost, tag damaged` - classified as LIVE (tag issue, not plant death)

### Performance Considerations
- Dead status corrections run per-individual, which can be slow for large sites
- HARV with ~1300 unaccounted trees takes longer due to the iteration

## Non-Forested Sites and Plot-Level Biomass Logic (2026-01-12)

### Authoritative Source for Plot-Years
The `vst_perplotperyear` table is now used as the authoritative source for which plot-years were surveyed. This includes plots that were surveyed but had no woody vegetation (previously these were excluded).

### Sites Without NEONForestAGB Data
Seven NEON sites have no data in the NEONForestAGB dataset:
- **Grasslands**: CPER, NOGP, DCFS, WOOD
- **Arid/semi-arid**: LAJA, MOAB, JORN

For these sites, `metadata['site_has_agb_data']` will be `False`.

### Plot-Level Biomass Logic

| Scenario | Tree Biomass |
|----------|-------------|
| No trees in plot | 0 |
| Only dead trees | 0 |
| Live trees with valid AGB estimates | Calculated sum |
| Live trees, ALL have NaN AGB (no ForestAGB data) | NaN |
| Mix of live trees (some with valid AGB) + dead trees | Calculated sum |

**Key principle**: Dead trees are set to 0 biomass (they have no living biomass). The NaN check only considers live trees - if ANY live trees exist but ALL of them lack AGB estimates, the plot biomass is NaN because we cannot estimate the living biomass.

### Gap-Filling and Dead Tree Zeroing Order

**Important**: Dead tree biomass is zeroed AFTER gap-filling, not before. This prevents the following bug:
1. Tree is alive in 2016, 2018, dies in 2023
2. If we zero the 2023 biomass to 0 before gap-filling...
3. Gap-filling would extrapolate that 0 backwards to 2016 and 2018
4. Result: incorrectly shows 0 biomass for years when tree was alive

The correct order is:
1. Apply `apply_dead_status_corrections()` to determine which trees are dead (sets `corrected_is_dead` column)
2. Perform gap-filling (interpolates NaN values based on valid observations)
3. Apply `zero_biomass_for_dead_trees()` to set dead tree biomass to 0

### Interpreting Results for Sites Without AGB Data

For sites like MOAB that have trees but no NEONForestAGB data:
- Plot-years with live trees will show NaN biomass (can't estimate)
- Plot-years with only dead trees or no trees will show 0 biomass
- The `unaccounted_trees` table can help identify which trees lack estimates

## Future Improvements

- Add support for vst_shrubgroup data (currently not used)
- Add support for vst_non-woody data (currently not used)
- Add more sophisticated gap-filling methods (e.g., species-specific growth curves)
- Add validation checks for data quality flags
