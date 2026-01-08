"""
NEON AGB (Aboveground Biomass Density) computation package.

This package provides functions to compute plot-level aboveground biomass
density estimates from NEON vegetation structure data (DP1.10098.001) and
the NEONForestAGB dataset.
"""

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
    gap_fill_individual_allometry,
    gap_fill_all_allometries,
    gap_fill_plot_data,
    create_complete_individual_year_grid,
)

from .biomass_calculator import (
    categorize_individual,
    add_category_column,
    calculate_tree_biomass_density,
    calculate_small_woody_biomass_density,
    calculate_plot_year_biomass,
    aggregate_plot_biomass_all_years,
    TREE_GROWTH_FORMS,
    SMALL_WOODY_GROWTH_FORMS,
    DIAMETER_THRESHOLD,
    ALLOMETRY_COLS,
    KG_TO_MG,
)

from .main import (
    compute_site_biomass,
    compute_all_sites_biomass,
    ALL_SITES,
)

__version__ = "0.1.0"
