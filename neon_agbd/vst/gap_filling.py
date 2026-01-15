"""
Gap filling functions for missing biomass values in vegetation structure data.
Also handles dead status corrections and related data cleaning.
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Tuple
from scipy import stats

from ..constants import DEAD_STATUSES, LIVE_STATUSES, REMOVED_STATUSES, ALLOMETRY_COLS


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


def is_removed_status(status: str) -> bool:
    """
    Determine if a plantStatus value indicates the tree was physically removed.

    Parameters
    ----------
    status : str
        The plantStatus value

    Returns
    -------
    bool
        True if status is 'Removed', False otherwise
    """
    if pd.isna(status):
        return False
    return status == 'Removed'


def is_not_qualified_status(status: str) -> bool:
    """
    Determine if a plantStatus value indicates the tree no longer qualifies for measurement.

    Parameters
    ----------
    status : str
        The plantStatus value

    Returns
    -------
    bool
        True if status is 'No longer qualifies', False otherwise
    """
    if pd.isna(status):
        return False
    return status == 'No longer qualifies'


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
        DataFrame with columns ['individualID', 'year', 'is_dead', 'is_removed',
        'is_not_qualified', 'has_status_observation'] sorted by year.
        'has_status_observation' is True if at least one plantStatus value was
        recorded (not NaN) for that year.
    """
    ind_df = df[df['individualID'] == individual_id].copy()

    if ind_df.empty:
        return pd.DataFrame(columns=['individualID', 'year', 'is_dead', 'is_removed',
                                      'is_not_qualified', 'has_status_observation'])

    # Group by year and check status
    results = []
    for year in ind_df['year'].unique():
        year_df = ind_df[ind_df['year'] == year]
        statuses = year_df['plantStatus'].unique()
        has_live = any(is_live_status(s) for s in statuses)
        has_dead = any(is_dead_status(s) for s in statuses)
        has_removed = any(is_removed_status(s) for s in statuses)
        has_not_qualified = any(is_not_qualified_status(s) for s in statuses)
        # Check if any plantStatus was actually recorded (not all NaN)
        has_status_observation = any(pd.notna(s) for s in statuses)
        # Only dead if no live stems and at least one dead stem
        is_dead = not has_live and has_dead
        # Removed/not-qualified take precedence if present (even with live stems)
        # because these indicate the tree is no longer being tracked
        is_removed = has_removed
        is_not_qualified = has_not_qualified and not has_removed  # removed takes precedence
        results.append({
            'year': year,
            'is_dead': is_dead,
            'is_removed': is_removed,
            'is_not_qualified': is_not_qualified,
            'has_status_observation': has_status_observation
        })

    yearly_status = pd.DataFrame(results)
    yearly_status['individualID'] = individual_id
    yearly_status = yearly_status[['individualID', 'year', 'is_dead', 'is_removed',
                                    'is_not_qualified', 'has_status_observation']].sort_values('year')

    return yearly_status


def correct_sandwiched_dead_status(yearly_status: pd.DataFrame) -> pd.DataFrame:
    """
    Correct "sandwiched" dead statuses where alive->dead->alive pattern occurs.

    If a dead status is sandwiched between two alive statuses, we assume the
    dead status was an error and the tree was actually alive.

    IMPORTANT: Only years with actual status observations are considered for
    the sandwiched pattern. Gap-filled years (no plantStatus) are ignored
    because they don't provide evidence of the tree being alive.

    Parameters
    ----------
    yearly_status : pd.DataFrame
        DataFrame with columns ['individualID', 'year', 'is_dead', 'has_status_observation']
        sorted by year

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

    # Check if has_status_observation column exists
    has_obs_col = 'has_status_observation' in df.columns

    # Look for sandwiched dead status
    for i in range(1, len(df) - 1):
        if df.loc[i, 'is_dead']:  # Current year is dead
            # Only correct if the dead year has an actual observation
            if has_obs_col and not df.loc[i, 'has_status_observation']:
                continue

            # Find the nearest previous year with an actual observation
            prev_alive = False
            for j in range(i - 1, -1, -1):
                if has_obs_col and not df.loc[j, 'has_status_observation']:
                    continue  # Skip gap-filled years
                prev_alive = not df.loc[j, 'is_dead']
                break

            # Find the nearest next year with an actual observation
            next_alive = False
            for j in range(i + 1, len(df)):
                if has_obs_col and not df.loc[j, 'has_status_observation']:
                    continue  # Skip gap-filled years
                next_alive = not df.loc[j, 'is_dead']
                break

            if prev_alive and next_alive:
                # Sandwiched dead - correct to alive
                df.loc[i, 'corrected_is_dead'] = False

    return df


def forward_fill_dead_status(yearly_status: pd.DataFrame) -> pd.DataFrame:
    """
    Forward-fill dead status: once a tree is dead, it stays dead forever.

    This should be run AFTER sandwiched dead correction. The logic is:
    - Find the first year where the tree is dead (using corrected_is_dead)
    - Mark all subsequent years as dead, regardless of their original status

    This prevents dead trees from "coming back to life" in gap-filled years
    where there is no plantStatus recorded.

    Parameters
    ----------
    yearly_status : pd.DataFrame
        DataFrame with columns including 'year' and 'corrected_is_dead',
        sorted by year. Must have been processed by correct_sandwiched_dead_status first.

    Returns
    -------
    pd.DataFrame
        DataFrame with corrected_is_dead updated to forward-fill dead status
    """
    df = yearly_status.copy()
    df = df.sort_values('year').reset_index(drop=True)

    # Find the first year where the tree is dead (after sandwiched correction)
    first_dead_idx = None
    for i in range(len(df)):
        if df.loc[i, 'corrected_is_dead']:
            first_dead_idx = i
            break

    # If tree was ever dead, mark all subsequent years as dead
    if first_dead_idx is not None:
        df.loc[first_dead_idx:, 'corrected_is_dead'] = True

    return df


def back_fill_dead_status(yearly_status: pd.DataFrame) -> pd.DataFrame:
    """
    Back-fill dead status: if first actual observation is dead, mark prior years as dead.

    This handles the case where a tree was first observed as dead (e.g., a snag added
    to the survey). Gap-filled years before the first observation should also be
    marked as dead since there's no evidence the tree was ever alive.

    This should be run AFTER forward_fill_dead_status.

    Parameters
    ----------
    yearly_status : pd.DataFrame
        DataFrame with columns including 'year', 'corrected_is_dead', and
        'has_status_observation'. Must have been processed by forward_fill_dead_status.

    Returns
    -------
    pd.DataFrame
        DataFrame with corrected_is_dead updated to back-fill dead status
    """
    df = yearly_status.copy()
    df = df.sort_values('year').reset_index(drop=True)

    if 'has_status_observation' not in df.columns:
        return df

    # Find the first year with an actual status observation
    first_obs_idx = None
    for i in range(len(df)):
        if df.loc[i, 'has_status_observation']:
            first_obs_idx = i
            break

    # If the first actual observation is dead, back-fill all prior years as dead
    if first_obs_idx is not None and first_obs_idx > 0:
        if df.loc[first_obs_idx, 'corrected_is_dead']:
            df.loc[:first_obs_idx - 1, 'corrected_is_dead'] = True

    return df


def forward_fill_removed_status(yearly_status: pd.DataFrame) -> pd.DataFrame:
    """
    Forward-fill removed status: once a tree is removed, it stays removed.

    Parameters
    ----------
    yearly_status : pd.DataFrame
        DataFrame with columns including 'year' and 'is_removed'.

    Returns
    -------
    pd.DataFrame
        DataFrame with 'corrected_is_removed' column added
    """
    df = yearly_status.copy()
    df = df.sort_values('year').reset_index(drop=True)

    # Initialize corrected status
    df['corrected_is_removed'] = df['is_removed'].copy() if 'is_removed' in df.columns else False

    # Find the first year where the tree is removed
    first_removed_idx = None
    for i in range(len(df)):
        if df.loc[i, 'corrected_is_removed']:
            first_removed_idx = i
            break

    # If tree was ever removed, mark all subsequent years as removed
    if first_removed_idx is not None:
        df.loc[first_removed_idx:, 'corrected_is_removed'] = True

    return df


def forward_fill_not_qualified_status(yearly_status: pd.DataFrame) -> pd.DataFrame:
    """
    Forward-fill not-qualified status: once a tree no longer qualifies, it stays that way.

    Parameters
    ----------
    yearly_status : pd.DataFrame
        DataFrame with columns including 'year' and 'is_not_qualified'.

    Returns
    -------
    pd.DataFrame
        DataFrame with 'corrected_is_not_qualified' column added
    """
    df = yearly_status.copy()
    df = df.sort_values('year').reset_index(drop=True)

    # Initialize corrected status
    df['corrected_is_not_qualified'] = df['is_not_qualified'].copy() if 'is_not_qualified' in df.columns else False

    # Find the first year where the tree no longer qualifies
    first_not_qualified_idx = None
    for i in range(len(df)):
        if df.loc[i, 'corrected_is_not_qualified']:
            first_not_qualified_idx = i
            break

    # If tree ever didn't qualify, mark all subsequent years
    if first_not_qualified_idx is not None:
        df.loc[first_not_qualified_idx:, 'corrected_is_not_qualified'] = True

    return df


def apply_dead_status_corrections(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply dead status corrections to the full dataset for trees.

    This function:
    1. Determines overall status for each individual by year
    2. Corrects sandwiched dead statuses (alive->dead->alive becomes alive->alive->alive)
    3. Forward-fills dead status (once dead, always dead)
    4. Back-fills dead status (if first observation is dead, prior gap-filled years are dead)
    5. Forward-fills removed status (once removed, stays removed)
    6. Forward-fills not-qualified status (once not qualified, stays that way)
    7. Adds 'corrected_is_dead', 'corrected_is_removed', 'corrected_is_not_qualified' columns

    The order of operations matters:
    - Sandwiched correction runs first to fix measurement errors
    - Forward-fill runs second to ensure dead trees stay dead
    - Back-fill runs third to handle trees first observed as dead (e.g., snags)
    - Removed/not-qualified forward-fill runs last

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with tree measurements, must have 'individualID', 'year', 'plantStatus'

    Returns
    -------
    pd.DataFrame
        DataFrame with added 'corrected_is_dead', 'corrected_is_removed',
        and 'corrected_is_not_qualified' columns
    """
    df = df.copy()

    if 'year' not in df.columns or 'plantStatus' not in df.columns:
        df['corrected_is_dead'] = False
        df['corrected_is_removed'] = False
        df['corrected_is_not_qualified'] = False
        return df

    # Get unique individuals
    individuals = df['individualID'].unique()

    # Build mappings of (individualID, year) -> corrected status
    dead_corrections = {}
    removed_corrections = {}
    not_qualified_corrections = {}

    for ind_id in individuals:
        yearly_status = get_individual_status_by_year(df, ind_id)
        if yearly_status.empty:
            continue

        # Step 1: Correct sandwiched dead statuses (alive->dead->alive)
        corrected = correct_sandwiched_dead_status(yearly_status)

        # Step 2: Forward-fill dead status (once dead, always dead)
        corrected = forward_fill_dead_status(corrected)

        # Step 3: Back-fill dead status (if first obs is dead, prior years are dead)
        corrected = back_fill_dead_status(corrected)

        # Step 4: Forward-fill removed status
        corrected = forward_fill_removed_status(corrected)

        # Step 5: Forward-fill not-qualified status
        corrected = forward_fill_not_qualified_status(corrected)

        for _, row in corrected.iterrows():
            key = (row['individualID'], row['year'])
            dead_corrections[key] = row['corrected_is_dead']
            removed_corrections[key] = row.get('corrected_is_removed', False)
            not_qualified_corrections[key] = row.get('corrected_is_not_qualified', False)

    # Apply corrections to dataframe
    df['corrected_is_dead'] = df.apply(
        lambda row: dead_corrections.get((row['individualID'], row['year']), False),
        axis=1
    )
    df['corrected_is_removed'] = df.apply(
        lambda row: removed_corrections.get((row['individualID'], row['year']), False),
        axis=1
    )
    df['corrected_is_not_qualified'] = df.apply(
        lambda row: not_qualified_corrections.get((row['individualID'], row['year']), False),
        axis=1
    )

    return df


def zero_biomass_for_dead_trees(df: pd.DataFrame, allometry_cols: List[str]) -> pd.DataFrame:
    """
    Set biomass to 0 for trees that are dead, removed, or no longer qualify.

    Also updates the gapFilling column to indicate the reason:
    - 'REMOVED' for trees that were physically removed from the plot
    - 'NOT_QUALIFIED' for trees that no longer meet measurement criteria

    Priority order (if multiple apply): REMOVED > NOT_QUALIFIED > dead
    Dead trees keep their original gapFilling value (ORIGINAL or FILLED).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'corrected_is_dead', 'corrected_is_removed',
        'corrected_is_not_qualified' columns and allometry columns
    allometry_cols : List[str]
        List of allometry column names to zero out

    Returns
    -------
    pd.DataFrame
        DataFrame with zeroed biomass and updated gapFilling for affected trees
    """
    df = df.copy()

    # Zero out biomass for dead trees
    if 'corrected_is_dead' in df.columns:
        dead_mask = df['corrected_is_dead'] == True
        for col in allometry_cols:
            if col in df.columns:
                df.loc[dead_mask, col] = 0.0

    # Zero out biomass for removed trees and set gapFilling
    if 'corrected_is_removed' in df.columns:
        removed_mask = df['corrected_is_removed'] == True
        for col in allometry_cols:
            if col in df.columns:
                df.loc[removed_mask, col] = 0.0
        if 'gapFilling' in df.columns:
            df.loc[removed_mask, 'gapFilling'] = 'REMOVED'

    # Zero out biomass for not-qualified trees and set gapFilling
    # Only set NOT_QUALIFIED if not already REMOVED
    if 'corrected_is_not_qualified' in df.columns:
        not_qualified_mask = df['corrected_is_not_qualified'] == True
        for col in allometry_cols:
            if col in df.columns:
                df.loc[not_qualified_mask, col] = 0.0
        if 'gapFilling' in df.columns:
            # Only update gapFilling if not already REMOVED
            not_qualified_not_removed = not_qualified_mask & (df['gapFilling'] != 'REMOVED')
            df.loc[not_qualified_not_removed, 'gapFilling'] = 'NOT_QUALIFIED'

    return df


# Keep mark_removed_individuals for backwards compatibility but it's deprecated
def mark_removed_individuals(df: pd.DataFrame, allometry_cols: List[str]) -> pd.DataFrame:
    """
    DEPRECATED: This function is no longer needed.

    Removed/not-qualified status is now handled by apply_dead_status_corrections
    and zero_biomass_for_dead_trees.

    This function now just returns the dataframe unchanged.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame (unused)
    allometry_cols : List[str]
        List of allometry column names (unused)

    Returns
    -------
    pd.DataFrame
        DataFrame unchanged
    """
    # Deprecated - just return unchanged
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
    Forward-fill growthForm and stemDiameter for gap-filled rows only.

    For gap-filled rows (gapFilling == 'FILLED') where these columns are NaN or
    empty string, this fills in the value from the most recent previous year where
    it was observed. If no previous observation exists, it uses the next available
    observation (backward fill).

    IMPORTANT: This function only fills values for FILLED (gap-created) rows,
    NOT for ORIGINAL rows that happen to have missing data. This prevents erroneous
    measurements from propagating to other years.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'individualID', 'year', 'growthForm', 'stemDiameter', and
        'gapFilling' columns

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

    # Check if gapFilling column exists
    has_gap_filling = 'gapFilling' in df.columns

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
                # Get indices of FILLED rows only (these are the ones we want to fill)
                if has_gap_filling:
                    filled_row_mask = ind_df['gapFilling'] == 'FILLED'
                else:
                    # If no gapFilling column, fill all NaN values (legacy behavior)
                    filled_row_mask = ind_df[col].isna()

                if not filled_row_mask.any():
                    continue

                # Compute forward-filled and back-filled values for the whole series
                filled_values = ind_df[col].ffill().bfill()

                # Only apply to FILLED rows
                filled_indices = ind_df[filled_row_mask].index
                df.loc[filled_indices, col] = filled_values.loc[filled_indices].values

    return df


def filter_diameter_outliers(
    df: pd.DataFrame,
    growth_threshold: float = 10.0,
    shrinkage_threshold: float = 5.0
) -> pd.DataFrame:
    """
    Filter out diameter measurements that show impossible growth followed by shrinkage.

    This function identifies "spike" outliers where a measurement shows:
    1. Impossible growth rate from the previous ORIGINAL observation (> growth_threshold cm/yr)
    2. AND impossible shrinkage rate to the next ORIGINAL observation (> shrinkage_threshold cm/yr)

    When both conditions are met, the measurement is marked as an outlier:
    - gapFilling column is set to 'OUTLIER'
    - All allometry AGB columns are set to NaN

    This filter is conservative - it only flags measurements that are clearly erroneous
    based on the surrounding observations.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with individual measurements. Must have columns:
        - individualID: Unique identifier for each tree
        - year: Survey year
        - stemDiameter: Diameter measurement in cm
        - gapFilling: Status column ('ORIGINAL', 'FILLED', etc.)
        - AGBJenkins, AGBChojnacky, AGBAnnighofer: Biomass columns
    growth_threshold : float, default 10.0
        Maximum allowed diameter growth rate (cm/year). Measurements exceeding
        this rate from the previous observation are candidates for outlier status.
    shrinkage_threshold : float, default 5.0
        Maximum allowed diameter shrinkage rate (cm/year). Measurements followed
        by shrinkage exceeding this rate are candidates for outlier status.

    Returns
    -------
    pd.DataFrame
        DataFrame with outliers marked in gapFilling column and AGB set to NaN.

    Notes
    -----
    - Only ORIGINAL observations are checked (gap-filled rows are interpolated)
    - For multi-stem trees, max diameter per year is used for comparison
    - Requires at least 3 unique years of observations for an individual to detect outliers
    - First and last year's observations cannot be flagged (need neighbors on both sides)

    Example
    -------
    The ABBY_073 case: vine maple with measurements 1.6cm (2017) -> 36.7cm (2018) -> 2.0cm (2019)
    - Growth rate: (36.7 - 1.6) / 1 = 35.1 cm/yr (> 10 threshold)
    - Shrinkage rate: (36.7 - 2.0) / 1 = 34.7 cm/yr (> 5 threshold)
    - Result: 2018 measurement flagged as OUTLIER
    """
    if df.empty:
        return df

    df = df.copy()

    # Track how many outliers we flag
    n_outliers = 0

    # Process each individual separately
    for ind_id in df['individualID'].unique():
        ind_mask = df['individualID'] == ind_id
        ind_df = df.loc[ind_mask].copy()

        # Get only ORIGINAL observations for comparison
        # These are the actual measurements, not gap-filled values
        if 'gapFilling' not in ind_df.columns:
            continue

        original_mask = ind_df['gapFilling'] == 'ORIGINAL'
        original_df = ind_df[original_mask].copy()

        if original_df.empty:
            continue

        # For multi-stem trees, aggregate to max diameter per year
        # This handles cases where the same individual has multiple stems measured per year
        year_agg = original_df.groupby('year').agg({
            'stemDiameter': 'max'  # Use max diameter for comparison
        }).reset_index()

        # Get unique years with valid diameter measurements
        year_agg = year_agg[year_agg['stemDiameter'].notna()]
        year_agg = year_agg.sort_values('year')

        if len(year_agg) < 3:
            # Need at least 3 unique years to detect a "sandwiched" outlier
            continue

        # Get arrays for efficient computation
        years = year_agg['year'].values
        max_diameters = year_agg['stemDiameter'].values

        # Check each year (except first and last)
        for i in range(1, len(year_agg) - 1):
            curr_year = years[i]
            curr_max_diam = max_diameters[i]
            prev_year = years[i - 1]
            prev_max_diam = max_diameters[i - 1]
            next_year = years[i + 1]
            next_max_diam = max_diameters[i + 1]

            # Calculate time differences
            years_since_prev = curr_year - prev_year
            years_to_next = next_year - curr_year

            if years_since_prev <= 0 or years_to_next <= 0:
                continue

            # Calculate growth rate from previous year
            growth_rate = (curr_max_diam - prev_max_diam) / years_since_prev

            # Calculate shrinkage rate to next year
            # Positive value means diameter decreased (shrinkage)
            shrinkage_rate = (curr_max_diam - next_max_diam) / years_to_next

            # Check if this is a spike outlier:
            # - Grew impossibly fast from previous
            # - AND shrank impossibly fast toward next
            if growth_rate > growth_threshold and shrinkage_rate > shrinkage_threshold:
                # Flag ALL rows for this individual+year as outliers
                # (including all stems measured that year)
                year_mask = (ind_df['year'] == curr_year) & (ind_df['gapFilling'] == 'ORIGINAL')
                year_indices = ind_df[year_mask].index.tolist()

                for idx in year_indices:
                    df.loc[idx, 'gapFilling'] = 'OUTLIER'

                    # Set all allometry columns to NaN
                    for col in ALLOMETRY_COLS:
                        if col in df.columns:
                            df.loc[idx, col] = np.nan

                n_outliers += len(year_indices)

    if n_outliers > 0:
        print(f"    Flagged {n_outliers} diameter outlier(s)")

    return df
