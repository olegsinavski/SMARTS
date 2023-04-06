from pathlib import Path

from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t

# scenario_path is a directory with the following structure:
# /path/to/dataset/{scenario_id}
# ├── log_map_archive_{scenario_id}.json
# └── scenario_{scenario_id}.parquet

PATH = "argoverse/data"
scenario_id = "05c20ce7-5c5f-4994-a99e-0fa2f1c0d934"  # e.g. "0000b6ab-e100-4f6b-aee8-b520b57c0530"
scenario_path = Path(__file__).resolve().parents[5] / PATH / scenario_id # e.g. Path("/home/user/argoverse/train/") / scenario_id

ego_mission = [
    t.Mission(
        t.Route(
            begin=("road-394976127", 0, 1.4),
            end=("road-394972059-394971269", 1, 26.1),
        )
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
    ),
    output_dir=Path(__file__).parent,
)
