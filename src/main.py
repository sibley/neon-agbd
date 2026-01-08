"""
Main workflow orchestration for computing plot-level AGB estimates
from NEON vegetation structure and NEONForestAGB data.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Optional

from .data_loader import (
    load_dp1_data,
    load_neon_forest_agb,
    load_plot_areas,
    pivot_agb_by_allometry,
    merge_agb_with_apparent_individual,
    extract_year_from_event_id,
    get_unique_plot_years,
)
from .gap_filling import (
    gap_fill_plot_data,
    create_complete_individual_year_grid,
)
from .biomass_calculator import (
    add_category_column,
    aggregate_plot_biomass_all_years,
    ALLOMETRY_COLS,
)


def compute_site_biomass(
    site_id: str,
    dp1_data_dir: str = "./data/DP1.10098",
    agb_data_dir: str = "./data/NEONForestAGB",
    plot_polygons_path: str = "./data/plot_polygons/NEON_TOS_Plot_Polygons.geojson",
    apply_gap_filling: bool = True,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Compute plot-level AGB estimates for all plots and years at a NEON site.

    This is the main workflow function that:
    1. Loads DP1.10098 data for the site
    2. Loads and filters NEONForestAGB data
    3. Merges AGB estimates with apparent individual data
    4. Applies gap filling for missing biomass values
    5. Categorizes individuals as trees or small_woody
    6. Calculates plot-level biomass density for each year

    Parameters
    ----------
    site_id : str
        Four-character NEON site code (e.g., 'SJER', 'HARV')
    dp1_data_dir : str
        Path to directory containing DP1.10098 pickle files
    agb_data_dir : str
        Path to directory containing NEONForestAGB CSV files
    plot_polygons_path : str
        Path to the plot polygons GeoJSON file
    apply_gap_filling : bool
        Whether to apply gap filling for missing biomass values
    verbose : bool
        Whether to print progress messages

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - siteID: Site identifier
        - plotID: Plot identifier
        - year: Sampling year
        - plotArea_m2: Plot area in square meters
        - tree_AGBJenkins, tree_AGBChojnacky, tree_AGBAnnighofer: Tree biomass density (Mg/ha)
        - n_trees: Number of trees
        - small_woody_AGBJenkins, small_woody_AGBChojnacky, small_woody_AGBAnnighofer: Small woody biomass density (Mg/ha)
        - n_small_woody_total: Total number of small woody individuals
        - n_small_woody_measured: Number of small woody individuals with measurements

    Notes
    -----
    Biomass density is reported in Mg/ha (megagrams per hectare, equivalent to tonnes per hectare).
    NEONForestAGB provides individual tree AGB in kg, which is converted to Mg/ha during calculation.
    """
    if verbose:
        print(f"Processing site: {site_id}")

    # Step 1: Load DP1 data
    if verbose:
        print("  Loading DP1.10098 data...")
    dp1_data = load_dp1_data(site_id, dp1_data_dir)
    vst_ai = dp1_data['vst_apparentindividual'].copy()

    # Step 2: Load NEONForestAGB data
    if verbose:
        print("  Loading NEONForestAGB data...")
    agb_df = load_neon_forest_agb(site_id, agb_data_dir)

    # Step 3: Pivot AGB data and merge with vst_apparentindividual
    if verbose:
        print("  Merging AGB estimates with apparent individual data...")
    agb_pivoted = pivot_agb_by_allometry(agb_df)
    merged_df = merge_agb_with_apparent_individual(vst_ai, agb_pivoted)

    # Add year column
    merged_df['year'] = merged_df['eventID'].apply(extract_year_from_event_id)

    # Step 4: Load plot areas
    if verbose:
        print("  Loading plot area data...")
    plot_areas = load_plot_areas(plot_polygons_path)
    plot_areas_site = plot_areas[plot_areas['siteID'] == site_id]

    # Get unique plot-year combinations
    plot_years = get_unique_plot_years(merged_df)

    # Step 5: Categorize individuals
    if verbose:
        print("  Categorizing individuals (tree vs small_woody)...")
    merged_df = add_category_column(merged_df)

    # Step 6: Process each plot
    if verbose:
        print("  Computing plot-level biomass...")

    all_results = []
    unique_plots = plot_years['plotID'].unique()

    for plot_id in unique_plots:
        # Get years for this plot
        years = plot_years[plot_years['plotID'] == plot_id]['year'].tolist()

        # Get plot area
        plot_area_row = plot_areas_site[plot_areas_site['plotID'] == plot_id]
        if len(plot_area_row) == 0:
            if verbose:
                print(f"    Warning: No plot area found for {plot_id}, skipping...")
            continue

        plot_area_m2 = plot_area_row['plotSize'].iloc[0]

        # Get data for this plot
        plot_df = merged_df[merged_df['plotID'] == plot_id].copy()

        # Apply gap filling if requested
        if apply_gap_filling:
            # Create complete grid and fill gaps
            plot_df = create_complete_individual_year_grid(plot_df, plot_id, years)
            plot_df = gap_fill_plot_data(plot_df, ALLOMETRY_COLS)
            # Re-categorize after gap filling (category may be NA for new rows)
            plot_df = add_category_column(plot_df)

        # Calculate biomass for all years
        plot_results = aggregate_plot_biomass_all_years(
            plot_df, plot_area_m2, years, site_id, plot_id
        )
        all_results.append(plot_results)

    # Combine all results
    if all_results:
        results_df = pd.concat(all_results, ignore_index=True)
    else:
        results_df = pd.DataFrame()

    if verbose:
        print(f"  Done! Computed biomass for {len(results_df)} plot-year combinations.")

    return results_df


def compute_all_sites_biomass(
    site_ids: List[str],
    dp1_data_dir: str = "./data/DP1.10098",
    agb_data_dir: str = "./data/NEONForestAGB",
    plot_polygons_path: str = "./data/plot_polygons/NEON_TOS_Plot_Polygons.geojson",
    apply_gap_filling: bool = True,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Compute plot-level AGB estimates for multiple NEON sites.

    Parameters
    ----------
    site_ids : List[str]
        List of four-character NEON site codes
    dp1_data_dir : str
        Path to directory containing DP1.10098 pickle files
    agb_data_dir : str
        Path to directory containing NEONForestAGB CSV files
    plot_polygons_path : str
        Path to the plot polygons GeoJSON file
    apply_gap_filling : bool
        Whether to apply gap filling for missing biomass values
    verbose : bool
        Whether to print progress messages

    Returns
    -------
    pd.DataFrame
        Combined DataFrame with results for all sites
    """
    all_site_results = []

    for site_id in site_ids:
        try:
            site_results = compute_site_biomass(
                site_id=site_id,
                dp1_data_dir=dp1_data_dir,
                agb_data_dir=agb_data_dir,
                plot_polygons_path=plot_polygons_path,
                apply_gap_filling=apply_gap_filling,
                verbose=verbose
            )
            all_site_results.append(site_results)
        except Exception as e:
            if verbose:
                print(f"  Error processing site {site_id}: {e}")
            continue

    if all_site_results:
        return pd.concat(all_site_results, ignore_index=True)
    else:
        return pd.DataFrame()


# List of all available sites (from README)
ALL_SITES = [
    'DELA', 'LENO', 'TALL', 'BONA', 'DEJU', 'HEAL', 'SRER', 'SJER', 'SOAP',
    'TEAK', 'CPER', 'NIWO', 'RMNP', 'DSNY', 'OSBS', 'JERC', 'PUUM', 'KONZ',
    'UKFS', 'SERC', 'HARV', 'UNDE', 'BART', 'JORN', 'DCFS', 'NOGP', 'WOOD',
    'GUAN', 'LAJA', 'GRSM', 'ORNL', 'CLBJ', 'MOAB', 'ONAQ', 'BLAN', 'MLBS',
    'SCBI', 'ABBY', 'WREF', 'STEI', 'TREE', 'YELL'
]


if __name__ == "__main__":
    # Example usage: process a single site
    import sys

    if len(sys.argv) > 1:
        site = sys.argv[1].upper()
    else:
        site = 'SJER'

    print(f"Computing biomass for site: {site}")
    results = compute_site_biomass(site)

    if not results.empty:
        print("\nResults preview:")
        print(results.head(10))

        # Save results
        output_file = f"./output/{site}_biomass.csv"
        Path("./output").mkdir(exist_ok=True)
        results.to_csv(output_file, index=False)
        print(f"\nResults saved to: {output_file}")
