import argparse
import os
import pickle

from smarts.core.sensors import EgoVehicleObservation

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "obs_file",
        help="The path to a pkl file of observations.",
        type=str,
    )
    args = parser.parse_args()

    # Load pickle file of observations
    datafile = os.path.abspath(args.obs_file)
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

    # Print start and end arguments for mission route
    print(
        f'begin=("{first_state.road_id}", {first_state.lane_index}, {round(first_state.lane_position.s, 1)})'
    )
    print(
        f'end=("{last_state.road_id}", {last_state.lane_index}, {round(last_state.lane_position.s, 1)})'
    )
