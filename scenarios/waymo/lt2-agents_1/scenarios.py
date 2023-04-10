from pathlib import Path
from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t

dataset_path = "/root/SMARTS/scenarios/waymo/lt2-agents_1/uncompressed_scenario_training_20s_training_20s.tfrecord-00002-of-01000"
scenario_id = "f2e494dc22c12ecd"
traffic_histories = [
    t.TrafficHistoryDataset(
        name=f"waymo",
        source_type="Waymo",
        input_path=dataset_path,
        scenario_id=scenario_id,
    )
]

route = t.Route(
    begin=("waymo_road-324_125-337_40-329_2", 2, 41.1), end=("waymo_road-170", 0, 4.7)
)

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
