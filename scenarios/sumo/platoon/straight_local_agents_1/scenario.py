from pathlib import Path

from smarts.core.colors import Colors
from smarts.sstudio.genscenario import gen_scenario
from smarts.sstudio.types import (
    EndlessMission,
    MapSpec,
    Trip,
    Traffic,
    Route,
    Scenario,
    ScenarioMetadata
)

traffic = Traffic(
    engine="SUMO",
    flows=[],
    trips=[
        Trip(
            vehicle_name="Leader-007",
            route=Route(
                begin=("E0", 1, 15),
                end=("E0", 0, "max"),
            ),
        ),
    ],
)


ego_missions = [EndlessMission(begin=("E0", 1, 5))]

scenario = Scenario(
    ego_missions=ego_missions,
    map_spec=MapSpec(
        source=Path(__file__).parent.absolute(),
        lanepoint_spacing=1.0,
    ),
    scenario_metadata=ScenarioMetadata("Leader-007",Colors.Blue)
)

gen_scenario(
    scenario=scenario,
    output_dir=Path(__file__).parent,
)
