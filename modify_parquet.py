import pandas as pd

path = "argoverse/data/0202affc-cf2b-451e-a170-3ededd46e88f/scenario_0202affc-cf2b-451e-a170-3ededd46e88f.parquet"
df = pd.read_parquet(path)

# df = df[df["track_id"] != "193416"]
# df = df[df["track_id"] != "193381"]
# df = df[df["track_id"] != "193425"]
df.loc[df["track_id"] == "59981", "track_id"] = "777777"
df = df.reset_index(drop=True)
df.to_parquet(path)
