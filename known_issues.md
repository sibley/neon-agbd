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

## vst_perplotperyear Data Quality Issues

### Incorrect totalSampledAreaTrees values (31 plots)

The `totalSampledAreaTrees` field in `vst_perplotperyear` contains incorrect values for 31 plots across 11 sites. These appear to be data entry errors where:

1. **Tower plots at tall-stature sites** are recorded as 400 m² when they should be 800 m² (2 of 4 subplots sampled from 40×40m plots)
2. **ORNL distributed plots in 2015** are recorded as 800 m² when they should be 400 m² (full 20×20m plot)

**Impact**: Biomass density (Mg/ha) is calculated by dividing total biomass by sampled area. When the area is wrong:
- Tower plots with 400 m² instead of 800 m²: biomass density is **doubled**
- ORNL 2015 plots with 800 m² instead of 400 m²: biomass density is **halved**

**Evidence**: Tree counts remain consistent across years for these plots, indicating the same area was sampled despite the recorded value changing.

### Affected plot-eventID mapping

```python
ANOMALOUS_SAMPLED_AREA_EVENTS = {
    # Tower plots incorrectly recorded as 400 m² (should be 800 m²)
    'BONA_073': 'vst_BONA_2023',
    'BONA_078': 'vst_BONA_2021',
    'BONA_084': 'vst_BONA_2023',
    'DELA_037': 'vst_DELA_2022',
    'DELA_040': 'vst_DELA_2021',
    'DELA_045': 'vst_DELA_2021',
    'GRSM_059': 'vst_GRSM_2023',
    'GRSM_060': 'vst_GRSM_2023',
    'HARV_038': 'vst_HARV_2023',
    'JERC_048': 'vst_JERC_2019',
    'ORNL_049': 'vst_ORNL_2023',
    'OSBS_028': 'vst_OSBS_2023',
    'RMNP_042': 'vst_RMNP_2022',
    'SJER_046': 'vst_SJER_2023',
    'TEAK_043': 'vst_TEAK_2023',
    # ORNL distributed plots incorrectly recorded as 800 m² (should be 400 m²)
    'ORNL_001': 'vst_ORNL_2015',
    'ORNL_002': 'vst_ORNL_2015',
    'ORNL_003': 'vst_ORNL_2015',
    'ORNL_004': 'vst_ORNL_2015',
    'ORNL_006': 'vst_ORNL_2015',
    'ORNL_007': 'vst_ORNL_2015',
    'ORNL_008': 'vst_ORNL_2015',
    'ORNL_009': 'vst_ORNL_2015',
    'ORNL_010': 'vst_ORNL_2015',
    'ORNL_012': 'vst_ORNL_2015',
    'ORNL_014': 'vst_ORNL_2015',
    'ORNL_027': 'vst_ORNL_2015',
    'ORNL_029': 'vst_ORNL_2015',
    'ORNL_032': 'vst_ORNL_2015',
    'ORNL_033': 'vst_ORNL_2015',
    'ORNL_035': 'vst_ORNL_2015',
}
```
