from pathlib import Path

from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t

# scenario_path is a directory with the following structure:
# /path/to/dataset/{scenario_id}
# ├── log_map_archive_{scenario_id}.json
# └── scenario_{scenario_id}.parquet

scenario_id = "00d45a24-6423-4a68-9878-db5de37b424d"  # e.g. "0000b6ab-e100-4f6b-aee8-b520b57c0530"
scenario_path = (
    Path("/root/argoverse/train/train/") / scenario_id
)  # e.g. Path("/home/user/argoverse/train/") / scenario_id

ego_missions = [
    t.Mission(
        t.Route(
            begin=("road-271753039-271752718", 0, 5),
            end=("road-271714908-271714917-271714954", 0, "max"),
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
        ego_missions=ego_missions,
        map_spec=t.MapSpec(source=f"{scenario_path}", lanepoint_spacing=1.0),
        # traffic_histories=traffic_histories,
    ),
    output_dir=Path(__file__).parent,
)
