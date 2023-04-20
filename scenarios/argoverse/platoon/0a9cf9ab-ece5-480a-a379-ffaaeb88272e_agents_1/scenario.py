from pathlib import Path

from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t
from smarts.core.colors import Colors

# scenario_path is a directory with the following structure:
# /path/to/dataset/{scenario_id}
# ├── log_map_archive_{scenario_id}.json
# └── scenario_{scenario_id}.parquet

PATH = "argoverse/data"
scenario_id = "0a9cf9ab-ece5-480a-a379-ffaaeb88272e"  # e.g. "0000b6ab-e100-4f6b-aee8-b520b57c0530"
scenario_path = (
    Path(__file__).resolve().parents[4] / PATH / scenario_id
)  # e.g. Path("/home/user/argoverse/train/") / scenario_id

traffic_histories = [
    t.TrafficHistoryDataset(
        name=f"argoverse_{scenario_id}",
        source_type="Argoverse",
        input_path=scenario_path,
    )
]
ego_mission = [t.EndlessMission(begin=("road-431065676-431065556", 1, 50.2))]
# ego_id = 58626

gen_scenario(
    t.Scenario(
        ego_missions=ego_mission,
        map_spec=t.MapSpec(source=f"{scenario_path}", lanepoint_spacing=1.0),
        traffic_histories=traffic_histories,
        scenario_metadata=t.ScenarioMetadata("16249", Colors.Blue),
    ),
    output_dir=Path(__file__).parent,
)
