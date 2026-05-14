import sqlite3
from pathlib import Path

from chinatravel.data.build_sqlite import build_sqlite
from chinatravel.environment.tools.attractions.apis import Attractions
from chinatravel.environment.tools.intercity_transport.apis import IntercityTransport
from chinatravel.environment.tools.poi.apis import Poi


def _count_csv_rows(path: Path) -> int:
    return max(0, len(path.read_text(encoding="utf-8").splitlines()) - 1)


def test_build_sqlite_contains_core_tables(tmp_path):
    db_path = build_sqlite(tmp_path / "chinatravel.sqlite")

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM attractions").fetchone()[0] == sum(
            _count_csv_rows(path)
            for path in Path("chinatravel/environment/database/attractions").glob("*/attractions.csv")
        )
        assert connection.execute("SELECT COUNT(*) FROM restaurants").fetchone()[0] == sum(
            _count_csv_rows(path)
            for path in Path("chinatravel/environment/database/restaurants").glob("*/restaurants_*.csv")
        )
        assert connection.execute("SELECT COUNT(*) FROM accommodations").fetchone()[0] == sum(
            _count_csv_rows(path)
            for path in Path("chinatravel/environment/database/accommodations").glob("*/accommodations.csv")
        )
        assert connection.execute("SELECT COUNT(*) FROM poi").fetchone()[0] > 0
        assert set(
            row[0] for row in connection.execute("SELECT key FROM json_blobs")
        ) == {"airplane", "subways", "train"}


def test_world_env_tools_can_read_sqlite_database():
    attractions = Attractions()
    assert len(attractions.data["北京"]) > 0

    poi = Poi()
    first_city = next(iter(poi.data.keys()))
    first_name = next(iter(poi.data[first_city].keys()))
    assert poi.search(first_city, first_name) == poi.data[first_city][first_name]

    intercity = IntercityTransport()
    first_route = next(iter(intercity.train_df_dict.keys()))
    assert len(intercity.select(first_route[0], first_route[1], "train")) > 0
