
import unittest
from unittest.mock import patch
import yfinance as yf
from pandas import DataFrame

# The function to be tested
def ticker_price(ticker: str):
    """
    Fetch the last closing price for a specified US stock ticker symbol.

    :param ticker: US stock ticker symbol as a string.
    :return: The last closing price as a float or an error message as a string.
    """
    # Input validation
    if not ticker or not ticker.isalnum():
        return "Error: Invalid ticker symbol format."

    try:
        # Fetching stock data using yfinance
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")

        # Check if the historical data is empty
        if hist.empty:
            return f"Error: No data available for ticker {ticker}."

        # Extract the last closing price
        last_close_price = hist['Close'].iloc[-1]
        return last_close_price

    except Exception as e:
        # General error handling
        return f"Error: {str(e)}"

# Unit tests
class TestGetLastClosePrice(unittest.TestCase):

    @patch('yfinance.Ticker')
    def test_valid_ticker(self, mock_ticker):
        # Mocking the yfinance Ticker object and history method
        mock_hist = DataFrame({
            'Close': [150.0],
        }, index=['2023-10-01'])
        mock_ticker.return_value.history.return_value = mock_hist
        
        # Test a valid ticker
        result = ticker_price('AAPL')
        self.assertEqual(result, 150.0)

    def test_invalid_ticker_format(self):
        # Test an invalid ticker format
        result = ticker_price('AAPL!')
        self.assertEqual(result, "Error: Invalid ticker symbol format.")

    @patch('yfinance.Ticker')
    def test_no_data_available(self, mock_ticker):
        # Mocking the yfinance Ticker object with empty data
        mock_hist = DataFrame(columns=['Close'])
        mock_ticker.return_value.history.return_value = mock_hist
        
        # Test a ticker with no data
        result = ticker_price('FAKE')
        self.assertEqual(result, "Error: No data available for ticker FAKE.")

if __name__ == "__main__":
    unittest.main()
