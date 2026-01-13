"""
NEON AGB (Aboveground Biomass Density) computation package.

This package provides functions to compute plot-level aboveground biomass
density estimates from NEON vegetation structure data (DP1.10098.001) and
the NEONForestAGB dataset.
"""

# Re-export constants
from .constants import (
    DEAD_STATUSES,
    LIVE_STATUSES,
    TREE_GROWTH_FORMS,
    SMALL_WOODY_GROWTH_FORMS,
    DIAMETER_THRESHOLD,
    ALLOMETRY_COLS,
    KG_TO_MG,
)

# Re-export VST module functions for convenience
from .vst import (
    # Data loading
    load_dp1_data,
    load_neon_forest_agb,
    load_plot_areas,
    pivot_agb_by_allometry,
    merge_agb_with_apparent_individual,
    extract_year_from_event_id,
    get_unique_plot_years,
    get_plot_years_from_perplotperyear,
    # Gap filling
    gap_fill_individual_allometry,
    gap_fill_all_allometries,
    gap_fill_plot_data,
    create_complete_individual_year_grid,
    apply_dead_status_corrections,
    zero_biomass_for_dead_trees,
    forward_fill_growth_form,
    # Biomass calculation
    categorize_individual,
    add_category_column,
    calculate_tree_biomass_density,
    calculate_small_woody_biomass_density,
    calculate_plot_year_biomass,
    aggregate_plot_biomass_all_years,
    # Main workflow
    compute_site_biomass,
    compute_site_biomass_full,
    compute_all_sites_biomass,
    ALL_SITES,
)

__version__ = "0.2.0"
