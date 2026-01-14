"""
Biomass calculation functions for computing plot-level AGB estimates.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple

from ..constants import (
    TREE_GROWTH_FORMS,
    SMALL_WOODY_GROWTH_FORMS,
    DIAMETER_THRESHOLD,
    ALLOMETRY_COLS,
    KG_TO_MG,
)


def categorize_individual(row: pd.Series) -> str:
    """
    Categorize an individual as 'tree', 'small_woody', or 'other'.

    Rules:
    - 'tree': growthForm in TREE_GROWTH_FORMS AND stemDiameter >= 10cm
    - 'small_woody': growthForm in SMALL_WOODY_GROWTH_FORMS AND stemDiameter < 10cm
    - 'other': everything else

    Parameters
    ----------
    row : pd.Series
        A row from the vst_apparentindividual table

    Returns
    -------
    str
        Category: 'tree', 'small_woody', or 'other'
    """
    growth_form = row.get('growthForm', '')
    stem_diameter = row.get('stemDiameter', np.nan)

    # Handle missing values
    if pd.isna(growth_form) or growth_form == '':
        return 'other'

    if pd.isna(stem_diameter):
        # If no diameter measurement, we can't categorize properly
        # but we can still count small_woody individuals
        if growth_form in SMALL_WOODY_GROWTH_FORMS:
            return 'small_woody'
        return 'other'

    # Apply categorization rules
    if growth_form in TREE_GROWTH_FORMS and stem_diameter >= DIAMETER_THRESHOLD:
        return 'tree'
    elif growth_form in SMALL_WOODY_GROWTH_FORMS and stem_diameter < DIAMETER_THRESHOLD:
        return 'small_woody'
    else:
        return 'other'


def add_category_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a 'category' column to the dataframe based on growth form and diameter.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with growthForm and stemDiameter columns

    Returns
    -------
    pd.DataFrame
        DataFrame with added 'category' column
    """
    df = df.copy()
    df['category'] = df.apply(categorize_individual, axis=1)
    return df


def calculate_tree_biomass_density(
    trees_df: pd.DataFrame,
    sampled_area_m2: float,
    year: int
) -> Dict[str, float]:
    """
    Calculate tree biomass density for a specific year.

    Uses the actual sampled area (totalSampledAreaTrees) which reflects
    the area where trees were actually measured. For 40x40m tower plots
    at tall-stature sites, this is typically 800 m² (2 of 4 subplots).
    For 20x20m distributed plots, this is 400 m².

    Parameters
    ----------
    trees_df : pd.DataFrame
        DataFrame containing only tree-category individuals for a plot,
        with allometry columns and 'year' column
    sampled_area_m2 : float
        The totalSampledAreaTrees in square meters for this specific year
        (the area where trees were actually sampled)
    year : int
        Year to calculate for

    Returns
    -------
    Dict[str, float]
        Dictionary with keys for each allometry type containing the
        biomass density in Mg/ha (tonnes per hectare)
    """
    # Convert sampled area to hectares
    sampled_area_ha = sampled_area_m2 / 10000.0 if not pd.isna(sampled_area_m2) else np.nan

    # Filter to the specified year
    year_df = trees_df[trees_df['year'] == year]

    result = {}

    # Identify live trees (not dead) for the NaN check
    if 'corrected_is_dead' in year_df.columns:
        live_mask = year_df['corrected_is_dead'] == False
        live_trees = year_df[live_mask]
    else:
        live_trees = year_df

    for col in ALLOMETRY_COLS:
        if col in year_df.columns:
            if len(year_df) == 0:
                # No trees at all - biomass is 0
                result[f'tree_{col}'] = 0.0
            elif len(live_trees) > 0 and live_trees[col].isna().all():
                # Live trees exist but ALL have NaN biomass - can't estimate
                result[f'tree_{col}'] = np.nan
            elif pd.isna(sampled_area_ha) or sampled_area_ha <= 0:
                # No valid sampled area - can't calculate density
                result[f'tree_{col}'] = np.nan
            else:
                # Either no live trees (only dead with 0), or some live trees have valid biomass
                # Sum all valid values (0 for dead, actual values for live with estimates)
                total_biomass_kg = year_df[col].sum(skipna=True)
                biomass_density_kg_ha = total_biomass_kg / sampled_area_ha
                result[f'tree_{col}'] = biomass_density_kg_ha * KG_TO_MG
        else:
            result[f'tree_{col}'] = np.nan

    # Count number of trees
    result['n_trees'] = len(year_df)

    # Count gap-filled, removed, and not-qualified trees
    if 'gapFilling' in year_df.columns:
        result['n_filled'] = (year_df['gapFilling'] == 'FILLED').sum()
        result['n_removed'] = (year_df['gapFilling'] == 'REMOVED').sum()
        result['n_not_qualified'] = (year_df['gapFilling'] == 'NOT_QUALIFIED').sum()
    else:
        result['n_filled'] = 0
        result['n_removed'] = 0
        result['n_not_qualified'] = 0

    return result


def calculate_small_woody_biomass_density(
    small_woody_df: pd.DataFrame,
    sampled_area_m2: float,
    year: int
) -> Dict[str, float]:
    """
    Calculate small woody biomass density for a specific year.

    The calculation:
    1. Sum biomass of all measured small_woody individuals
    2. Divide by totalSampledAreaShrubSapling to get density

    This uses the actual sampled area for shrubs/saplings, which may be a
    nested subplot smaller than the full plot area.

    Parameters
    ----------
    small_woody_df : pd.DataFrame
        DataFrame containing only small_woody-category individuals for a plot,
        with allometry columns and 'year' column
    sampled_area_m2 : float
        The totalSampledAreaShrubSapling in square meters for this specific year
        (the area where shrubs/saplings were actually sampled)
    year : int
        Year to calculate for

    Returns
    -------
    Dict[str, float]
        Dictionary with keys for each allometry type containing the
        biomass density in Mg/ha (tonnes per hectare)
    """
    # Convert sampled area to hectares
    sampled_area_ha = sampled_area_m2 / 10000.0 if not pd.isna(sampled_area_m2) else np.nan

    # Filter to the specified year
    year_df = small_woody_df[small_woody_df['year'] == year]

    # Total count of small_woody individuals
    n_total = len(year_df)

    result = {}
    for col in ALLOMETRY_COLS:
        if col in year_df.columns:
            # Get only measured individuals (those with non-NA biomass values)
            measured_df = year_df[year_df[col].notna()]
            n_measured = len(measured_df)

            if n_measured > 0:
                # Sum biomass of all measured individuals
                total_biomass_kg = measured_df[col].sum()
                # Convert to density in Mg/ha (tonnes/ha)
                if sampled_area_ha > 0 and not np.isnan(sampled_area_ha):
                    biomass_density_kg_ha = total_biomass_kg / sampled_area_ha
                    result[f'small_woody_{col}'] = biomass_density_kg_ha * KG_TO_MG
                else:
                    result[f'small_woody_{col}'] = np.nan
            else:
                # No measured individuals
                result[f'small_woody_{col}'] = 0.0 if n_total == 0 else np.nan
        else:
            result[f'small_woody_{col}'] = np.nan

    # Count statistics
    result['n_small_woody_total'] = n_total
    # Count measured (those with at least one allometry value)
    has_measurement = year_df[ALLOMETRY_COLS].notna().any(axis=1)
    result['n_small_woody_measured'] = has_measurement.sum()

    return result


def calculate_plot_year_biomass(
    plot_df: pd.DataFrame,
    year: int,
    site_id: str,
    plot_id: str,
    tree_sampled_area_m2: float,
    small_woody_sampled_area_m2: float
) -> Dict:
    """
    Calculate all biomass metrics for a single plot-year combination.

    Parameters
    ----------
    plot_df : pd.DataFrame
        DataFrame containing all individuals for a plot (already categorized),
        with allometry columns and 'year' column
    year : int
        Year to calculate for
    site_id : str
        Site ID
    plot_id : str
        Plot ID
    tree_sampled_area_m2 : float
        The totalSampledAreaTrees for this specific year.
        For 40x40m tower plots, typically 800 m² (2 of 4 subplots).
        For 20x20m distributed plots, typically 400 m².
    small_woody_sampled_area_m2 : float
        The totalSampledAreaShrubSapling for this specific year.
        Can vary significantly based on nested subplot selection.

    Returns
    -------
    Dict
        Dictionary containing all biomass and count metrics for the plot-year
    """
    # Separate by category
    trees_df = plot_df[plot_df['category'] == 'tree']
    small_woody_df = plot_df[plot_df['category'] == 'small_woody']

    # Calculate biomass densities using year-specific sampled areas
    tree_results = calculate_tree_biomass_density(trees_df, tree_sampled_area_m2, year)
    small_woody_results = calculate_small_woody_biomass_density(small_woody_df, small_woody_sampled_area_m2, year)

    # Combine results
    result = {
        'siteID': site_id,
        'plotID': plot_id,
        'year': year,
        'totalSampledAreaTrees_m2': tree_sampled_area_m2,
        'totalSampledAreaShrubSapling_m2': small_woody_sampled_area_m2,
    }
    result.update(tree_results)
    result.update(small_woody_results)

    return result


def aggregate_plot_biomass_all_years(
    plot_df: pd.DataFrame,
    years: List[int],
    site_id: str,
    plot_id: str,
    tree_sampled_areas: Dict[int, float],
    small_woody_sampled_areas: Dict[int, float]
) -> pd.DataFrame:
    """
    Calculate biomass metrics for a plot across all sampled years.

    Parameters
    ----------
    plot_df : pd.DataFrame
        DataFrame containing all individuals for a plot (already categorized)
    years : List[int]
        List of years to calculate for
    site_id : str
        Site ID
    plot_id : str
        Plot ID
    tree_sampled_areas : Dict[int, float]
        Dictionary mapping year to totalSampledAreaTrees for that year.
        For 40x40m tower plots, typically 800 m² (2 of 4 subplots).
        For 20x20m distributed plots, typically 400 m².
    small_woody_sampled_areas : Dict[int, float]
        Dictionary mapping year to totalSampledAreaShrubSapling for that year.
        Can vary significantly based on nested subplot selection.

    Returns
    -------
    pd.DataFrame
        DataFrame with one row per year, containing all biomass metrics
    """
    results = []
    for year in years:
        # Get year-specific sampled areas (use NaN if not available)
        tree_area = tree_sampled_areas.get(year, np.nan)
        sw_area = small_woody_sampled_areas.get(year, np.nan)

        year_result = calculate_plot_year_biomass(
            plot_df, year, site_id, plot_id,
            tree_sampled_area_m2=tree_area,
            small_woody_sampled_area_m2=sw_area
        )
        results.append(year_result)

    return pd.DataFrame(results)
