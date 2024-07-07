import os
import json
import subprocess
from datetime import datetime
from llm_api import llm_call

class ToolGenerator:
    def __init__(self, api_key: str, log_dir: str = 'tool_logs', tool_dir: str = 'tools', test_dir: str = 'tests'):
        self.api_key = api_key
        self.design: str = ""
        self.code: str = ""
        self.tests: str = ""
        self.log_dir: str = log_dir
        self.tool_dir: str = tool_dir
        self.test_dir: str = test_dir

        # Create directories if they do not exist
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.tool_dir, exist_ok=True)
        os.makedirs(self.test_dir, exist_ok=True)

    def log_interaction(self, tool_name: str, stage: str, query: str, response: str) -> None:
        log_file = os.path.join(self.log_dir, f"{tool_name}.json")
        
        log_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stage": stage,
            "query": query,
            "response": response
        }
        
        # Append log data to the log file
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = json.load(f)
        else:
            logs = []

        logs.append(log_data)
        
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)

    def load_existing_state(self, tool_name: str):
        tool_file = os.path.join(self.tool_dir, f"{tool_name}.py")
        log_file = os.path.join(self.log_dir, f"{tool_name}.json")

        # Load design from logs if available
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = json.load(f)
                design_logs = [log for log in logs if log['stage'].startswith('design')]
                if design_logs:
                    self.design = design_logs[-1]['response']
        
        # Load the last generated code if exists
        if os.path.exists(tool_file):
            with open(tool_file, 'r') as f:
                self.code = f.read()


    def save_tool_code(self, tool_name: str) -> None:
        tool_file = os.path.join(self.tool_dir, f"{tool_name}.py")
        with open(tool_file, 'w') as f:
            f.write(self.code)

    def generate_design(self, tool_name: str, tool_description: str) -> str:
        if not self.design:
            query = f"Create a plan to design a python script for Description. Be clear and concise and don't worry about code yet, we're just planning \
                Description: {tool_description}"
            self.design = llm_call(query)
            self.log_interaction(tool_name, "initial_design", query, self.design)

            for i in range(1):
                query = "Please revise and improve the design below. Think critically and summarize all findings in the response. remember no code yet"
                self.design = llm_call(query, context=f'Design: {self.design}')
                self.log_interaction(tool_name, f"design_revision_{i+1}", query, self.design)

        return self.design

    def generate_code(self, tool_name: str) -> str:
        query = f"Using the following design, write the Python code to implement it:\n\n{self.design} \
Ensure the code is concise and effective, Do not include unit test, as they will be added shortly"

        iteration = 1
        max_iterations = 10  # Limit the number of iterations to prevent infinite loops

        while (iteration <= max_iterations):
            code = llm_call(query)
            # Remove unwanted delimiters
            self.code = code[code.find("```python")+9:code.rfind("```")]
            self.log_interaction(tool_name, f"code_generation_{iteration}", query, code)
            self.save_tool_code(tool_name)  # Save the code on every generation

            try:
                exec(self.code)
                if len(self.code) != 0:
                    break
            except Exception as e:
                error_message = str(e)
                query = (
                    f"The following code has resulted in an error:\n\n{self.code}\n\n"
                    f"Error: {error_message}\n\n"
                    f"The assitant will respond with only the full python script. \
Ensure the code is concise and effective, Do not include unit test, as they will be added shortly \
Comments may be provided within the script but should be formatted accordingly as the response will be run as is."
                )
                iteration += 1
                self.log_interaction(tool_name, f"code_error_{iteration}", query, error_message)

        if iteration > max_iterations:
            raise RuntimeError(f"Failed to generate working code after {max_iterations} iterations.")

        return self.code
    
    def save_test_code(self, tool_name: str) -> None:
        test_file = os.path.join(self.test_dir, f"{tool_name}-tests.py")
        with open(test_file, 'w') as f:
            f.write(self.tests)

    def generate_tests(self, tool_name: str) -> str:
        query = f"Given the following code, write 3 unit tests for it:\n\n{self.code} \
                    The assitant will respond with only the full python script. \
                        Comments may be provided within the script\
                              but should be formatted accordingly as the response will be run as is."
        tests = llm_call(query)
        # Remove unwanted delimiters
        self.tests = tests[tests.find("```python")+9:tests.rfind("```")]

        self.log_interaction(tool_name, "test_generation", query, tests)
        self.save_test_code(tool_name)
        return self.tests

    def run_tests(self) -> bool:
        full_code = f"{self.code}\n\n{self.tests}"
        
        with open("temp_test.py", "w") as f:
            f.write(full_code)
        
        result = subprocess.run(["python", "-m", "unittest", "temp_test.py"], capture_output=True, text=True)
        print(result.stdout)  # For debugging purposes
        print(result.stderr)  # For debugging purposes
        
        return result.returncode == 0

    def create_tool(self, tool_name: str, tool_description: str) -> str:
        self.load_existing_state(tool_name)
        self.generate_design(tool_name, tool_description)
        self.generate_code(tool_name)
        self.generate_tests(tool_name)

        test_iteration = 1
        max_test_iterations = 2  # Limit the number of test iterations to prevent infinite loops
        while test_iteration <= max_test_iterations and not self.run_tests():
            self.generate_code(tool_name)
            self.generate_tests(tool_name)
            test_iteration += 1

        if test_iteration > max_test_iterations:
            raise RuntimeError(f"Failed to pass tests after {max_test_iterations} iterations.")

        # Save the final tool code to the tools directory
        self.save_tool_code(tool_name)
        self.save_test_code(tool_name)

        return self.code
