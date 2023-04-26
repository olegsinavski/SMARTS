import sys
from pathlib import Path

import gym
import time
import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1].absolute()))
from examples.tools.argument_parser import default_argument_parser
from smarts.core.agent import Agent
from smarts.core.agent_interface import AgentInterface, AgentType
from smarts.core.observations import Observation
from smarts.core.utils.episodes import episodes
from smarts.sstudio.scenario_construction import build_scenarios
from smarts.zoo.agent_spec import AgentSpec


def measure_fps(n_agent):
    scenarios = [
        str(Path(__file__).absolute().parents[1] / "scenarios" / "sumo" / "minicity")
    ]

    agent_ids = ["Agent_%i" % i for i in range(n_agent)]

    agent_specs = {
        agent_id: AgentSpec(
            interface=AgentInterface.from_type(
                AgentType.LanerWithSpeed,
                max_episode_steps=None,
            ),
            agent_builder=Agent,
        )
        for agent_id in agent_ids
    }

    env = gym.make(
        "smarts.env:hiway-v0",
        scenarios=scenarios,
        agent_specs=agent_specs,
        headless=True,
        sumo_headless=True,
    )
    print("Resetting..")
    observations = env.reset()
    action = (0., 0, 0)
    timestamps = []
    num_agents = []
    for i in range(100):
        actions = {
            agent_id: action
            for agent_id, agent_obs in observations.items()
        }
        observations, rewards, dones, infos = env.step(actions)
        num_agents.append(len(observations.keys()))
        timestamps.append(time.time())

    dt = np.median(np.diff(timestamps))
    mean_agents_count = np.mean(num_agents)
    print("FPS:", 1. / dt, " Alive agents:", mean_agents_count)

    env.close()


if __name__ == "__main__":
    parser = default_argument_parser("chase-via-points")
    parser.add_argument(
        "n_agent",
        help="Number of agents",
        type=int,
    )
    args = parser.parse_args()


    measure_fps(
        n_agent=args.n_agent
    )
