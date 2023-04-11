from pathlib import Path
from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t

dataset_path = "/root/waymo/uncompressed_scenario_training_20s_training_20s.tfrecord-00000-of-01000"
scenario_id = "fe6141aeb4061824"
traffic_histories = [
    t.TrafficHistoryDataset(
        name=f"waymo",
        source_type="Waymo",
        input_path=dataset_path,
        scenario_id=scenario_id,
    )
]
mission = [
    t.Mission(
        route=t.RandomRoute(), entry_tactic=t.IdEntryTactic("history-vehicle-3712")
    )
]
gen_scenario(
    t.Scenario(
        map_spec=t.MapSpec(
            source=f"{dataset_path}#{scenario_id}", lanepoint_spacing=1.0
        ),
        traffic_histories=traffic_histories,
        # ego_missions=mission,
    ),
    output_dir=Path(__file__).parent,
)
