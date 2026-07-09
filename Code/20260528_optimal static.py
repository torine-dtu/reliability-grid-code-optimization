# %%
from config_optimization import *

# OPTIMAL EPS RESULTS FOR PENALTY x AND SYSTEM RELIABILITY 90%

start_time = time.perf_counter()

model = 'static' # "static" or "dynamic"
eps_input = {i: np.nan for i in range(N_TIME)} if model == 'dynamic' else np.nan

input_meta = dict(
    model_type = model,
    GENERATORS = GENERATORS,
    HOURS = HOURS,
    SCENARIOS = SCENARIOS,
    penalty = 1000,
    demand = {i: 50 for i in range(N_TIME)},
    eps_sys = 0.1,
    bigM = {i: 50 for i in range(N_TIME)},
    eps_input = eps_input,
    defined_percentile = 0.2
)

data = InputData(input_meta)

mm = OptimizationProblem(data, generators=[g1, g2, g3])

mm.run(tee=True, tuning=True)

end_time = time.perf_counter()
print(f"Model: {model}")
print(f"Elapsed time: {end_time - start_time:.4f} seconds")

mmm = Accessors(mm)
optimal_eps = mmm.get_something("eps")['eps']
print(f"Optimal objective value: {mmm.get_original_objective():.2f} \u20ac")
print(f"Optimal objective value (optimization): {mmm.get_objective():.2f} \u20ac")
print(f"MIP gap: {mmm.get_mipgap():.4f}")
print(f"Optimal reliability: {1-optimal_eps:.2f}")

optimal_accepted_bids = {f'accepted_bid[{t},{g}]': mmm.get_something(f"accepted_bid[{t},{g}]")[f"accepted_bid[{t},{g}]"] for t in HOURS for g in GENERATORS}
optimal_demand = mmm.get_cleared_demand()

# %% APPROXIMATION GAP EPS*ACCEPTED BID

for t in HOURS:
    for i in GENERATORS:
        if mmm.get_something('accepted_bid')[f'accepted_bid[{t},{i}]']*optimal_eps > 0:
            print(100*abs(mmm.get_something('accepted_bid')[f'accepted_bid[{t},{i}]']*optimal_eps - mmm.get_something('u_epsb')[f'u_epsb[{t},{i}]'])/mmm.get_something('accepted_bid')[f'accepted_bid[{t},{i}]']*optimal_eps)

# %% OOS SHORTFALL ANALYSIS

fig, ax = new_fig("single", n_row=2, n_col=1, sharey=True, sharex=True, aspect=0.3)

width = 0.35

n_shortfall = {}
for g in [0, 1]:
    for t in range(N_TIME):
        n_shortfall[t] = 0
        acc_bid = mmm.get_something(f"accepted_bid[{t},{g}]")[f"accepted_bid[{t},{g}]"]
        n_scen = len(OOS_scenarios[f"g{g+1}"][t])
        for i in range(n_scen):
            if OOS_scenarios[f"g{g+1}"][t][i] < acc_bid:
                n_shortfall[t] += 1

        n_shortfall[t] = n_shortfall[t]/n_scen

    if g==0: 
        d = width/2
        color = g1.color
        edc = '#fff'
    if g==1: 
        d = - width/2
        color = g2.color
        edc = g3.color
    ax[0].bar(np.arange(N_TIME) + d, n_shortfall.values(), width, color=color, edgecolor=edc, linewidth=0.5)

if model == "static":
    ax[0].axhline(y=optimal_eps, ls="dashed", color="k", alpha=0.8, label=r"$\varepsilon^{*}$")
if model == "dynamic":
    ax[0].scatter(HOURS, [optimal_eps[f'eps[{t}]'] for t in HOURS], marker="_", label=r"$\varepsilon_{t}^{*}$", color="k")

ax[0].set_ylabel('(8a) [\%]')

n_shortfall = {}
for g in [0, 1]:
    for t in range(N_TIME):
        n_shortfall[t] = 0
        acc_bid = mmm.get_something(f"accepted_bid[{t},{g}]")[f"accepted_bid[{t},{g}]"]
        n_scen = len(OOS_scenarios[f"g{g+1}"][t])
        for i in range(n_scen):
            if acc_bid == 0: continue
            elif OOS_scenarios[f"g{g+1}"][t][i] < acc_bid:
                n_shortfall[t] += (acc_bid - OOS_scenarios[f"g{g+1}"][t][i]) / acc_bid

        n_shortfall[t] = n_shortfall[t]/n_scen

    if g==0: 
        d = width/2
        color = g1.color
        edc = '#fff'
    if g==1: 
        d = - width/2
        color = g2.color
        edc = g3.color
    ax[1].bar(np.arange(N_TIME) + d, n_shortfall.values(), width, color=color, edgecolor=edc, linewidth=0.5)

if model == "static":
    ax[1].axhline(y=optimal_eps, ls="dashed", color="k", alpha=0.8, label=r"$\varepsilon^{*}$")
if model == "dynamic":
    ax[1].scatter(HOURS, [optimal_eps[f'eps[{t}]'] for t in HOURS], marker="_", label=r"$\varepsilon_{t}^{*}$", color="k")

ax[1].set_xlabel('Hour')
ax[1].set_ylabel('(8b) [\%]')

handles1, labels1 = ax[1].get_legend_handles_labels()
legend_elements = [
    Patch(facecolor=g2.color, edgecolor='white'),
    Patch(facecolor=g1.color, edgecolor="white")
] + handles1
labels = ['Wind', 'EV'] + labels1
fig.legend(loc='upper center', bbox_to_anchor=(0.5, 0.02), ncol=4, frameon=False, handles=legend_elements, labels=labels)

save_fig_bool = False
if save_fig_bool:
    save_fig(fig, "single", f"{save_fig_path}OOS_{model}_shortfalls_all.pdf")

# %% VARY EPSILON AND GET RESULTS TO CONSTRUCT PARETO FRONT STATIC

model = "static" # "static" or "dynamic"
n = 50
eps_range = np.linspace(0.001, 0.2, n).tolist()

demand_res_static = {}
bids_res_static = {}
offered_bids_static = {}
obj_res_static = {}
hourly_res_static = {}
failure_cost_static = {}
procurement_cost_static = {}
shortfalls_res_static = {}

for i in range(n):
    eps_input = eps_range[i]
    print(f"Running model with epsilon={eps_input:.4f}...")

    base_parameters = dict(
        model_type = model,
        GENERATORS = GENERATORS,
        HOURS = HOURS,
        SCENARIOS = SCENARIOS,
        penalty = 1000,
        demand = {i: 50 for i in range(N_TIME)},
        eps_sys = 0.1,
        bigM = {i: 50 for i in range(N_TIME)},
        eps_input = eps_input,
        defined_percentile = 0.2
    )

    data = InputData(base_parameters)
    mm = OptimizationProblem(data, generators=[g1, g2, g3])

    mm.run(tee=False, tuning=True)
    mmm = Accessors(mm)
    demand_res_static[eps_range[i]] = mmm.get_something("demand")
    bids_res_static[eps_range[i]] = mmm.get_something("accepted_bid")
    offered_bids_static[eps_range[i]] = mmm.get_something("offered_bid")
    obj_res_static[eps_range[i]] = mmm.get_original_objective()
    shortfalls_res_static[eps_range[i]] = mmm.get_total_shortfall()
    failure_cost_static[eps_range[i]] = mmm.failure_cost()
    procurement_cost_static[eps_range[i]] = mmm.get_procurement_cost()

# %% Cost at P90

model = "static" # "static" or "dynamic"
eps_input = [0.001, optimal_eps, 0.1, 0.2, 0.0045]
eps_input.sort()
for i in range(len(eps_input)):
    print(f"Running model for eps_input = {eps_input[i]:.4f}")
    base_parameters = dict(
        model_type = model,
        GENERATORS = GENERATORS,
        HOURS = HOURS,
        SCENARIOS = SCENARIOS,
        penalty = 1000,
        demand = {i: 50 for i in range(N_TIME)},
        eps_sys = 0.1,
        bigM = {i: 50 for i in range(N_TIME)},
        eps_input = eps_input[i],
        defined_percentile = 0.2
    )

    data = InputData(base_parameters)
    mm = OptimizationProblem(data, generators=[g1, g2, g3])

    mm.run(tee=False)
    mmm = Accessors(mm)

    obj_res = mmm.get_original_objective()
    obj_optimization = mmm.get_objective()
    print(f"Cost at optimal: {obj_res:.2f} \u20ac")
    print(f"Optimization objective value at optimal: {obj_optimization:.2f} \u20ac")
    print('=======')    


# %% PLOT IT

fig, ax = new_fig("single", n_row=1, n_col=1, sharey=False, sharex=False, aspect=0.6, r=0.9)

# PARETO CURVE:
ax.plot([1-e for e in eps_range], obj_res_static.values(), color=g1.color, linewidth=2.5)#, label="Obj val")
ind = list(obj_res_static.keys())[list(obj_res_static.values()).index(min(obj_res_static.values()))]
ax.scatter(1-ind, obj_res_static[ind], color=g3.color, marker='D', s=15, linewidths=0, zorder=2)
ax.set_ylabel("Cost [\u20ac]")
ax.set_xlabel(r"$1-\varepsilon$")
ax.set_xlim(0.8,1)
ax.ticklabel_format(axis='y', style='sci', scilimits=(4,4))
ax.axvline(0.9, color='k', linestyle='dashed', linewidth=1.5, label="P90")

save_fig_bool = False
if save_fig_bool:
    save_fig(fig, 'single', f"{save_fig_path}pareto_all_newtest.pdf")

# %% COMBINED GENERATION MIX

ind = list(obj_res_static.keys())[list(obj_res_static.values()).index(min(obj_res_static.values()))]

fig, ax = new_fig("single", n_row=1, n_col=1, sharey=False, sharex=False, ax_aspect=1, r=0.55)

bids1, bids2, bids3 = [], [], []
bids1 = [sum([bids_res_static[e][f'accepted_bid[{h},0]'] for h in range(N_TIME)]) for e in eps_range]
bids2 = [sum([bids_res_static[e][f'accepted_bid[{h},1]'] for h in range(N_TIME)]) for e in eps_range]
bids3 = [sum([bids_res_static[e][f'accepted_bid[{h},2]'] for h in range(N_TIME)]) for e in eps_range]

ax.stackplot([1-e for e in eps_range], bids2, bids1, bids3, colors=[g2.color, g1.color, g3.color], labels=['Wind', 'EV', 'Conventional'])
ax.set_xlabel(r'$1-\varepsilon$')
ax.ticklabel_format(axis='y', style='sci', scilimits=(2,2))
ax.axvline(1-optimal_eps, 0, color='k', linestyle='dashed', linewidth=1.5, label='Optimal reliability')

ax12 = ax.twinx()
ax12.grid(False)
ax12.set_box_aspect(1)
ax12.plot([1-e for e in eps_range], [failure_cost_static[e] for e in eps_range], linewidth=2, color=shortfall_color, label="Cost of shortfall")
ax12.ticklabel_format(axis='y', style='sci', scilimits=(4,3))
ax12.set_ylabel('Cost of shortfall [\u20ac]')

ax.set_ylabel(r'$\sum_t b_{t,i}$ [MW]')

handles1, labels1 = ax.get_legend_handles_labels()
handles2, labels2 = ax12.get_legend_handles_labels()

handles = handles1[0:3] + handles2 + handles1[3:]
labels = labels1[0:3] + labels2 + labels1[3:]

fig.legend(loc='upper center', bbox_to_anchor=(0.5, 0.24), ncol=3, frameon=False, handles=handles, labels=labels)
save_fig_bool = True
if save_fig_bool:
    save_fig(fig, "single", f"{save_fig_path}mix_{model}.pdf")

# %%

def get_eps_price(eps, g):
    return g.cost_intercept + g.cost_slope*eps/0.2

hours_plot = [3]

best_eps = [optimal_eps[f"eps[{hours_plot[0]}]"]] if model == 'dynamic' else [optimal_eps]

dem = optimal_demand[f'demand[{hours_plot[0]}]']
e = optimal_eps
bids1 = optimal_accepted_bids[f'accepted_bid[{hours_plot[0]},0]']
bids2 = optimal_accepted_bids[f'accepted_bid[{hours_plot[0]},1]']
bids3 = optimal_accepted_bids[f'accepted_bid[{hours_plot[0]},2]']

print(f'{1-e:.2f} & {bids2/(bids1+bids2+bids3):.2f} ({get_eps_price(e, g2):.2f}) & {bids1/(bids1+bids2+bids3):.2f} ({get_eps_price(e, g1):.2f}) & {bids3/(bids1+bids2+bids3):.2f} ({get_eps_price(e, g3):.2f})')

# %%

e_plot = [eps_range[-1], eps_range[0]]
colors = [g3.color, g1.color]
for i in range(len(e_plot)):
    e = e_plot[i]
    bids1 = bids_res_static[e][f'accepted_bid[{hours_plot[0]},0]']
    bids2 = bids_res_static[e][f'accepted_bid[{hours_plot[0]},1]']
    bids3 = bids_res_static[e][f'accepted_bid[{hours_plot[0]},2]']
    print(f'{1-e:.2f} & {bids2/(bids1+bids2+bids3):.2f} ({get_eps_price(e, g2):.2f}) & {bids1/(bids1+bids2+bids3):.2f} ({get_eps_price(e, g1):.2f}) & {bids3/(bids1+bids2+bids3):.2f} ({get_eps_price(e, g3):.2f})')



# %%

# Wind, EV, Conventional, Demand cleared
optimal_demand[f'demand[{hours_plot[0]}]']