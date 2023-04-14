import random
import sys
from pathlib import Path

import gym

sys.path.insert(0, str(Path(__file__).parents[2].absolute()))
from examples.tools.argument_parser import default_argument_parser
from smarts.core.agent import Agent
from smarts.core.agent_interface import AgentInterface, AgentType, DoneCriteria
from smarts.core.utils.episodes import episodes
from smarts.sstudio.scenario_construction import build_scenarios
from smarts.zoo.agent_spec import AgentSpec

N_AGENTS = 1
AGENT_IDS = ["Agent %i" % i for i in range(N_AGENTS)]


class KeepLaneAgent(Agent):
    def act(self, obs):
        val = ["keep_lane", "slow_down", "change_lane_left", "change_lane_right"]
        return random.choice(val)


def main(scenarios, headless, num_episodes, max_episode_steps):
    agent_specs = {
        agent_id: AgentSpec(
            interface=AgentInterface.from_type(
                AgentType.Laner,
                max_episode_steps=max_episode_steps,
                done_criteria=DoneCriteria(collision=False),
            ),
            agent_builder=KeepLaneAgent,
        )
        for agent_id in AGENT_IDS
    }

    env = gym.make(
        "smarts.env:hiway-v0",
        scenarios=scenarios,
        agent_interfaces={
            a_id: a_intrf.interface for a_id, a_intrf in agent_specs.items()
        },
        headless=headless,
        sumo_headless=True,
    )

    for episode in episodes(n=num_episodes):
        agents = {
            agent_id: agent_spec.build_agent()
            for agent_id, agent_spec in agent_specs.items()
        }
        observations = env.reset()
        episode.record_scenario(env.scenario_log)

        dones = {"__all__": False}
        while not dones["__all__"]:
            actions = {
                agent_id: agents[agent_id].act(agent_obs)
                for agent_id, agent_obs in observations.items()
            }
            neighbor_state = observations["Agent 0"].neighborhood_vehicle_states
            for i in neighbor_state:
                if i.id == "Leader-007":
                    leader_state = [i]
            if leader_state == None or leader_state == []:
                raise Exception("Leader missing")
            if leader_state:
                leader_initial_offset = leader_state[0].lane_position.s
                ego_initial_offset = observations[
                    "Agent 0"
                ].ego_vehicle_state.lane_position.s
                initial_distance = leader_initial_offset - ego_initial_offset
                if (4 <= initial_distance <= 18) == False:
                    print(initial_distance)
                    raise Exception("Initial distance is not proper")
                if leader_initial_offset < ego_initial_offset:
                    raise Exception("ego appears in front of leader")
            observations, rewards, dones, infos = env.step(actions)
            episode.record_step(observations, rewards, dones, infos)

    env.close()


if __name__ == "__main__":
    parser = default_argument_parser("laner")
    args = parser.parse_args()

    if not args.scenarios:
        args.scenarios = [
            str(Path(__file__).absolute().parents[2] / "scenarios" / "sumo" / "loop"),
            str(
                Path(__file__).absolute().parents[2]
                / "scenarios"
                / "sumo"
                / "figure_eight"
            ),
        ]

    build_scenarios(scenarios=args.scenarios)

    main(
        scenarios=args.scenarios,
        headless=args.headless,
        num_episodes=50,
        max_episode_steps=1,
    )
