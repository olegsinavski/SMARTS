from pathlib import Path
from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t

dataset_path = "/root/waymo/uncompressed_scenario_training_20s_training_20s.tfrecord-00002-of-01000"
scenario_id = "22a0f7b761362cc0"
traffic_histories = [
    t.TrafficHistoryDataset(
        name=f"waymo",
        source_type="Waymo",
        input_path=dataset_path,
        scenario_id=scenario_id,
    )
]

route = t.Route(begin=("waymo_road-133", 0, 89.4), end=("waymo_road-201", 0, 3.0))

ego_mission = [t.Mission(route=route)]

gen_scenario(
    t.Scenario(
        map_spec=t.MapSpec(
            source=f"{dataset_path}#{scenario_id}", lanepoint_spacing=1.0
        ),
        traffic_histories=traffic_histories,
        ego_missions=ego_mission,
    ),
    output_dir=Path(__file__).parent,
)
