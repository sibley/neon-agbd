# Known Issues

## NEONForestAGB Data Quality Issues

### ABBY_073: Erroneous 36.7 cm measurement for individual NEON.PLA.D16.ABBY.00034

Individual NEON.PLA.D16.ABBY.00034 (*Acer circinatum* - vine maple) has an anomalous measurement in 2018:

| Year | Diameter | Height | Growth Form |
|------|----------|--------|-------------|
| 2016 | 1.0 cm | 2.3 m | small tree |
| 2017 | 1.6 cm | 2.3 m | small tree |
| **2018** | **1.8 cm** | **2.8 m** | **small tree** |
| **2018** | **36.7 cm** | **29.7 m** | **single bole tree** |
| 2019 | 2.0-2.2 cm | 3.5 m | small tree |
| 2020+ | 2.2-3.0 cm | 3.4-4.4 m | small tree |

The 36.7 cm / 29.7 m record in 2018 is impossible for this individual. A vine maple doesn't grow from 1.6 cm to 36.7 cm in one year and then shrink back to 2.0 cm the next. This appears to be a data entry error in NEONForestAGB - perhaps a measurement from a different tree was accidentally assigned to this individualID.

Supporting evidence:
1. The 36.7 cm record has status "Live, physically damaged" while the 1.8 cm record on the same date has "Live"
2. There are other ~36 cm trees in the plot (00023, 00025, 00029) that are Douglas firs
3. The erroneous record only appears in 2018 and never again

**Impact**: This causes a ~15 Mg/ha spike in small_woody biomass for ABBY_073 in 2018, because the erroneous 741 kg AGB value gets assigned to the small tree record through our merge process, inflating the average small_woody biomass from ~1-3 kg to ~95 kg.
