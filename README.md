# neon-agbd

This repository houses functions that are used to compute aboveground biomass density using (1) field survey plot data and (2) lidar data from the AOP (aerial observation platform). These functions are specific to the NEON database structure. 


## 1.  Survey plot data

### 1.1 The datasets

#### 1.1.1 Veg structure data (DP1.10098.001)

Most of the relevant data for a given site will be contained in the dictionary returned by running the retrieval function nu.load_by_product. 

```python
import neonUtilities as nu

veg_dict = nu.load_by_product(dpid="DP1.10098.001", 
                              site="SJER", 
                              package="basic", 
                              release="RELEASE-2025",
                              check_size=False)
```

where dpid is the data product ID (will always be DP1.10098.001 for this exercise), the site is a 4 digit site code (SJER = San Joaquin Experimental Range in this example), and all other arguments can be left as defaults. a successful run of `nu.load_by_product` results in a dictionary containing several data objects.  

The current list of DPIDs that have been downloaded are: 

```python
dpids = ['DELA','LENO','TALL','BONA','DEJU','HEAL','SRER','SJER','SOAP',
              'TEAK','CPER','NIWO','RMNP','DSNY','OSBS','JERC','PUUM','KONZ',
              'UKFS','SERC','HARV','UNDE','BART','JORN','DCFS','NOGP','WOOD',
              'GUAN','LAJA','GRSM','ORNL','CLBJ','MOAB','ONAQ','MLBS',
              'SCBI','ABBY','WREF','TREE','YELL']
```

## 2. AOP data 

This is an area of active research and will be updated at a later time. 