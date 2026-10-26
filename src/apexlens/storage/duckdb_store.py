"""In-process DuckDB views over the Parquet layers (read-only, no database server)."""

from __future__ import annotations

import threading

import duckdb
import pandas as pd

from apexlens.storage.io import partition_files
from apexlens.storage.paths import DataPaths

SILVER_VIEWS = ["laps", "events", "sessions", "drivers", "constructors", "circuits", "race_results", "qualifying_results",
                "pit_stops", "stints", "weather_observations", "telemetry_laps", "session_participants", "starting_grids"]
GOLD_VIEWS = ["lap_features", "driver_session_summary", "driver_event_form", "driver_profiles", "corner_metrics",
              "circuit_profiles", "corner_definitions", "driver_corner_profiles", "tyre_degradation"]


class DuckStore:
    def __init__(self, paths: DataPaths):
        self.paths = paths
        self._local = threading.local()

    def _con(self) -> duckdb.DuckDBPyConnection:
        con = getattr(self._local, "con", None)
        if con is None:
            con = duckdb.connect(database=":memory:")
            for name in SILVER_VIEWS:
                self._register(con, name, self.paths.silver(name))
            for name in GOLD_VIEWS:
                self._register(con, name, self.paths.gold(name))
            self._local.con = con
        return con

    @staticmethod
    def _register(con, name: str, table_dir) -> None:
        if partition_files(table_dir):
            pattern = str(table_dir / "*.parquet").replace("'", "''")
            con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{pattern}', union_by_name=true)")

    def query(self, sql: str, params: list | None = None) -> pd.DataFrame:
        return self._con().execute(sql, params or []).df()

    def has(self, view: str) -> bool:
        try:
            self._con().execute(f"SELECT 1 FROM {view} LIMIT 0")
            return True
        except duckdb.Error:
            return False
