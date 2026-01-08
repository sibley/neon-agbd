"""
Gap filling functions for missing biomass values in vegetation structure data.
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Tuple
from scipy import stats


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
        merged in and missing combinations having NA for measurement columns
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

    # Merge original data onto grid
    merged = grid.merge(
        df[['individualID', 'year'] + value_columns],
        on=['individualID', 'year'],
        how='left'
    )

    return merged
