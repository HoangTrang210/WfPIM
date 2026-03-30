from pathlib import Path
import pandas as pd
from sdv.metadata import Metadata
from sdv.single_table import CTGANSynthesizer

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

SOURCE_CSV = OUTPUT_DIR / "Employee_data_10.csv"
SYN_100_CSV = OUTPUT_DIR / "Employee_data_gan_100.csv"
SYN_1000_CSV = OUTPUT_DIR / "Employee_data_gan_1000.csv"

def main():
    df = pd.read_csv(SOURCE_CSV)

    metadata = Metadata.detect_from_dataframe(data=df)

    synthesizer = CTGANSynthesizer(
        metadata,
        epochs=300
    )

    synthesizer.fit(df)

    syn_100 = synthesizer.sample(num_rows=100)
    syn_1000 = synthesizer.sample(num_rows=1000)

    syn_100.to_csv(SYN_100_CSV, index=False, encoding="utf-8-sig")
    syn_1000.to_csv(SYN_1000_CSV, index=False, encoding="utf-8-sig")

    print("done")
    print("100 rows ->", SYN_100_CSV)
    print("1000 rows ->", SYN_1000_CSV)

if __name__ == "__main__":
    main()