from unittest.mock import MagicMock, create_autospec

import pandas as pd
import pytest

from connectors.fred_client import FredClient
from connectors.real_yield_fetcher import RealYieldFetcher


@pytest.fixture
def mock_client() -> MagicMock:
    return create_autospec(FredClient, instance=True)


@pytest.fixture
def fetcher(mock_client: MagicMock) -> RealYieldFetcher:
    return RealYieldFetcher(fred_client=mock_client)


def test_fetch_returns_series(fetcher: RealYieldFetcher, mock_client: MagicMock) -> None:
    dates = pd.date_range("2020-01-01", "2025-01-01", freq="B")
    values = [1.5 + i * 0.001 for i in range(len(dates))]
    series = pd.Series(values, index=dates)
    mock_client.get_series.return_value = series

    result = fetcher.fetch()

    mock_client.get_series.assert_called_once_with(
        "DFII10", observation_start=None, observation_end=None, use_cache=True,
    )
    assert isinstance(result, pd.Series)
    assert len(result) == len(dates)


def test_fetch_empty_on_exception(fetcher: RealYieldFetcher, mock_client: MagicMock) -> None:
    mock_client.get_series.side_effect = ValueError("API error")

    result = fetcher.fetch()

    assert isinstance(result, pd.Series)
    assert len(result) == 0


def test_fetch_latest_returns_correct(fetcher: RealYieldFetcher, mock_client: MagicMock) -> None:
    dates = pd.date_range("2020-01-01", "2025-01-01", freq="B")
    values = [1.5 + i * 0.001 for i in range(len(dates))]
    series = pd.Series(values, index=dates)
    mock_client.get_series.return_value = series

    obs_date, value = fetcher.fetch_latest()

    assert obs_date == dates[-1]
    assert value == pytest.approx(values[-1])


def test_fetch_latest_none_on_empty(fetcher: RealYieldFetcher, mock_client: MagicMock) -> None:
    mock_client.get_series.return_value = pd.Series(dtype="float64")

    obs_date, value = fetcher.fetch_latest()

    assert obs_date is None
    assert value is None


def test_fetch_window_returns_correct_count(fetcher: RealYieldFetcher, mock_client: MagicMock) -> None:
    dates = pd.date_range("2020-01-01", "2025-01-01", freq="B")
    values = [1.5 + i * 0.001 for i in range(len(dates))]
    series = pd.Series(values, index=dates)
    mock_client.get_series.return_value = series

    result = fetcher.fetch_window(window_observations=100)

    assert len(result) == 100
    assert result.index[-1] == dates[-1]


def test_fetch_window_respects_max_data(fetcher: RealYieldFetcher, mock_client: MagicMock) -> None:
    dates = pd.date_range("2020-01-01", "2020-02-01", freq="B")
    values = [1.5] * len(dates)
    series = pd.Series(values, index=dates)
    mock_client.get_series.return_value = series

    result = fetcher.fetch_window(window_observations=5000)

    assert len(result) == len(dates)  # returns all available
    assert result.index[0] == dates[0]


def test_fetch_window_invalid(fetcher: RealYieldFetcher, mock_client: MagicMock) -> None:
    mock_client.get_series.return_value = pd.Series(dtype="float64")

    result = fetcher.fetch_window(window_observations=0)

    assert isinstance(result, pd.Series)
    assert len(result) == 0


def test_fetch_uses_cache_parameter(fetcher: RealYieldFetcher, mock_client: MagicMock) -> None:
    dates = pd.date_range("2020-01-01", "2025-01-01", freq="B")
    series = pd.Series([1.5] * len(dates), index=dates)
    mock_client.get_series.return_value = series

    fetcher.fetch(use_cache=False)
    mock_client.get_series.assert_called_once_with(
        "DFII10", observation_start=None, observation_end=None, use_cache=False,
    )


def test_fetch_with_observation_start(fetcher: RealYieldFetcher, mock_client: MagicMock) -> None:
    dates = pd.date_range("2023-01-01", "2025-01-01", freq="B")
    series = pd.Series([1.5] * len(dates), index=dates)
    mock_client.get_series.return_value = series

    fetcher.fetch(observation_start="2024-01-01")
    mock_client.get_series.assert_called_once_with(
        "DFII10", observation_start="2024-01-01", observation_end=None, use_cache=True,
    )
