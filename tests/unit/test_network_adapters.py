"""Jolpica, OpenF1 and FastF1 adapters exercised against mocked providers (no network)."""

import json

import httpx
import pandas as pd
import pytest

from apexlens.data_sources.fastf1_source import FastF1Source
from apexlens.data_sources.http import HttpClient
from apexlens.data_sources.jolpica import JolpicaSource
from apexlens.data_sources.openf1 import OpenF1Source


def client(tmp_path, handler):
    return HttpClient(cache_dir=tmp_path, transport=httpx.MockTransport(handler), sleep=lambda s: None)


def test_jolpica_pagination(tmp_path):
    races = [{"season": "2024", "round": str(i), "raceName": f"R{i}", "Circuit": {"circuitId": f"c{i}"}, "date": "2024-03-02"}
             for i in range(1, 151)]
    seen = []

    def handler(request):
        offset = int(request.url.params["offset"])
        limit = int(request.url.params["limit"])
        seen.append(offset)
        body = {"MRData": {"limit": str(limit), "offset": str(offset), "total": "150",
                           "RaceTable": {"Races": races[offset: offset + limit]}}}
        return httpx.Response(200, json=body)

    src = JolpicaSource(client(tmp_path, handler), "https://api.example/ergast/f1")
    df = src.races(2024)
    assert len(df) == 150 and seen == [0, 100]
    assert df["round"].max() == 150


def test_jolpica_results_normalisation(tmp_path):
    body = {"MRData": {"limit": "100", "offset": "0", "total": "1", "RaceTable": {"Races": [{
        "season": "2024", "round": "1", "Results": [{
            "number": "1", "position": "1", "positionText": "1", "points": "26", "grid": "1", "laps": "57",
            "status": "Finished", "Driver": {"driverId": "max_verstappen", "code": "VER", "familyName": "Verstappen",
                                             "dateOfBirth": "1997-09-30"},
            "Constructor": {"constructorId": "red_bull"}}]}]}}}
    src = JolpicaSource(client(tmp_path, lambda r: httpx.Response(200, json=body)), "https://api.example/ergast/f1")
    df = src.results(2024, 1)
    assert df.iloc[0].driver_code == "VER" and df.iloc[0].points == 26.0 and df.iloc[0].grid == 1


def test_openf1_query_and_errors(tmp_path):
    def handler(request):
        if request.url.path.endswith("/overtakes"):
            assert request.url.params["session_key"] == "9999"
            return httpx.Response(200, json=[{"overtaking_driver_number": 1, "overtaken_driver_number": 16, "position": 1}])
        return httpx.Response(200, json={"detail": "error"})

    src = OpenF1Source(client(tmp_path, handler), "https://api.example/v1")
    df = src.overtakes(9999)
    assert df.iloc[0].overtaking_driver_number == 1
    with pytest.raises(RuntimeError):
        src.stints(1)
    with pytest.raises(ValueError):
        src.get("not_an_endpoint")


class _FakeLaps(pd.DataFrame):
    def get_weather_data(self):
        return pd.DataFrame({"Time": pd.to_timedelta([10, 20], unit="s"), "AirTemp": [20.0, 21.0],
                             "TrackTemp": [30.0, 31.0], "Humidity": [40.0, 41.0], "Pressure": [1010.0, 1010.0],
                             "Rainfall": [False, False], "WindDirection": [10, 20], "WindSpeed": [1.0, 1.1]})


class _FakeSession:
    def __init__(self):
        self.laps = _FakeLaps({
            "Driver": ["VER", "VER"], "DriverNumber": ["1", "1"], "LapNumber": [1.0, 2.0],
            "LapTime": pd.to_timedelta([97.3, 96.3], unit="s"), "Time": pd.to_timedelta([3697.5, 3793.8], unit="s"),
            "Compound": ["SOFT", "SOFT"], "TyreLife": [4.0, 5.0], "TrackStatus": ["12", "1"], "IsAccurate": [False, True],
        })
        self.weather_data = pd.DataFrame({"Time": pd.to_timedelta([0, 60], unit="s"), "AirTemp": [20.0, 20.5]})
        self.race_control_messages = pd.DataFrame({"Message": ["GREEN LIGHT"]})
        self.results = pd.DataFrame({"Abbreviation": ["VER"], "DriverNumber": ["1"], "TeamName": ["Red Bull Racing"]})
        self.event = {"EventName": "Bahrain Grand Prix"}

    def load(self, **kwargs):
        self.loaded = kwargs

    def get_circuit_info(self):
        class CI:
            corners = pd.DataFrame({"X": [1.0], "Y": [2.0], "Number": [1], "Letter": [""], "Angle": [10.0], "Distance": [700.0]})
            rotation = 92.0
        return CI()


class _FakeFastF1:
    def get_session(self, year, event, identifier):
        assert identifier == "Race"
        return _FakeSession()


def test_fastf1_adapter_converts_to_seconds(tmp_path):
    payload = FastF1Source(tmp_path, fastf1_module=_FakeFastF1()).load_session(2024, "Bahrain", "R")
    assert payload.laps["LapTime"].tolist() == pytest.approx([97.3, 96.3])
    assert payload.laps["AirTemp"].tolist() == [20.0, 21.0]
    assert payload.weather["Time"].tolist() == [0.0, 60.0]
    assert payload.rotation == 92.0 and payload.meta["event_name"] == "Bahrain Grand Prix"
    assert payload.drivers[0]["driver"] == "VER"
    json.dumps(payload.drivers)
