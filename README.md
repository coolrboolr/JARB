J UST

A NOTHER

R EGULAR

B OT

A simple agentic flow that allows you to store functions for later use. 

Runs as a module for testing with main.py

or as a node app with:

py api.py

  and 

cd node_fe

node index.js

agent class can run create_tool to iterate through agentic flow

The flow:
1. Create a plan, iterate through it to optimize
2. Write code, and fix general errors until functional
3. Write unit tests and check to see if the code is running as expected
4. Save

Logs for each tool are available in tool_logs/tool_name.json - one file per tool created