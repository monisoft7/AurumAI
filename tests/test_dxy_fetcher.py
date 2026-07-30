from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from connectors.dxy_fetcher import DXYFetcher


@pytest.fixture
def mock_yfinance() -> MagicMock:
    dates = pd.date_range("2020-01-01", "2025-01-01", freq="B")
    values = [100.0 + i * 0.01 for i in range(len(dates))]
    df = pd.DataFrame({"Close": values}, index=dates)
    with patch("connectors.dxy_fetcher.yf.download", return_value=df) as mock:
        yield mock


@pytest.fixture
def fetcher() -> DXYFetcher:
    return DXYFetcher()


class TestFetch:
    def test_fetch_returns_series(
        self, fetcher: DXYFetcher, mock_yfinance: MagicMock,
    ) -> None:
        result = fetcher.fetch()
        mock_yfinance.assert_called_once()
        assert isinstance(result, pd.Series)
        assert len(result) > 0

    def test_fetch_empty_on_exception(self, fetcher: DXYFetcher) -> None:
        with patch("connectors.dxy_fetcher.yf.download", side_effect=ValueError("API error")):
            result = fetcher.fetch()
        assert isinstance(result, pd.Series)
        assert len(result) == 0

    def test_fetch_empty_on_empty_response(self, fetcher: DXYFetcher) -> None:
        with patch("connectors.dxy_fetcher.yf.download", return_value=pd.DataFrame()):
            result = fetcher.fetch()
        assert isinstance(result, pd.Series)
        assert len(result) == 0

    def test_fetch_drops_nan(self, fetcher: DXYFetcher) -> None:
        dates = pd.date_range("2020-01-01", "2025-01-01", freq="B")
        values = [100.0] * len(dates)
        values[3] = None
        df = pd.DataFrame({"Close": values}, index=dates)
        with patch("connectors.dxy_fetcher.yf.download", return_value=df):
            result = fetcher.fetch()
        assert len(result) == len(dates) - 1
        assert not result.isna().any()

    def test_fetch_with_period(self, fetcher: DXYFetcher) -> None:
        dates = pd.date_range("2024-01-01", "2025-01-01", freq="B")
        df = pd.DataFrame({"Close": [100.0] * len(dates)}, index=dates)
        with patch("connectors.dxy_fetcher.yf.download", return_value=df) as mock:
            fetcher.fetch(period="1y")
        mock.assert_called_once()
        call_kwargs = mock.call_args[1]
        assert call_kwargs.get("period") == "1y"


class TestFetchLatest:
    def test_fetch_latest_returns_correct(
        self, fetcher: DXYFetcher, mock_yfinance: MagicMock,
    ) -> None:
        obs_date, value = fetcher.fetch_latest()
        assert obs_date is not None
        assert value is not None
        assert isinstance(value, float)

    def test_fetch_latest_none_on_empty(self, fetcher: DXYFetcher) -> None:
        with patch("connectors.dxy_fetcher.yf.download", return_value=pd.DataFrame()):
            obs_date, value = fetcher.fetch_latest()
        assert obs_date is None
        assert value is None

    def test_fetch_latest_default_period_is_1mo(
        self, fetcher: DXYFetcher, mock_yfinance: MagicMock,
    ) -> None:
        fetcher.fetch_latest()
        call_kwargs = mock_yfinance.call_args[1]
        assert call_kwargs.get("period") == "1mo"


class TestFetchWindow:
    def test_fetch_window_returns_correct_count(
        self, fetcher: DXYFetcher, mock_yfinance: MagicMock,
    ) -> None:
        result = fetcher.fetch_window(window_observations=100)
        assert len(result) == 100

    def test_fetch_window_respects_max_data(
        self, fetcher: DXYFetcher, mock_yfinance: MagicMock,
    ) -> None:
        result = fetcher.fetch_window(window_observations=50000)
        mock_data = mock_yfinance.return_value
        expected_len = len(mock_data)
        assert len(result) == expected_len

    def test_fetch_window_invalid(self, fetcher: DXYFetcher) -> None:
        with patch("connectors.dxy_fetcher.yf.download", return_value=pd.DataFrame()):
            result = fetcher.fetch_window(window_observations=0)
        assert isinstance(result, pd.Series)
        assert len(result) == 0
