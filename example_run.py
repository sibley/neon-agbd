#!/usr/bin/env python3
"""
Example script demonstrating how to run the NEON-AGBD biomass calculation workflow.

This script processes a specified NEON site and produces:
1. Plot-level biomass estimates with growth metrics
2. A table of unaccounted trees (UNMEASURED or NO_ALLOMETRY)
3. Individual tree measurements in long form

Output is saved as both a pickle file (dictionary) and individual CSVs.
"""

import pickle
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from src.main import compute_site_biomass_full, ALL_SITES


def process_site(site_id: str, output_dir: str = "./output") -> dict:
    """
    Process a single NEON site and save results.

    Parameters
    ----------
    site_id : str
        Four-character NEON site code (e.g., 'SJER', 'HARV')
    output_dir : str
        Directory to save output files

    Returns
    -------
    dict
        Dictionary containing all output tables and metadata
    """
    # Ensure output directory exists
    Path(output_dir).mkdir(exist_ok=True)

    csvs_output_dir = Path(output_dir) / "csvs"
    csvs_output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Processing site: {site_id}")
    print(f"{'='*60}\n")

    # Run the full workflow
    output = compute_site_biomass_full(
        site_id=site_id,
        dp1_data_dir="./data/DP1.10098",
        agb_data_dir="./data/NEONForestAGB",
        plot_polygons_path="./data/plot_polygons/NEON_TOS_Plot_Polygons.geojson",
        apply_gap_filling=True,
        apply_dead_corrections=True,
        verbose=True
    )

    # Save as pickle (dictionary)
    pkl_file = Path(output_dir) / f"{site_id}.pkl"
    with open(pkl_file, 'wb') as f:
        pickle.dump(output, f)
    print(f"\nPickle file saved: {pkl_file}")

    # Save individual DataFrames as CSVs for easy inspection
    csv_files = {
        'plot_biomass': f"{site_id}_plot_biomass.csv",
        'unaccounted_trees': f"{site_id}_unaccounted_trees.csv",
        'individual_trees': f"{site_id}_individual_trees.csv"
    }

    for key, filename in csv_files.items():
        filepath = Path(csvs_output_dir) / filename
        output[key].to_csv(filepath, index=False)
        print(f"CSV saved: {filepath}")

    # Print summary
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"{'='*60}")
    print(f"  Site: {output['site_id']}")
    print(f"  Number of plots: {output['metadata']['n_plots']}")
    print(f"  Plot-year combinations: {output['metadata']['n_plot_years']}")
    print(f"  Unaccounted trees: {output['metadata']['n_unaccounted_trees']}")
    print(f"  Individual tree records: {output['metadata']['n_individual_tree_records']}")

    # Show sample of each output
    if not output['plot_biomass'].empty:
        print(f"\nPlot biomass table columns:")
        print(f"  {list(output['plot_biomass'].columns)}")
        print(f"\nSample rows:")
        print(output['plot_biomass'].head(3).to_string())

    if not output['unaccounted_trees'].empty:
        print(f"\nUnaccounted trees by status:")
        print(output['unaccounted_trees']['status'].value_counts().to_string())

    return output


def main():
    """Main entry point."""
    # Default site or take from command line
    if len(sys.argv) > 1:
        site_id = sys.argv[1].upper()
    else:
        site_id = 'SJER'  # San Joaquin Experimental Range

    # Validate site
    if site_id not in ALL_SITES:
        print(f"Error: Site '{site_id}' not found in available sites.")
        print(f"Available sites: {', '.join(sorted(ALL_SITES))}")
        sys.exit(1)

    # Process the site
    output = process_site(site_id)

    print(f"\n{'='*60}")
    print("Done!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
