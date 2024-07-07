import os
from agent import Agent

os.environ['OPENAI_KEY'] = open('.pass/OPENAI_KEY','r').read().strip()

# Example usage
if __name__ == "__main__":
    agent = Agent("openai")
    
    # Create a new tool
    agent.create_tool(
        "subtract_numbers",
        "Create a function that subtracts 2 numbers"
    )
    
    # Use the tool
    result = agent.use_tool("subtract_numbers", num1=3, num2=5)
    if result is not None:
        print(f"Result of subtract_numbers: {result}")

    # List all tools
    print("Available tools:", agent.tool_library.list_tools())
