import argparse
import subprocess
import pickle
from smarts.core.sensors import EgoVehicleObservation
from smarts.dataset import traffic_histories_to_observations
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument(
    "scenario_path",
    help="The path to a raw scenario.",
    type=str,
)
args = parser.parse_args()

data_path = args.scenario_path
scenario_id = data_path.split("/")[-2]

# Copy data to smarts directory
subprocess.check_output(
    f"cp -R {data_path} /root/driving-smarts-2.competition-scenarios/dataset/",
    shell=True,
)
# Create scenario file
scenario_path = (
    f"/root/driving-smarts-2.competition-scenarios/t2/temp/{scenario_id}_agents_1"
)
subprocess.check_output(f"mkdir -p {scenario_path}", shell=True)

filepath = Path(scenario_path) / "scenario.py"
with filepath.open("w", encoding="utf-8") as f:
    f.write(
        f"""from pathlib import Path

from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t

# scenario_path is a directory with the following structure:
# /path/to/dataset/{{scenario_id}}
# ├── log_map_archive_{{scenario_id}}.json
# └── scenario_{{scenario_id}}.parquet

PATH = "dataset"
scenario_id = "{scenario_id}"  # e.g. "0000b6ab-e100-4f6b-aee8-b520b57c0530"
scenario_path = Path(__file__).resolve().parents[3] / PATH / scenario_id # e.g. Path("/home/user/argoverse/train/") / scenario_id

traffic_histories = [
t.TrafficHistoryDataset(
    name=f"argoverse_{{scenario_id}}",
    source_type="Argoverse",
    input_path=scenario_path,
)
]
# ego_mission = [t.EndlessMission()]

gen_scenario(
t.Scenario(
    # ego_missions=ego_mission,
    map_spec=t.MapSpec(source=f"{{scenario_path}}", lanepoint_spacing=1.0),
    traffic_histories=traffic_histories,
),
output_dir=Path(__file__).parent,
)
"""
    )

process = subprocess.run(
    ["scl", "run", "--envision", "examples/egoless.py", scenario_path]
)
while True:
    try:
        vehicle_id = input("Enter the vehicle id of interest: ")
        recorder = traffic_histories_to_observations.ObservationRecorder(
            scenario=scenario_path,
            output_dir=scenario_path,
            seed=42,
            start_time=None,
            end_time=None,
        )
        recorder.collect(vehicles_with_sensors=[int(vehicle_id)], headless=True)

        # Load pickle file of observations
        with open(
            f"{scenario_path}/Agent-history-vehicle-{vehicle_id}.pkl", "rb"
        ) as pf:
            data = pickle.load(pf)
        break
    except FileNotFoundError:
        print("Vehicle id not found. Try again.")

# Sort the keys of the dict so we can select the first and last times
keys = list(data.keys())
keys.sort()

# Extract vehicle state from first and last times
first_time = keys[0]
last_time = keys[-1]
first_state: EgoVehicleObservation = data[first_time].ego_vehicle_state
last_state: EgoVehicleObservation = data[last_time].ego_vehicle_state

# Print start and end arguments for mission route
print(
    f'begin=("{first_state.road_id}", {first_state.lane_index}, {round(first_state.lane_position.s, 1)})'
)
print(
    f'end=("{last_state.road_id}", {last_state.lane_index}, {round(last_state.lane_position.s, 1)})'
)
save_to = input("Which folder this scenario should be saved to?")
subprocess.run(
    [
        "rsync",
        "-a",
        scenario_path,
        f"/root/driving-smarts-2.competition-scenarios/t2/test/{save_to}",
    ]
)
subprocess.run(
    "rm -rf /root/driving-smarts-2.competition-scenarios/t2/temp/*", shell=True
)
scenario_path = f"/root/driving-smarts-2.competition-scenarios/t2/test/{save_to}/{scenario_id}_agents_1"
filepath = Path(scenario_path) / "scenario.py"
# write in the mission route
with filepath.open("w", encoding="utf-8") as f:
    f.write(
        f"""from pathlib import Path

from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t

# scenario_path is a directory with the following structure:
# /path/to/dataset/{{scenario_id}}
# ├── log_map_archive_{{scenario_id}}.json
# └── scenario_{{scenario_id}}.parquet

PATH = "dataset"
scenario_id = "{scenario_id}"  # e.g. "0000b6ab-e100-4f6b-aee8-b520b57c0530"
scenario_path = Path(__file__).resolve().parents[4] / PATH / scenario_id # e.g. Path("/home/user/argoverse/train/") / scenario_id

traffic_histories = [
t.TrafficHistoryDataset(
    name=f"argoverse_{{scenario_id}}",
    source_type="Argoverse",
    input_path=scenario_path,
)
]
ego_mission = [t.Mission(route=t.Route(begin=("{first_state.road_id}", {first_state.lane_index}, {round(first_state.lane_position.s, 1)}), end=("{last_state.road_id}", {last_state.lane_index}, {round(last_state.lane_position.s, 1)})))]

gen_scenario(
t.Scenario(
    ego_missions=ego_mission,
    map_spec=t.MapSpec(source=f"{{scenario_path}}", lanepoint_spacing=1.0),
    traffic_histories=traffic_histories,
),
output_dir=Path(__file__).parent,
)
"""
    )
subprocess.run(["black", filepath])
subprocess.run(["code", f"{scenario_path}/scenario.py"])
while True:
    subprocess.run(
        [
            "scl",
            "run",
            "--envision",
            "examples/control/chase_via_points.py",
            scenario_path,
        ]
    )
    vis = input("Does it look good? Press any key to continue, otherwise press 'n': ")
    if vis != "n":
        break
    else:
        print("replay the scenario")
