"""
Constants used across the neon-agbd codebase.
"""

# Plant status values that indicate the tree is dead
DEAD_STATUSES = {
    'Dead, broken bole',
    'Downed',
    'Lost, burned',
    'Lost, fate unknown',
    'Lost, herbivory',
    'Lost, presumed dead',
    'Removed',
    'Standing dead',
    'No longer qualifies',
}

# Plant status values that indicate the tree is alive
LIVE_STATUSES = {
    '',
    'Live',
    'Live,  other damage',
    'Live, broken bole',
    'Live, disease damaged',
    'Live, insect damaged',
    'Live, physically damaged',
    'Lost, tag damaged',
}

# Constants for categorizing growth forms
TREE_GROWTH_FORMS = ['single bole tree', 'multi-bole tree', 'small tree']
SMALL_WOODY_GROWTH_FORMS = ['small tree', 'sapling', 'single shrub', 'small shrub']

# Diameter threshold (cm) for separating trees from small woody
DIAMETER_THRESHOLD = 10.0

# Allometry column names
ALLOMETRY_COLS = ['AGBJenkins', 'AGBChojnacky', 'AGBAnnighofer']

# Unit conversion: NEONForestAGB provides AGB in kg, we convert to Mg (tonnes)
# 1 Mg = 1000 kg, so Mg/ha = kg/ha / 1000
KG_TO_MG = 1 / 1000.0
