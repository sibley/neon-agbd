# Claude Notes for neon-agbd

This file contains notes for future sessions working with this codebase.

## Code Structure

The `/neon_agbd/` package contains:

- **constants.py** - Shared constants (at package root)
- **vst/** - Vegetation structure processing submodule

### constants.py
All hardcoded constants used across the codebase:
   - `DEAD_STATUSES` - Plant status values indicating dead trees
   - `LIVE_STATUSES` - Plant status values indicating live trees
   - `TREE_GROWTH_FORMS` - Growth forms that qualify as trees
   - `SMALL_WOODY_GROWTH_FORMS` - Growth forms that qualify as small woody
   - `DIAMETER_THRESHOLD` - Diameter cutoff (10cm) for tree vs small woody
   - `ALLOMETRY_COLS` - Names of allometry columns
   - `KG_TO_MG` - Unit conversion factor

### vst/data_loader.py
Functions for loading and preparing data:
   - `load_dp1_data()` - Load DP1.10098.001 pickle files
   - `load_neon_forest_agb()` - Load and concatenate NEONForestAGB CSVs
   - `pivot_agb_by_allometry()` - Convert long to wide format for AGB
   - `merge_agb_with_apparent_individual()` - Join AGB with vst_apparentindividual
   - `get_plot_years_from_perplotperyear()` - Extract plot-year combinations with sampled areas

### vst/gap_filling.py
Functions for filling missing biomass values:
   - Uses linear interpolation when 2+ observations exist
   - Uses constant fill when 1 observation exists
   - Leaves NA when 0 observations exist

### vst/biomass_calculator.py
Functions for computing plot-level biomass:
   - Categorizes individuals as 'tree', 'small_woody', or 'other'
   - Trees: growthForm in [single bole tree, multi-bole tree, small tree] AND stemDiameter >= 10cm
   - Small woody: growthForm in [small tree, sapling, single shrub, small shrub] AND stemDiameter < 10cm

### vst/main.py
Main workflow orchestration:
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

### Sampled Areas
Sampled areas are obtained from `vst_perplotperyear` columns (NOT GeoJSON plot polygons):
- `totalSampledAreaTrees` - Area where trees ≥10cm were measured (400 or 800 m²)
- `totalSampledAreaShrubSapling` - Area where shrubs/saplings were measured (8-800 m²)

These are year-specific as they can vary between survey campaigns.

### Biomass Units
- NEONForestAGB provides individual tree AGB in **kg** (kilograms)
- Output biomass density is reported in **Mg/ha** (megagrams per hectare, equivalent to tonnes per hectare)
- Conversion factor: `KG_TO_MG = 1/1000`

### Small Woody Calculation
Small woody biomass density is calculated by:
1. Sum biomass of all measured small woody individuals
2. Divide by `totalSampledAreaShrubSapling` for that year

When no measured individuals exist, the biomass is reported as NaN (not 0).

## Known Issues / Edge Cases

1. **Same-year duplicate observations**: Fixed by using mean value instead of linear regression when all observations are from the same year.

2. **Missing sampled areas**: If `totalSampledAreaTrees` is NaN for all years of a plot, that plot is skipped with a warning.

3. **AGBAnnighofer NaN values**: For many sites/species, this allometry type returns NaN values. This is expected behavior from the NEONForestAGB dataset.

## Usage Example

All data loading functions require **absolute paths** (no defaults). This allows reading data from any location.

```python
from pathlib import Path
from neon_agbd.vst.main import compute_site_biomass_full

# Set up absolute paths
data_root = Path("/path/to/data")
dp1_dir = str(data_root / "DP1.10098")
agb_dir = str(data_root / "NEONForestAGB")

# Single site
results = compute_site_biomass_full(
    site_id='SJER',
    dp1_data_dir=dp1_dir,
    agb_data_dir=agb_dir
)
```

## Output Format

The `plot_biomass` DataFrame has the following columns:
- siteID, plotID, year
- totalSampledAreaTrees_m2, totalSampledAreaShrubSapling_m2
- tree_AGBJenkins, tree_AGBChojnacky, tree_AGBAnnighofer (Mg/ha)
- n_trees, n_filled, n_removed, n_not_qualified
- small_woody_AGBJenkins, small_woody_AGBChojnacky, small_woody_AGBAnnighofer (Mg/ha)
- n_small_woody_total, n_small_woody_measured
- n_unaccounted_trees
- total_AGBJenkins, total_AGBChojnacky, total_AGBAnnighofer
- annual_growth_t-1_to_t

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
- `plot_jenkins_ts`: Interpolated time series for Jenkins allometry
- `plot_chojnacky_ts`: Interpolated time series for Chojnacky allometry
- `plot_annighofer_ts`: Interpolated time series for Annighofer allometry
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
- `annual_growth_t-1_to_t`: Year-over-year growth rate (Mg/ha/year) in plot_biomass
- Individual trees still have both year-over-year and cumulative growth per allometry

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
Plant statuses are classified into three categories (see `constants.py`):
- **DEAD_STATUSES**: Standing dead, Downed, Dead broken bole, Lost fate unknown, Lost burned, Lost herbivory, Lost presumed dead
- **REMOVED_STATUSES**: Removed, No longer qualifies (handled separately with distinct markers)
- **LIVE_STATUSES**: Live, Live broken bole, Live physically damaged, etc.
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

## Session 4 Updates (2026-01-13)

### Dead Status Forward/Back-Fill

The dead status handling now includes:
1. **Forward-fill**: Once a tree is dead, it stays dead for all subsequent years
2. **Back-fill**: If the first actual observation is dead, prior gap-filled years are also marked dead

This prevents incorrect biomass values from being extrapolated to years when trees should have 0 biomass.

### Removed/Not-Qualified Status Handling

Two statuses are now handled separately from dead trees:
- **Removed**: Tree physically cut and removed by human activity (NEON.DOC.000987vM)
- **No longer qualifies**: Tree no longer meets measurement criteria (e.g., badly broken)

Both are treated like dead trees (biomass = 0 from status appearance onward) but with distinct gapFilling markers:
- `gapFilling = 'REMOVED'` for removed trees
- `gapFilling = 'NOT_QUALIFIED'` for not-qualified trees

The constants are now separated in `constants.py`:
```python
DEAD_STATUSES = {'Standing dead', 'Downed', 'Dead, broken bole', ...}
REMOVED_STATUSES = {'Removed', 'No longer qualifies'}
```

### New Count Columns in plot_biomass

Three new columns track the composition of each plot-year:
- `n_filled` - count of gap-filled tree records
- `n_removed` - count of trees with "Removed" status
- `n_not_qualified` - count of trees with "No longer qualifies" status

### Growth Column Changes

- Renamed `growth` to `annual_growth_t-1_to_t` for clarity
- Removed `growth_cumu` column from plot_biomass (still available in individual_trees)

### Interpolated Time Series Tables

Three new wide-format tables are now included in the output:
- `plot_jenkins_ts`
- `plot_chojnacky_ts`
- `plot_annighofer_ts`

Each table has one row per plot with:
- `siteID`, `plotID` as identifiers
- `agb_YYYY` columns for each year (interpolated between surveys)
- `change_YYYY` columns for annual change (NaN for first survey year)

**Interpolation logic**: For years between survey years, values are linearly interpolated. Years outside a plot's survey range are NaN.

### Known Data Quality Issues

See `known_issues.md` for documented issues in source data. Example:
- ABBY_073 in 2018 has erroneous 36.7 cm measurement for a vine maple that's actually 1-3 cm

### NEONForestAGB Merge Limitation

The current `pivot_agb_by_allometry()` function pivots on `individualID` and `date` only, which can cause issues when an individual has multiple stems with different diameters measured on the same date. The first AGB value encountered is used for all stems. This is a known limitation that may need addressing for multi-stem accuracy.

## Session 5 Updates (2026-01-14) - Sampled Area Methodology

### Critical Discovery: Plot Polygon Areas vs Actual Sampled Areas

**Problem identified**: The previous implementation used GeoJSON plot polygon areas (400m² or 1600m²) to calculate biomass density. This is incorrect because NEON uses nested subplot sampling, particularly for 40×40m tower plots.

### NEON Sampling Strategy Research

After consultation with NEON staff and detailed research of documentation:

#### Distributed Plots
- **Always 20×20m (400 m²)**
- **Fully sampled** for trees ≥10cm DBH
- No subsampling of the plot area for trees

#### Tower Plots

| Site Vegetation | Plot Dimensions | Trees Sampled Area | Notes |
|-----------------|-----------------|-------------------|-------|
| Short-stature (grassland/shrubland) | 20×20m | 400 m² | Identical to distributed plots |
| Tall-stature (forest/savannah) | 40×40m | 800 m² | **Only 2 of 4 subplots** randomly selected |

#### Key Findings from Data Analysis

Verified in actual data (HARV, WREF, DELA, etc.):
- `totalSampledAreaTrees` = 400 m² for distributed plots
- `totalSampledAreaTrees` = 800 m² for 40×40m tower plots (2 × 400m² subplots)
- `totalSampledAreaShrubSapling` varies significantly (8 m² to 800 m²) based on nested subplot selection

#### Subplot Consistency Across Years

**Important**: The same subplots are measured in each survey year. Verified at WREF:
```
WREF_070: 2017, 2019, 2020 → always 21_400|39_400
WREF_071: 2017, 2019, 2020 → always 21_400|23_400
WREF_073: 2017-2023 (6 years) → always 23_400|39_400
```

Subplots are randomly selected initially but then **fixed** for all subsequent remeasurements.

#### Trees ≥10cm Are Not Further Subsampled

From NEON VST Protocol (NEON.DOC.000987):
> "Nested subplots are not employed for individuals with DBH ≥ 10 cm."

Within the sampled area (whether 400 m² or 800 m²), ALL trees ≥10cm are measured.

### Code Changes Implemented

1. **Removed GeoJSON plot polygon dependency** - `plot_polygons_path` parameter is now deprecated
2. **Year-specific sampled areas** - Both tree and small_woody biomass now use year-specific values from `vst_perplotperyear`
3. **New output columns**:
   - `totalSampledAreaTrees_m2` - replaces `plotArea_m2`
   - `totalSampledAreaShrubSapling_m2` - new column for small woody area

### Updated Biomass Calculation

**Trees**:
```
biomass_density_Mg_ha = sum(tree_biomass_kg) / totalSampledAreaTrees_ha * KG_TO_MG
```

**Small Woody** (simplified from previous extrapolation method):
```
biomass_density_Mg_ha = sum(measured_biomass_kg) / totalSampledAreaShrubSapling_ha * KG_TO_MG
```

The previous small_woody calculation multiplied average biomass by total count - this was incorrect. The new method simply divides total measured biomass by the sampled area, which properly accounts for the nested subplot sampling.

### Impact on Results

For sites with 40×40m tower plots (tall-stature forests), previous biomass density estimates may have been **underestimated by up to 50%** because we were dividing by 1600 m² instead of 800 m².

### Reference Documentation

- [NEON VST Protocol (NEON.DOC.000987)](https://data.neonscience.org/api/v0/documents/NEON.DOC.000987vJ)
- [Meier et al. 2023 - Spatial and temporal sampling strategy](https://esajournals.onlinelibrary.wiley.com/doi/10.1002/ecs2.4455)
- [NEON Quick Start Guide DP1.10098.001](https://data.neonscience.org/data-products/DP1.10098.001)

## Future Improvements

- Add support for vst_shrubgroup data (currently not used)
- Add support for vst_non-woody data (currently not used)
- Add more sophisticated gap-filling methods (e.g., species-specific growth curves)
- Add validation checks for data quality flags
- Fix NEONForestAGB merge to preserve stem-level AGB granularity
