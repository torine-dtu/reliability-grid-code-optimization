import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class GeneratorBase:
    """
    Base class for power generators storing hourly distribution fitting results.
    """

    def __init__(
        self,
        name: str,
        hourly_data: Optional[Dict[int, Any]] = None,
        generator_type: Optional[str] = None,
        cost_intercept: Optional[float] = None,
        cost_slope: Optional[float] = None,
        color: Optional[str] = None,
        scenarios: Optional[List[Any]] = None,
    ):
        self.name = name
        self.hourly_data = {int(k): v for k, v in (hourly_data or {}).items()}
        self._generator_type = generator_type
        self._cost_intercept = cost_intercept
        self._cost_slope = cost_slope
        self._color = color
        self._scenarios = scenarios if scenarios is not None else []

    @classmethod
    def from_json(cls, filepath: str | Path):
        path = Path(filepath)
        with open(path, "r") as f:
            data = json.load(f)
        hourly_data = {int(k): v for k, v in data.items()}
        return cls(name=path.stem, hourly_data=hourly_data)

    def to_json(self, filepath: str | Path):
        """Save generator data (including metadata) to a JSON file."""
        path = Path(filepath)
        payload = {
            "meta": {
                "generator_type": self._generator_type,
                "cost_intercept": self._cost_intercept,
                "cost_slope": self._cost_slope,
                "color": self._color,
                "scenarios": self._scenarios,
            },
            "hourly_data": self.hourly_data,
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=4)

    @property
    def generator_type(self) -> Optional[str]:
        return self._generator_type

    @generator_type.setter
    def generator_type(self, value: str):
        self._generator_type = value

    @property
    def cost_intercept(self) -> Optional[float]:
        return self._cost_intercept

    @cost_intercept.setter
    def cost_intercept(self, value: float):
        self._cost_intercept = float(value)

    @property
    def cost_slope(self) -> Optional[float]:
        return self._cost_slope

    @cost_slope.setter
    def cost_slope(self, value: float):
        self._cost_slope = float(value)

    def set_cost_function(self, intercept: float, slope: float):
        """Set both cost function parameters at once."""
        self.cost_intercept = intercept
        self.cost_slope = slope

    def get_cost_function(self) -> Dict[str, Optional[float]]:
        """Return intercept and slope as a dict."""
        return {"intercept": self._cost_intercept, "slope": self._cost_slope}

    def evaluate_cost(self, eps: float) -> Optional[float]:
        """Evaluate the linear cost function at a given eps level."""
        if self._cost_intercept is None or self._cost_slope is None:
            return None
        return self._cost_intercept + self._cost_slope * eps

    @property
    def color(self) -> Optional[str]:
        return self._color

    @color.setter
    def color(self, value: str):
        self._color = value

    @property
    def scenarios(self) -> Dict[int, Dict[int, Any]]:
        return self._scenarios

    @scenarios.setter
    def scenarios(self, value: Dict[int, Dict[int, Any]]):
        self._scenarios = {int(t): {int(w): v for w, v in scenarios.items()}
                        for t, scenarios in value.items()}

    def get_scenario_t(self, t: int) -> Optional[Dict[int, Any]]:
        """Return all scenarios at hour t."""
        return self._scenarios.get(int(t))

    def get_scenario_tw(self, t: int, w: int) -> Optional[Any]:
        """Return the value for scenario w at hour t."""
        hour = self._scenarios.get(int(t))
        return hour.get(int(w)) if hour is not None else None

    def clear_scenarios(self):
        self._scenarios.clear()

    def get_hour_data(self, hour: int) -> Optional[Dict[str, Any]]:
        return self.hourly_data.get(int(hour))

    def get_parameters(self, hour: int) -> Optional[Dict[str, Any]]:
        entry = self.get_hour_data(hour)
        return entry["parameters"] if entry else None

    def get_errors(self, hour: int) -> Optional[Dict[str, Any]]:
        entry = self.get_hour_data(hour)
        return entry["errors"] if entry else None

    def get_distribution_name(self, hour: int) -> Optional[str]:
        entry = self.get_hour_data(hour)
        return entry["distribution"] if entry else None

    def list_hours(self):
        return sorted(self.hourly_data.keys())

    def add_or_update_hour(
        self,
        hour: int,
        distribution_name: str,
        parameters: Dict[str, float],
        errors: Dict[str, float],
    ):
        self.hourly_data[int(hour)] = {
            "distribution": distribution_name,
            "parameters": parameters,
            "errors": errors,
        }

    def remove_hour(self, hour: int):
        hour = int(hour)
        if hour in self.hourly_data:
            del self.hourly_data[hour]

    def clear(self):
        self.hourly_data.clear()

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} name={self.name!r} "
            f"type={self._generator_type!r} hours={len(self.hourly_data)} "
            f"scenarios={len(self._scenarios)}>"
        )

class Stochastic(GeneratorBase):
    def __init__(self, name="Generator 1", hourly_data=None, **kwargs):
        super().__init__(name=name, hourly_data=hourly_data, **kwargs)

    def add_hour_data(self, hour, kappa, gamma, quantile, nll, D, p_val):
        parameters = {"kappa": kappa, "gamma": gamma, "quantile": quantile}
        errors = {"nll": nll, "ks_statistic": D, "ks_pvalue": p_val}
        self.add_or_update_hour(hour, "weibull", parameters, errors)

class Conventional(GeneratorBase):
    def __init__(self, name="Generator 3", hourly_data=None, **kwargs):
        super().__init__(name=name, hourly_data=hourly_data, **kwargs)

    def add_hour_data(self, hour, capacity):
        parameters = {"capacity": capacity}
        self.add_or_update_hour(hour, "fixed", parameters, errors={})