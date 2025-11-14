import logging

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

import jarb_core

# Initialize Flask app
app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

jarb_core.configure()


def _success(data=None, status: int = 200):
    return (
        jsonify({
            "success": True,
            "data": data,
            "error": None,
        }),
        status,
    )


def _error(code: str, message: str, status: int):
    return (
        jsonify({
            "success": False,
            "data": None,
            "error": {
                "code": code,
                "message": message,
            },
        }),
        status,
    )

# Define routes for the API
@app.route('/api/create_tool', methods=['POST'])
def create_tool():
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    description = data.get('description')
    if not name or not description:
        return _error("BAD_REQUEST", "Name and description are required", 400)
    try:
        jarb_core.create_tool(name, description)
        return _success({"message": "Tool created"}, 201)
    except Exception as e:
        app.logger.exception("Error creating tool: %s", e)
        return _error("CREATE_FAILED", str(e), 500)

@app.route('/api/use_tool', methods=['POST'])
def use_tool():
    data = request.get_json(silent=True) or {}
    tool_name = data.get('tool_name')
    params = data.get('params', {})
    if not tool_name:
        return _error("BAD_REQUEST", "Tool name is required", 400)
    if not isinstance(params, dict):
        return _error("BAD_REQUEST", "Params must be an object", 400)
    try:
        app.logger.debug("Using tool '%s' with params %s", tool_name, params)
        result = jarb_core.use_tool(tool_name, **params)
        return _success({"result": result})
    except FileNotFoundError:
        return _error("NOT_FOUND", f"The tool {tool_name} does not exist or could not be loaded.", 404)
    except Exception as e:
        app.logger.exception("Error using tool %s: %s", tool_name, e)
        return _error("USE_FAILED", str(e), 500)

@app.route('/api/list_tools', methods=['GET'])
def list_tools():
    try:
        tools = jarb_core.list_tools()
        return _success({"tools": tools})
    except Exception as e:
        app.logger.exception("Error listing tools: %s", e)
        return _error("LIST_FAILED", str(e), 500)

@app.route('/api/tool_parameters/<tool_name>', methods=['GET'])
def tool_parameters(tool_name):
    try:
        description = jarb_core.describe_tool(tool_name)
        app.logger.debug("Description for tool %s: %s", tool_name, description)
        return _success({
            "name": description.get('name', tool_name),
            "parameters": description.get('parameters', []),
            "docstring": description.get('docstring'),
            "return_annotation": description.get('return_annotation'),
        })
    except FileNotFoundError:
        return _error("NOT_FOUND", f"The tool {tool_name} does not exist or could not be loaded.", 404)
    except Exception as e:
        app.logger.exception("Error getting tool parameters for %s: %s", tool_name, e)
        return _error("DESCRIBE_FAILED", str(e), 500)


@app.route('/api/tools', methods=['GET'])
def tools_catalog():
    try:
        catalog = jarb_core.get_tool_catalog()
        return _success({"tools": catalog})
    except Exception as e:
        app.logger.exception("Error fetching tools catalog: %s", e)
        return _error("CATALOG_FAILED", "Failed to load tool catalog", 500)


@app.route('/api/tool_runs/<tool_name>', methods=['GET'])
def tool_runs(tool_name):
    limit_param = request.args.get('limit', type=int)
    limit = limit_param if limit_param and limit_param > 0 else 20
    try:
        runs = jarb_core.get_tool_runs(tool_name, limit=limit)
        return _success({"runs": runs})
    except FileNotFoundError:
        return _error("NOT_FOUND", f"The tool {tool_name} does not exist or could not be loaded.", 404)
    except Exception as e:
        app.logger.exception("Error fetching tool runs for %s: %s", tool_name, e)
        return _error("RUNS_FAILED", "Failed to load tool run history", 500)


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return error
    app.logger.exception("Unhandled exception: %s", error)
    return _error("INTERNAL_ERROR", "An unexpected error occurred.", 500)


@app.after_request
def add_cors_headers(response):
    response.headers.setdefault("Access-Control-Allow-Origin", "*")
    response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
    response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    return response
@app.route('/api/create_flow', methods=['POST'])
def create_flow():
    data = request.get_json(silent=True) or {}
    flow_spec = data.get('flow')
    if not isinstance(flow_spec, dict):
        return _error("BAD_REQUEST", "flow must be an object", 400)
    try:
        jarb_core.create_flow(flow_spec)
        return _success({"message": "Flow created"}, 201)
    except ValueError as exc:
        return _error("BAD_REQUEST", str(exc), 400)
    except Exception as exc:  # pragma: no cover - unexpected path
        app.logger.exception("Error creating flow: %s", exc)
        return _error("CREATE_FLOW_FAILED", str(exc), 500)


@app.route('/api/run_flow', methods=['POST'])
def run_flow():
    data = request.get_json(silent=True) or {}
    flow_name = data.get('flow_name')
    inputs = data.get('inputs', {}) or {}
    if not flow_name:
        return _error("BAD_REQUEST", "flow_name is required", 400)
    if not isinstance(inputs, dict):
        return _error("BAD_REQUEST", "inputs must be an object", 400)
    try:
        result = jarb_core.run_flow(flow_name, inputs)
        return _success({"result": result})
    except FileNotFoundError:
        return _error("NOT_FOUND", f"The flow {flow_name} does not exist or could not be loaded.", 404)
    except ValueError as exc:
        return _error("BAD_REQUEST", str(exc), 400)
    except Exception as exc:  # pragma: no cover
        app.logger.exception("Error running flow %s: %s", flow_name, exc)
        return _error("RUN_FLOW_FAILED", str(exc), 500)


@app.route('/api/flows', methods=['GET'])
def flows_catalog():
    try:
        flows = jarb_core.list_flows()
        return _success({"flows": flows})
    except Exception as exc:  # pragma: no cover - unexpected path
        app.logger.exception("Error listing flows: %s", exc)
        return _error("FLOWS_FAILED", "Failed to load flow catalog", 500)


@app.route('/api/flow/<flow_name>', methods=['GET'])
def flow_detail(flow_name: str):
    try:
        spec = jarb_core.describe_flow(flow_name)
        return _success({"flow": spec})
    except FileNotFoundError:
        return _error("NOT_FOUND", f"The flow {flow_name} does not exist or could not be loaded.", 404)
    except Exception as exc:  # pragma: no cover
        app.logger.exception("Error fetching flow %s: %s", flow_name, exc)
        return _error("FLOW_FAILED", "Failed to load flow", 500)


@app.route('/api/flow_runs/<flow_name>', methods=['GET'])
def flow_runs(flow_name: str):
    limit_param = request.args.get('limit', type=int)
    limit = limit_param if limit_param and limit_param > 0 else 20
    try:
        runs = jarb_core.get_flow_runs(flow_name, limit=limit)
        return _success({"runs": runs})
    except FileNotFoundError:
        return _error("NOT_FOUND", f"The flow {flow_name} does not exist or could not be loaded.", 404)
    except Exception as exc:  # pragma: no cover
        app.logger.exception("Error fetching flow runs for %s: %s", flow_name, exc)
        return _error("FLOW_RUNS_FAILED", "Failed to load flow run history", 500)


if __name__ == '__main__':
    app.run(debug=True)
