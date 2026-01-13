library(arrow)

# Change this to wherever you download the file
source("~/code/NEONForestAGB/R/NEONForestAGB.R")

# import the data
df <- getAGB()


meta = getAGBMeta()

taxons = getAGBTaxons()

write_parquet(df, '~/data/NEON/All_trees_biomass.parquet')
write_parquet(meta, '~/data/NEON/All_trees_biomass_metadata.parquet')
write_parquet(taxons, '~/data/NEON/All_trees_biomass_taxons.parquet')
