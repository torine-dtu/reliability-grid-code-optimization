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