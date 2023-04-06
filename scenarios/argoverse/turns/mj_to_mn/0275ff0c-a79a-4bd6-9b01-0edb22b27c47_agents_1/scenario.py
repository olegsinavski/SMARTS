from pathlib import Path

from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t

# scenario_path is a directory with the following structure:
# /path/to/dataset/{scenario_id}
# ├── log_map_archive_{scenario_id}.json
# └── scenario_{scenario_id}.parquet

scenario_id = "0275ff0c-a79a-4bd6-9b01-0edb22b27c47"  # e.g. "0000b6ab-e100-4f6b-aee8-b520b57c0530"
scenario_path = (
    Path("/home/kyber/argoverse/") / scenario_id
)  # e.g. Path("/home/user/argoverse/train/") / scenario_id

ego_mission = [
    t.Mission(
        t.Route(
            begin=("road-216105989-216105899-216105960", 0, 21.9),
            end=("road-216105858", 0, 25),
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
