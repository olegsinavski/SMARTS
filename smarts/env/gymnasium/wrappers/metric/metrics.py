# Copyright (C) 2022. Huawei Technologies Co., Ltd. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import gymnasium as gym

from smarts.core.agent_interface import ActorsAliveDoneCriteria, AgentInterface
from smarts.core.coordinates import Point, RefLinePoint
from smarts.core.observations import Observation
from smarts.core.plan import EndlessGoal, PositionalGoal
from smarts.core.road_map import RoadMap
from smarts.core.scenario import Scenario
from smarts.core.traffic_provider import TrafficProvider
from smarts.core.utils.import_utils import import_module_from_file
from smarts.core.vehicle_index import VehicleIndex
from smarts.env.gymnasium.wrappers.metric.costs import (
    CostFuncs,
    Done,
    get_dist,
    make_cost_funcs,
)
from smarts.env.gymnasium.wrappers.metric.formula import Score
from smarts.env.gymnasium.wrappers.metric.params import Params
from smarts.env.gymnasium.wrappers.metric.types import Costs, Counts, Record
from smarts.env.gymnasium.wrappers.metric.utils import (
    add_dataclass,
    divide,
    op_dataclass,
)


class MetricsError(Exception):
    """Raised when Metrics env wrapper fails."""

    pass


class MetricsBase(gym.Wrapper):
    """Computes agents' performance metrics in a SMARTS environment."""

    def __init__(self, env: gym.Env, formula_path: Optional[Path] = None):
        super().__init__(env)

        # Import scoring formula.
        if formula_path:
            import_module_from_file("custom_formula", formula_path)
            from custom_formula import Formula
        else:
            from smarts.env.gymnasium.wrappers.metric.formula import Formula

        self._formula = Formula()
        self._params = self._formula.params()

        _check_env(agent_interfaces=self.env.agent_interfaces, params=self._params)

        self._scen: Scenario
        self._scen_name: str
        self._road_map: RoadMap
        self._cur_agents: Set[str]
        self._steps: Dict[str, int]
        self._done_agents: Set[str]
        self._vehicle_index: VehicleIndex
        self._cost_funcs: Dict[str, CostFuncs]
        self._records_sum: Dict[str, Dict[str, Record]] = {}

    def step(self, action: Dict[str, Any]):
        """Steps the environment by one step."""
        result = super().step(action)

        obs, _, terminated, truncated, info = result

        # Only count steps in which an ego agent is present.
        if len(obs) == 0:
            return result

        dones = {}
        if isinstance(terminated, dict):
            # Caters to environments which use (i) ObservationOptions.multi_agent,
            # (ii) ObservationOptions.unformated, and (iii) ObservationOptions.default .
            dones = {k: v or truncated[k] for k, v in terminated.items()}
        elif isinstance(terminated, bool):
            # Caters to environments which use (i) ObservationOptions.full .
            if terminated or truncated:
                dones["__all__"] = True
            else:
                dones["__all__"] = False
            dones.update({a: d["done"] for a, d in info.items()})

        if isinstance(next(iter(obs.values())), dict):
            # Caters to environments which use (i) ObservationOptions.multi_agent,
            # (ii) ObservationOptions.full, and (iii) ObservationOptions.default .
            active_agents = [
                agent_id for agent_id, agent_obs in obs.items() if agent_obs["active"]
            ]
        else:
            # Caters to environments which uses (i) ObservationOptions.unformated .
            active_agents = list(obs.keys())

        for agent_name in active_agents:
            base_obs: Observation = info[agent_name]["env_obs"]
            self._steps[agent_name] += 1

            # Compute all cost functions.
            costs = Costs()
            for _, cost_func in self._cost_funcs[agent_name].items():
                new_costs = cost_func(
                    self._road_map,
                    self._vehicle_index,
                    Done(dones[agent_name]),
                    base_obs,
                )
                if dones[agent_name]:
                    costs = add_dataclass(new_costs, costs)

            if dones[agent_name] == False:
                # Skip the rest, if agent is not done yet.
                continue

            self._done_agents.add(agent_name)
            # Only these termination reasons are considered by the current metrics.
            if not (
                base_obs.events.reached_goal
                or len(base_obs.events.collisions)
                or base_obs.events.off_road
                or base_obs.events.reached_max_episode_steps
                or base_obs.events.actors_alive_done
            ):
                raise MetricsError(
                    "Expected reached_goal, collisions, off_road, "
                    "max_episode_steps, or actors_alive_done, to be true "
                    f"on agent done, but got events: {base_obs.events}."
                )

            # Update stored counts and costs.
            counts = Counts(
                episodes=1,
                steps=self._steps[agent_name],
                goals=base_obs.events.reached_goal,
            )
            self._records_sum[self._scen_name][agent_name].counts = add_dataclass(
                counts, self._records_sum[self._scen_name][agent_name].counts
            )
            self._records_sum[self._scen_name][agent_name].costs = add_dataclass(
                costs, self._records_sum[self._scen_name][agent_name].costs
            )

        if dones["__all__"] is True:
            assert (
                self._done_agents == self._cur_agents
            ), f'done["__all__"]==True but not all agents are done. Current agents = {self._cur_agents}. Agents done = {self._done_agents}.'

        return result

    def reset(self, **kwargs):
        """Resets the environment."""
        result = super().reset(**kwargs)
        self._cur_agents = set(self.env.agent_interfaces.keys())
        self._steps = dict.fromkeys(self._cur_agents, 0)
        self._done_agents = set()
        self._scen = self.env.smarts.scenario
        self._scen_name = self.env.smarts.scenario.name
        self._road_map = self.env.smarts.scenario.road_map
        self._vehicle_index = self.env.smarts.vehicle_index
        self._cost_funcs = {}

        _check_scen(scenario=self._scen, agent_interfaces=self.env.agent_interfaces)

        # Refresh the cost functions for every episode.
        for agent_name in self._cur_agents:
            end_pos = Point(0, 0, 0)
            dist_tot = 0
            if self._params.dist_to_destination.active:
                actors_alive = self.env.agent_interfaces[
                    agent_name
                ].done_criteria.actors_alive
                if isinstance(actors_alive, ActorsAliveDoneCriteria):
                    end_pos, dist_tot = _get_sumo_smarts_dist(
                        vehicle_name=actors_alive.actors_of_interest[0],
                        traffic_sims=self.env.smarts.traffic_sims,
                        road_map=self._road_map,
                    )
                elif actors_alive == None:
                    end_pos = self._scen.missions[agent_name].goal.position
                    dist_tot = get_dist(
                        road_map=self._road_map,
                        point_a=Point(*self._scen.missions[agent_name].start.position),
                        point_b=end_pos,
                    )

            self._cost_funcs[agent_name] = make_cost_funcs(
                params=self._params,
                dist_to_destination={
                    "end_pos": end_pos,
                    "dist_tot": dist_tot,
                },
                dist_to_obstacles={
                    "ignore": self._params.dist_to_obstacles.ignore,
                },
                vehicle_gap={
                    "num_agents": len(self._cur_agents),
                    "actor": self._params.vehicle_gap.actor,
                },
                steps={
                    "max_episode_steps": self.env.agent_interfaces[
                        agent_name
                    ].max_episode_steps,
                },
            )

        # Create new entry in records_sum for new scenarios.
        if self._scen_name not in self._records_sum.keys():
            self._records_sum[self._scen_name] = {
                agent_name: Record(
                    costs=Costs(),
                    counts=Counts(),
                )
                for agent_name in self._cur_agents
            }

        return result

    def records(self) -> Dict[str, Dict[str, Record]]:
        """
        Fine grained performance metric for each agent in each scenario.

        .. code-block:: bash

            $ env.records()
            $ {
                  scen1: {
                      agent1: Record(costs, counts),
                      agent2: Record(costs, counts),
                  },
                  scen2: {
                      agent1: Record(costs, counts),
                  },
              }

        Returns:
            Dict[str, Dict[str, Record]]: Performance record in a nested
            dictionary for each agent in each scenario.
        """

        records = {}
        for scen, agents in self._records_sum.items():
            records[scen] = {}
            for agent, data in agents.items():
                data_copy = copy.deepcopy(data)
                records[scen][agent] = Record(
                    costs=op_dataclass(
                        data_copy.costs, data_copy.counts.episodes, divide
                    ),
                    counts=data_copy.counts,
                )

        return records

    def score(self) -> Score:
        """
        Computes score according to environment specific formula from the
        Formula class.

        Returns:
            Dict[str, float]: Contains key-value pairs denoting score
            components.
        """
        records_sum_copy = copy.deepcopy(self._records_sum)
        return self._formula.score(records_sum=records_sum_copy)


def _get_sumo_smarts_dist(
    vehicle_name: str, traffic_sims: List[TrafficProvider], road_map: RoadMap
) -> Tuple[Point, float]:
    """Computes the end point and route distance of a SUMO or a SMARTS vehicle
    specified by `vehicle_name`.

    Args:
        vehicle_name (str): Name of vehicle.
        traffic_sims (List[TrafficProvider]): Traffic providers.
        road_map (RoadMap): Underlying road map.

    Returns:
        Tuple[Point, float]: End point and route distance.
    """
    traffic_sim = [
        traffic_sim
        for traffic_sim in traffic_sims
        if traffic_sim.manages_actor(vehicle_name)
    ]
    assert (
        len(traffic_sim) == 1
    ), "None or multiple, traffic sims contain the vehicle of interest."
    traffic_sim = traffic_sim[0]
    dest_road = traffic_sim.vehicle_dest_road(vehicle_name)
    end_pos = (
        road_map.road_by_id(dest_road)
        .lane_at_index(0)
        .from_lane_coord(RefLinePoint(s=1e10))
    )
    route = traffic_sim.route_for_vehicle(vehicle_name)
    dist_tot = route.road_length
    return end_pos, dist_tot


class Metrics(gym.Wrapper):
    """Metrics class wraps an underlying MetricsBase class. The underlying
    MetricsBase class computes agents' performance metrics in a SMARTS
    environment. Whereas, this Metrics class is a basic gym.Wrapper class
    which prevents external users from accessing or modifying (i) protected
    attributes or (ii) attributes beginning with an underscore, to ensure
    security of the metrics computed.

    Args:
        env (gym.Env): A gym.Env to be wrapped.

    Raises:
        AttributeError: Upon accessing (i) a protected attribute or (ii) an
        attribute beginning with an underscore.

    Returns:
        gym.Env: A wrapped gym.Env which computes agents' performance metrics.
    """

    def __init__(self, env: gym.Env, formula_path: Optional[Path] = None):
        env = MetricsBase(env, formula_path)
        super().__init__(env)

    def __getattr__(self, name: str):
        """Returns an attribute with ``name``, unless ``name`` is a restricted
        attribute or starts with an underscore."""
        if name == "_np_random":
            raise AttributeError(
                "Can't access `_np_random` of a wrapper, use `self.unwrapped._np_random` or `self.np_random`."
            )
        elif name.startswith("_") or name in [
            "smarts",
        ]:
            raise AttributeError(f"accessing private attribute '{name}' is prohibited")

        return getattr(self.env, name)


def _check_env(agent_interfaces: Dict[str, AgentInterface], params: Params):
    """Checks environment suitability to compute performance metrics.
    Args:
        agent_interfaces (Dict[str,AgentInterface]): Agent interfaces.
        params (Params): Metric parameters.

    Raises:
        AttributeError: If any required agent interface is disabled or
            is ill defined.
    """

    def check_intrfc(agent_intrfc: AgentInterface):
        intrfc = {
            "accelerometer": bool(agent_intrfc.accelerometer),
            "max_episode_steps": bool(agent_intrfc.max_episode_steps),
            "neighborhood_vehicle_states": bool(agent_intrfc.neighborhood_vehicles),
            "waypoint_paths": bool(agent_intrfc.waypoints),
            "done_criteria.collision": agent_intrfc.done_criteria.collision,
            "done_criteria.off_road": agent_intrfc.done_criteria.off_road,
        }
        return intrfc

    for agent_name, agent_interface in agent_interfaces.items():
        intrfc = check_intrfc(agent_interface)
        if not all(intrfc.values()):
            raise AttributeError(
                (
                    "Enable {0}'s disabled interface to "
                    "compute its metrics. Current interface is "
                    "{1}."
                ).format(agent_name, intrfc)
            )

        actors_alive = agent_interface.done_criteria.actors_alive
        if (
            params.dist_to_destination.active
            and isinstance(actors_alive, ActorsAliveDoneCriteria)
            and len(actors_alive.actors_of_interest) != 1
        ):
            raise AttributeError(
                (
                    "ActorsAliveDoneCriteria with none or multiple actors of "
                    "interest is currently not supported when "
                    "dist_to_destination cost function is enabled. Current "
                    "interface is {0}:{1}."
                ).format(agent_name, actors_alive)
            )


def _check_scen(scenario: Scenario, agent_interfaces: Dict[str, AgentInterface]):
    """Checks scenario suitability to compute performance metrics.

    Args:
        scen (Scenario): A ``smarts.core.scenario.Scenario`` class.
        agent_interfaces (Dict[str,AgentInterface]): Agent interfaces.

    Raises:
        AttributeError: If any agent's mission is not of type PositionGoal.
    """
    goal_types = {
        agent_name: type(agent_mission.goal)
        for agent_name, agent_mission in scenario.missions.items()
    }

    for agent_name, agent_interface in agent_interfaces.items():
        actors_alive = agent_interface.done_criteria.actors_alive
        if not (
            (goal_types[agent_name] == PositionalGoal and actors_alive == None)
            or (
                goal_types[agent_name] == EndlessGoal
                and isinstance(actors_alive, ActorsAliveDoneCriteria)
            )
        ):
            raise AttributeError(
                "{0} has an unsupported goal type {1} and actors alive done criteria {2} "
                "combination.".format(agent_name, goal_types[agent_name], actors_alive)
            )
