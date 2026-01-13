# NEON Plot-Level Aboveground Biomass Density

This repository computes plot-level aboveground biomass density (AGB) estimates from NEON vegetation structure data (DP1.10098.001) and the NEONForestAGB dataset.

## Overview

The workflow processes individual tree measurements, applies gap-filling to create continuous time series, handles dead tree status corrections, and aggregates to plot-level biomass density in Mg/ha (megagrams per hectare).

## Design Considerations

### Individual Classification
- **Trees**: Individuals with `growthForm` in {single bole tree, multi-bole tree, small tree} AND `stemDiameter` >= 10 cm
- **Small woody**: Individuals with `growthForm` in {small tree, sapling, single shrub, small shrub} AND `stemDiameter` < 10 cm
- Other individuals are excluded from biomass calculations

### Dead Tree Handling
Trees marked as dead have their biomass set to **0**. Dead statuses include: `"Standing dead", "Downed", "Dead broken bole", "Lost presumed dead", "Removed".`

**Sandwiched dead correction**: If a tree shows alive → dead → alive pattern across years, the middle "dead" status is assumed to be a measurement error and corrected to alive.

### Gap-Filling Strategy
For each individual, missing biomass values are filled using:
1. **Linear interpolation/extrapolation** if 2+ observations exist
2. **Constant fill** (single value) if exactly 1 observation exists
3. **No fill** (remains NaN) if 0 observations exist

**Critical order of operations**: Gap-filling occurs BEFORE zeroing dead tree biomass. This prevents dead tree zeros from being extrapolated backwards into years when trees were alive.

### Plot-Level Biomass Logic

In order to get a good number for plot-level biomass density, one must consider what to do with plots that have no woody vegetation, plots that have only dead woody veg, plots that have live woody veg but are missing all measurements, and plots that have a mix of live trees with at least 1 valid diameter measurement and live trees with no valid measurements. 

| Scenario | Plot Biomass Value |
|----------|-------------------|
| No trees in plot | 0 |
| Only dead trees | 0 |
| Live trees with valid AGB estimates | Calculated sum (Mg/ha) |
| Live trees, ALL have NaN AGB | NaN |
| Mix of live trees (some valid AGB) + dead trees | Calculated sum |

The key distinction: live trees without any biomass estimates cannot be included in the plot biomass, and are simply left out of biomass calculations, as long as some trees in the plot do have valid measurements. **In the future**, it may be wise to set a threshold here to minimize the impact of missing trees. 

### Small Woody Biomass Calculation
Only a subsample of the small woody individuals are measured. To use those measurements and extrapolate to all of the small woody individuals:
1. Calculate average biomass from measured individuals
2. Multiply by total count of small woody individuals in plot
3. Divide by plot area

If no individuals are measured, small woody biomass = NaN.

### Sites Without NEONForestAGB Data
Seven NEON sites have no data in NEONForestAGB (grasslands, arid sites): CPER, NOGP, DCFS, WOOD, LAJA, MOAB, JORN. For these:
- Plots with live trees → NaN (cannot estimate)
- Plots without live trees → 0 T/ha

These are included because sites with 0 biomass are useful for evaluating the performance of biomass models, comparing with AOP data, etc...

## Workflow DAG

```
                                    ┌─────────────────────┐
                                    │   DP1.10098.001     │
                                    │   (site pickle)     │
                                    └─────────┬───────────┘
                                              │
              ┌───────────────────────────────┼───────────────────────────────┐
              │                               │                               │
              ▼                               ▼                               ▼
┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│  vst_apparentindividual │   │  vst_mappingandtagging  │   │   vst_perplotperyear    │
│  (measurements)         │   │  (taxonomy, location)   │   │   (surveyed plot-years) │
└───────────┬─────────────┘   └───────────┬─────────────┘   └───────────┬─────────────┘
            │                             │                             │
            ▼                             │                             │
┌─────────────────────────┐               │                             │
│  Merge with             │◄──────────────┼─────────────────────────────┘
│  NEONForestAGB          │               │
│  (adds AGB columns)     │               │
└───────────┬─────────────┘               │
            │                             │
            ▼                             │
┌─────────────────────────┐               │
│  Categorize individuals │               │
│  (tree vs small_woody)  │               │
└───────────┬─────────────┘               │
            │                             │
            ├─────────────────────────────┤
            │                             │
            ▼                             ▼
┌─────────────────────────┐   ┌─────────────────────────┐
│       TREES             │   │     SMALL WOODY         │
└───────────┬─────────────┘   └───────────┬─────────────┘
            │                             │
            ▼                             │
┌─────────────────────────┐               │
│  Apply dead status      │               │
│  corrections            │               │
│  (sandwiched fix)       │               │
└───────────┬─────────────┘               │
            │                             │
            ▼                             │
┌─────────────────────────┐               │
│  Create complete grid   │               │
│  (individual × year)    │               │
└───────────┬─────────────┘               │
            │                             │
            ▼                             │
┌─────────────────────────┐               │
│  Gap-fill biomass       │               │
│  (linear interp/extrap) │               │
└───────────┬─────────────┘               │
            │                             │
            ▼                             │
┌─────────────────────────┐               │
│  Zero dead tree biomass │               │
│  (AFTER gap-filling)    │               │
└───────────┬─────────────┘               │
            │                             │
            ▼                             ▼
┌─────────────────────────┐   ┌─────────────────────────┐
│  Sum tree biomass       │   │  Avg measured × total   │
│  per plot-year          │   │  per plot-year          │
└───────────┬─────────────┘   └───────────┬─────────────┘
            │                             │
            └──────────────┬──────────────┘
                           │
                           ▼
            ┌─────────────────────────────┐
            │  Combine tree + small_woody │
            │  Calculate growth rates     │
            │  Count unaccounted trees    │
            └─────────────┬───────────────┘
                          │
                          ▼
            ┌─────────────────────────────┐
            │       OUTPUT TABLES         │
            │  - plot_biomass             │
            │  - individual_trees         │
            │  - unaccounted_trees        │
            └─────────────────────────────┘
```

## Input Data

### DP1.10098.001 (Vegetation Structure)
- **Source**: NEON data portal, pre-downloaded as pickle files per site
- **Key tables**: `vst_apparentindividual`, `vst_mappingandtagging`, `vst_perplotperyear`
- **Location**: `./data/DP1.10098/`

### NEONForestAGB
- **Source**: NEONForestAGBv2 dataset (CSV files)
- **Contains**: Individual-level biomass estimates using three allometry equations
- **Location**: `./data/NEONForestAGB/`

### Plot Polygons
- **Source**: NEON TOS Plot Polygons GeoJSON
- **Contains**: Plot areas in m²
- **Location**: `./data/plot_polygons/`

## Outputs

The `compute_site_biomass_full()` function returns a dictionary containing:

### 1. Plot Biomass Table (`plot_biomass`)
One row per plot-year combination with columns:

- **Identifiers**: `siteID`, `plotID`, `year`, `plotArea_m2`
- **Tree biomass (Mg/ha)**:
  - `tree_AGBJenkins` - Jenkins et al. 2003 allometry
  - `tree_AGBChojnacky` - Chojnacky et al. 2014 allometry
  - `tree_AGBAnnighofer` - Annighofer et al. allometry
  - `n_trees` - Count of trees in plot-year
- **Small woody biomass (Mg/ha)**:
  - `small_woody_AGBJenkins`, `small_woody_AGBChojnacky`, `small_woody_AGBAnnighofer`
  - `n_small_woody_total` - Total count
  - `n_small_woody_measured` - Count with measurements
- **Totals**:
  - `total_AGBJenkins`, `total_AGBChojnacky`, `total_AGBAnnighofer` - Tree + small woody
- **Growth metrics**:
  - `growth` - Year-over-year change (Mg/ha/year)
  - `growth_cumu` - Cumulative trend from linear regression slope
- **Quality indicator**: `n_unaccounted_trees` - Trees not included in estimates

### 2. Individual Trees Table (`individual_trees`)
One row per tree per survey year with columns:

- **Identifiers**: `siteID`, `plotID`, `individualID`, `year`
- **Biomass (kg)**: `AGBJenkins`, `AGBChojnacky`, `AGBAnnighofer`
- **Growth rates**: `growth_AGBJenkins`, `growth_cumu_AGBJenkins` (and for other allometries)
- **Measurements**: `stemDiameter`, `height`, `plantStatus`
- **Status**: `corrected_is_dead`, `gapFilling` (ORIGINAL or FILLED)
- **Taxonomy**: `scientificName`, `taxonID`, `genus`, `family`
- **Location**: `pointID`, `stemDistance`, `stemAzimuth`

### 3. Unaccounted Trees Table (`unaccounted_trees`)
Trees excluded from biomass calculations:

- **Columns**: `siteID`, `plotID`, `individualID`, `scientificName`, `taxonID`, `status`, `reason`
- **Reasons**:
  - `UNMEASURED` - In mapping table but never measured
  - `NO_ALLOMETRY` - Has diameter but no biomass estimate from any allometry

### 4. Metadata
- `site_id` - Site identifier
- `site_has_agb_data` - Boolean indicating if NEONForestAGB data exists for site

## Usage

```python
from src.main import compute_site_biomass_full

# Process a single site
results = compute_site_biomass_full('HARV')

# Access output tables
plot_biomass = results['plot_biomass']
individual_trees = results['individual_trees']
unaccounted_trees = results['unaccounted_trees']

# Check metadata
print(f"Site has AGB data: {results['metadata']['site_has_agb_data']}")
```

See `example_run.py` for a complete example that saves outputs as pickle and CSV files.

## File Structure

```
neon-agbd/
├── src/
│   ├── __init__.py
│   ├── constants.py         # Shared constants (growth forms, statuses)
│   ├── data_loader.py       # Data loading and merging functions
│   ├── gap_filling.py       # Gap-filling and dead status corrections
│   ├── biomass_calculator.py # Plot-level biomass calculations
│   └── main.py              # Main workflow orchestration
├── data/
│   ├── DP1.10098/           # Site pickle files
│   ├── NEONForestAGB/       # AGB CSV files
│   └── plot_polygons/       # GeoJSON with plot areas
├── output/                  # Processed results
├── example_run.py           # Example usage script
└── README.md
```

## Notes

- **Units**: Individual biomass in kg; plot-level density in Mg/ha (1 Mg = 1000 kg = 1 tonne)
- **Multi-stem trees**: Biomass summed across stems; individual is alive if ANY stem is alive
- **AGBAnnighofer**: Often NaN for many species/sites - this is expected
- **Surveyed plot-years**: Determined from `vst_perplotperyear`, not presence of individuals
