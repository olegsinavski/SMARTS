import argparse
import os
import pickle
import glob
import subprocess
from smarts.core.sensors import EgoVehicleObservation
from smarts.dataset import traffic_histories_to_observations
from smarts.sstudio.scenario_construction import build_scenario

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "scenario",
        help="The path to a raw scenario.",
        type=str,
    )
    parser.add_argument(
        "output_dir",
        help="The path to store the scenario.",
        type=str,
    )
    args = parser.parse_args()

    # Create scenario
    scenario_id = args.scenario.split("/")[-1]
    scenario_local_path = "/root/argoverse/train/train/"
    scenario_dir = f"{args.output_dir}/{scenario_id}_agents_1"
    print(scenario_dir)
    os.mkdir(scenario_dir)
    filename = "scenario.py"
    with open(os.path.join(scenario_dir, filename), "w") as f:
        f.write(
            f"""from pathlib import Path

from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t

# scenario_path is a directory with the following structure:
# /path/to/dataset/{{scenario_id}}
# ├── log_map_archive_{{scenario_id}}.json
# └── scenario_{{scenario_id}}.parquet

scenario_id = "{scenario_id}"  # e.g. "0000b6ab-e100-4f6b-aee8-b520b57c0530"
scenario_path = Path("{scenario_local_path}") / scenario_id  # e.g. Path("/home/user/argoverse/train/") / scenario_id

traffic_histories = [
    t.TrafficHistoryDataset(
        name=f"argoverse_{{scenario_id}}",
        source_type="Argoverse",
        input_path=scenario_path,
    )
]

gen_scenario(
    t.Scenario(
        map_spec=t.MapSpec(source=f"{{scenario_path}}", lanepoint_spacing=1.0),
        traffic_histories=traffic_histories,
    ),
    output_dir=Path(__file__).parent,
)
"""
        )
    # Convert traffic history to observations
    build_scenario(scenario=scenario_dir, clean=False, seed=42)
    recorder = traffic_histories_to_observations.ObservationRecorder(
        scenario=scenario_dir,
        output_dir=scenario_dir,
        seed=42,
        start_time=None,
        end_time=None,
    )
    recorder.collect(vehicles_with_sensors=None, headless=True)

    # Load pickle file of observations
    datafile = glob.glob(f"{scenario_dir}/*.pkl")[0]
    with open(datafile, "rb") as pf:
        data = pickle.load(pf)

    # Sort the keys of the dict so we can select the first and last times
    keys = list(data.keys())
    keys.sort()

    # Extract vehicle state from first and last times
    first_time = keys[0]
    last_time = keys[-1]
    first_state: EgoVehicleObservation = data[first_time].ego_vehicle_state
    last_state: EgoVehicleObservation = data[last_time].ego_vehicle_state

    # Overwrite scenario.py with new mission route
    with open(os.path.join(scenario_dir, filename), "w") as f:
        f.write(
            f"""from pathlib import Path

from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t

# scenario_path is a directory with the following structure:
# /path/to/dataset/{{scenario_id}}
# ├── log_map_archive_{{scenario_id}}.json
# └── scenario_{{scenario_id}}.parquet

scenario_id = "{scenario_id}"  # e.g. "0000b6ab-e100-4f6b-aee8-b520b57c0530"
scenario_path = Path("{scenario_local_path}") / scenario_id  # e.g. Path("/home/user/argoverse/train/") / scenario_id

ego_mission = [
    t.Mission(
        t.Route(
            begin=("{first_state.road_id}", {first_state.lane_index}, {round(first_state.lane_position.s, 1)}),
            end=("{last_state.road_id}", {last_state.lane_index}, {round(last_state.lane_position.s, 1)}),
        )
    )
]

traffic_histories = [
    t.TrafficHistoryDataset(
        name=f"argoverse_{{scenario_id}}",
        source_type="Argoverse",
        input_path=scenario_path,
    )
]

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

subprocess.run(["scl", "run", "--envision", "examples/egoless.py", f"{scenario_dir}"])
