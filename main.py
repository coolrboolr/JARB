import os
from dotenv import load_dotenv
from agent import Agent

load_dotenv()
#OPENAI_KEY


# Example usage
if __name__ == "__main__":
    agent = Agent("openai")
    
    # Create a new tool
    agent.create_tool(
        "ticker_news",
        "Given a US stock ticker, return a summary of the past week of events in the news, the most recent 10k and analyst reports"
        "the parameter of the ticker_news function should be 'ticker: str'"
        "at the end call openai and summarize all the findings"
    )
    
    # Use the tool
    result = agent.use_tool("ticker_news", ticker='AAPL')
    if result is not None:
        print(f"Result of ticker search: {result}")

    # List all tools
    print("Available tools:", agent.tool_library.list_tools())
