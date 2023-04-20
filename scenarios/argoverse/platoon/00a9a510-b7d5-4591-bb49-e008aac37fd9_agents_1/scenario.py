from itertools import product
from pathlib import Path
from smarts.core.colors import Colors
from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t
from smarts.sstudio.types import EndlessMission, ScenarioMetadata

PATH = "argoverse/data"
scenario_id = "00a9a510-b7d5-4591-bb49-e008aac37fd9"
scenario_path = Path(__file__).resolve().parents[4] / PATH / scenario_id

ego_mission = [EndlessMission(begin=("road-218234520-218234522", 1, 7.5), start_time=3)]

traffic_histories = [
    t.TrafficHistoryDataset(
        name=f"argoverse_{scenario_id}",
        source_type="Argoverse",
        input_path=scenario_path,
    )
]

gen_scenario(
    t.Scenario(
        ego_missions=ego_mission,
        map_spec=t.MapSpec(source=f"{scenario_path}", lanepoint_spacing=1.0),
        traffic_histories=traffic_histories,
        # scenario_metadata=ScenarioMetadata("777777", Colors.Blue),
    ),
    output_dir=Path(__file__).parent,
)
