from flask import Flask, request, jsonify
import os
from agent import Agent
import logging
import inspect

# Initialize Flask app
app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variable for OpenAI API key
os.environ['OPENAI_KEY'] = open('.pass/OPENAI_KEY','r').read().strip()

# Initialize Agent
agent = Agent("openai")

# Define routes for the API
@app.route('/api/create_tool', methods=['POST'])
def create_tool():
    data = request.get_json()
    name = data.get('name')
    description = data.get('description')
    if not name or not description:
        return jsonify({'error': 'Name and description are required'}), 400
    try:
        agent.create_tool(name, description)
        return jsonify({'message': 'Tool created successfully'}), 201
    except Exception as e:
        logging.error(f"Error creating tool: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/use_tool', methods=['POST'])
def use_tool():
    data = request.get_json()
    tool_name = data.get('tool_name')
    params = data.get('params', {})
    if not tool_name:
        return jsonify({'error': 'Tool name is required'}), 400
    try:
        logging.debug(f"Using tool: {tool_name} with params: {params}")
        result = agent.use_tool(tool_name, **params)
        return jsonify({'result': result}), 200
    except Exception as e:
        logging.error(f"Error using tool: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/list_tools', methods=['GET'])
def list_tools():
    try:
        tools = agent.tool_library.list_tools()
        return jsonify({'tools': tools}), 200
    except Exception as e:
        logging.error(f"Error listing tools: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tool_parameters/<tool_name>', methods=['GET'])
def tool_parameters(tool_name):
    try:
        tool = agent.tool_library.get_tool(tool_name)
        if not tool:
            return jsonify({'error': 'Tool not found'}), 404
        sig = inspect.signature(tool)
        parameters = [
            {'name': param.name, 'default': param.default if param.default != inspect.Parameter.empty else None}
            for param in sig.parameters.values()
        ]
        return jsonify({'parameters': parameters}), 200
    except Exception as e:
        logging.error(f"Error getting tool parameters: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
