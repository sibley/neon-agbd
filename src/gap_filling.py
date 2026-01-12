"""
Gap filling functions for missing biomass values in vegetation structure data.
Also handles dead status corrections and related data cleaning.
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Tuple
from scipy import stats

from .constants import DEAD_STATUSES, LIVE_STATUSES


def is_dead_status(status: str) -> bool:
    """
    Determine if a plantStatus value indicates the tree is dead.

    Parameters
    ----------
    status : str
        The plantStatus value

    Returns
    -------
    bool
        True if the status indicates dead, False otherwise
    """
    if pd.isna(status):
        return False
    return status in DEAD_STATUSES


def is_live_status(status: str) -> bool:
    """
    Determine if a plantStatus value indicates the tree is alive.

    Parameters
    ----------
    status : str
        The plantStatus value

    Returns
    -------
    bool
        True if the status indicates alive, False otherwise
    """
    if pd.isna(status):
        return False
    return status in LIVE_STATUSES


def get_individual_status_by_year(df: pd.DataFrame, individual_id: str) -> pd.DataFrame:
    """
    Get the overall status for an individual by year.

    For multi-stem individuals, if ANY stem is alive, the individual is considered alive.
    The status is determined as 'dead' only if ALL stems are dead.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing individual measurements with 'individualID', 'year', 'plantStatus'
    individual_id : str
        The individualID to get status for

    Returns
    -------
    pd.DataFrame
        DataFrame with columns ['individualID', 'year', 'is_dead'] sorted by year
    """
    ind_df = df[df['individualID'] == individual_id].copy()

    if ind_df.empty:
        return pd.DataFrame(columns=['individualID', 'year', 'is_dead'])

    # Group by year and check if any stem is alive
    results = []
    for year in ind_df['year'].unique():
        year_df = ind_df[ind_df['year'] == year]
        statuses = year_df['plantStatus'].unique()
        has_live = any(is_live_status(s) for s in statuses)
        has_dead = any(is_dead_status(s) for s in statuses)
        # Only dead if no live stems and at least one dead stem
        is_dead = not has_live and has_dead
        results.append({'year': year, 'is_dead': is_dead})

    yearly_status = pd.DataFrame(results)
    yearly_status['individualID'] = individual_id
    yearly_status = yearly_status[['individualID', 'year', 'is_dead']].sort_values('year')

    return yearly_status


def correct_sandwiched_dead_status(yearly_status: pd.DataFrame) -> pd.DataFrame:
    """
    Correct "sandwiched" dead statuses where alive->dead->alive pattern occurs.

    If a dead status is sandwiched between two alive statuses, we assume the
    dead status was an error and the tree was actually alive.

    Parameters
    ----------
    yearly_status : pd.DataFrame
        DataFrame with columns ['individualID', 'year', 'is_dead'] sorted by year

    Returns
    -------
    pd.DataFrame
        Corrected DataFrame with same columns, plus 'corrected_is_dead'
    """
    df = yearly_status.copy()
    df = df.sort_values('year').reset_index(drop=True)

    # Initialize corrected status as original
    df['corrected_is_dead'] = df['is_dead'].copy()

    if len(df) < 3:
        return df

    # Look for sandwiched dead status
    for i in range(1, len(df) - 1):
        if df.loc[i, 'is_dead']:  # Current year is dead
            # Check if previous is alive (not dead)
            prev_alive = not df.loc[i-1, 'is_dead']
            # Check if next is alive (not dead)
            next_alive = not df.loc[i+1, 'is_dead']

            if prev_alive and next_alive:
                # Sandwiched dead - correct to alive
                df.loc[i, 'corrected_is_dead'] = False

    return df


def apply_dead_status_corrections(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply dead status corrections to the full dataset for trees.

    This function:
    1. Determines overall status for each individual by year
    2. Corrects sandwiched dead statuses
    3. Adds a 'corrected_is_dead' column to the dataframe

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with tree measurements, must have 'individualID', 'year', 'plantStatus'

    Returns
    -------
    pd.DataFrame
        DataFrame with added 'corrected_is_dead' column
    """
    df = df.copy()

    if 'year' not in df.columns or 'plantStatus' not in df.columns:
        df['corrected_is_dead'] = False
        return df

    # Get unique individuals
    individuals = df['individualID'].unique()

    # Build a mapping of (individualID, year) -> corrected_is_dead
    corrections = {}

    for ind_id in individuals:
        yearly_status = get_individual_status_by_year(df, ind_id)
        if yearly_status.empty:
            continue

        corrected = correct_sandwiched_dead_status(yearly_status)

        for _, row in corrected.iterrows():
            corrections[(row['individualID'], row['year'])] = row['corrected_is_dead']

    # Apply corrections to dataframe
    df['corrected_is_dead'] = df.apply(
        lambda row: corrections.get((row['individualID'], row['year']), False),
        axis=1
    )

    return df


def zero_biomass_for_dead_trees(df: pd.DataFrame, allometry_cols: List[str]) -> pd.DataFrame:
    """
    Set biomass to 0 for trees that are confirmed dead (after correction).

    Only zeros biomass if corrected_is_dead is True - this means the dead
    status was persistent and not a sandwiched error.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'corrected_is_dead' column and allometry columns
    allometry_cols : List[str]
        List of allometry column names to zero out

    Returns
    -------
    pd.DataFrame
        DataFrame with zeroed biomass for dead trees
    """
    df = df.copy()

    if 'corrected_is_dead' not in df.columns:
        return df

    # Zero out biomass for dead trees
    # Dead trees have no living biomass, so their contribution is 0
    dead_mask = df['corrected_is_dead'] == True
    for col in allometry_cols:
        if col in df.columns:
            df.loc[dead_mask, col] = 0.0

    return df


def fit_linear_model(years: np.ndarray, values: np.ndarray) -> Tuple[float, float]:
    """
    Fit a simple linear regression model.

    Parameters
    ----------
    years : np.ndarray
        Array of years (x values)
    values : np.ndarray
        Array of values (y values)

    Returns
    -------
    Tuple[float, float]
        Slope and intercept of the linear fit
    """
    slope, intercept, _, _, _ = stats.linregress(years, values)
    return slope, intercept


def predict_from_linear(year: int, slope: float, intercept: float) -> float:
    """
    Predict a value using a linear model.

    Parameters
    ----------
    year : int
        Year to predict for
    slope : float
        Slope of the linear model
    intercept : float
        Intercept of the linear model

    Returns
    -------
    float
        Predicted value (non-negative, clipped to 0 minimum)
    """
    predicted = slope * year + intercept
    return max(0, predicted)  # Biomass can't be negative


def gap_fill_individual_allometry(
    df: pd.DataFrame,
    individual_id: str,
    allometry_col: str
) -> pd.DataFrame:
    """
    Gap fill missing values for a specific individual and allometry type.

    Logic:
    - If >= 2 observations exist, use linear interpolation/extrapolation
    - If exactly 1 observation exists, use that value for all missing years
    - If 0 observations exist, leave as NA

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing data for one individual, with columns 'year' and
        the specified allometry column
    individual_id : str
        The individualID (for reference, not used in computation)
    allometry_col : str
        Name of the allometry column to gap fill (e.g., 'AGBJenkins')

    Returns
    -------
    pd.DataFrame
        DataFrame with gap-filled values in the allometry column
    """
    df = df.copy()

    # Get valid (non-NA) observations
    valid_mask = df[allometry_col].notna()
    valid_df = df[valid_mask]

    n_valid = len(valid_df)

    if n_valid == 0:
        # No observations, leave all as NA
        return df

    elif n_valid == 1:
        # Use single value for all missing
        fill_value = valid_df[allometry_col].iloc[0]
        df[allometry_col] = df[allometry_col].fillna(fill_value)

    else:
        # Use linear fit for missing values
        years = valid_df['year'].values
        values = valid_df[allometry_col].values

        # Check if we have variation in years (required for linear regression)
        unique_years = np.unique(years)
        if len(unique_years) < 2:
            # All observations are from the same year, use mean value
            fill_value = np.mean(values)
            df[allometry_col] = df[allometry_col].fillna(fill_value)
        else:
            slope, intercept = fit_linear_model(years, values)

            # Fill missing values
            missing_mask = df[allometry_col].isna()
            for idx in df[missing_mask].index:
                year = df.loc[idx, 'year']
                df.loc[idx, allometry_col] = predict_from_linear(year, slope, intercept)

    return df


def gap_fill_all_allometries(
    df: pd.DataFrame,
    individual_id: str,
    allometry_cols: List[str] = ['AGBJenkins', 'AGBChojnacky', 'AGBAnnighofer']
) -> pd.DataFrame:
    """
    Gap fill all allometry columns for an individual.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing data for one individual
    individual_id : str
        The individualID
    allometry_cols : List[str]
        List of allometry column names to gap fill

    Returns
    -------
    pd.DataFrame
        DataFrame with all allometry columns gap-filled
    """
    for col in allometry_cols:
        if col in df.columns:
            df = gap_fill_individual_allometry(df, individual_id, col)

    return df


def gap_fill_plot_data(
    df: pd.DataFrame,
    allometry_cols: List[str] = ['AGBJenkins', 'AGBChojnacky', 'AGBAnnighofer']
) -> pd.DataFrame:
    """
    Gap fill biomass values for all individuals in a plot.

    This function processes each individual separately, applying the gap-filling
    logic to their time series of measurements.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing data for all individuals in a plot,
        must have 'individualID', 'year', and the allometry columns
    allometry_cols : List[str]
        List of allometry column names to gap fill

    Returns
    -------
    pd.DataFrame
        DataFrame with gap-filled values for all individuals
    """
    if df.empty:
        return df

    result_dfs = []

    for individual_id in df['individualID'].unique():
        individual_df = df[df['individualID'] == individual_id].copy()
        filled_df = gap_fill_all_allometries(individual_df, individual_id, allometry_cols)
        result_dfs.append(filled_df)

    return pd.concat(result_dfs, ignore_index=True)


def create_complete_individual_year_grid(
    df: pd.DataFrame,
    plot_id: str,
    years: List[int]
) -> pd.DataFrame:
    """
    Create a complete grid of individual-year combinations for a plot.

    This ensures that each individual that ever appeared in the plot
    has a row for each year that the plot was sampled, even if the
    individual wasn't measured in that year.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing apparent individual data for a plot
    plot_id : str
        The plotID
    years : List[int]
        List of years to include

    Returns
    -------
    pd.DataFrame
        DataFrame with complete individual-year grid, with original data
        merged in and missing combinations having NA for measurement columns.
        Includes 'gapFilling' column: 'ORIGINAL' for measured rows,
        'FILLED' for gap-filled rows.
    """
    if df.empty:
        return df

    # Get all unique individuals in this plot
    individuals = df['individualID'].unique()

    # Create complete grid
    grid = pd.DataFrame([
        {'individualID': ind, 'year': year, 'plotID': plot_id}
        for ind in individuals
        for year in years
    ])

    # Get columns to keep from original df (excluding those we're creating)
    value_columns = [c for c in df.columns if c not in ['individualID', 'year', 'plotID']]

    # Mark original data
    df_with_flag = df.copy()
    df_with_flag['gapFilling'] = 'ORIGINAL'

    # Merge original data onto grid
    merged = grid.merge(
        df_with_flag[['individualID', 'year', 'gapFilling'] + value_columns],
        on=['individualID', 'year'],
        how='left'
    )

    # Mark gap-filled rows
    merged['gapFilling'] = merged['gapFilling'].fillna('FILLED')

    return merged


def forward_fill_growth_form(df: pd.DataFrame) -> pd.DataFrame:
    """
    Forward-fill growthForm and stemDiameter for each individual.

    For gap-filled rows where these columns are NaN or empty string, this fills
    in the value from the most recent previous year where it was observed. If no
    previous observation exists, it uses the next available observation (backward fill).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'individualID', 'year', 'growthForm', and 'stemDiameter' columns

    Returns
    -------
    pd.DataFrame
        DataFrame with growthForm and stemDiameter filled for gap-filled rows
    """
    if df.empty:
        return df

    df = df.copy()

    columns_to_fill = ['growthForm', 'stemDiameter']
    columns_present = [c for c in columns_to_fill if c in df.columns]

    if not columns_present:
        return df

    # Replace empty strings with NaN so they can be filled
    for col in columns_present:
        if df[col].dtype == object:  # String column
            df[col] = df[col].replace('', np.nan)

    # Opt-in to future pandas behavior to avoid FutureWarning
    with pd.option_context('future.no_silent_downcasting', True):
        # Process each individual separately
        for ind_id in df['individualID'].unique():
            ind_mask = df['individualID'] == ind_id
            ind_df = df.loc[ind_mask].sort_values('year')

            for col in columns_present:
                # Forward fill then backward fill
                filled_values = ind_df[col].ffill().bfill()
                df.loc[ind_mask, col] = filled_values.values

    return df
