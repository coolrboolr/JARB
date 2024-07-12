
import yfinance as yf

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

# Example usage
if __name__ == "__main__":
    # Replace 'AAPL' with any valid US stock ticker symbol for testing
    ticker = 'AAPL'
    result = ticker_price(ticker)
    print("Last closing price of {}: {}".format(ticker, result))
