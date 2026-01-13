"""
Main workflow orchestration for computing plot-level AGB estimates
from NEON vegetation structure and NEONForestAGB data.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Any
from scipy import stats

from .data_loader import (
    load_dp1_data,
    load_neon_forest_agb,
    load_plot_areas,
    pivot_agb_by_allometry,
    merge_agb_with_apparent_individual,
    extract_year_from_event_id,
    get_unique_plot_years,
    get_plot_years_from_perplotperyear,
)
from .gap_filling import (
    gap_fill_plot_data,
    create_complete_individual_year_grid,
    forward_fill_growth_form,
    apply_dead_status_corrections,
    zero_biomass_for_dead_trees,
)
from .biomass_calculator import (
    add_category_column,
    aggregate_plot_biomass_all_years,
)
from ..constants import (
    ALLOMETRY_COLS,
    TREE_GROWTH_FORMS,
    DIAMETER_THRESHOLD,
)


def calculate_growth_rate(current_biomass: float, previous_biomass: float,
                          current_year: int, previous_year: int) -> float:
    """
    Calculate growth rate in tonnes/year between two survey periods.

    Parameters
    ----------
    current_biomass : float
        Biomass at current survey (Mg/ha)
    previous_biomass : float
        Biomass at previous survey (Mg/ha)
    current_year : int
        Current survey year
    previous_year : int
        Previous survey year

    Returns
    -------
    float
        Growth rate in tonnes/year, or NaN if inputs invalid
    """
    if pd.isna(current_biomass) or pd.isna(previous_biomass):
        return np.nan

    year_diff = current_year - previous_year
    if year_diff <= 0:
        return np.nan

    return (current_biomass - previous_biomass) / year_diff


def calculate_cumulative_growth(years: np.ndarray, biomass: np.ndarray) -> float:
    """
    Calculate cumulative average growth rate using linear regression slope.

    Parameters
    ----------
    years : np.ndarray
        Array of survey years
    biomass : np.ndarray
        Array of biomass values corresponding to years

    Returns
    -------
    float
        Slope of linear regression (tonnes/year), or NaN if insufficient data
    """
    # Remove NaN values
    valid_mask = ~np.isnan(biomass)
    years_valid = years[valid_mask]
    biomass_valid = biomass[valid_mask]

    if len(years_valid) < 2:
        return np.nan

    # Check if we have variation in years
    if len(np.unique(years_valid)) < 2:
        return np.nan

    try:
        slope, _, _, _, _ = stats.linregress(years_valid, biomass_valid)
        return slope
    except Exception:
        return np.nan


def create_empty_plot_year_row(
    site_id: str,
    plot_id: str,
    year: int,
    plot_area_m2: float,
    site_has_agb_data: bool,
    has_trees_in_vst_ai: bool = False,
    has_small_woody_in_vst_ai: bool = False
) -> Dict:
    """
    Create a row for a plot-year with no woody individuals or no AGB data.

    Parameters
    ----------
    site_id : str
        Site identifier
    plot_id : str
        Plot identifier
    year : int
        Survey year
    plot_area_m2 : float
        Plot area in square meters
    site_has_agb_data : bool
        Whether the site has NEONForestAGB data
    has_trees_in_vst_ai : bool
        Whether trees >=10cm exist in vst_apparentindividual for this plot-year
    has_small_woody_in_vst_ai : bool
        Whether small_woody exist in vst_apparentindividual for this plot-year

    Returns
    -------
    Dict
        Row dictionary with appropriate 0/NaN values
    """
    # Determine tree biomass value
    # 0 = no trees present, NaN = trees present but can't estimate
    if has_trees_in_vst_ai and not site_has_agb_data:
        tree_value = np.nan
    else:
        tree_value = 0.0

    # Determine small_woody biomass value
    if has_small_woody_in_vst_ai and not site_has_agb_data:
        sw_value = np.nan
    else:
        sw_value = 0.0

    return {
        'siteID': site_id,
        'plotID': plot_id,
        'year': year,
        'plotArea_m2': plot_area_m2,
        'tree_AGBJenkins': tree_value,
        'tree_AGBChojnacky': tree_value,
        'tree_AGBAnnighofer': tree_value,
        'n_trees': 0,
        'n_filled': 0,
        'n_removed': 0,
        'n_not_qualified': 0,
        'small_woody_AGBJenkins': sw_value,
        'small_woody_AGBChojnacky': sw_value,
        'small_woody_AGBAnnighofer': sw_value,
        'n_small_woody_total': 0,
        'n_small_woody_measured': 0,
    }


def identify_unaccounted_trees(
    vst_ai: pd.DataFrame,
    vst_mapping: pd.DataFrame,
    merged_df: pd.DataFrame,
    site_id: str
) -> pd.DataFrame:
    """
    Identify trees that are unaccounted for in the biomass calculations.

    Two categories:
    - UNMEASURED: Trees in vst_mappingandtagging that never appear in measurements
    - NO_ALLOMETRY: Trees with diameter measurements but no biomass estimates

    Parameters
    ----------
    vst_ai : pd.DataFrame
        The vst_apparentindividual table
    vst_mapping : pd.DataFrame
        The vst_mappingandtagging table
    merged_df : pd.DataFrame
        Merged dataframe with biomass columns and category
    site_id : str
        Site identifier

    Returns
    -------
    pd.DataFrame
        DataFrame with unaccounted trees and their status
    """
    unaccounted_records = []

    # Get all individuals from mapping table for this site
    mapping_individuals = set(vst_mapping['individualID'].unique())

    # Get all individuals that appear in apparent individual
    measured_individuals = set(vst_ai['individualID'].unique())

    # Category 1: UNMEASURED - in mapping but never in apparent individual
    unmeasured = mapping_individuals - measured_individuals

    for ind_id in unmeasured:
        # Get info from mapping table
        mapping_row = vst_mapping[vst_mapping['individualID'] == ind_id].iloc[0]
        record = {
            'siteID': site_id,
            'plotID': mapping_row.get('plotID', np.nan),
            'individualID': ind_id,
            'scientificName': mapping_row.get('scientificName', np.nan),
            'taxonID': mapping_row.get('taxonID', np.nan),
            'status': 'UNMEASURED',
            'reason': 'Never measured in survey campaigns'
        }
        unaccounted_records.append(record)

    # Category 2: NO_ALLOMETRY - has measurements but no biomass for any allometry
    # Filter to trees only (we only track unaccounted trees, not small_woody)
    if 'category' in merged_df.columns:
        trees_df = merged_df[merged_df['category'] == 'tree'].copy()
    else:
        # If no category yet, filter by growth form and diameter
        trees_df = merged_df[
            (merged_df['growthForm'].isin(TREE_GROWTH_FORMS)) &
            (merged_df['stemDiameter'] >= DIAMETER_THRESHOLD)
        ].copy()

    # Find individuals with at least one diameter measurement
    has_diameter = trees_df[trees_df['stemDiameter'].notna()]['individualID'].unique()

    for ind_id in has_diameter:
        ind_df = trees_df[trees_df['individualID'] == ind_id]

        # Check if ANY allometry value exists for this individual
        has_any_allometry = False
        for col in ALLOMETRY_COLS:
            if col in ind_df.columns and ind_df[col].notna().any():
                has_any_allometry = True
                break

        if not has_any_allometry:
            # Get best available info from mapping or apparent individual
            first_row = ind_df.iloc[0]

            # Try to get scientific name from mapping
            mapping_match = vst_mapping[vst_mapping['individualID'] == ind_id]
            if len(mapping_match) > 0:
                sci_name = mapping_match.iloc[0].get('scientificName', np.nan)
                taxon_id = mapping_match.iloc[0].get('taxonID', np.nan)
            else:
                sci_name = np.nan
                taxon_id = np.nan

            record = {
                'siteID': site_id,
                'plotID': first_row.get('plotID', np.nan),
                'individualID': ind_id,
                'scientificName': sci_name,
                'taxonID': taxon_id,
                'status': 'NO_ALLOMETRY',
                'reason': 'Has diameter measurements but no biomass estimates'
            }
            unaccounted_records.append(record)

    return pd.DataFrame(unaccounted_records)


def create_individual_tree_table(
    merged_df: pd.DataFrame,
    vst_mapping: pd.DataFrame,
    site_id: str
) -> pd.DataFrame:
    """
    Create a table of individual tree measurements in long form.

    Parameters
    ----------
    merged_df : pd.DataFrame
        Merged dataframe with biomass columns and categories
    vst_mapping : pd.DataFrame
        The vst_mappingandtagging table for time-invariant attributes
    site_id : str
        Site identifier

    Returns
    -------
    pd.DataFrame
        Long-form table with one row per tree per survey year
    """
    # Filter to trees only
    if 'category' not in merged_df.columns:
        merged_df = add_category_column(merged_df)

    trees_df = merged_df[merged_df['category'] == 'tree'].copy()

    if trees_df.empty:
        return pd.DataFrame()

    # For multi-stem trees, aggregate biomass by summing across stems per year
    # First, get the columns we need to aggregate
    # Use lambda with min_count to preserve NaN when all values are NaN
    def sum_preserve_nan(x):
        """Sum values, but return NaN if all values are NaN."""
        if x.isna().all():
            return np.nan
        return x.sum()

    agg_cols = {col: sum_preserve_nan for col in ALLOMETRY_COLS if col in trees_df.columns}

    # Add other aggregations
    agg_cols['stemDiameter'] = 'max'  # Take max diameter for the individual
    agg_cols['height'] = 'max'
    agg_cols['plantStatus'] = 'first'  # Take first status (representative)

    # Also keep corrected_is_dead if present
    if 'corrected_is_dead' in trees_df.columns:
        agg_cols['corrected_is_dead'] = 'first'

    # Also keep gapFilling if present
    if 'gapFilling' in trees_df.columns:
        agg_cols['gapFilling'] = 'first'

    # Group by individual and year
    grouped = trees_df.groupby(['individualID', 'year', 'plotID']).agg(agg_cols).reset_index()

    # Merge with mapping table to get time-invariant attributes
    mapping_cols = ['individualID', 'scientificName', 'taxonID', 'genus',
                    'family', 'taxonRank', 'pointID', 'stemDistance', 'stemAzimuth']
    mapping_subset = vst_mapping[vst_mapping['individualID'].isin(grouped['individualID'].unique())]

    # Take most recent entry per individual from mapping
    mapping_subset = mapping_subset.sort_values('date').groupby('individualID').last().reset_index()
    mapping_cols_available = [c for c in mapping_cols if c in mapping_subset.columns]

    # Merge
    result = grouped.merge(
        mapping_subset[mapping_cols_available],
        on='individualID',
        how='left'
    )

    # Add site ID
    result['siteID'] = site_id

    # Calculate growth rates per individual
    result = result.sort_values(['individualID', 'year']).reset_index(drop=True)

    # Calculate growth for each allometry type
    for col in ALLOMETRY_COLS:
        if col not in result.columns:
            continue

        growth_col = f'growth_{col}'
        growth_cumu_col = f'growth_cumu_{col}'

        result[growth_col] = np.nan
        result[growth_cumu_col] = np.nan

        for ind_id in result['individualID'].unique():
            ind_mask = result['individualID'] == ind_id
            ind_df = result[ind_mask].copy()

            if len(ind_df) < 1:
                continue

            # Calculate year-over-year growth
            years = ind_df['year'].values
            biomass = ind_df[col].values

            growth_values = [np.nan]  # First year has no growth
            for i in range(1, len(ind_df)):
                growth = calculate_growth_rate(
                    biomass[i], biomass[i-1],
                    years[i], years[i-1]
                )
                growth_values.append(growth)

            result.loc[ind_mask, growth_col] = growth_values

            # Calculate cumulative growth
            cumu_growth = calculate_cumulative_growth(years, biomass)
            result.loc[ind_mask, growth_cumu_col] = cumu_growth

    # Reorder columns
    first_cols = ['siteID', 'plotID', 'individualID', 'year']
    allometry_cols_present = [c for c in ALLOMETRY_COLS if c in result.columns]
    growth_cols = [c for c in result.columns if c.startswith('growth_')]
    other_cols = [c for c in result.columns if c not in first_cols + allometry_cols_present + growth_cols]

    result = result[first_cols + allometry_cols_present + growth_cols + other_cols]

    return result


def add_growth_columns_to_output(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add annual_growth_t-1_to_t column to the output biomass table.

    Growth is calculated using the sum of tree and small_woody biomass
    for each allometry type (using Jenkins as the primary allometry).

    Parameters
    ----------
    df : pd.DataFrame
        Output dataframe with biomass columns per plot-year

    Returns
    -------
    pd.DataFrame
        DataFrame with added growth column
    """
    df = df.copy()
    df = df.sort_values(['plotID', 'year']).reset_index(drop=True)

    # Calculate total biomass for each allometry type
    for col in ALLOMETRY_COLS:
        tree_col = f'tree_{col}'
        sw_col = f'small_woody_{col}'
        total_col = f'total_{col}'

        if tree_col in df.columns and sw_col in df.columns:
            df[total_col] = df[tree_col].fillna(0) + df[sw_col].fillna(0)
        elif tree_col in df.columns:
            df[total_col] = df[tree_col]
        elif sw_col in df.columns:
            df[total_col] = df[sw_col]
        else:
            df[total_col] = np.nan

    # Add growth column (renamed from 'growth')
    df['annual_growth_t-1_to_t'] = np.nan

    # Use Jenkins as the primary allometry for growth calculations
    # (or first available)
    primary_total_col = None
    for col in ALLOMETRY_COLS:
        total_col = f'total_{col}'
        if total_col in df.columns and df[total_col].notna().any():
            primary_total_col = total_col
            break

    if primary_total_col is None:
        return df

    # Calculate growth per plot
    for plot_id in df['plotID'].unique():
        plot_mask = df['plotID'] == plot_id
        plot_df = df[plot_mask].sort_values('year')

        if len(plot_df) < 1:
            continue

        years = plot_df['year'].values
        biomass = plot_df[primary_total_col].values

        # Year-over-year growth
        growth_values = [np.nan]  # First year is NA
        for i in range(1, len(plot_df)):
            growth = calculate_growth_rate(
                biomass[i], biomass[i-1],
                years[i], years[i-1]
            )
            growth_values.append(growth)

        df.loc[plot_mask, 'annual_growth_t-1_to_t'] = growth_values

    return df


def create_interpolated_timeseries(
    plot_biomass_df: pd.DataFrame,
    allometry_col: str
) -> pd.DataFrame:
    """
    Create an interpolated time series table for a specific allometry type.

    For each plot, creates a continuous time series with values for every year
    between the first and last survey years. Values are linearly interpolated
    between actual survey years.

    Parameters
    ----------
    plot_biomass_df : pd.DataFrame
        The plot_biomass output table with total_AGBxxx columns
    allometry_col : str
        The allometry column name (e.g., 'AGBJenkins')

    Returns
    -------
    pd.DataFrame
        Wide-format table with one row per plot, columns:
        - siteID, plotID, plotArea_m2: Plot identifiers
        - agb_YYYY: Interpolated biomass for each year
        - change_YYYY: Annual change from previous year (NaN for first year)
    """
    total_col = f'total_{allometry_col}'

    if total_col not in plot_biomass_df.columns:
        return pd.DataFrame()

    df = plot_biomass_df.copy()
    df = df.sort_values(['plotID', 'year'])

    # Get global year range across all plots
    all_years = sorted(df['year'].unique())
    if len(all_years) == 0:
        return pd.DataFrame()

    min_year = min(all_years)
    max_year = max(all_years)

    results = []

    for plot_id in df['plotID'].unique():
        plot_df = df[df['plotID'] == plot_id].sort_values('year')

        if plot_df.empty:
            continue

        # Get plot metadata (time-invariant)
        site_id = plot_df['siteID'].iloc[0]
        plot_area = plot_df['plotArea_m2'].iloc[0]

        # Get survey years and biomass values for this plot
        survey_years = plot_df['year'].values
        survey_biomass = plot_df[total_col].values

        # Determine year range for this plot (first to last survey)
        plot_min_year = int(survey_years.min())
        plot_max_year = int(survey_years.max())

        # Create a row with plot identifiers
        row = {
            'siteID': site_id,
            'plotID': plot_id,
            'plotArea_m2': plot_area,
        }

        # Create interpolated values for all years in the plot's range
        interpolated_biomass = {}

        for year in range(plot_min_year, plot_max_year + 1):
            if year in survey_years:
                # Use actual survey value
                idx = np.where(survey_years == year)[0][0]
                interpolated_biomass[year] = survey_biomass[idx]
            else:
                # Interpolate between surrounding survey years
                # Find the closest survey years before and after
                years_before = survey_years[survey_years < year]
                years_after = survey_years[survey_years > year]

                if len(years_before) > 0 and len(years_after) > 0:
                    year_before = years_before.max()
                    year_after = years_after.min()

                    idx_before = np.where(survey_years == year_before)[0][0]
                    idx_after = np.where(survey_years == year_after)[0][0]

                    biomass_before = survey_biomass[idx_before]
                    biomass_after = survey_biomass[idx_after]

                    if pd.notna(biomass_before) and pd.notna(biomass_after):
                        # Linear interpolation
                        fraction = (year - year_before) / (year_after - year_before)
                        interpolated_biomass[year] = biomass_before + fraction * (biomass_after - biomass_before)
                    else:
                        interpolated_biomass[year] = np.nan
                else:
                    # Outside survey range (shouldn't happen given our year range)
                    interpolated_biomass[year] = np.nan

        # Add agb_YEAR columns
        for year in range(min_year, max_year + 1):
            col_name = f'agb_{year}'
            if year in interpolated_biomass:
                row[col_name] = interpolated_biomass[year]
            else:
                row[col_name] = np.nan

        # Add change_YEAR columns
        prev_biomass = None
        for year in range(min_year, max_year + 1):
            col_name = f'change_{year}'
            current_biomass = interpolated_biomass.get(year, np.nan)

            if prev_biomass is not None and pd.notna(prev_biomass) and pd.notna(current_biomass):
                row[col_name] = current_biomass - prev_biomass
            else:
                row[col_name] = np.nan

            # Update prev_biomass only if this year is within the plot's survey range
            if year >= plot_min_year and year <= plot_max_year:
                prev_biomass = current_biomass

        results.append(row)

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)

    # Order columns: identifiers first, then agb_YEAR, then change_YEAR
    id_cols = ['siteID', 'plotID', 'plotArea_m2']
    agb_cols = sorted([c for c in result_df.columns if c.startswith('agb_')])
    change_cols = sorted([c for c in result_df.columns if c.startswith('change_')])

    ordered_cols = id_cols + agb_cols + change_cols
    result_df = result_df[ordered_cols]

    return result_df


def compute_site_biomass_full(
    site_id: str,
    dp1_data_dir: str,
    agb_data_dir: str,
    plot_polygons_path: str,
    apply_gap_filling: bool = True,
    apply_dead_corrections: bool = True,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Compute comprehensive biomass outputs for a NEON site.

    This function returns a dictionary containing multiple output tables:
    - plot_biomass: Plot-level biomass density with growth metrics
    - unaccounted_trees: Trees not included in calculations
    - individual_trees: Individual tree measurements in long form
    - plot_jenkins_ts: Interpolated time series table for Jenkins allometry
    - plot_chojnacky_ts: Interpolated time series table for Chojnacky allometry
    - plot_annighofer_ts: Interpolated time series table for Annighofer allometry

    Parameters
    ----------
    site_id : str
        Four-character NEON site code (e.g., 'SJER', 'HARV')
    dp1_data_dir : str
        Absolute path to directory containing DP1.10098 pickle files
    agb_data_dir : str
        Absolute path to directory containing NEONForestAGB CSV files
    plot_polygons_path : str
        Absolute path to the plot polygons GeoJSON file
    apply_gap_filling : bool
        Whether to apply gap filling for missing biomass values
    apply_dead_corrections : bool
        Whether to apply dead status corrections and zero biomass for dead trees
    verbose : bool
        Whether to print progress messages

    Returns
    -------
    Dict[str, Any]
        Dictionary containing:
        - 'plot_biomass': DataFrame with plot-level biomass and growth
        - 'unaccounted_trees': DataFrame with trees not in calculations
        - 'individual_trees': DataFrame with individual tree measurements
        - 'plot_jenkins_ts': DataFrame with interpolated Jenkins time series
        - 'plot_chojnacky_ts': DataFrame with interpolated Chojnacky time series
        - 'plot_annighofer_ts': DataFrame with interpolated Annighofer time series
        - 'site_id': The site identifier
        - 'metadata': Dictionary with processing information
    """
    if verbose:
        print(f"Processing site: {site_id}")

    # Step 1: Load DP1 data
    if verbose:
        print("  Loading DP1.10098 data...")
    dp1_data = load_dp1_data(site_id, dp1_data_dir)
    vst_ai = dp1_data['vst_apparentindividual'].copy()
    vst_mapping = dp1_data['vst_mappingandtagging'].copy()
    vst_ppy = dp1_data['vst_perplotperyear'].copy()

    # Step 2: Load NEONForestAGB data
    if verbose:
        print("  Loading NEONForestAGB data...")
    agb_df = load_neon_forest_agb(agb_data_dir, site_id)
    site_has_agb_data = len(agb_df) > 0

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

    # Get unique plot-year combinations from vst_perplotperyear (authoritative source)
    # This includes plots that were surveyed but had no woody vegetation
    plot_years = get_plot_years_from_perplotperyear(vst_ppy)
    if verbose:
        print(f"  Found {len(plot_years)} plot-year combinations from vst_perplotperyear")

    # Step 5: Categorize individuals
    if verbose:
        print("  Categorizing individuals (tree vs small_woody)...")
    merged_df = add_category_column(merged_df)

    # Step 5b: Apply dead status corrections for trees
    # NOTE: We only apply status corrections here (to get corrected_is_dead column).
    # We do NOT zero dead tree biomass yet - that happens AFTER gap filling.
    # Otherwise gap filling would use the 0s to extrapolate into years when trees were alive.
    if apply_dead_corrections:
        if verbose:
            print("  Applying dead status corrections...")
        # Only apply to trees
        trees_mask = merged_df['category'] == 'tree'
        trees_df = merged_df[trees_mask].copy()

        if not trees_df.empty:
            trees_df = apply_dead_status_corrections(trees_df)
            # Do NOT call zero_biomass_for_dead_trees here - wait until after gap filling

            # Update merged_df with corrected tree data
            merged_df = merged_df[~trees_mask].copy()
            merged_df = pd.concat([merged_df, trees_df], ignore_index=True)

    # Step 6: Identify unaccounted trees
    if verbose:
        print("  Identifying unaccounted trees...")
    unaccounted_trees = identify_unaccounted_trees(vst_ai, vst_mapping, merged_df, site_id)

    # Create unaccounted count per plot
    if not unaccounted_trees.empty:
        unaccounted_by_plot = unaccounted_trees.groupby('plotID').size().reset_index(name='n_unaccounted_trees')
    else:
        unaccounted_by_plot = pd.DataFrame(columns=['plotID', 'n_unaccounted_trees'])

    # Step 7: Process each plot for biomass
    if verbose:
        print("  Computing plot-level biomass...")

    # Pre-compute which plot-years have individuals in vst_ai (for determining 0 vs NaN)
    vst_ai_with_year = vst_ai.copy()
    vst_ai_with_year['year'] = vst_ai_with_year['eventID'].apply(extract_year_from_event_id)

    all_results = []
    all_plot_dfs = []
    unique_plots = plot_years['plotID'].unique()

    for plot_id in unique_plots:
        # Get years for this plot from vst_perplotperyear
        plot_year_rows = plot_years[plot_years['plotID'] == plot_id]
        years = plot_year_rows['year'].tolist()

        # Get plot area - try plot_areas first, then fallback to totalSampledAreaTrees from vst_perplotperyear
        plot_area_row = plot_areas_site[plot_areas_site['plotID'] == plot_id]
        if len(plot_area_row) > 0:
            plot_area_m2 = plot_area_row['plotSize'].iloc[0]
        elif 'totalSampledAreaTrees' in plot_year_rows.columns:
            # Use totalSampledAreaTrees as fallback
            plot_area_m2 = plot_year_rows['totalSampledAreaTrees'].iloc[0]
            if pd.isna(plot_area_m2):
                if verbose:
                    print(f"    Warning: No plot area found for {plot_id}, skipping...")
                continue
        else:
            if verbose:
                print(f"    Warning: No plot area found for {plot_id}, skipping...")
            continue

        # Get data for this plot from merged_df
        plot_df = merged_df[merged_df['plotID'] == plot_id].copy()

        # Check if plot has any data
        if plot_df.empty:
            # No individuals in merged_df for this plot
            # Check vst_ai to determine if there are woody individuals without AGB estimates
            plot_vst_ai = vst_ai_with_year[vst_ai_with_year['plotID'] == plot_id]

            # Create empty rows for each year
            empty_rows = []
            for year in years:
                year_vst_ai = plot_vst_ai[plot_vst_ai['year'] == year]

                # Check for trees (>=10cm) and small_woody (<10cm) in vst_ai
                has_trees = False
                has_small_woody = False
                if not year_vst_ai.empty and 'stemDiameter' in year_vst_ai.columns:
                    has_trees = (year_vst_ai['stemDiameter'] >= DIAMETER_THRESHOLD).any()
                    has_small_woody = (year_vst_ai['stemDiameter'] < DIAMETER_THRESHOLD).any()

                empty_row = create_empty_plot_year_row(
                    site_id, plot_id, year, plot_area_m2,
                    site_has_agb_data, has_trees, has_small_woody
                )
                empty_rows.append(empty_row)

            all_results.append(pd.DataFrame(empty_rows))
            continue

        # Apply gap filling if requested
        if apply_gap_filling:
            # Create complete grid and fill gaps
            plot_df = create_complete_individual_year_grid(plot_df, plot_id, years)
            plot_df = forward_fill_growth_form(plot_df)
            plot_df = gap_fill_plot_data(plot_df, ALLOMETRY_COLS)
            # Re-categorize after gap filling (category may be NA for new rows)
            plot_df = add_category_column(plot_df)

            # Re-apply dead corrections after gap filling
            if apply_dead_corrections:
                trees_mask = plot_df['category'] == 'tree'
                if trees_mask.any():
                    trees_df = plot_df[trees_mask].copy()
                    trees_df = apply_dead_status_corrections(trees_df)
                    trees_df = zero_biomass_for_dead_trees(trees_df, ALLOMETRY_COLS)
                    plot_df = plot_df[~trees_mask].copy()
                    plot_df = pd.concat([plot_df, trees_df], ignore_index=True)
        else:
            # No gap filling, but still need to zero dead trees if corrections are enabled
            if apply_dead_corrections:
                trees_mask = plot_df['category'] == 'tree'
                if trees_mask.any():
                    trees_df = plot_df[trees_mask].copy()
                    trees_df = zero_biomass_for_dead_trees(trees_df, ALLOMETRY_COLS)
                    plot_df = plot_df[~trees_mask].copy()
                    plot_df = pd.concat([plot_df, trees_df], ignore_index=True)

        all_plot_dfs.append(plot_df)

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

    # Combine all plot data for individual tree table
    if all_plot_dfs:
        all_merged_processed = pd.concat(all_plot_dfs, ignore_index=True)
    else:
        all_merged_processed = merged_df

    # Step 8: Add n_unaccounted_trees to results
    if not results_df.empty and not unaccounted_by_plot.empty:
        results_df = results_df.merge(unaccounted_by_plot, on='plotID', how='left')
        results_df['n_unaccounted_trees'] = results_df['n_unaccounted_trees'].fillna(0).astype(int)
    elif not results_df.empty:
        results_df['n_unaccounted_trees'] = 0

    # Step 9: Add growth columns
    if verbose:
        print("  Calculating growth metrics...")
    if not results_df.empty:
        results_df = add_growth_columns_to_output(results_df)

    # Step 10: Create interpolated time series tables
    if verbose:
        print("  Creating interpolated time series tables...")
    plot_jenkins_ts = create_interpolated_timeseries(results_df, 'AGBJenkins')
    plot_chojnacky_ts = create_interpolated_timeseries(results_df, 'AGBChojnacky')
    plot_annighofer_ts = create_interpolated_timeseries(results_df, 'AGBAnnighofer')

    # Step 11: Create individual tree table
    if verbose:
        print("  Creating individual tree table...")
    individual_trees = create_individual_tree_table(all_merged_processed, vst_mapping, site_id)

    if verbose:
        print(f"  Done! Computed biomass for {len(results_df)} plot-year combinations.")
        print(f"  Found {len(unaccounted_trees)} unaccounted trees.")
        print(f"  Created individual tree table with {len(individual_trees)} records.")

    # Build output dictionary - start with input DP1 data and add computed outputs
    output = dp1_data.copy()
    output['plot_biomass'] = results_df
    output['unaccounted_trees'] = unaccounted_trees
    output['individual_trees'] = individual_trees
    output['plot_jenkins_ts'] = plot_jenkins_ts
    output['plot_chojnacky_ts'] = plot_chojnacky_ts
    output['plot_annighofer_ts'] = plot_annighofer_ts
    output['site_id'] = site_id
    output['metadata'] = {
        'apply_gap_filling': apply_gap_filling,
        'apply_dead_corrections': apply_dead_corrections,
        'site_has_agb_data': site_has_agb_data,
        'n_plots': len(unique_plots),
        'n_plot_years': len(results_df),
        'n_unaccounted_trees': len(unaccounted_trees),
        'n_individual_tree_records': len(individual_trees)
    }

    return output


def compute_site_biomass(
    site_id: str,
    dp1_data_dir: str,
    agb_data_dir: str,
    plot_polygons_path: str,
    apply_gap_filling: bool = True,
    apply_dead_corrections: bool = True,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Compute plot-level AGB estimates for all plots and years at a NEON site.

    This is the main workflow function that:
    1. Loads DP1.10098 data for the site
    2. Loads and filters NEONForestAGB data
    3. Merges AGB estimates with apparent individual data
    4. Applies dead status corrections (corrects sandwiched dead->alive patterns)
    5. Applies gap filling for missing biomass values
    6. Categorizes individuals as trees or small_woody
    7. Calculates plot-level biomass density for each year

    Parameters
    ----------
    site_id : str
        Four-character NEON site code (e.g., 'SJER', 'HARV')
    dp1_data_dir : str
        Absolute path to directory containing DP1.10098 pickle files
    agb_data_dir : str
        Absolute path to directory containing NEONForestAGB CSV files
    plot_polygons_path : str
        Absolute path to the plot polygons GeoJSON file
    apply_gap_filling : bool
        Whether to apply gap filling for missing biomass values
    apply_dead_corrections : bool
        Whether to apply dead status corrections and zero biomass for dead trees
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
        - n_unaccounted_trees: Number of unaccounted trees in the plot
        - growth: Growth in tonnes/year since last survey (NA for first survey)
        - growth_cumu: Average growth per year from linear regression of all surveys

    Notes
    -----
    Biomass density is reported in Mg/ha (megagrams per hectare, equivalent to tonnes per hectare).
    NEONForestAGB provides individual tree AGB in kg, which is converted to Mg/ha during calculation.

    Dead status corrections:
    - If a tree's status goes alive->dead->alive, the sandwiched dead status is assumed incorrect
    - If dead status persists (alive->dead->dead), biomass is set to 0 for dead periods
    """
    # Use the full function and extract just the plot_biomass table
    output = compute_site_biomass_full(
        site_id=site_id,
        dp1_data_dir=dp1_data_dir,
        agb_data_dir=agb_data_dir,
        plot_polygons_path=plot_polygons_path,
        apply_gap_filling=apply_gap_filling,
        apply_dead_corrections=apply_dead_corrections,
        verbose=verbose
    )
    return output['plot_biomass']


def compute_all_sites_biomass(
    site_ids: List[str],
    dp1_data_dir: str,
    agb_data_dir: str,
    plot_polygons_path: str,
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
        Absolute path to directory containing DP1.10098 pickle files
    agb_data_dir : str
        Absolute path to directory containing NEONForestAGB CSV files
    plot_polygons_path : str
        Absolute path to the plot polygons GeoJSON file
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
    import pickle

    if len(sys.argv) > 1:
        site = sys.argv[1].upper()
    else:
        site = 'SJER'

    # Determine repo root (this file is in neon_agbd/vst/)
    repo_root = Path(__file__).parent.parent.parent.resolve()

    # Set up paths
    dp1_data_dir = repo_root / "data" / "DP1.10098"
    agb_data_dir = repo_root / "data" / "NEONForestAGB"
    plot_polygons_path = repo_root / "data" / "plot_polygons" / "NEON_TOS_Plot_Polygons.geojson"
    output_dir = repo_root / "output"

    print(f"Computing biomass for site: {site}")

    # Use the full function to get all outputs
    output = compute_site_biomass_full(
        site_id=site,
        dp1_data_dir=str(dp1_data_dir),
        agb_data_dir=str(agb_data_dir),
        plot_polygons_path=str(plot_polygons_path)
    )

    # Create output directory
    output_dir.mkdir(exist_ok=True)

    # Preview results
    if not output['plot_biomass'].empty:
        print("\nPlot biomass preview:")
        print(output['plot_biomass'].head(10))

    if not output['unaccounted_trees'].empty:
        print(f"\nUnaccounted trees: {len(output['unaccounted_trees'])}")
        print(output['unaccounted_trees'].head(5))

    if not output['individual_trees'].empty:
        print(f"\nIndividual tree records: {len(output['individual_trees'])}")
        print(output['individual_trees'].head(5))

    # Save as pickle
    pkl_file = output_dir / f"{site}.pkl"
    with open(pkl_file, 'wb') as f:
        pickle.dump(output, f)
    print(f"\nResults saved to: {pkl_file}")

    # Also save individual CSVs for inspection
    csv_dir = output_dir / "csvs"
    csv_dir.mkdir(exist_ok=True)
    output['plot_biomass'].to_csv(csv_dir / f"{site}_plot_biomass.csv", index=False)
    output['unaccounted_trees'].to_csv(csv_dir / f"{site}_unaccounted_trees.csv", index=False)
    output['individual_trees'].to_csv(csv_dir / f"{site}_individual_trees.csv", index=False)
    print(f"Individual CSVs also saved to {csv_dir}/")
