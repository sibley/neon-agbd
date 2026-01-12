"""
Biomass calculation functions for computing plot-level AGB estimates.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple

from .constants import (
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
    plot_area_m2: float,
    year: int
) -> Dict[str, float]:
    """
    Calculate tree biomass density for a specific year.

    Parameters
    ----------
    trees_df : pd.DataFrame
        DataFrame containing only tree-category individuals for a plot,
        with allometry columns and 'year' column
    plot_area_m2 : float
        Plot area in square meters
    year : int
        Year to calculate for

    Returns
    -------
    Dict[str, float]
        Dictionary with keys for each allometry type containing the
        biomass density in Mg/ha (tonnes per hectare)
    """
    # Convert plot area to hectares
    plot_area_ha = plot_area_m2 / 10000.0

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
            else:
                # Either no live trees (only dead with 0), or some live trees have valid biomass
                # Sum all valid values (0 for dead, actual values for live with estimates)
                total_biomass_kg = year_df[col].sum(skipna=True)
                biomass_density_kg_ha = total_biomass_kg / plot_area_ha if plot_area_ha > 0 else np.nan
                result[f'tree_{col}'] = biomass_density_kg_ha * KG_TO_MG if not np.isnan(biomass_density_kg_ha) else np.nan
        else:
            result[f'tree_{col}'] = np.nan

    # Also count number of trees
    result['n_trees'] = len(year_df)

    return result


def calculate_small_woody_biomass_density(
    small_woody_df: pd.DataFrame,
    plot_area_m2: float,
    year: int
) -> Dict[str, float]:
    """
    Calculate small woody biomass density for a specific year.

    The calculation:
    1. Sum biomass of measured small_woody individuals
    2. Divide by number of measured individuals to get average
    3. Multiply by total number of small_woody individuals in the plot
    4. Divide by plot area to get density

    Parameters
    ----------
    small_woody_df : pd.DataFrame
        DataFrame containing only small_woody-category individuals for a plot,
        with allometry columns and 'year' column
    plot_area_m2 : float
        Plot area in square meters
    year : int
        Year to calculate for

    Returns
    -------
    Dict[str, float]
        Dictionary with keys for each allometry type containing the
        biomass density in Mg/ha (tonnes per hectare)
    """
    # Convert plot area to hectares
    plot_area_ha = plot_area_m2 / 10000.0

    # Filter to the specified year
    year_df = small_woody_df[small_woody_df['year'] == year]

    # Total count of small_woody individuals (including unmeasured)
    n_total = len(year_df)

    result = {}
    for col in ALLOMETRY_COLS:
        if col in year_df.columns:
            # Get only measured individuals (those with non-NA biomass values)
            measured_df = year_df[year_df[col].notna()]
            n_measured = len(measured_df)

            if n_measured > 0 and n_total > 0:
                # Calculate average biomass of measured individuals
                avg_biomass_kg = measured_df[col].mean()
                # Estimate total plot biomass
                total_biomass_kg = avg_biomass_kg * n_total
                # Convert to density in Mg/ha (tonnes/ha)
                biomass_density_kg_ha = total_biomass_kg / plot_area_ha if plot_area_ha > 0 else np.nan
                result[f'small_woody_{col}'] = biomass_density_kg_ha * KG_TO_MG if not np.isnan(biomass_density_kg_ha) else np.nan
            else:
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
    plot_area_m2: float,
    year: int,
    site_id: str,
    plot_id: str
) -> Dict:
    """
    Calculate all biomass metrics for a single plot-year combination.

    Parameters
    ----------
    plot_df : pd.DataFrame
        DataFrame containing all individuals for a plot (already categorized),
        with allometry columns and 'year' column
    plot_area_m2 : float
        Plot area in square meters
    year : int
        Year to calculate for
    site_id : str
        Site ID
    plot_id : str
        Plot ID

    Returns
    -------
    Dict
        Dictionary containing all biomass and count metrics for the plot-year
    """
    # Separate by category
    trees_df = plot_df[plot_df['category'] == 'tree']
    small_woody_df = plot_df[plot_df['category'] == 'small_woody']

    # Calculate biomass densities
    tree_results = calculate_tree_biomass_density(trees_df, plot_area_m2, year)
    small_woody_results = calculate_small_woody_biomass_density(small_woody_df, plot_area_m2, year)

    # Combine results
    result = {
        'siteID': site_id,
        'plotID': plot_id,
        'year': year,
        'plotArea_m2': plot_area_m2,
    }
    result.update(tree_results)
    result.update(small_woody_results)

    return result


def aggregate_plot_biomass_all_years(
    plot_df: pd.DataFrame,
    plot_area_m2: float,
    years: List[int],
    site_id: str,
    plot_id: str
) -> pd.DataFrame:
    """
    Calculate biomass metrics for a plot across all sampled years.

    Parameters
    ----------
    plot_df : pd.DataFrame
        DataFrame containing all individuals for a plot (already categorized)
    plot_area_m2 : float
        Plot area in square meters
    years : List[int]
        List of years to calculate for
    site_id : str
        Site ID
    plot_id : str
        Plot ID

    Returns
    -------
    pd.DataFrame
        DataFrame with one row per year, containing all biomass metrics
    """
    results = []
    for year in years:
        year_result = calculate_plot_year_biomass(
            plot_df, plot_area_m2, year, site_id, plot_id
        )
        results.append(year_result)

    return pd.DataFrame(results)
