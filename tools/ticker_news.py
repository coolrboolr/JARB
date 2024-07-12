'''### Revised and Improved Design for `ticker_news`

**Objective:** Create a Python script that, given a US stock ticker, returns a summary of the past week's news events, the most recent 10-K report, and recent analyst reports.

### Essential Components

**1. Input:**
   - `ticker: str` - A string representing the US stock ticker.

**2. Output:**
   - A summary of the past week's news events.
   - The most recent 10-K report.
   - Recent analyst reports.

### Detailed Steps and Considerations

**1. Import Needed Libraries:**
   - `requests`: For making HTTP requests to APIs.
   - `pandas`: For data manipulation and organization.
   - `datetime`: For handling date-related operations.
   - `json`: For parsing API responses in JSON format.
   - `BeautifulSoup` from `bs4`: For parsing HTML content, if web scraping is needed.
   - `re`: For regular expression operations (particularly for data extraction).

**2. Validate Input:**
   - Verify that the `ticker` is a valid string, consisting only of uppercase letters and has an appropriate length (typically 1-4 characters for most US tickers).

**3. Fetch News Data:**
   - **API Selection:** Choose a reliable financial news API to fetch the latest news related to the given ticker.
       - Options: NewsAPI, Alpha Vantage, or FinancialModelingPrep.
   - **Date Filtering:** Retrieve news from the past week by calculating the date range.
   - **Data Parsing:** Extract and summarize key information such as headlines, dates, and a brief description of each relevant news article.

**4. Fetch 10-K Report:**
   - **API Utilization:** Use the SEC's EDGAR database API to find the most recent 10-K filing.
   - **Document Retrieval:** Download and possibly parse the 10-K document.
   - **Content Extraction:** Focus on key sections like Management's Discussion and Analysis (MD&A), financial statements, and risk factors.

**5. Fetch Analyst Reports:**
   - **API Selection:** Access financial data providers such as IEX Cloud or Alpha Vantage for recent analyst ratings and reports.
   - **Data Extraction:** Summarize key findings, rating changes, and price targets.

**6. Combine Data and Output:**
   - **Aggregation:** Combine the summarized news events, 10-K report highlights, and analyst reports into a coherent structure.
   - **Formatting:** Structure the output for readability, possibly using a dictionary or a pandas DataFrame.

**7. Error Handling:**
   - **HTTP Errors:** Ensure robust handling of HTTP errors and connection issues.
   - **API Response Validation:** Validate the response from APIs before processing to handle empty or malformed data gracefully.
   - **Input Validation:** Handle invalid ticker symbols and provide meaningful error messages.

**8. Security and Rate Limiting:**
   - **API Keys Management:** Store and manage API keys securely using environment variables.
   - **Rate Limiting:** Implement checks to handle API rate limits, including retry mechanisms or delays if necessary.

### Summary of Findings:

1. **Robust Input Validation:** Ensuring the ticker input is correctly formatted prevents unnecessary API call failures.
2. **Use of Appropriate APIs:** Each data type (news, 10-K reports, analyst reports) requires specialized APIs that provide reliable and up-to-date information.
3. **Date Filtering for News:** Efficiently filtering news to include only the past week's events enhances relevance.
4. **Content Extraction from Filings:** Focusing on crucial sections of the 10-K filing avoids overwhelming users with unnecessary data.
5. **Error Handling and Validation:** Robust error handling ensures the script gracefully manages and informs users about issues.
6. **Security Measures:** Secure management of API keys and adherence to rate limits ensures compliance and uninterrupted service.
7. **Data Aggregation and Formatting:** Clear and concise aggregation and formatting of information facilitates easy understanding and usability.

By following these revised steps and considerations, the script will be more robust, secure, and user-friendly, providing comprehensive and relevant information for the given stock ticker.
'''


import requests
import pandas as pd
import datetime
import json
import os
from bs4 import BeautifulSoup
import re
import openai

def ticker_news(ticker: str):
    # Validate Ticker
    if not re.match(r'^[A-Z]{1,4}$', ticker):
        return "Invalid ticker symbol. Please use 1-4 uppercase letters."

    # Fetch News Data
    def fetch_news(ticker):
        API_KEY = os.getenv('NEWS_API_KEY')
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=7)
        url = f"https://newsapi.org/v2/everything?q={ticker}&from={start_date.strftime('%Y-%m-%d')}&to={end_date.strftime('%Y-%m-%d')}&apiKey={API_KEY}"
        response = requests.get(url)
        if response.status_code != 200:
            return "Error fetching news data."

        news_data = response.json()
        if 'articles' not in news_data or not news_data['articles']:
            return "No news articles found."

        news_summary = []
        for article in news_data['articles']:
            news_summary.append({
                'headline': article['title'],
                'date': article['publishedAt'],
                'description': article['description']
            })
        return news_summary

    # Fetch 10-K Report from SEC EDGAR
    def fetch_10k(ticker):
        url = f"https://data.sec.gov/submissions/CIK{ticker}.json"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return "Error fetching 10-K report."

        company_data = response.json()
        filings = company_data.get('filings', {}).get('recent', {})
        report_links = [filings['primaryDocument'][i] for i, form in enumerate(filings['form']) if form == '10-K']
        if not report_links:
            return "No recent 10-K report found."

        latest_10k_url = f"https://www.sec.gov/Archives/{report_links[0]}"
        response = requests.get(latest_10k_url, headers=headers)
        if response.status_code != 200:
            return "Error fetching 10-K document."

        soup = BeautifulSoup(response.content, 'html.parser')
        # Extract sections (simplified example, actual extraction might need more complex parsing)
        sections = {h.text: h.find_next('div').text for h in soup.find_all('h2')}
        relevant_sections = {k: sections[k] for k in sections if k in ["Management's Discussion and Analysis", "Financial Statements", "Risk Factors"]}
        return relevant_sections

    # Fetch Analyst Reports
    def fetch_analyst_reports(ticker):
        API_KEY = os.getenv('ANALYST_API_KEY')
        url = f"https://finnhub.io/api/v1/stock/recommendation?symbol={ticker}&token={API_KEY}"
        response = requests.get(url)
        if response.status_code != 200:
            return "Error fetching analyst reports."

        analyst_data = response.json()
        if not analyst_data:
            return "No analyst reports found."

        latest_reports = analyst_data[:5]  # Get the most recent 5 reports
        reports_summary = []
        for report in latest_reports:
            reports_summary.append({
                'date': report['period'],
                'rating': report['rating'],
                'target_price': report['targetPrice']
            })
        return reports_summary

    # Aggregating Data
    news_summary = fetch_news(ticker)
    ten_k_summary = fetch_10k(ticker)
    analyst_summary = fetch_analyst_reports(ticker)

    context = {
        'news_summary': news_summary,
        'ten_k_summary': ten_k_summary,
        'analyst_summary': analyst_summary
    }

    openai.api_key = os.environ['OPENAI_KEY']
    messages = [{"role": "user", "content": f"summarize these documents about {ticker} that I've compiled"}]
    if context:
        messages.insert(0, {"role": "assistant", "content": json.dumps(context, indent=4)})

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=1000
    )
    return response.choices[0].message.content.strip()
