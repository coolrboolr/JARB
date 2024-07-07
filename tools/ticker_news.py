
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import json
from sec_edgar_downloader import Downloader
import openai  # Assuming you have an API key set up
import yfinance as yf

# Constants for API keys (replace with your own)
NEWS_API_KEY = 'your_news_api_key'
OPENAI_API_KEY = 'your_openai_api_key'

# Set up OpenAI API key
openai.api_key = OPENAI_API_KEY

def get_stock_summary(ticker: str):
    ticker = ticker.upper()
    
    # Validate ticker
    if not ticker.isalpha():
        print("Invalid ticker format.")
        return

    print(f"Gathering news articles for {ticker}...")
    news_summary = get_news_summary(ticker)
    
    print(f"Fetching the latest 10-K filing for {ticker}...")
    ten_k_summary = get_latest_ten_k_summary(ticker)
    
    print(f"Gathering analyst reports for {ticker}...")
    analyst_summary = get_analyst_reports(ticker)
    
    print("\nSummary Report")
    print("="*50)
    print(f"Stock Ticker: {ticker}")
    print("\nNews Summary:")
    print(news_summary)
    print("\n10-K Filing Summary:")
    print(ten_k_summary)
    print("\nAnalyst Reports Summary:")
    print(analyst_summary)

def get_news_summary(ticker: str):
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=7)
    
    url = (
        f"https://newsapi.org/v2/everything?q={ticker}&from={start_date}&to={end_date}&sortBy=publishedAt"
        f"&apiKey={NEWS_API_KEY}"
    )
    
    response = requests.get(url)
    
    if response.status_code == 200:
        articles = response.json().get('articles', [])
        return format_news_articles(articles)
    else:
        return "Failed to fetch news articles."

def format_news_articles(articles):
    summary = ""
    for article in articles[:5]:  # Limit to top 5 articles
        summary += f"Title: {article['title']}\n"
        summary += f"Description: {article['description']}\n"
        summary += f"URL: {article['url']}\n"
        summary += "-"*50 + "\n"
    return summary

def get_latest_ten_k_summary(ticker: str):
    dl = Downloader()
    
    try:
        filings = dl.get('10-K', ticker)
        if filings:
            latest_filing = max(filings, key=lambda x: x['date_filed'])
            file_path = latest_filing['local_path']

            with open(file_path) as f:
                ten_k_report = f.read()

            return summarize_document(ten_k_report)
        else:
            return "No 10-K filings found."
    except Exception as e:
        return f"Failed to fetch 10-K filing: {e}"

def summarize_document(text: str):
    response = openai.Completion.create(
        engine="davinci",
        prompt=f"Summarize the following SEC 10-K filing document:\n\n{text}",
        max_tokens=300,  # Adjust as needed
        temperature=0.5
    )
    
    return response.choices[0].text.strip()

def get_analyst_reports(ticker: str):
    stock = yf.Ticker(ticker)
    recommendations = stock.recommendations
    
    if recommendations is not None and not recommendations.empty:
        recent_recs = recommendations.tail(5)
        return format_analyst_reports(recent_recs)
    else:
        return "No recent analyst reports found."

def format_analyst_reports(recommendations):
    summary = ""
    for index, row in recommendations.iterrows():
        summary += f"Date: {row.name.date()}\n"
        summary += f"Firm: {row['Firm']}\n"
        summary += f"To Grade: {row['To Grade']}\n"
        summary += f"From Grade: {row['From Grade']}\n"
        summary += "-"*50 + "\n"
    return summary

# Main call
if __name__ == "__main__":
    ticker = input("Enter the stock ticker: ")
    get_stock_summary(ticker)
