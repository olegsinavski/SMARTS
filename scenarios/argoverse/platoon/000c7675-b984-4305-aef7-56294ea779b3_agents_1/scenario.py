from itertools import product
from pathlib import Path
from smarts.core.colors import Colors
from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t
from smarts.sstudio.types import EndlessMission, ScenarioMetadata

PATH = "argoverse/data"
scenario_id = "000c7675-b984-4305-aef7-56294ea779b3"
scenario_path = Path(__file__).resolve().parents[4] / PATH / scenario_id

ego_mission = [
    EndlessMission(begin=("road-244397938-244398046", 1, 18.0), start_time=1)
]

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
