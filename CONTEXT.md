# WIEMIP project context

The Warming-Induced Greenhouse Gas Emissions Model Intercomparison Project is a MIP
organized by Spark Climate Solutions. There are two sets of simulations that models will
run: the one percent co2 simulations (analogous to the CMIP6 one percent co2 simulations)
and various climate overshoot simulations. The one percent co2 simulation will focus on
computing the gamma_land and beta_land feedback factors for the land surface. All models are land
surface only. Driver data is provided by the PRIME workflow (Mathison et al) which uses
the FaIR SCM to compute a temperature change from GHG emission or concentration data and
then applies the IMOGEN pattern scaling algorithm using the temperature change to arrive
at spatially resolved climate fields.

The one percent CO2 simulations consist of a spinup, a control run, a biogeochemically
coupled (bgc) and a fully coupled (cou) run, and extend for 150 years, doubling Co2 concentrations
after 70 years and quadrupling after 140 years. Since the models are uncoupled, they are
forced with the climate data derived from the PRIME workflow. There are three GCM patterns
used to generate the climate data: UKESM, GFDL, and IPSL. BGC varies CO2 with constant
climate and COU varies CO2 and applies the transient climate from the PRIME workflow. Beta_land is computed
from the BGC run and gamma_land is computed from the COU - BGC run. The
protocol is very similar to the C4MIP CMIP7 one percent co2 protocol. The protocol differs
in one key way: it asks for factorial simulations for the one percent runs. A factorial
simulation is a simulation where a model disables a process (like fire disturbance) and
then runs the model forward. The factorial simulations will be used to understand how the
inclusion of different processes impacts the gamma_land and beta_land factors. The goal is to
collect data to train a function to translate the gamma_land and beta_land from a CMIP7 ESM that
does not include e.g. fire to an estimated gamma_land and beta_land if the ESM did include fire.

For the overshoot runs, the required simulations are spinup, historical (using a version
of CRUJRA that has been downscaled to 6-hourly using the JULES weather generator), and
various future scenarios derived from CMIP7's ScenarioMIP. The required future simulations
are L, HL, HL-counterfactual (a custom wiemip simulation) and M, though data is provided
for the rest of the ScenarioMIP simulations along with some more counterfactuals (e.g.,
ML-CF). The future runs extend from 2024-2300. Land use fractions are fixed at 2023 values 
from spinup, to historical, to future to reduce the impact of land use change.

This file is hosted on a Jupyterhub that is a shared space for analyzing WIEMIP
submissions from participating models.

There is a shared python package (wiemip_registry) available to all users. It's used to
overlay the cloud storage where models submit and easily retrieve variables. Note: on any
latitudinal sum the resulting .csv file is cached in the Hub's filesystem.

Spinups for both one percent co2 and overshoot runs require recycled climate and constant "everything else": population,
n deposition, land use change, lightning. For 1pct runs, land use is fixed in 1850, while for overshoot, it's fixed 
in 2023.

Models submit to a shared Wasabi cloud storage bucket.
