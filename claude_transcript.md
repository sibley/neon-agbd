# Claude Code Conversation Transcript

## Session 1 - Initial Implementation

**Date**: 2026-01-08

### User Request
Asked Claude to read the `claude_prompt.md` file and implement the workflow described in `README.md` for computing plot-level aboveground biomass density (AGB) from NEON vegetation structure data and the NEONForestAGB dataset.

### Claude's Actions

1. **Read project documentation**
   - Read `claude_prompt.md` to understand the task
   - Read `README.md` to understand the workflow
   - Read documentation in `/docs/` folder for detailed data specifications
   - Read `docs/DP1.10098.001/NEON.QSG.DP1.10098.001v2.md`
   - Read `docs/NEONForestAGB/README.md`

2. **Examined data structures**
   - Loaded sample pickle file (SJER.pkl) to understand DP1.10098.001 structure
   - Examined NEONForestAGB CSV structure
   - Examined plot polygon GeoJSON structure
   - Reviewed existing notebooks in `/notebooks/` for reference

3. **Key findings from data exploration**
   - eventID format: `vst_SJER_2015` (year is last 4 characters)
   - growthForm values: 'single bole tree', 'small shrub', 'single shrub', 'multi-bole tree', 'sapling', 'small tree', 'liana'
   - Some small_woody individuals have stemDiameter measurements, others don't
   - Three allometry types: AGBJenkins, AGBChojnacky, AGBAnnighofer

4. **Implemented code modules**
   - Created `/src/` directory
   - Created `data_loader.py` with data loading functions
   - Created `gap_filling.py` with gap-filling logic
   - Created `biomass_calculator.py` with biomass calculation functions
   - Created `main.py` with main workflow orchestration
   - Created `__init__.py` for package structure

5. **Fixed bug during testing**
   - Initial test revealed error with linear regression when all years are identical
   - Fixed by detecting this case and using mean value instead

6. **Tested the code**
   - Successfully tested with SJER site (102 plot-year combinations)
   - Successfully tested with HARV site (186 plot-year combinations)

### Output Format
The code produces a DataFrame with 13 columns:
- siteID, plotID, year, plotArea_m2
- tree_AGBJenkins, tree_AGBChojnacky, tree_AGBAnnighofer (Mg/ha)
- n_trees
- small_woody_AGBJenkins, small_woody_AGBChojnacky, small_woody_AGBAnnighofer (Mg/ha)
- n_small_woody_total, n_small_woody_measured

### Notes
- Created `claude.md` with detailed notes for future sessions
- AGBAnnighofer values are often NaN depending on site/species
- Small woody calculation uses average of measured individuals multiplied by total count

---

## Session 1 - Update 1: Unit Conversion

**Date**: 2026-01-08

### User Request
Asked Claude to add conversion of biomass units from kg/ha to Mg/ha (tonnes per hectare).

### Claude's Actions

1. **Updated `biomass_calculator.py`**
   - Added `KG_TO_MG = 1/1000.0` constant
   - Updated `calculate_tree_biomass_density()` to convert to Mg/ha
   - Updated `calculate_small_woody_biomass_density()` to convert to Mg/ha
   - Updated docstrings to reflect new units

2. **Updated `__init__.py`**
   - Added `KG_TO_MG` to exports

3. **Updated `main.py`**
   - Updated docstrings to reflect Mg/ha units

4. **Updated documentation**
   - Updated `claude.md` with biomass units section
   - Updated `claude_transcript.md` with this session

---

## Session 2 - Version 2 Features

**Date**: 2026-01-11

### User Request
Asked Claude to read `claude_prompt2.md` and implement several improvements:
1. Dead status persistence logic for trees
2. Unaccounted trees table (UNMEASURED and NO_ALLOMETRY status)
3. Growth columns (year-over-year and cumulative) in output table
4. Individual tree measurements table in long form
5. Example script for running the workflow and saving as pkl

### Claude's Actions

1. **Re-familiarized with codebase**
   - Read original `claude_prompt.md` and `README.md`
   - Read all existing source files in `/src/`
   - Explored DP1 data structure to understand `plantStatus` values
   - Examined multi-stem tree behavior in the data

2. **Implemented dead status persistence logic** (`gap_filling.py`)
   - Added `DEAD_STATUSES` and `LIVE_STATUSES` constants
   - Added `is_dead_status()` and `is_live_status()` helper functions
   - Added `get_individual_status_by_year()` to determine overall status per year
   - Added `correct_sandwiched_dead_status()` to fix alive→dead→alive patterns
   - Added `apply_dead_status_corrections()` to process full dataset
   - Added `zero_biomass_for_dead_trees()` to set biomass=0 for persistent dead

3. **Implemented unaccounted trees table** (`main.py`)
   - Added `identify_unaccounted_trees()` function
   - UNMEASURED: Trees in `vst_mappingandtagging` but never in measurements
   - NO_ALLOMETRY: Trees with diameter but no biomass from any allometry
   - Includes siteID, plotID, individualID, scientificName, taxonID, status, reason

4. **Implemented growth calculations** (`main.py`)
   - Added `calculate_growth_rate()` for year-over-year growth
   - Added `calculate_cumulative_growth()` using linear regression slope
   - Added `add_growth_columns_to_output()` for plot-level growth
   - Added `n_unaccounted_trees` column to output table

5. **Implemented individual tree measurements table** (`main.py`)
   - Added `create_individual_tree_table()` function
   - Long form with one row per tree per survey year
   - Includes AGB for all three allometry types
   - Includes growth rates per allometry (year-over-year and cumulative)
   - Merges time-invariant attributes from `vst_mappingandtagging`
   - Aggregates multi-stem trees by summing biomass per year

6. **Created new main workflow function** (`main.py`)
   - Added `compute_site_biomass_full()` returning dictionary with all tables
   - Updated `compute_site_biomass()` to use new function (backward compatible)
   - Dictionary contains: plot_biomass, unaccounted_trees, individual_trees, site_id, metadata

7. **Created example script** (`example_run.py`)
   - Processes specified site (default: SJER)
   - Saves output as pkl dictionary
   - Also saves individual CSVs for easy inspection
   - Prints summary of results

8. **Fixed pandas FutureWarning**
   - Replaced `groupby().apply()` with explicit loop to avoid deprecation warning

9. **Tested on multiple sites**
   - SJER: 102 plot-years, 22 unaccounted trees, 548 individual records
   - HARV: 186 plot-years, 1354 unaccounted trees, 10,292 individual records
   - TALL: 141 plot-years, 608 unaccounted trees, 4,300 individual records

### New Output Structure

**plot_biomass table** (19 columns):
- siteID, plotID, year, plotArea_m2
- tree_AGBJenkins, tree_AGBChojnacky, tree_AGBAnnighofer, n_trees
- small_woody_AGBJenkins, small_woody_AGBChojnacky, small_woody_AGBAnnighofer
- n_small_woody_total, n_small_woody_measured
- n_unaccounted_trees
- total_AGBJenkins, total_AGBChojnacky, total_AGBAnnighofer
- growth, growth_cumu

**unaccounted_trees table** (7 columns):
- siteID, plotID, individualID, scientificName, taxonID, status, reason

**individual_trees table** (25 columns):
- siteID, plotID, individualID, year
- AGBJenkins, AGBChojnacky, AGBAnnighofer
- growth_AGBJenkins, growth_cumu_AGBJenkins (and same for other allometries)
- stemDiameter, height, plantStatus, corrected_is_dead
- scientificName, taxonID, genus, family, taxonRank, pointID, stemDistance, stemAzimuth

### Notes
- Updated `claude.md` with Version 2 features documentation
- Dead status is determined at the individual level (if ANY stem is alive, individual is alive)
- Growth calculated using Jenkins allometry as primary (first available)

---

## Session 3 - Non-Forested Sites and Gap-Filling Fix

**Date**: 2026-01-12

### User Request
Asked Claude to handle non-forested sites (grasslands) and sites without NEONForestAGB data appropriately, ensuring plots with no woody vegetation report 0 biomass rather than being excluded.

### Key Issues Discovered

1. **Missing plot-years**: The original implementation only included plot-years where individuals existed in `vst_apparentindividual`, missing plots that were surveyed but had no woody vegetation.

2. **Gap-filling order of operations bug**: Dead trees were being zeroed BEFORE gap-filling, causing the 0 values to be extrapolated backwards into years when trees were alive.

3. **Incorrect NaN vs 0 logic**: Needed clear rules for when to report 0 (no vegetation) vs NaN (vegetation exists but can't estimate biomass).

### Claude's Actions

1. **Used vst_perplotperyear as authoritative source**
   - Added `get_plot_years_from_perplotperyear()` function to `data_loader.py`
   - This table includes ALL surveyed plot-years, including those with no woody vegetation
   - Modified `compute_site_biomass_full()` to use this as the source of plot-years

2. **Created constants.py**
   - Centralized all hardcoded constants (DEAD_STATUSES, LIVE_STATUSES, TREE_GROWTH_FORMS, etc.)
   - Updated all modules to import from constants.py

3. **Fixed gap-filling order of operations** (`main.py`)
   - Initial dead corrections now ONLY apply `apply_dead_status_corrections()` to get the `corrected_is_dead` column
   - `zero_biomass_for_dead_trees()` is now called AFTER gap-filling
   - This prevents dead tree 0 values from being extrapolated into years when trees were alive

4. **Updated biomass calculation logic** (`biomass_calculator.py`)
   - Modified `calculate_tree_biomass_density()` to check live trees separately from dead trees
   - If live trees exist but ALL have NaN biomass → plot biomass = NaN
   - Dead trees (with 0 biomass) are excluded from this check

5. **Added forward-filling for growthForm and stemDiameter** (`gap_filling.py`)
   - Added `forward_fill_growth_form()` function
   - Gap-filled rows now inherit growthForm and stemDiameter from adjacent measurements
   - Handles both NaN and empty string values

6. **Added gapFilling column**
   - Individual tree records now include a `gapFilling` column: 'ORIGINAL' or 'FILLED'

### Plot-Level Biomass Logic

| Scenario | Tree Biomass |
|----------|-------------|
| No trees in plot | 0 |
| Only dead trees | 0 |
| Live trees with valid AGB estimates | Calculated sum |
| Live trees, ALL have NaN AGB (no ForestAGB data) | NaN |
| Mix of live trees (some with valid AGB) + dead trees | Calculated sum |

### Sites Without NEONForestAGB Data

Seven NEON sites have no data in the NEONForestAGB dataset:
- CPER, NOGP, DCFS, WOOD (grasslands)
- LAJA, MOAB, JORN (arid/semi-arid)

For these sites:
- Trees: If live trees exist → NaN (can't estimate); if no live trees → 0
- Small woody: If individuals exist → NaN (can't estimate); if none → 0
- `metadata['site_has_agb_data']` indicates whether the site has ForestAGB data

### Test Results

**MOAB** (site with trees but no AGB data):
- 165 plot-year combinations
- Plot-years with live trees: NaN (correctly indicates can't estimate)
- Plot-years without trees: 0

**HARV** (forested site with AGB data):
- 207 plot-year combinations
- All have valid biomass values (mean: 93.88 Mg/ha)

**CPER** (grassland, no trees, no AGB data):
- 160 plot-year combinations
- All tree biomass = 0
- Small woody with individuals: NaN; without: 0

### Notes
- The `unaccounted_trees` table helps interpret plots where some trees have estimates and others don't
- Updated CLAUDE.md with new functionality documentation

---

## Session 4 - Bug Fixes and New Features

**Date**: 2026-01-13

### User Request
Continuation of debugging session. User asked to:
1. Investigate anomalous biomass changes in specific plots (ABBY_075, ABBY_067, ABBY_007, ABBY_073)
2. Implement proper handling of "Removed" and "No longer qualifies" statuses
3. Add new count columns to track gap-filled, removed, and not-qualified trees
4. Rename growth column and create interpolated time series tables

### Bug Investigation Summary

#### ABBY_075: Dead tree biomass in gap-filled years
- **Issue**: Tree NEON.PLA.D16.ABBY.00012 (171.4 cm dead snag) was contributing ~31,891 kg in gap-filled 2019 when it should be 0
- **Root cause**: Dead status not being forward-filled to gap-filled years
- **Fix**: Added `forward_fill_dead_status()` function - once dead, always dead

#### ABBY_067: Dead snag biomass back-filled to prior years
- **Issue**: Tree NEON.PLA.D16.ABBY.01003 (222 cm dead snag) first observed as dead in 2016, but 2015 was gap-filled and got biomass extrapolated backward
- **Root cause**: First observation being dead wasn't propagating to earlier gap-filled years
- **Fix**: Added `back_fill_dead_status()` function - if first actual observation is dead, mark prior gap-filled years as dead too

#### ABBY_007: Biomass doubling from Removed status
- **Issue**: Trees with both "Live" and "Removed" status in same year were getting AGB values via gap-filling, causing doubled biomass
- **Root cause**: "Removed" status wasn't being handled separately from dead status
- **Fix**: Added `forward_fill_removed_status()` and `forward_fill_not_qualified_status()` functions to set biomass to 0 from status appearance onward

#### ABBY_073: Small woody biomass spike
- **Issue**: ~15 Mg/ha spike in 2018, then drop in 2019
- **Root cause**: Data quality issue in NEONForestAGB - individual NEON.PLA.D16.ABBY.00034 (Acer circinatum, vine maple) had an erroneous 36.7 cm / 741 kg measurement in 2018 when it's actually a 1-3 cm small tree
- **Result**: Documented in `known_issues.md` - this is a source data issue, not a pipeline bug

### Claude's Actions

1. **Implemented dead status forward-fill** (`gap_filling.py`)
   - Added `forward_fill_dead_status()` - ensures once dead, always dead for subsequent years

2. **Implemented dead status back-fill** (`gap_filling.py`)
   - Added `back_fill_dead_status()` - if first actual observation is dead, prior gap-filled years are also marked dead
   - Updated `get_individual_status_by_year()` to track `has_status_observation`

3. **Implemented Removed/Not-Qualified handling** (`gap_filling.py`)
   - Separated `REMOVED_STATUSES` from `DEAD_STATUSES` in `constants.py`
   - Added `forward_fill_removed_status()` and `forward_fill_not_qualified_status()`
   - Updated `zero_biomass_for_dead_trees()` to set gapFilling='REMOVED' or 'NOT_QUALIFIED'

4. **Researched NEON documentation**
   - Found in NEON.DOC.000987vM Table 15:
     - "Removed" = tree physically cut and removed by human activity
     - "No longer qualifies" = tree no longer meets measurement criteria

5. **Added count columns to plot_biomass** (`biomass_calculator.py`)
   - `n_filled` - count of gap-filled tree records
   - `n_removed` - count of trees with "Removed" status
   - `n_not_qualified` - count of trees with "No longer qualifies" status

6. **Updated growth reporting** (`main.py`)
   - Renamed `growth` to `annual_growth_t-1_to_t`
   - Removed `growth_cumu` column from plot_biomass

7. **Created interpolated time series tables** (`main.py`)
   - Added `create_interpolated_timeseries()` function
   - Creates three new tables: `plot_jenkins_ts`, `plot_chojnacky_ts`, `plot_annighofer_ts`
   - One row per plot with `agb_YYYY` and `change_YYYY` columns
   - Linear interpolation between survey years

8. **Created known_issues.md**
   - Documented the NEONForestAGB data quality issue for ABBY_073

### Status Handling Summary

| Status | Classification | Biomass | gapFilling marker |
|--------|---------------|---------|-------------------|
| Standing dead, Downed, etc. | DEAD | 0 | (unchanged) |
| Removed | REMOVED | 0 | 'REMOVED' |
| No longer qualifies | NOT_QUALIFIED | 0 | 'NOT_QUALIFIED' |

### New Output Tables

**Interpolated Time Series** (`plot_jenkins_ts`, `plot_chojnacky_ts`, `plot_annighofer_ts`):
- One row per plot
- `siteID`, `plotID`, `plotArea_m2` as identifiers
- `agb_YYYY` columns with values for each year (interpolated between surveys)
- `change_YYYY` columns with annual change (NaN for first survey year)

**Interpolation method**: For years between survey years, values are linearly interpolated. Example: if surveys in 2016 and 2019, values for 2017 and 2018 are 1/3 and 2/3 of the way between.

### Test Results

**ABBY site after all fixes:**
- 130 plot-year combinations
- 411 unaccounted trees
- 4,258 individual tree records
- New columns (n_filled, n_removed, n_not_qualified) working correctly
- Time series tables generating with proper interpolation

---

## Session 5 - NEON Plot Sampling Methodology and Biomass Calculation Updates

**Date**: 2026-01-14

### Initial Question

User asked about which `totalSampledArea` field in `vst_perplotperyear` corresponds to the small_woody vegetation categories (small tree, sapling, single shrub, small shrub).

### Research Phase 1: Small Woody Sampling Areas

**Finding**: `totalSampledAreaShrubSapling` is the correct field for small_woody categories.

NEON documentation groups these growth forms together for sampling:
- smt = small tree
- sis = single shrub
- sap = sapling
- sms = small shrub

**Issue discovered**: The previous code was using the full plot area (from GeoJSON polygons) for small_woody biomass calculations, not the `totalSampledAreaShrubSapling`.

### Research Phase 2: Tree Sampling Strategy

User consulted with NEON staff who confirmed the need to use proper sampled areas.

**Key research questions investigated**:
1. Are distributed plots fully surveyed or can they be subsampled?
2. What are the dimensions of distributed vs tower plots?
3. Are the same subplots measured each survey year?

### Findings from Documentation Review

#### NEON Plot Types

| Plot Type | Dimensions | Tree Sampled Area | Description |
|-----------|------------|-------------------|-------------|
| Distributed plots | 20×20m | 400 m² | All trees measured in full plot |
| Tower plots (short-stature) | 20×20m | 400 m² | All trees measured in full plot |
| Tower plots (tall-stature) | 40×40m | 800 m² | 2 of 4 subplots randomly selected |

#### Data Verification

Analyzed actual NEON data across multiple sites (HARV, WREF, ABBY, SERC, TALL, KONZ, CPER, DELA, BART):

```
=== Tree sampled areas by site and plot type ===

site    plotType  n_plots     tree_areas
HARV distributed       22        [400.0]
HARV       tower       20 [400.0, 800.0]
WREF       tower       20        [800.0]
WREF distributed       20        [400.0]
SERC       tower       22        [800.0]
SERC distributed       20        [400.0]
KONZ       tower       30        [400.0]   # Short-stature site
KONZ distributed        3        [400.0]
```

Key findings:
- **Distributed plots**: Always 400 m² (20×20m fully sampled)
- **Tower plots at tall-stature sites**: 800 m² (two 20×20m subplots from 40×40m)
- **Tower plots at short-stature sites**: 400 m² (full 20×20m plot)

#### Subplot Consistency Verification

Checked if same subplots are measured each year at WREF:

```
WREF_070: 2017, 2019, 2020 → always 21_400|39_400
WREF_071: 2017, 2019, 2020 → always 21_400|23_400
WREF_073: 2017-2023 (6 years) → always 23_400|39_400
```

**Confirmed**: Subplots are randomly selected initially, then **fixed** for all subsequent remeasurements.

#### Trees ≥10cm Are Not Subsampled

From NEON VST Protocol (NEON.DOC.000987):
> "Nested subplots are not employed for individuals with DBH ≥ 10 cm."

Within the sampled area (400 or 800 m²), ALL trees ≥10cm are measured.

### Code Changes Implemented

#### 1. biomass_calculator.py

**`calculate_tree_biomass_density()`**:
- Renamed `plot_area_m2` → `sampled_area_m2`
- Now uses `totalSampledAreaTrees` instead of plot polygon area

**`calculate_small_woody_biomass_density()`**:
- Now takes `sampled_area_m2` parameter
- Simplified calculation: sum(biomass) / sampled_area
- Previous method (avg × total count) was incorrect

**`calculate_plot_year_biomass()`**:
- Removed `plot_area_m2` parameter
- Added `tree_sampled_area_m2` and `small_woody_sampled_area_m2` parameters

**`aggregate_plot_biomass_all_years()`**:
- Accepts year-specific dictionaries for both tree and small_woody sampled areas

#### 2. main.py

- Removed GeoJSON plot polygon loading
- Now builds year-specific sampled area dictionaries from `vst_perplotperyear`
- `plot_polygons_path` parameter is now deprecated (kept for backward compatibility)
- New output columns: `totalSampledAreaTrees_m2`, `totalSampledAreaShrubSapling_m2`

### Impact Assessment

For sites with 40×40m tower plots (tall-stature forests like HARV, WREF):
- Previous biomass density estimates may have been **underestimated by up to 50%**
- We were dividing by 1600 m² (full plot) instead of 800 m² (actual sampled area)

### Reference Documentation

- [NEON VST Protocol (NEON.DOC.000987)](https://data.neonscience.org/api/v0/documents/NEON.DOC.000987vJ)
- [Meier et al. 2023 - Spatial and temporal sampling strategy](https://esajournals.onlinelibrary.wiley.com/doi/10.1002/ecs2.4455)
- [Barnett et al. 2019 - Plant diversity sampling design](https://esajournals.onlinelibrary.wiley.com/doi/10.1002/ecs2.2603)
- [NEON Quick Start Guide DP1.10098.001](https://data.neonscience.org/data-products/DP1.10098.001)

### Files Modified

1. `neon_agbd/vst/biomass_calculator.py` - Updated all biomass calculation functions
2. `neon_agbd/vst/main.py` - Removed GeoJSON dependency, added sampled area handling
3. `README.md` - Updated documentation to reflect new methodology
4. `CLAUDE.md` - Added Session 5 research notes and updated outdated sections

### Testing

Successfully tested on DELA site:
```
Plot biomass shape: (164, 22)
Sample output showing year-specific sampled areas working correctly.
```

---

## Session 6 - Diameter Outlier Filter and Sampled Area Anomalies

**Date**: 2026-01-15

### User Request
Continuation from previous session to:
1. Integrate `filter_diameter_outliers()` into the main workflow
2. Investigate specific plot anomalies (ABBY_061, BONA_078)
3. Run comprehensive test across all NEON sites to identify sampled area anomalies

### Diameter Outlier Filter

Implemented automatic detection and exclusion of erroneous diameter measurements that create impossible growth patterns.

**Detection criteria**:
- Growth rate from previous year exceeds 10 cm/year, AND
- Shrinkage rate to next year exceeds 5 cm/year

**Implementation details**:
- Filter runs on ALL individuals (not just trees) to catch cases where erroneous measurements push small_woody into tree category
- Handles multi-stem trees by aggregating to max diameter per year before comparing
- Flagged measurements have biomass set to NaN and `gapFilling` set to 'OUTLIER'

### Bug Fixes

#### forward_fill_growth_form() propagating errors
- **Problem**: Function was filling stemDiameter for ALL NaN rows including ORIGINAL measurements with missing data
- **Fix**: Modified to only fill for FILLED (gap-created) rows, not ORIGINAL rows

#### Sandwiched dead correction using gap-filled rows
- **Problem**: Gap-filled rows (no plantStatus) were treated as "alive" evidence, incorrectly flipping dead trees to alive
- **Fix**: Modified `correct_sandwiched_dead_status()` to only consider rows with actual status observations (`has_status_observation=True`)

### Plot Investigations

#### ABBY_061: Biomass dip and resurgence (2018→2019→2020)
- **Finding**: Large dead tree (88.2 cm, ~6000 kg) marked "Dead, broken bole" in 2018 was incorrectly having its dead status flipped to alive by sandwiched correction
- **Resolution**: After fixing sandwiched correction to only use actual observations, plot shows consistent growth

#### BONA_078: Biomass spike in 2021
- **Finding**: `totalSampledAreaTrees` changed from 800 to 400 m² in 2021 only
- **Cause**: Data entry error in `vst_perplotperyear`, not real biomass change
- **Impact**: Total biomass was consistent (~7,250 kg), but dividing by half the area doubled the density

### Comprehensive Sampled Area Anomaly Scan

Ran analysis across all NEON sites to identify plots where `totalSampledAreaTrees` varies between years but tree counts remain consistent.

**Results**: 31 anomalous records across 11 sites

| Pattern | Sites | Issue |
|---------|-------|-------|
| Tower plots at 400 m² (should be 800 m²) | BONA, DELA, GRSM, HARV, JERC, ORNL, OSBS, RMNP, SJER, TEAK | Biomass density doubled |
| ORNL distributed plots at 800 m² in 2015 (should be 400 m²) | ORNL | Biomass density halved |

### Files Modified

1. `neon_agbd/vst/gap_filling.py` - Added `filter_diameter_outliers()`, fixed `forward_fill_growth_form()` and `correct_sandwiched_dead_status()`
2. `neon_agbd/vst/main.py` - Integrated outlier filter into workflow
3. `known_issues.md` - Added sampled area anomalies documentation with full plotID→eventID mapping
4. `README.md` - Added "Diameter Outlier Detection" section
5. `CLAUDE.md` - Added Session 6 documentation

### Anomalous Plot-EventID Mapping

Documented in `known_issues.md`:

```python
ANOMALOUS_SAMPLED_AREA_EVENTS = {
    # Tower plots incorrectly recorded as 400 m² (should be 800 m²)
    'BONA_073': 'vst_BONA_2023',
    'BONA_078': 'vst_BONA_2021',
    'BONA_084': 'vst_BONA_2023',
    'DELA_037': 'vst_DELA_2022',
    'DELA_040': 'vst_DELA_2021',
    'DELA_045': 'vst_DELA_2021',
    'GRSM_059': 'vst_GRSM_2023',
    'GRSM_060': 'vst_GRSM_2023',
    'HARV_038': 'vst_HARV_2023',
    'JERC_048': 'vst_JERC_2019',
    'ORNL_049': 'vst_ORNL_2023',
    'OSBS_028': 'vst_OSBS_2023',
    'RMNP_042': 'vst_RMNP_2022',
    'SJER_046': 'vst_SJER_2023',
    'TEAK_043': 'vst_TEAK_2023',
    # ORNL distributed plots incorrectly recorded as 800 m² (should be 400 m²)
    'ORNL_001': 'vst_ORNL_2015',
    'ORNL_002': 'vst_ORNL_2015',
    # ... (16 ORNL distributed plots total)
}
```
