"""
Data loading functions for NEON vegetation structure and NEONForestAGB datasets.
"""

import pickle
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple


def load_dp1_data(site_id: str, data_dir: str) -> Dict:
    """
    Load the DP1.10098.001 vegetation structure data for a given site.

    Parameters
    ----------
    site_id : str
        Four-character NEON site code (e.g., 'SJER', 'HARV')
    data_dir : str
        Absolute path to the directory containing the pickle files

    Returns
    -------
    dict
        Dictionary containing the vegetation structure tables:
        - vst_apparentindividual
        - vst_mappingandtagging
        - vst_perplotperyear
        - vst_shrubgroup
        - and other metadata tables
    """
    pkl_path = Path(data_dir) / f"{site_id}.pkl"

    if not pkl_path.exists():
        raise FileNotFoundError(f"No data file found for site {site_id} at {pkl_path}")

    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)

    return data


def load_neon_forest_agb(
    data_dir: str,
    site_id: Optional[str] = None
) -> pd.DataFrame:
    """
    Load and concatenate all NEONForestAGBv2 CSV files.

    Parameters
    ----------
    data_dir : str
        Absolute path to the directory containing the NEONForestAGB CSV files
    site_id : str, optional
        If provided, filter to only this site. If None, return all sites.

    Returns
    -------
    pd.DataFrame
        Concatenated dataframe with columns including:
        individualID, date, allometry, AGB, siteID, plotID, etc.
    """
    data_path = Path(data_dir)
    csv_files = sorted(data_path.glob("NEONForestAGBv2_part*.csv"))

    if not csv_files:
        raise FileNotFoundError(f"No NEONForestAGBv2 CSV files found in {data_dir}")

    dfs = []
    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        dfs.append(df)

    combined_df = pd.concat(dfs, ignore_index=True)

    if site_id is not None:
        combined_df = combined_df[combined_df['siteID'] == site_id].copy()
        if len(combined_df) == 0:
            import warnings
            warnings.warn(f"No NEONForestAGB data found for site {site_id}. "
                         "This site may be non-forested (e.g., grassland).")

    return combined_df


def load_plot_areas(geojson_path: str) -> pd.DataFrame:
    """
    Load plot area information from the NEON TOS Plot Polygons GeoJSON file.

    Parameters
    ----------
    geojson_path : str
        Absolute path to the GeoJSON file containing plot polygons

    Returns
    -------
    pd.DataFrame
        DataFrame with plotID, plotSize (m²), and siteID columns
    """
    with open(geojson_path, 'r') as f:
        data = json.load(f)

    records = []
    for feature in data['features']:
        props = feature['properties']
        records.append({
            'plotID': props.get('plotID'),
            'plotSize': props.get('plotSize'),  # in square meters
            'siteID': props.get('siteID'),
            'plotType': props.get('plotType')
        })

    return pd.DataFrame(records)


def pivot_agb_by_allometry(agb_df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot the NEONForestAGB dataframe so each allometry type becomes a column.

    Takes the long-format AGB data (3 rows per individual-date combination,
    one for each allometry type) and pivots to wide format with columns for
    each allometry type.

    Parameters
    ----------
    agb_df : pd.DataFrame
        NEONForestAGB dataframe with columns including
        individualID, date, allometry, AGB

    Returns
    -------
    pd.DataFrame
        Pivoted dataframe with individualID, date as index columns
        and AGBJenkins, AGBChojnacky, AGBAnnighofer as value columns
    """
    # Select only the columns we need for pivoting
    pivot_df = agb_df[['individualID', 'date', 'allometry', 'AGB']].copy()

    # Pivot the dataframe
    pivoted = pivot_df.pivot_table(
        index=['individualID', 'date'],
        columns='allometry',
        values='AGB',
        aggfunc='first'  # Take first value if duplicates exist
    ).reset_index()

    # Flatten column names
    pivoted.columns.name = None

    return pivoted


def merge_agb_with_apparent_individual(
    vst_ai: pd.DataFrame,
    agb_pivoted: pd.DataFrame
) -> pd.DataFrame:
    """
    Merge the pivoted AGB data with the vst_apparentindividual table.

    Parameters
    ----------
    vst_ai : pd.DataFrame
        The vst_apparentindividual table from DP1.10098.001
    agb_pivoted : pd.DataFrame
        Pivoted NEONForestAGB data with columns for each allometry type

    Returns
    -------
    pd.DataFrame
        Merged dataframe with all vst_apparentindividual columns plus
        the three allometry AGB columns. Rows without matching AGB data
        will have NA values for the AGB columns.
    """
    # Ensure date columns are in the same format
    vst_ai = vst_ai.copy()
    agb_pivoted = agb_pivoted.copy()

    # Convert dates to string format YYYY-MM-DD for consistent merging
    vst_ai['date_str'] = pd.to_datetime(vst_ai['date']).dt.strftime('%Y-%m-%d')
    agb_pivoted['date_str'] = pd.to_datetime(agb_pivoted['date']).dt.strftime('%Y-%m-%d')

    # Determine which allometry columns are available
    allometry_cols = ['AGBJenkins', 'AGBChojnacky', 'AGBAnnighofer']
    available_cols = [c for c in allometry_cols if c in agb_pivoted.columns]
    merge_cols = ['individualID', 'date_str'] + available_cols

    # Merge on individualID and date
    merged = vst_ai.merge(
        agb_pivoted[merge_cols],
        left_on=['individualID', 'date_str'],
        right_on=['individualID', 'date_str'],
        how='left'
    )

    # Add missing allometry columns as NaN
    for col in allometry_cols:
        if col not in merged.columns:
            merged[col] = np.nan

    # Drop the temporary date_str column
    merged = merged.drop(columns=['date_str'])

    return merged


def extract_year_from_event_id(event_id: str) -> int:
    """
    Extract the year from an eventID string.

    The eventID format is 'vst_SITE_YYYY' (e.g., 'vst_SJER_2015').

    Parameters
    ----------
    event_id : str
        The eventID string

    Returns
    -------
    int
        The year as an integer
    """
    return int(event_id[-4:])


def get_unique_plot_years(vst_ai: pd.DataFrame) -> pd.DataFrame:
    """
    Get all unique combinations of plotID and year from the vst_apparentindividual table.

    Parameters
    ----------
    vst_ai : pd.DataFrame
        The vst_apparentindividual table

    Returns
    -------
    pd.DataFrame
        DataFrame with columns plotID and year
    """
    df = vst_ai.copy()
    df['year'] = df['eventID'].apply(extract_year_from_event_id)

    unique_combinations = df[['plotID', 'year']].drop_duplicates().sort_values(['plotID', 'year'])

    return unique_combinations.reset_index(drop=True)


def get_plot_years_from_perplotperyear(vst_ppy: pd.DataFrame) -> pd.DataFrame:
    """
    Get all unique combinations of plotID and year from vst_perplotperyear.

    This is the authoritative source for which plots were surveyed in which years,
    including plots that had no woody vegetation.

    Parameters
    ----------
    vst_ppy : pd.DataFrame
        The vst_perplotperyear table

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: plotID, year, totalSampledAreaTrees,
        totalSampledAreaShrubSapling, treesPresent, shrubsPresent
    """
    df = vst_ppy.copy()
    df['year'] = df['eventID'].apply(extract_year_from_event_id)

    # Select relevant columns
    cols_to_keep = ['plotID', 'year', 'totalSampledAreaTrees',
                    'totalSampledAreaShrubSapling', 'treesPresent', 'shrubsPresent']
    cols_available = [c for c in cols_to_keep if c in df.columns]

    result = df[cols_available].drop_duplicates().sort_values(['plotID', 'year'])

    return result.reset_index(drop=True)
