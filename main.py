import json
import os

import jarb_core


def _maybe_create_example_tool():
    if os.getenv("CREATE_TOOL_EXAMPLE") != "1":
        return

    jarb_core.create_tool(
        "ticker_news",
        (
            "Given a US stock ticker, return a summary of the past week of events in the news, "
            "the most recent 10k and analyst reports. The parameter of the ticker_news function "
            "should be ticker: str. At the end call the LLM backend and summarize all findings."
        ),
    )


def _maybe_run_flow():
    flow_name = os.getenv("RUN_FLOW")
    if not flow_name:
        return

    inputs_raw = os.getenv("RUN_FLOW_INPUTS", "{}")
    try:
        inputs = json.loads(inputs_raw)
    except json.JSONDecodeError:
        print("RUN_FLOW_INPUTS must be valid JSON. Skipping flow execution.")
        return

    print(f"Running flow '{flow_name}' with inputs: {inputs}")
    try:
        result = jarb_core.run_flow(flow_name, inputs)
        print(f"Flow '{flow_name}' result: {result}")
    except FileNotFoundError:
        print(f"Flow '{flow_name}' not found. Create it first via the API or jarb_core.")
    except Exception as exc:  # pragma: no cover - smoke helper
        print(f"Flow '{flow_name}' failed: {exc}")


def main():
    jarb_core.configure()

    print("Available tools:", jarb_core.list_tools())
    print("Available flows:", jarb_core.list_flows())

    _maybe_create_example_tool()
    _maybe_run_flow()

    try:
        result = jarb_core.use_tool("subtract_numbers", a=5, b=2)
        print("subtract_numbers(5, 2) =>", result)
    except FileNotFoundError:
        print("No subtract_numbers tool found. Create one via the API or Agent before running this smoke test.")


if __name__ == "__main__":
    main()
