from itertools import product
from pathlib import Path
from smarts.core.colors import Colors
from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t
from smarts.sstudio.types import EndlessMission, ScenarioMetadata

PATH = "argoverse/data"
scenario_id = "00ebc61b-b442-4bec-91f6-46fb9adb0282"
scenario_path = Path(__file__).resolve().parents[4] / PATH / scenario_id

ego_mission = [
    EndlessMission(
        begin=("road-173644931-173645301-173645305-173645094", 1, 24.8), start_time=1.2
    )
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
        scenario_metadata=ScenarioMetadata("16249", Colors.Blue),
    ),
    output_dir=Path(__file__).parent,
)
