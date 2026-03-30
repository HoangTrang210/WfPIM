from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

real_df = pd.read_csv(OUTPUT_DIR / "Employee_data_10.csv")
syn_df = pd.read_csv(OUTPUT_DIR / "Employee_data_gan_100.csv")

print("real:", real_df.shape)
print("synthetic:", syn_df.shape)
print(syn_df.head(10))
print(syn_df.dtypes)