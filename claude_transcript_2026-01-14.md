# Claude Session Transcript - 2026-01-14

## Topic: NEON Plot Sampling Methodology and Biomass Calculation Updates

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
