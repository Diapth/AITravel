from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_ROOT = PROJECT_ROOT / "chinatravel" / "environment" / "database"
DEFAULT_OUTPUT = DATABASE_ROOT / "chinatravel.sqlite"


def _write_csv_table(connection: sqlite3.Connection, table: str, category: str, pattern: str) -> None:
    frames = []
    for path in sorted((DATABASE_ROOT / category).glob(pattern)):
        frame = pd.read_csv(path)
        frame.insert(0, "city", path.parent.name)
        frames.append(frame)
    if not frames:
        raise FileNotFoundError(f"No source files found for {category}/{pattern}")
    pd.concat(frames, ignore_index=True).to_sql(table, connection, if_exists="replace", index=False)


def _write_poi(connection: sqlite3.Connection) -> None:
    rows = []
    for path in sorted((DATABASE_ROOT / "poi").glob("*/poi.json")):
        city = path.parent.name
        for item in json.loads(path.read_text(encoding="utf-8")):
            position = item.get("position") or []
            rows.append(
                {
                    "city": city,
                    "name": item.get("name"),
                    "lat": position[0] if len(position) > 0 else None,
                    "lon": position[1] if len(position) > 1 else None,
                }
            )
    pd.DataFrame(rows).to_sql("poi", connection, if_exists="replace", index=False)


def _write_json_blob(connection: sqlite3.Connection, key: str, value: object) -> None:
    connection.execute(
        "INSERT INTO json_blobs(key, value) VALUES (?, ?)",
        (key, json.dumps(value, ensure_ascii=False)),
    )


def build_sqlite(output_path: Path = DEFAULT_OUTPUT) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    with sqlite3.connect(output_path) as connection:
        _write_csv_table(connection, "attractions", "attractions", "*/attractions.csv")
        _write_csv_table(connection, "restaurants", "restaurants", "*/restaurants_*.csv")
        _write_csv_table(connection, "accommodations", "accommodations", "*/accommodations.csv")
        _write_poi(connection)

        connection.execute("CREATE TABLE json_blobs(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        _write_json_blob(
            connection,
            "subways",
            json.loads((DATABASE_ROOT / "transportation" / "subways.json").read_text(encoding="utf-8")),
        )
        _write_json_blob(
            connection,
            "airplane",
            [
                json.loads(line)
                for line in (DATABASE_ROOT / "intercity_transport" / "airplane.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ],
        )
        train_data = {
            path.stem: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((DATABASE_ROOT / "intercity_transport" / "train").glob("*.json"))
        }
        _write_json_blob(connection, "train", train_data)

        for table in ("attractions", "restaurants", "accommodations", "poi"):
            connection.execute(f"CREATE INDEX idx_{table}_city ON {table}(city)")
        connection.execute("CREATE INDEX idx_poi_city_name ON poi(city, name)")

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the ChinaTravel SQLite runtime database.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    path = build_sqlite(args.output)
    print(path)


if __name__ == "__main__":
    main()
