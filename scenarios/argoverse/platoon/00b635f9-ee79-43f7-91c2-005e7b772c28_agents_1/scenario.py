from itertools import product
from pathlib import Path
from smarts.core.colors import Colors
from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t
from smarts.sstudio.types import EndlessMission, ScenarioMetadata

PATH = "argoverse/data"
scenario_id = "00b635f9-ee79-43f7-91c2-005e7b772c28"
scenario_path = Path(__file__).resolve().parents[4] / PATH / scenario_id

ego_mission = [
    EndlessMission(begin=("road-331939615-331939827", 0, 35.5), start_time=1),
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
