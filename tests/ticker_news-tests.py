
import unittest
from unittest.mock import patch, MagicMock
import datetime
import requests
import os
import json

# Assuming ticker_news function is imported from the given module
from module_name import ticker_news

class TestTickerNews(unittest.TestCase):

    @patch('module_name.requests.get')
    def test_invalid_ticker(self, mock_get):
        self.assertEqual(ticker_news('AAPL1'), "Invalid ticker symbol. Please use 1-4 uppercase letters.")
        self.assertEqual(ticker_news('apple'), "Invalid ticker symbol. Please use 1-4 uppercase letters.")
        self.assertEqual(ticker_news('A P L'), "Invalid ticker symbol. Please use 1-4 uppercase letters.")

    @patch('module_name.requests.get')
    def test_fetch_news_api_call(self, mock_get):
        # Mock environment variable for API Key
        mock_getenv = patch('module_name.os.getenv', return_value='test_news_api_key')
        mock_getenv.start()

        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'articles': [
                {
                    'title': 'Test News 1',
                    'publishedAt': '2023-11-01T12:00:00Z',
                    'description': 'Description of test news 1.'
                },
                {
                    'title': 'Test News 2',
                    'publishedAt': '2023-11-02T12:00:00Z',
                    'description': 'Description of test news 2.'
                }
            ]
        }
        mock_get.return_value = mock_response

        result = ticker_news('AAPL')

        # Check that the news API was called with the expected URL and API key
        expected_url = mock_get.call_args[0][0]
        self.assertIn('apiKey=test_news_api_key', expected_url)
        self.assertIn('AAPL', expected_url)
        self.assertIn('https://newsapi.org/v2/everything', expected_url)

        # Check that the result contains the news summary
        self.assertIn('news_summary', result)
        self.assertEqual(len(result['news_summary']), 2)

        mock_getenv.stop()

    @patch('module_name.requests.get')
    def test_fetch_analyst_reports(self, mock_get):
        # Mock environment variable for API Key
        mock_getenv = patch('module_name.os.getenv', return_value='test_analyst_api_key')
        mock_getenv.start()

        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'period': '2023-11-01',
                'rating': 'buy',
                'targetPrice': 150
            },
            {
                'period': '2023-11-02',
                'rating': 'hold',
                'targetPrice': 145
            }
        ]
        mock_get.return_value = mock_response

        result = ticker_news('AAPL')

        # Check that the analyst API was called with the expected URL and API key
        expected_url = mock_get.call_args[0][0]
        self.assertIn('token=test_analyst_api_key', expected_url)
        self.assertIn('AAPL', expected_url)
        self.assertIn('https://finnhub.io/api/v1/stock/recommendation', expected_url)

        # Check that the result contains the analyst summary
        self.assertIn('analyst_summary', result)
        self.assertEqual(len(result['analyst_summary']), 2)

        mock_getenv.stop()

if __name__ == '__main__':
    unittest.main()
