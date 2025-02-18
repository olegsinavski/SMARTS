# Copyright (C) 2020. Huawei Technologies Co., Ltd. All rights reserved.
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

import logging
import weakref
from concurrent import futures
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from envision.types import format_actor_id
from smarts.core.actor import ActorRole
from smarts.core.agent_interface import AgentInterface
from smarts.core.bubble_manager import BubbleManager
from smarts.core.data_model import SocialAgent
from smarts.core.heterogenous_agent_buffer import HeterogenousAgentBuffer
from smarts.core.observations import Observation
from smarts.core.plan import Mission, Plan, PositionalGoal
from smarts.core.sensor_manager import SensorManager
from smarts.core.sensors import Sensors
from smarts.core.utils.id import SocialAgentId
from smarts.core.vehicle_state import VehicleState
from smarts.zoo.registry import make as make_social_agent


class AgentManager:
    """Tracks agent states and implements methods for managing agent life cycle.

    XXX: It is very likely that this class will see heavy changes in the near future.
         Documentation for specific attributes and methods will be supplied at a later
         time.
    """

    def __init__(self, sim, interfaces, zoo_addrs=None):
        from smarts.core.vehicle_index import VehicleIndex

        self._log = logging.getLogger(self.__class__.__name__)
        self._sim = weakref.ref(sim)
        self._vehicle_index: VehicleIndex = sim.vehicle_index
        self._sensor_manager: SensorManager = sim.sensor_manager
        self._agent_buffer = None
        self._zoo_addrs = zoo_addrs
        self._ego_agent_ids = set()
        self._social_agent_ids = set()

        # Initial interfaces are for agents that are spawned at the beginning of the
        # episode and that we'd re-spawn upon episode reset. This would include ego
        # agents and social agents defined in SStudio. Hijacking agents in bubbles
        # would not be included
        self._initial_interfaces = interfaces
        self._pending_agent_ids = set()
        self._pending_social_agent_ids = set()

        # Agent interfaces are interfaces for _all_ active agents
        self._agent_interfaces = {}

        # TODO: This field is only for social agents, but is being used as if it were
        #       for any agent. Revisit the accessors.
        self._social_agent_data_models: Dict[str, SocialAgent] = {}

        # We send observations and receive actions for all values in this dictionary
        self._remote_social_agents = {}
        self._remote_social_agents_action = {}
        self._social_agent_observation_callbacks = {}
        self._reserved_social_agent_actions = {}

    def teardown(self):
        """Clean up resources."""
        self._log.debug("Tearing down AgentManager")
        self.teardown_ego_agents()
        self.teardown_social_agents()
        self._pending_agent_ids = set()

    def destroy(self):
        """Clean up remaining resources for deletion."""
        if self._agent_buffer:
            self._agent_buffer.destroy()
            self._agent_buffer = None

    @property
    def agent_ids(self) -> Set[str]:
        """A list of all agents in the simulation."""
        return self._ego_agent_ids | self._social_agent_ids

    @property
    def ego_agent_ids(self) -> Set[str]:
        """A list of only the active ego agents in the simulation."""
        return self._ego_agent_ids

    @property
    def social_agent_ids(self) -> Set[str]:
        """A list of only the active social agents in the simulation."""
        return self._social_agent_ids

    @property
    def agent_interfaces(self) -> Dict[str, AgentInterface]:
        """A list of all agent to agent interface mappings."""
        return self._agent_interfaces

    def agent_interface_for_agent_id(self, agent_id) -> AgentInterface:
        """Get the agent interface of a specific agent."""
        return self._agent_interfaces[agent_id]

    @property
    def pending_agent_ids(self) -> Set[str]:
        """The IDs of agents that are waiting to enter the simulation"""
        return self._pending_agent_ids

    @property
    def pending_social_agent_ids(self) -> Set[str]:
        """The IDs of social agents that are waiting to enter the simulation"""
        return self._pending_social_agent_ids

    @property
    def active_agents(self) -> Set[str]:
        """A list of all active agents in the simulation (agents that have a vehicle.)"""
        return self.agent_ids - self.pending_agent_ids

    @property
    def shadowing_agent_ids(self) -> Set[str]:
        """Get all agents that currently observe, but not control, a vehicle."""
        return self._vehicle_index.shadower_ids()

    def is_ego(self, agent_id) -> bool:
        """Test if the agent is an ego agent."""
        return agent_id in self.ego_agent_ids

    def remove_pending_agent_ids(self, agent_ids):
        """Remove an agent from the group of agents waiting to enter the simulation."""
        assert agent_ids.issubset(self.agent_ids)
        self._pending_agent_ids -= agent_ids

    def agent_for_vehicle(self, vehicle_id) -> str:
        """Get the controlling agent for the given vehicle."""
        return self._vehicle_index.owner_id_from_vehicle_id(vehicle_id)

    def agent_has_vehicle(self, agent_id) -> bool:
        """Test if an agent has an actor associated with it."""
        return len(self.vehicles_for_agent(agent_id)) > 0

    def vehicles_for_agent(self, agent_id) -> List[str]:
        """Get the vehicles associated with an agent."""
        return self._vehicle_index.vehicle_ids_by_owner_id(
            agent_id, include_shadowers=True
        )

    def _vehicle_has_agent(self, a_id, v_or_v_id):
        assert (
            a_id
        ), f"Vehicle `{getattr(v_or_v_id, 'id', v_or_v_id)}` does not have an agent registered to it to get observations for."
        return v_or_v_id is not None and a_id is not None

    def observe_from(
        self, vehicle_ids: Set[str], done_this_step: Optional[Set[str]] = None
    ) -> Tuple[
        Dict[str, Observation], Dict[str, float], Dict[str, float], Dict[str, bool]
    ]:
        """Attempt to generate observations from the given vehicles."""
        done_this_step = done_this_step or set()
        sim = self._sim()
        assert sim
        observations = {}
        rewards = {}
        dones = {}
        scores = {}

        sim_frame = sim.cached_frame
        agent_vehicle_pairs = {
            self.agent_for_vehicle(v_id): v_id for v_id in vehicle_ids
        }
        agent_ids = {
            a_id
            for a_id, v_id in agent_vehicle_pairs.items()
            if self._vehicle_has_agent(a_id, v_id)
        }
        observations, dones = sim.sensor_manager.observe(
            sim_frame,
            sim.local_constants,
            agent_ids,
            sim.renderer_ref,
            sim.bc,
        )
        for agent_id in agent_ids:
            v_id = agent_vehicle_pairs[agent_id]
            sensors = sim.sensor_manager.sensors_for_actor_ids([v_id])
            trip_meter_sensor = sensors[v_id]["trip_meter_sensor"]
            rewards[agent_id] = trip_meter_sensor(increment=True)
            scores[agent_id] = trip_meter_sensor()

        # also add agents that were done in virtue of just dropping out
        for done_v_id in done_this_step:
            agent_id = self._vehicle_index.owner_id_from_vehicle_id(done_v_id)
            if agent_id:
                dones[agent_id] = True

        return observations, rewards, scores, dones

    def observe(
        self,
    ) -> Tuple[
        Dict[str, Union[Dict[str, Observation], Observation]],
        Dict[str, Union[Dict[str, float], float]],
        Dict[str, Union[Dict[str, float], float]],
        Dict[str, Union[Dict[str, bool], bool]],
    ]:
        """Generate observations from all vehicles associated with an active agent."""
        sim = self._sim()
        assert sim
        observations = {}
        rewards = {}
        scores = {}
        dones = {
            agent_id: agent_id not in self.pending_agent_ids | self.shadowing_agent_ids
            for agent_id in self.agent_ids
            if not self.agent_has_vehicle(agent_id)
        }

        sim_frame = sim.cached_frame

        active_standard_agents = set()
        active_boid_agents = set()
        for agent_id in self.active_agents:
            if self.is_boid_agent(agent_id):
                active_boid_agents.add(agent_id)
            else:
                active_standard_agents.add(agent_id)

        agent_vehicle_pairs = {
            a_id: (self.vehicles_for_agent(a_id) + [None])[0]
            for a_id in active_standard_agents
        }
        agent_ids = {
            a_id
            for a_id, v in agent_vehicle_pairs.items()
            if self._vehicle_has_agent(a_id, v)
            and self._sensor_manager.sensor_state_exists(v)
        }
        observations, new_dones = sim.sensor_manager.observe(
            sim_frame,
            sim.local_constants,
            agent_ids,
            sim.renderer_ref,
            sim.bc,
        )
        dones.update(new_dones)
        for agent_id in agent_ids:
            v_id = agent_vehicle_pairs[agent_id]
            sensors = sim.sensor_manager.sensors_for_actor_ids([v_id])
            trip_meter_sensor = sensors[v_id]["trip_meter_sensor"]
            rewards[agent_id] = trip_meter_sensor(increment=True)
            scores[agent_id] = trip_meter_sensor()

        ## TODO MTA, support boid agents with parallel observations
        for agent_id in active_boid_agents:
            # An agent may be pointing to its own vehicle or observing a social vehicle
            vehicle_ids = self._vehicle_index.vehicle_ids_by_owner_id(
                agent_id, include_shadowers=True
            )

            vehicles = [
                self._vehicle_index.vehicle_by_id(vehicle_id)
                for vehicle_id in vehicle_ids
            ]
            # returns format of {<agent_id>: {<vehicle_id>: {...}}}
            sensor_states = {
                vehicle.id: self._sensor_manager.sensor_state_for_actor_id(vehicle.id)
                for vehicle in vehicles
            }
            observations[agent_id], dones[agent_id] = sim.sensor_manager.observe_batch(
                sim_frame,
                sim.local_constants,
                agent_id,
                sensor_states,
                {v.id: v for v in vehicles},
                sim.renderer_ref,
                sim.bc,
            )
            # TODO: Observations and rewards should not be generated here.
            rewards[agent_id] = {
                vehicle_id: self._vehicle_reward(vehicle_id)
                for vehicle_id in sensor_states.keys()
            }
            scores[agent_id] = {
                format_actor_id(
                    agent_id, vehicle_id, is_multi=True
                ): self._vehicle_score(vehicle_id)
                for vehicle_id in sensor_states.keys()
            }
        if sim.should_reset:
            for agent_id in dones:
                if self.is_boid_agent(agent_id):
                    for v_id in dones[agent_id]:
                        # pytype: disable=unsupported-operands
                        dones[agent_id][v_id] = True
                        # pytype: enable=unsupported-operands
                else:
                    dones[agent_id] = True
            dones["__sim__"] = True

        return observations, rewards, scores, dones

    def _diagnose_mismatched_observation_vehicles(self, vehicle_ids, agent_id: str):
        try:
            assert len(vehicle_ids) == 1, (
                "Unless this vehicle is part of a boid then we should only have a "
                f"single vehicle under agent_id={agent_id}\n "
                f"(vehicle_ids={vehicle_ids})"
            )
        except AssertionError as error:
            if agent_id.startswith("BUBBLE-AGENT"):
                related_vehicle_ids = [
                    v_id
                    for v_id, _ in self._vehicle_index.vehicleitems()
                    if v_id.endswith(agent_id[-5:])
                ]
                logging.error(
                    "Vehicles of interest for `%s`: `%s`", agent_id, related_vehicle_ids
                )
            raise error

    def _vehicle_reward(self, vehicle_id: str) -> float:
        return self._vehicle_index.vehicle_by_id(vehicle_id).trip_meter_sensor(
            increment=True
        )

    def _vehicle_score(self, vehicle_id: str) -> float:
        return self._vehicle_index.vehicle_by_id(vehicle_id).trip_meter_sensor()

    def _filter_for_active_ego(self, dict_):
        return {
            id_: dict_[id_]
            for id_ in self._ego_agent_ids
            if not id_ in self.pending_agent_ids
        }

    def filter_response_for_ego(
        self,
        response_tuple: Tuple[
            Dict[str, Observation], Dict[str, float], Dict[str, float], Dict[str, bool]
        ],
    ) -> Tuple[
        Dict[str, Observation], Dict[str, float], Dict[str, float], Dict[str, bool]
    ]:
        """Filter all (observations, rewards, dones, infos) down to those related to ego agents."""
        return tuple(map(self._filter_for_active_ego, response_tuple))

    def fetch_agent_actions(self, ego_agent_actions: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve available social agent actions."""
        try:
            social_agent_actions = {
                agent_id: (
                    self._remote_social_agents_action[agent_id].result()
                    if self._remote_social_agents_action.get(agent_id, None)
                    else None
                )
                for agent_id, remote_agent in self._remote_social_agents.items()
            }
        except Exception as e:
            self._log.error(
                "Resolving the remote agent's action (a Future object) generated exception."
            )
            raise e

        agents_without_actions = [
            agent_id
            for (agent_id, action) in social_agent_actions.items()
            if action is None
        ]
        if len(agents_without_actions) > 0:
            self._log.debug(
                f"social_agents=({', '.join(agents_without_actions)}) returned no action"
            )

        social_agent_actions = (
            self._filter_social_agent_actions_for_controlled_vehicles(
                social_agent_actions
            )
        )

        return {**ego_agent_actions, **social_agent_actions}

    def _filter_social_agent_actions_for_controlled_vehicles(
        self, social_agent_actions
    ):
        """Some agents may not be controlling a vehicle, such as when a vehicle is in
        the airlock, where the agent is observing and running its policy, but the
        returned action should not be executed on the vehicle until it is hijacked
        by the agent.
        """
        vehicle_ids_controlled_by_agents = self._vehicle_index.agent_vehicle_ids()
        controlling_agent_ids = set(
            [
                self._vehicle_index.owner_id_from_vehicle_id(v_id)
                for v_id in vehicle_ids_controlled_by_agents
            ]
        )

        social_agent_actions = {
            agent_id: social_agent_actions[agent_id]
            for agent_id in social_agent_actions
            if agent_id in controlling_agent_ids
        }

        # Handle boids where some vehicles are hijacked and some have not yet been
        for agent_id, actions in social_agent_actions.items():
            if self.is_boid_agent(agent_id):
                controlled_vehicle_ids = self._vehicle_index.vehicle_ids_by_owner_id(
                    agent_id, include_shadowers=False
                )
                social_agent_actions[agent_id] = {
                    vehicle_id: vehicle_action
                    for vehicle_id, vehicle_action in actions.items()
                    if vehicle_id in controlled_vehicle_ids
                }

        return social_agent_actions

    def add_social_agent_observations_callback(
        self, callback: Callable[[Any], None], callback_id: str
    ):
        """Suscribe to observe social agents."""
        self._social_agent_observation_callbacks[callback_id] = callback

    def remove_social_agent_observations_callback(self, callback_id: str):
        """Remove a subscription to social agents."""
        del self._social_agent_observation_callbacks[callback_id]

    def reserve_social_agent_action(self, agent_id: str, action: Any):
        """Override a current social agent action."""
        self._reserved_social_agent_actions[agent_id] = action

    def _send_observations_to_social_agents(self, observations: Dict[str, Observation]):
        self._remote_social_agents_action = {}
        for agent_id, action in self._reserved_social_agent_actions.items():
            future_action = futures.Future()
            future_action.set_result(action)
            self._remote_social_agents_action[agent_id] = future_action
        self._reserved_social_agent_actions.clear()
        for callback in self._social_agent_observation_callbacks.values():
            callback(
                dict(
                    filter(
                        lambda k: k[0] in self._remote_social_agents,
                        observations.items(),
                    )
                )
            )
        for agent_id, remote_agent in self._remote_social_agents.items():
            if self._remote_social_agents_action.get(agent_id) is not None:
                continue
            obs = observations[agent_id]
            self._remote_social_agents_action[agent_id] = remote_agent.act(obs)

    def send_observations_to_social_agents(self, observations: Dict[str, Observation]):
        """Forwards observations to managed social agents."""
        # TODO: Don't send observations (or receive actions) from agents that have done
        #       vehicles.
        self._send_observations_to_social_agents(observations)

    def switch_initial_agents(self, agent_interfaces: Dict[str, AgentInterface]):
        """Replaces the initial agent interfaces with a new group. This comes into effect on next reset."""
        self._initial_interfaces = agent_interfaces

    def setup_agents(self):
        """Initializes all agents."""
        self.init_ego_agents()
        self._setup_social_agents()
        self._start_keep_alive_boid_agents()

    def add_ego_agent(
        self, agent_id: str, agent_interface: AgentInterface, for_trap: bool = True
    ):
        """Adds an ego agent to the manager."""
        if for_trap:
            self.pending_agent_ids.add(agent_id)
        self._ego_agent_ids.add(agent_id)
        self.agent_interfaces[agent_id] = agent_interface
        # agent will now be given vehicle by trap manager when appropriate

    def init_ego_agents(self):
        """Initialize all ego agents."""
        for agent_id, agent_interface in self._initial_interfaces.items():
            self.add_ego_agent(agent_id, agent_interface)

    def _setup_agent_buffer(self):
        if not self._agent_buffer:
            self._agent_buffer = HeterogenousAgentBuffer(
                zoo_manager_addrs=self._zoo_addrs
            )

    def _setup_social_agents(self):
        """Initialize all social agents."""
        sim = self._sim()
        assert sim
        social_agents = sim.scenario.social_agents
        self._pending_social_agent_ids.update(social_agents.keys())

    def _start_keep_alive_boid_agents(self):
        """Configures and adds boid agents to the sim."""
        sim = self._sim()
        assert sim
        for bubble in filter(
            lambda b: b.is_boid and b.keep_alive, sim.scenario.bubbles
        ):
            actor = bubble.actor
            agent_id = BubbleManager._make_boid_social_agent_id(actor)

            social_agent = make_social_agent(
                locator=actor.agent_locator,
                **actor.policy_kwargs,
            )

            actor = bubble.actor
            social_agent_data_model = SocialAgent(
                id=SocialAgentId.new(actor.name),
                actor_name=actor.name,
                is_boid=True,
                is_boid_keep_alive=True,
                agent_locator=actor.agent_locator,
                policy_kwargs=actor.policy_kwargs,
                initial_speed=actor.initial_speed,
            )
            self.start_social_agent(agent_id, social_agent, social_agent_data_model)

    def add_and_emit_social_agent(
        self, agent_id: str, agent_spec, agent_model: SocialAgent
    ):
        """Generates an entirely new social agent and emits a vehicle for it immediately.

        Args:
            agent_id (str): The agent id for the new agent.
            agent_spec (AgentSpec): The agent spec of the new agent
            agent_model (SocialAgent): The agent configuration of the new vehicle.
        Returns:
            bool:
                If the agent is added. False if the agent id is already reserved
                by a pending ego agent or current social/ego agent.
        """
        if agent_id in self.agent_ids or agent_id in self.pending_agent_ids:
            return False

        self._setup_agent_buffer()
        remote_agent = self._agent_buffer.acquire_agent()
        self._add_agent(
            agent_id=agent_id,
            agent_interface=agent_spec.interface,
            agent_model=agent_model,
            trainable=False,
            boid=False,
        )
        if agent_id in self._pending_social_agent_ids:
            self._pending_social_agent_ids.remove(agent_id)
        remote_agent.start(agent_spec=agent_spec)
        self._remote_social_agents[agent_id] = remote_agent
        self._agent_interfaces[agent_id] = agent_spec.interface
        self._social_agent_ids.add(agent_id)
        self._social_agent_data_models[agent_id] = agent_model
        return True

    def _add_agent(
        self,
        agent_id,
        agent_interface,
        agent_model: SocialAgent,
        boid=False,
        trainable=True,
    ):
        # TODO: Disentangle what is entangled below into:
        # 1. AgentState initialization,
        # 2. Agent vehicle initialization, which should live elsewhere, and
        # 3. Provider related state initialization, which does not belong here.
        #
        # A couple of things forced the current unhappy state --
        #
        # 1. SMARTS internal coordinate system should be 100% unified. Coordinate
        #    transformation should happen only at the interface between SMARTS and
        #    its providers. For example, mission start pose should just be vehicle
        #    initial pose.
        # 2. AgentState should be allowed to fully initialized (setup) without vehicle
        #    information. We currently rely on the creation of the Vehicle instance to
        #    do the coordinate transformation. :-(
        # 3. Providers should not be creating vehicles. They do need to get notified
        #    about new vehicles entering their territory through the VehicleState
        #    message. But that does not need to happen at Agent instantiation.

        sim = self._sim()
        assert sim
        assert isinstance(agent_id, str)  # SUMO expects strings identifiers

        scenario = sim.scenario
        mission = scenario.mission(agent_id)
        plan = Plan(sim.road_map, mission)

        vehicle = self._vehicle_index.build_agent_vehicle(
            sim,
            agent_id,
            agent_interface,
            plan,
            scenario.vehicle_filepath,
            scenario.tire_parameters_filepath,
            trainable,
            scenario.surface_patches,
            agent_model.initial_speed,
            boid=boid,
            vehicle_id=agent_model.actor_name,
        )

        role = ActorRole.EgoAgent if trainable else ActorRole.SocialAgent
        for provider in sim.providers:
            if agent_interface.action not in provider.actions:
                continue
            state = VehicleState(
                actor_id=vehicle.id,
                actor_type=vehicle.vehicle_type,
                source=provider.source_str,
                role=role,
                vehicle_config_type="passenger",  # XXX: vehicles in history missions will have a type
                pose=vehicle.pose,
                dimensions=vehicle.chassis.dimensions,
            )
            if provider.can_accept_actor(state):
                # Note: this just takes the first one that we come across,
                # so the order in the sim.providers list matters.
                provider.add_actor(state)
                break
        else:
            # We should never get here because there will always be an AgentsProvider in SMARTS
            # willing to accept SocialAgents.
            provider = None
            assert (
                False
            ), f"could not find suitable provider supporting role={role} for action space {agent_interface.action}"

        self._agent_interfaces[agent_id] = agent_interface
        self._social_agent_data_models[agent_id] = agent_model

    def start_social_agent(self, agent_id, social_agent, agent_model):
        """Starts a managed social agent."""
        self._setup_agent_buffer()
        remote_agent = self._agent_buffer.acquire_agent()
        remote_agent.start(social_agent)
        self._remote_social_agents[agent_id] = remote_agent
        self._agent_interfaces[agent_id] = social_agent.interface
        self._social_agent_ids.add(agent_id)
        self._social_agent_data_models[agent_id] = agent_model

    def teardown_ego_agents(self, filter_ids: Optional[Set] = None):
        """Tears down all given ego agents passed through the filter.
        Args:
            filter_ids (Optional[Set[str]]): The whitelist of agent ids. If `None`, all ids are whitelisted.
        """
        ids_ = self._teardown_agents_by_ids(self._ego_agent_ids, filter_ids)
        self._ego_agent_ids -= ids_
        return ids_

    def teardown_social_agents(self, filter_ids: Optional[Set] = None):
        """Tears down all given social agents passed through the filter.
        Args:
            filter_ids (Optional[Set[str]]): The whitelist of agent ids. If `None`, all ids are whitelisted.
        """
        ids_ = self._teardown_agents_by_ids(self._social_agent_ids, filter_ids)

        for id_ in ids_:
            self._remote_social_agents[id_].terminate()
            del self._remote_social_agents[id_]
            del self._social_agent_data_models[id_]

        self._social_agent_ids -= ids_
        return ids_

    def _teardown_agents_by_ids(self, agent_ids, filter_ids: Set):
        ids_ = agent_ids.copy()
        if filter_ids is not None:
            ids_ = ids_ & filter_ids

        if ids_:
            self._log.debug("Tearing down agents=%s", ids_)

        for agent_id in ids_:
            self._agent_interfaces.pop(agent_id, None)

        self._pending_agent_ids = self._pending_agent_ids - ids_
        return ids_

    def reset_agents(self, observations: Dict[str, Observation]):
        """Reset agents, feeding in an initial observation."""
        self._send_observations_to_social_agents(observations)

        # Observations contain those for social agents; filter them out
        return self._filter_for_active_ego(observations)

    def agent_name(self, agent_id: str) -> str:
        """Get the resolved agent name."""
        if agent_id not in self._social_agent_data_models:
            return ""

        return self._social_agent_data_models[agent_id].actor_name

    def is_boid_agent(self, agent_id: str) -> bool:
        """Check if an agent is a boid agent"""
        if agent_id not in self._social_agent_data_models:
            return False

        return self._social_agent_data_models[agent_id].is_boid

    def is_boid_keep_alive_agent(self, agent_id: str) -> bool:
        """Check if this is a persistent boid agent"""
        if agent_id not in self._social_agent_data_models:
            return False

        return self._social_agent_data_models[agent_id].is_boid_keep_alive

    def is_boid_done(self, agent_id: str) -> bool:
        """Check if this boid agent should not disappear yet."""
        if self.is_boid_keep_alive_agent(agent_id):
            return False

        if self.agent_has_vehicle(agent_id):
            return False

        return True
