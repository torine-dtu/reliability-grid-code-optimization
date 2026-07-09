import math
import numpy as np
import gurobipy as gp
from gurobipy import GRB
import generator_class as gc

class InputData:
    
    def __init__(
        self, 
        input_data: dict
    ):
        self.model_type = input_data['model_type']
        self.I = input_data['GENERATORS']
        self.T = input_data['HOURS']
        self.W = input_data['SCENARIOS']
        self.PENALTY = input_data['penalty']
        self.DEMAND = input_data['demand']
        self.eps_sys = input_data['eps_sys']
        self.eps_input = input_data['eps_input']
        self.bigM = input_data['bigM']
        self.defined_percentile = input_data.get('defined_percentile', 0.2) # default to 0.2 if not provided

# Helper function for inverse Weibull CDF for constructing upper bounds
def weibull(eps, params, c0=0.2):
    kappa, gamma, quantile = params["kappa"], params["gamma"], params["quantile"]
    return quantile - ((-1.0 / kappa) * math.log(float(eps) / c0)) ** (1.0 / gamma)

class OptimizationProblem:
    def __init__(self, input_data, generators, name="market_model"):
        self.model_type = input_data.model_type
        self.data = input_data
        self.generators = generators

        self.model = gp.Model(name)
        # Allow nonconvex quadratic terms (needed for bilinear constraints/objective)
        self.model.Params.NonConvex = 2

        self.vars = {}
        self._build_variables()
        self._build_constraints()
        self._build_objective()

        self.results = {}

    def _offered_bid_ub(self, t, i):
        gen = self.generators[i]
        gen_type = gen.generator_type
        params = gen.get_parameters(hour=t)

        if gen_type == 'Wind' or gen_type == 'EV':
            return weibull(0.2, params, c0=self.data.defined_percentile)
        elif gen_type == 'Conventional':
            return params["capacity"]
        else:
            raise ValueError(f"Unknown generator type: {gen_type}")

    def _demand_ub(self, t):
        total = 0.0
        for i in self.data.I:
            gen = self.generators[i]
            gen_type = gen.generator_type
            params = gen.get_parameters(hour=t)
            if gen_type == 'Wind' or gen_type == 'EV':
                total += weibull(0.2, params, c0=self.data.defined_percentile)
            elif gen_type == 'Conventional':
                total += params["capacity"]
            else:
                raise ValueError(f"Unknown generator type: {gen_type}")
        return total

    def _system_shortfall_ub(self, t, w):
        total = 0.0
        for i in self.data.I:
            total += self._offered_bid_ub(t, i)
        return total

    def _build_variables(self):
        m = self.model
        T, I, W = self.data.T, self.data.I, self.data.W

        # --- Epsilon ---
        if self.model_type == "dynamic":
            eps_lb = []
            eps_ub = []

            for t in T:
                val = self.data.eps_input[t]
                if np.isnan(val):
                    eps_lb.append(0.001)  # free variable: use default bounds
                    eps_ub.append(0.2)
                else:
                    eps_lb.append(val)     # fixed variable: pin lb == ub
                    eps_ub.append(val)

            self.vars["eps"] = m.addVars(T, lb=eps_lb, ub=eps_ub, name="eps")
        elif self.model_type == "static":
            if not np.isnan(self.data.eps_input):
                self.vars["eps"] = m.addVar(lb=self.data.eps_input, 
                                            ub=self.data.eps_input, name="eps")
            else:
                self.vars["eps"] = m.addVar(lb=0.001, ub=0.2, name="eps")
        else:
            raise ValueError("model_type must be 'dynamic' or 'static'.")

        # --- Demand with UB ---
        self.vars["demand"] = m.addVars(T, lb=0.0, ub={t: self._demand_ub(t) for t in T},
            name="demand"
        )

        # --- Shortfall vars ---
        self.vars["shortfall"] = m.addVars(T, I, W, lb=0.0, name="shortfall")
        self.vars["system_shortfall"] = m.addVars(
            T, W,
            lb=0.0,
            ub={(t, w): self._system_shortfall_ub(t, w) for t in T for w in W},
            name="system_shortfall"
        )
        self.vars["system_shortfall_binary"] = m.addVars(T, W, vtype=GRB.BINARY, name="viol_bin")

        self.vars["system_compromise"] = m.addVars(T, W, lb=0.0, name="system_compromise")

        # --- Generator-level vars ---
        # z_expr will be linked via PWL or equality (Conventional)
        self.vars["z_expr"] = m.addVars(T, I, lb=0.0, ub={(t, i): self._offered_bid_ub(t, i) for t in T for i in I}, name="z_expr")
        # offered_bid, accepted_bid inherit UB from _offered_bid_ub
        offered_ub = {(t, i): self._offered_bid_ub(t, i) for t in T for i in I}
        self.vars["offered_bid"] = m.addVars(T, I, lb=0.0, ub=offered_ub, name="offered_bid")
        self.vars["accepted_bid"] = m.addVars(T, I, lb=0.0, ub=offered_ub, name="accepted_bid")

        self.vars["mu_upper"] = m.addVars(T, I, lb=0.0, ub=max(gen.cost_intercept for gen in self.generators), name="mu_upper")
        self.vars["mu_lower"] = m.addVars(T, I, lb=0.0, name="mu_lower")

        # --- Market-level vars ---
        self.vars["lam"] = m.addVars(T, lb=0, ub=max(gen.cost_intercept for gen in self.generators), name="lam")
        self.vars["nu_upper"] = m.addVars(T, I, lb=0.0, ub=max(gen.cost_intercept for gen in self.generators), name="nu_upper")
        self.vars["nu_lower"] = m.addVars(T, I, lb=0.0, name="nu_lower")

        # --- McCormick envelope vars for lam * demand ---
        self.vars["u_lamd"] = m.addVars(T, lb=0.0, name="u_lamd")

        # --- McCormick envelope vars for eps * accepted_bid ---
        self.vars["u_epsb"] = m.addVars(T, I, lb=0.0, name="u_epsb")

        # --- McCormick envelope vars for nu_upper * offered_bid ---
        self.vars["u_nub"] = m.addVars(T, I, lb=0.0, name="u_nub")

        # --- McCormick envelope vars for mu_upper * z_expr ---
        self.vars["u_muz"] = m.addVars(T, I, lb=0.0, name="u_muz")

        self.model.update()

    # -----------------------------
    # Constraints
    # -----------------------------

    def _add_pwl_z_constraints(self):
        m = self.model
        v = self.vars
        T, I = self.data.T, self.data.I

        eps_grid = np.linspace(0.001, 0.2, 100).tolist()

        for t in T:
            for i in I:
                gen = self.generators[i]
                gen_type = gen.generator_type
                params = gen.get_parameters(hour=t)

                eps_var = v["eps"][t] if self.model_type == "dynamic" else v["eps"]

                if gen_type == "Conventional":
                    m.addConstr(v["z_expr"][t, i] == params["capacity"], name=f"z_expr[{t},{i}]")
                elif gen_type == "Wind" or gen_type == "EV":
                    z_grid = [max(0, weibull(eps, params, c0=self.data.defined_percentile)) for eps in eps_grid]
                    z_grid = [max(num, 0) for num in z_grid]
                    m.addGenConstrPWL(eps_var, v["z_expr"][t, i], eps_grid, z_grid, name=f"z_expr[{t},{i}]")
                else:
                    raise ValueError(f"Unknown generator type: {gen_type}")

    def _build_constraints(self):
        m = self.model
        v = self.vars
        T, I, W = self.data.T, self.data.I, self.data.W

        # helper function
        def eps_at(t):
            return v["eps"][t] if self.model_type == "dynamic" else v["eps"]

        # -- PWL mapping for z_expr
        self._add_pwl_z_constraints()

        # offered_bid ≤ z_expr
        m.addConstrs(
            (v["offered_bid"][t, i] <= v["z_expr"][t, i] for t in T for i in I), name="offered_bid_bound"
        )

        # TSO: shortfall ≥ accepted_bid - realization
        I_stochastic = [i for i in I if not isinstance(self.generators[i], gc.Conventional)]

        m.addConstrs(
            (v["shortfall"][t, i, w] >= v["accepted_bid"][t, i] - self.generators[i].get_scenario_tw(t, w)
            for t in T for i in I_stochastic for w in W),
            name="shortfall_quantification"
        )

        # System shortfall equality
        m.addConstrs(
            (v["system_shortfall"][t, w] == gp.quicksum(v["shortfall"][t, i, w] for i in I)
             for t in T for w in W),
            name="system_shortfall_quantity"
        )

        # Big-M violation counting
        m.addConstrs(
            (v["demand"][t] - v["system_shortfall"][t, w] + self.data.bigM[t] * v["system_shortfall_binary"][t, w]
             >= self.data.DEMAND[t] for t in T for w in W),
            name="system_shortfall_bigM"
        )

        # Sum of violations constraint
        m.addConstrs(
            (gp.quicksum(v["system_shortfall_binary"][t, w] for w in W)
             <= len(W) * self.data.eps_sys for t in T),
            name="system_shortfall_violations"
        )

        # define compromising variable
        m.addConstrs(
            (- self.data.DEMAND[t] + v["demand"][t] - v["system_shortfall"][t, w] 
            >= -v["system_compromise"][t, w] for t in T for w in W),
            name="system_compromise"
        )

        # Generator KKT stationarity: -1 + mu_upper - mu_lower = 0
        m.addConstrs(
            (-1 + v["mu_upper"][t, i] - v["mu_lower"][t, i] == 0
             for t in T for i in I),
            name="generator_stationarity"
        )

        # Reverse weak duality (generator): -mu_upper * z_expr >= -offered_bid
        # Quadratic, NonConvex=2 is enabled at model level.
        m.addConstrs(
            (-v["mu_upper"][t, i] * v["z_expr"][t, i] >= -v["offered_bid"][t, i]
             for t in T for i in I),
            name="weak_reverse_duality_generator"
        )

        # Market stationarity for each generator:
        # cost_intercept - cost_slope * eps/0.2 - nu_lower + nu_upper - lam == 0
        m.addConstrs((
            self.generators[i].cost_intercept + self.generators[i].cost_slope * (eps_at(t) / 0.2) - v["nu_lower"][t, i] + v["nu_upper"][t, i] - v["lam"][t] == 0 for i in I for t in T),
            name=f"market_stationarity_generator"
        )

        # accepted_bid ≤ offered_bid
        m.addConstrs(
            (v["accepted_bid"][t, i] <= v["offered_bid"][t, i]
             for t in T for i in I),
            name="accepted_bid_bound"
        )

        # Market clearing: demand = sum_g accepted_bid
        m.addConstrs(
            (v["demand"][t] == gp.quicksum(v["accepted_bid"][t, i] for i in I)
             for t in T),
            name="market_clearing"
        )

        # Reverse weak duality (market):
        for t in T:
            dual = -gp.quicksum(v["u_nub"][t, i] for i in I) \
                   + v["u_lamd"][t] # replace lam*d with u_lamd, which is linked via binary expansion constraints below
            primal = gp.quicksum(
                self.generators[i].cost_intercept * v["accepted_bid"][t, i] + self.generators[i].cost_slope * v["u_epsb"][t, i]/0.2
                for i in I)
            m.addConstr(dual >= primal, name=f"weak_reverse_duality_market_{t}")

        # -- McCormick for lam * d in reverse weak duality (market)
        m.addConstrs(v['u_lamd'][t] >= v['lam'][t].UB * v['demand'][t] + v['lam'][t] * v['demand'][t].UB - v['lam'][t].UB * v['demand'][t].UB for t in T)
        m.addConstrs(v['u_lamd'][t] <= v['lam'][t].UB * v['demand'][t] for t in T)
        m.addConstrs(v['u_lamd'][t] <= v['lam'][t] * v['demand'][t].UB for t in T)

        # -- McCormick constraints for objective function
        m.addConstrs(v["u_epsb"][t, i] >= eps_at(t).UB * v["accepted_bid"][t, i] + 
                        eps_at(t) * v["accepted_bid"][t, i].UB - 
                        eps_at(t).UB * v["accepted_bid"][t, i].UB for t in T for i in I)
        m.addConstrs(v["u_epsb"][t, i] <= eps_at(t).UB * v["accepted_bid"][t, i] for t in T for i in I)
        m.addConstrs(v["u_epsb"][t, i] <= eps_at(t) * v["accepted_bid"][t, i].UB for t in T for i in I)

        # -- McCormick constraints for nu_upper * offered_bid in market stationarity, both variables have 0 lower bound
        m.addConstrs(v["u_nub"][t, i] >= v["nu_upper"][t, i].UB * v["offered_bid"][t, i] +
                        v["nu_upper"][t, i] * v["offered_bid"][t, i].UB -
                        v["nu_upper"][t, i].UB * v["offered_bid"][t, i].UB for t in T for i in I)
        m.addConstrs(v["u_nub"][t, i] <= v["nu_upper"][t, i].UB * v["offered_bid"][t, i] for t in T for i in I)
        m.addConstrs(v["u_nub"][t, i] <= v["nu_upper"][t, i] * v["offered_bid"][t, i].UB for t in T for i in I)

        # -- McCormick constraints for mu_upper * z_expr in generator stationarity, both variables have 0 lower bound
        m.addConstrs(v["u_muz"][t, i] >= v["mu_upper"][t, i].UB * v["z_expr"][t, i] +
                        v["mu_upper"][t, i] * v["z_expr"][t, i].UB -
                        v["mu_upper"][t, i].UB * v["z_expr"][t, i].UB for t in T for i in I)
        m.addConstrs(v["u_muz"][t, i] <= v["mu_upper"][t, i].UB * v["z_expr"][t, i] for t in T for i in I)
        m.addConstrs(v["u_muz"][t, i] <= v["mu_upper"][t, i] * v["z_expr"][t, i].UB for t in T for i in I)


    def _build_objective(self):
        v = self.vars
        T, I, W = self.data.T, self.data.I, self.data.W

        def eps_at(t):
            return v["eps"][t] if self.model_type == "dynamic" else v["eps"]

        obj = gp.quicksum(
            gp.quicksum(gen.cost_intercept * v["accepted_bid"][t, i] + gen.cost_slope * v["u_epsb"][t, i] / 0.2 for i, gen in enumerate(self.generators))
            + self.data.PENALTY *
            gp.quicksum(( 1 / len(W) ) * v["system_compromise"][t, w] for w in W)
            + 0.5*self.data.PENALTY *
            gp.quicksum(( 1 / len(W) ) * v["system_shortfall"][t, w] for w in W) for t in T
        )
        self.model.setObjective(obj, GRB.MINIMIZE)

    def apply_warm_start(
        self,
        lam_start=None,
        eps_start=None,
     ):
        def _safe_start(var_container, key, value):
            """
            Assign start value only if:
            - variable exists
            - value is not None
            - value is finite
            """
            if value is None:
                return

            if isinstance(value, float) and np.isnan(value):
                return

            try:
                var = var_container[key]
                var.Start = value
            except Exception:
                pass

        if lam_start is not None:
            for key, val in lam_start.items():
                _safe_start(self.vars["lam"], key, val)

        if eps_start is not None:

            if self.model_type == "dynamic":
                for key, val in eps_start.items():
                    _safe_start(self.vars["eps"], key, val)

            elif self.model_type == "static":
                self.vars["eps"].Start = eps_start

        # Push starts into model
        self.model.update()

    def run(self, tee=True, tuning=False):
        if not tee:
            self.model.Params.OutputFlag = 0
        # Optional tuning knobs:
        if tuning:
            #self.model.Params.TimeLimit = 600
            self.model.Params.MIPGap = 0.0

        self.model.optimize()

        if self.model.status not in (GRB.OPTIMAL, GRB.INTERRUPTED, GRB.TIME_LIMIT) and \
           self.model.status != GRB.SUBOPTIMAL:
            raise RuntimeError(f"Gurobi ended with status {self.model.status}")

        self._save_results()

    def _save_results(self):
        m = self.model
        v = self.vars

        self.results["objective"] = m.objVal
        self.results["status"] = m.status
        self.results["runtime"] = m.Runtime
        self.results["mipgap"] = m.MIPGap

        vars_out = {}
        
        for v in m.getVars():
            vars_out[f"{v.VarName}"] = v.X

        self.results["variables"] = vars_out

        # vars_out = {}
        # vars_out["TSO"] = {}
        # vars_out["units"] = {}
        # vars_out["market"] = {}
        # vars_out["rest"] = {}
        
        # for v in m.getVars():
        #     if (any(s in v.VarName for s in ["eps", "shortfall", "demand", "system", "bin"])
        #         and "epsb" not in v.VarName):
        #         vars_out["TSO"][f"{v.VarName}"] = v.X
        #     elif any(s in v.VarName for s in ["offered_bid", "mu", "z_expr"]):
        #         vars_out["units"][f"{v.VarName}"] = v.X
        #     elif any(s in v.VarName for s in ["accepted_bid", "nu", "lam"]):
        #         vars_out["market"][f"{v.VarName}"] = v.X
        #     else:
        #         vars_out["rest"][f"{v.VarName}"] = v.X

        # self.results["variables"] = vars_out

class Accessors(OptimizationProblem):
    def __init__(self, model):
        self.model = model
        self.results = model.results
        self.data = model.data
        self.model_type = model.model_type
        self.generators = model.generators
    
    def eps_at(self, t):
        v = self.results["variables"]
        return v[f"eps[{t}]"] if self.model_type == "dynamic" else v["eps"]

    def get_objective(self):
        return self.results["objective"]

    def get_status(self):
        return self.results["status"]
    
    def get_runtime(self):
        return self.results["runtime"]

    def get_mipgap(self):
        return self.results["mipgap"]

    def get_original_objective(self):
        v = self.results["variables"]
        T, I, W = self.data.T, self.data.I, self.data.W

        obj = 0
        for t in T:
            obj += np.sum([(self.generators[i].cost_intercept + self.generators[i].cost_slope * self.eps_at(t) / 0.2)
                        * v[f"accepted_bid[{t},{i}]"] for i in I]) \
                            + self.data.PENALTY * np.sum([(1 / len(W)) * v[f"system_compromise[{t},{w}]"] for w in W]) \
                            + 0.5 * self.data.PENALTY * np.sum([(1 / len(W)) * v[f"system_shortfall[{t},{w}]"] for w in W])
        return obj

    def get_something(self, variable):
        res = {}
        for k, v in self.results["variables"].items():
            if variable in k: res[k] = v
        return res
    
    def get_clearing_price(self):
        res = {}
        for k, v in self.results["variables"].items():
            if "lam" in k: res[k] = v
        return res

    def get_eps_result(self):
        res = {}
        for k, v in self.results["variables"].items():
            if "eps" in k and not "u" in k: res[k] = v
        return res
    
    def get_cleared_demand(self):
        res = {}
        for k, v in self.results["variables"].items():
            if "demand" in k: res[k] = v
        return res

    def get_bid_per_generator(self):
        res = {}
        for k, v in self.results["variables"]["units"].items():
            if "bid" in k: res[k] = v
        return res

    def get_positive_shortfall(self):
        res = {}
        for k, v in self.results["variables"].items():
            if "shortfall" in k and not "system" in k:
                if v > 0: res[k] = v
        return res

    def get_total_shortfall(self):
        res = 0
        for k, v in self.results["variables"].items():
            if "shortfall" in k and not "system" in k:
                res += v
        return res

    def get_hourly_cost(self):
        v = self.results["variables"]
        res = {}

        for t in self.data.T:
            res[t] = np.sum([(self.generators[i].cost_intercept*v[f"accepted_bid[{t},{i}]"] \
                + self.generators[i].cost_slope*v[f"u_epsb[{t},{i}]"]/0.2) \
                     for i in self.data.I]) + self.data.PENALTY * np.sum([( 1 / len(self.data.W) ) \
                        * v[f"system_compromise[{t},{w}]"] for w in self.data.W]) \
                            + 0.5*self.data.PENALTY * np.sum([( 1 / len(self.data.W) ) * v[f"system_shortfall[{t},{w}]"] for w in self.data.W])
        return res

    def get_original_hourly_cost(self):
        v = self.results["variables"]

        res = {}

        for t in self.data.T:
            res[t] = 0.0
            res[t] += np.sum([(self.generators[i].cost_intercept + self.generators[i].cost_slope*self.eps_at(t)/0.2)*v[f"accepted_bid[{t},{i}]"] for i in self.data.I]) + self.data.PENALTY * np.sum([( 1 / len(self.data.W) ) * v[f"system_compromise[{t},{w}]"] for w in self.data.W]) + 0.5 * self.data.PENALTY * np.sum([( 1 / len(self.data.W) ) * v[f"system_shortfall[{t},{w}]"] for w in self.data.W])
        return res

    def failure_cost(self):
        v = self.results["variables"]
        penalty = self.data.PENALTY
        nW = len(self.data.W)

        res = 0
        for t in self.data.T:
            res += self.data.PENALTY * np.sum([( 1 / len(self.data.W) ) * v[f"system_compromise[{t},{w}]"] for w in self.data.W]) + 0.5 * self.data.PENALTY * np.sum([( 1 / len(self.data.W) ) * v[f"system_shortfall[{t},{w}]"] for w in self.data.W])
        return res


    def get_procurement_cost(self):
        v = self.results["variables"]

        res = 0
        for t in self.data.T:
            res += np.sum([(self.generators[i].cost_intercept + self.generators[i].cost_slope*self.eps_at(t)/0.2)*v[f"accepted_bid[{t},{i}]"] for i in self.data.I])
        return res

# class Accessors(OptimizationProblem):
#     def __init__(self, model):
#         self.model = model
#         self.results = model.results
#         self.data = model.data
#         self.model_type = model.model_type
#         self.generators = model.generators
    
#     def eps_at(t):
#         v = self.results["variables"]
#         return v["TSO"][f"eps[{t}]"] if self.model_type == "dynamic" else v["TSO"]["eps"]

#     def get_objective(self):
#         return self.results["objective"]

#     def get_status(self):
#         return self.results["status"]
    
#     def get_runtime(self):
#         return self.results["runtime"]

#     def get_mipgap(self):
#         return self.results["mipgap"]

#     def get_original_objective(self):
#         v = self.results["variables"]
#         T, I, W = self.data.T, self.data.I, self.data.W

#         obj = np.sum([
#             np.sum([(self.generators[i].cost_intercept + self.generators[i].cost_slope * eps_at(t) / 0.2)
#                     * v["market"][f"accepted_bid[{t},{i}]"] for i in I])
#             + self.data.PENALTY * np.sum(
#                 [(1 / len(W)) * v["TSO"][f"system_compromise[{t},{w}]"] for w in W])
#             + 0.5 * self.data.PENALTY * np.sum(
#                 [(1 / len(W)) * v["TSO"][f"system_shortfall[{t},{w}]"] for w in W])
#             for t in T
#         ])
#         return obj

#     def get_something(self, level, variable):
#         res = {}
#         for k, v in self.results["variables"][level].items():
#             if variable in k: res[k] = v
#         return res
    
#     def get_clearing_price(self):
#         res = {}
#         for k, v in self.results["variables"]["market"].items():
#             if "lam" in k: res[k] = v
#         return res

#     def get_eps_result(self):
#         res = {}
#         for k, v in self.results["variables"]["TSO"].items():
#             if "eps" in k: res[k] = v
#         return res
    
#     def get_cleared_demand(self):
#         res = {}
#         for k, v in self.results["variables"]["TSO"].items():
#             if "demand" in k: res[k] = v
#         return res

#     def get_bid_per_generator(self):
#         res = {}
#         for k, v in self.results["variables"]["units"].items():
#             if "bid" in k: res[k] = v
#         return res

#     def get_positive_shortfall(self):
#         res = {}
#         for k, v in self.results["variables"]["TSO"].items():
#             if "shortfall" in k and not "system" in k:
#                 if v > 0: res[k] = v
#         return res

#     def get_total_shortfall(self):
#         res = 0
#         for k, v in self.results["variables"]["TSO"].items():
#             if "shortfall" in k and not "system" in k:
#                 res += v
#         return res

#     def get_hourly_cost(self):
#         v = self.results["variables"]
#         res = {}

#         for t in self.data.T:
#             res[t] = np.sum([(self.generators[i].cost_intercept*v["market"][f"accepted_bid[{t},{i}]"] \
#                 + self.generators[i].cost_slope*v["rest"][f"u_epsb[{t},{i}]"]/0.2) \
#                      for i in self.data.I]) + self.data.PENALTY * np.sum([( 1 / len(self.data.W) ) \
#                         * v["TSO"][f"system_compromise[{t},{w}]"] for w in self.data.W]) \
#                             + 0.5*self.data.PENALTY * np.sum([( 1 / len(self.data.W) ) * v["TSO"][f"system_shortfall[{t},{w}]"] for w in self.data.W])
#         return res

#     def get_original_hourly_cost(self):
#         v = self.results["variables"]

#         res = {}

#         for t in self.data.T:
#             res[t] = 0.0
#             res[t] += np.sum([(self.generators[i].cost_intercept + self.generators[i].cost_slope*eps_at(t)/0.2)*v["market"][f"accepted_bid[{t},{i}]"] for i in self.data.I]) + self.data.PENALTY * np.sum([( 1 / len(self.data.W) ) * v["TSO"][f"system_compromise[{t},{w}]"] for w in self.data.W]) + 0.5 * self.data.PENALTY * np.sum([( 1 / len(self.data.W) ) * v["TSO"][f"system_shortfall[{t},{w}]"] for w in self.data.W])
#         return res

#     def failure_cost(self):
#         v = self.results["variables"]
#         penalty = self.data.PENALTY
#         nW = len(self.data.W)

#         res = 0
#         for t in self.data.T:
#             res += self.data.PENALTY * np.sum([( 1 / len(self.data.W) ) * v["TSO"][f"system_compromise[{t},{w}]"] for w in self.data.W]) + 0.5 * self.data.PENALTY * np.sum([( 1 / len(self.data.W) ) * v["TSO"][f"system_shortfall[{t},{w}]"] for w in self.data.W])
#         return res


#     def get_procurement_cost(self):
#         v = self.results["variables"]

#         res = 0
#         for t in self.data.T:
#             res += np.sum([(self.generators[i].cost_intercept + self.generators[i].cost_slope*eps_at(t)/0.2)*v["market"][f"accepted_bid[{t},{i}]"] for i in self.data.I])
#         return res
    