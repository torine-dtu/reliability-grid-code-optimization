from gurobi_pwl_mccormick import *
from scenario_generation import *
from generator_class import *
from IEEE_plotting_functions import *
apply_ieee_style()
import random
import time
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# Path for saving figures
save_fig_path = "Latex\\686fa94c623cde79680deee6\\"
# save_fig_path = "Output\\"
save_fig_bool = False

# Ranges
N_GENERATORS = 3
N_TIME = 24
N_SCENARIOS = 50

# Indexes
GENERATORS = [g for g in range(N_GENERATORS)]
HOURS = [h for h in range(N_TIME)]
SCENARIOS = [s for s in range(N_SCENARIOS)]

# Scenarios
# 42 is used as random seed in the distribution fitting, so we use a different seed here to avoid any unintended correlation between scenario generation and distribution fitting
random.seed(1605)

scen_dict_EV, scen_dict_EV_OOS = generate_scenarios_EV(N_SCENARIOS)
scen_dict_wind, scen_dict_wind_OOS = generate_scenarios_wind(N_SCENARIOS)
scen_dict_conventional = generate_scenarios_conventional(N_SCENARIOS, 50)

OOS_scenarios = {'g1': scen_dict_EV_OOS, 'g2': scen_dict_wind_OOS}
scenarios = {'g1': scen_dict_EV, 'g2': scen_dict_wind, 'g3': scen_dict_conventional}

# Some colors
shortfall_color = '#c1121f'

# Generators
g1 = GeneratorBase.from_json("Output\EV_fits.json")
g1.color = "#52796f"
g1.generator_type = "EV"
g1.set_cost_function(intercept=45, slope=-25)
g1.scenarios = scen_dict_EV

g2 = GeneratorBase.from_json("Output\wind_fits.json")
g2.color = "#cad2c5"
g2.generator_type = "Wind"
g2.set_cost_function(intercept=30, slope=-20)
g2.scenarios = scen_dict_wind

g3 = Conventional()
g3.color = "#2f3e46"
g3.generator_type = "Conventional"
g3.set_cost_function(intercept=100, slope=0)
for i in range(N_TIME):
    g3.add_hour_data(i, 50)
