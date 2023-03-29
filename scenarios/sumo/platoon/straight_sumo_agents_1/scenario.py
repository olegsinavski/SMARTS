from pathlib import Path

from smarts.core.colors import Colors
from smarts.sstudio.genscenario import gen_scenario
from smarts.sstudio.types import (
    MapSpec,
    Route,
    Scenario,
    TrafficActor,
    Traffic,
    Trip,
    Distribution,
    EndlessMission,
    ScenarioMetadata,
)

ego_missions = [EndlessMission(begin=("E0", 1, 5))]

traffic_actor = TrafficActor(
    name="leader",
    speed=Distribution(sigma=0.5, mean=1),
)
traffic = Traffic(
    engine="SUMO",
    flows=[],
    trips=[
        Trip(
            vehicle_name="Leader-007",
            route=Route(
                begin=("E0", 1, 20),
                end=("E0", 0, "max"),
            ),
        ),
    ],
)

scenario = Scenario(
    ego_missions=ego_missions,
    traffic={"basic": traffic},
    map_spec=MapSpec(
        source=Path(__file__).parent.absolute(),
        lanepoint_spacing=1.0,
    ),
    scenario_metadata=ScenarioMetadata("Leader-007", Colors.Blue),
)

gen_scenario(
    scenario=scenario,
    output_dir=Path(__file__).parent,
)
