# Second major prompt to Claude

Hello Claude. Welcome back to the neon-agbd repo. Last time you followed claude_prompt.md to create the code in ./src/. You made some great code! Check out the old prompt and the documentation and data in this repo to re-familiarize yourself with the work we are doing.

Now we are going to work on returning some more outputs from the workflow. I'd like to have the existing output table and a couple of other tables that will be packed in a dictionary that can be written out as a pkl file. I would also like to make sure we build in some checks to catch certain cases / logic. These changes are outlined in the bullet points below. In all cases where tree are mentioned, we are talking about individuals that fall into the "tree" category as defined previously (things that are not "small_woody"). 


- If we did not build in this logic already, if the status of a tree is marked "dead", check to see if that is a persistent feature. For example if status goes from alive to dead to alive, we should assume that the sandwiched dead status is incorrect, and that the tree was alive for the whole duration. In the other case, where dead status persists (example, alive dead dead, or alive alive dead), then we should assume the status is correct, and all biomass for "dead" periods should be 0, no matter what the diameter measurement is (we are only tracking live woody biomass). 

- Make a table called unaccountedTrees to which we will add the information for apparent individuals that have been logged as belonging to a given plotID, but which never show up as measured in the survey campaigns. In these cases, we should give them a status (in a column called "status") of "UNMEASURED". In this case we are flagging trees with no diameter measurements. In the case of apparent individual trees that do have at least 1 diameter measurement, but do not have any biomass estimates for any of the 3 allometry types, add them to the table and give status "NO_ALLOMETRY". 

- To the existing output table, let's add in addition to the n of trees (which should be the trees that were included in the total biomass calculation), the n_unaccounted_trees for the plot so we can easily see how many unaccountedTrees there are. Also a column called "growth" which is the growth in tonnes/year for the plot between the last survey and the current one. Will be NA for the first survey date. Also a column called "growth_cumu" that is the average growth per year across all survey dates, determined by taking a linear regression of all survey dates for the plot and using the slope (which should be in tonnes per year).

- We should add a table of individual tree measurements. This table will be in "long" form (individuals will be represented in more than 1 row). For this we will want:
  - A column tracking the survey year 
  - A column for agbd calculated using each of the allometry types 
  - A column called "growth" which is the growth in tonnes/year for the tree between the last survey and the current one. Will be NA for the first survey date. Also a column called "growth_cumu" that is the average growth per year across all survey dates, determined by taking a linear regression of all survey dates for the tree and using the slope (which should be in tonnes per year).
  - Keep all columns for trees that do not change in time / are an attribute of the tree and are found in the DP1.10098 pkl file. For example, the scientific name of the tree should be kept in this dataframe, etc...
  
- Please provide an example script which runs this process for a specified site and returns the dictionary and writes the pkl file. 

This is all for this round of revision. Some of the new additions could probably fit in nicely to places in the current workflow, while others will need to be added as separate routines. Please focus on making a clean set of code that follows the DRY principle and is thoughtful about when part of a given existing workflow can be used to accomplish one of these new tasks. A clean codebase is a happy codebase. Please feel free to take all of the time you need, be methodical, and test your code on several of the provided datasets. You have already been doing great work and I believe you will do great work again. This is a great contribution to plant science that is very important!

