import argparse
from pathlib import Path
import pickle
import glob
import shutil
import subprocess
from smarts.core.sensors import EgoVehicleObservation
from smarts.dataset import traffic_histories_to_observations
from smarts.sstudio.scenario_construction import build_scenario


def copy_data_to_smarts_dir(data_local_path):
    smarts_dir = "argoverse/data"
    scenario_id = data_local_path.split("/")[-2]
    scenario_path = Path(__file__).resolve().parents[0] / smarts_dir / scenario_id
    shutil.copytree(data_local_path, scenario_path, dirs_exist_ok=True)
    return scenario_id, smarts_dir


def write_scenario_py(scenario_dir, scenario_id):
    filepath = Path(f"{scenario_dir}/scenario.py")
    with filepath.open("w", encoding="utf-8") as f:
        f.write(
            f"""from pathlib import Path

from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t

# scenario_path is a directory with the following structure:
# /path/to/dataset/{{scenario_id}}
# ├── log_map_archive_{{scenario_id}}.json
# └── scenario_{{scenario_id}}.parquet

PATH = "argoverse/data"
scenario_id = "{scenario_id}"  # e.g. "0000b6ab-e100-4f6b-aee8-b520b57c0530"
scenario_path = Path(__file__).resolve().parents[5] / PATH / scenario_id # e.g. Path("/home/user/argoverse/train/") / scenario_id

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


def generate_pkl(scenario_dir, vehicle_id):
    # Convert traffic history to observations
    build_scenario(scenario=scenario_dir, clean=False, seed=42)
    recorder = traffic_histories_to_observations.ObservationRecorder(
        scenario=scenario_dir,
        output_dir=scenario_dir,
        seed=42,
        start_time=None,
        end_time=None,
    )
    recorder.collect(vehicles_with_sensors=vehicle_id, headless=True)


def generate_route(scenario_dir):
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
    return first_state, last_state


def write_mission_to_scenario(scenario_dir, scenario_id, first_state, last_state):
    filepath = Path(f"{scenario_dir}/scenario.py")
    with filepath.open("w", encoding="utf-8") as f:
        f.write(
            f"""from pathlib import Path

from smarts.sstudio import gen_scenario
from smarts.sstudio import types as t

# scenario_path is a directory with the following structure:
# /path/to/dataset/{{scenario_id}}
# ├── log_map_archive_{{scenario_id}}.json
# └── scenario_{{scenario_id}}.parquet

PATH = "argoverse/data"
scenario_id = "{scenario_id}"  # e.g. "0000b6ab-e100-4f6b-aee8-b520b57c0530"
scenario_path = Path(__file__).resolve().parents[5] / PATH / scenario_id # e.g. Path("/home/user/argoverse/train/") / scenario_id

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


def main(data_local_path, output_dir, vehicle_id):
    scenario_id = data_local_path.split("/")[-2]
    scenario_dir = (
        Path(output_dir.rstrip(args.output_dir[-1])) / f"{scenario_id}_agents_1"
    )
    scenario_dir.mkdir(exist_ok=True)
    copy_data_to_smarts_dir(data_local_path)
    write_scenario_py(scenario_dir, scenario_id)
    generate_pkl(scenario_dir, vehicle_id)
    first_state, last_state = generate_route(scenario_dir)
    write_mission_to_scenario(scenario_dir, scenario_id, first_state, last_state)
    subprocess.run(
        [
            "scl",
            "run",
            "--envision",
            "examples/control/laner.py",
            f"{scenario_dir}",
        ]
    )


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
    parser.add_argument(
        "vehicle_id", help="The id of vehicle of interest", type=int, nargs="*"
    )
    args = parser.parse_args()

    main(
        data_local_path=args.scenario,
        output_dir=args.output_dir,
        vehicle_id=args.vehicle_id,
    )
