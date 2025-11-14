from datetime import datetime
from dotenv import load_dotenv
import json
import os
import re
import subprocess
import sys
from typing import Callable, Optional

from llm_api import LLMConfig, llm_call

BASE_QUERY = ("The assistant will respond with only the full python script."
            "Ensure the code is concise and effective, Do not include unit tests, as they will be added shortly"
            "Comments may be provided within the script but should be formatted accordingly as the response will be run as is."
            "do not include any pip installations, these will be handled as long as they are imported"
            "Pull all keys and secrets from the environment via 'API_KEY = os.getenv('NAME_OF_KEY')'")

class ToolGenerator:
    """
    A class to generate tools based on LLM descriptions, manage dependencies, and handle environment variables.

    Attributes:
    -----------
    llm_config : LLMConfig
        Configuration for the LLM backend.
    log_dir : str
        The directory where log files are stored.
    tool_dir : str
        The directory where tool scripts are saved.
    test_dir : str
        The directory where test scripts are saved.
    design : str
        The design of the tool being generated.
    code : str
        The code of the tool being generated.
    tests : str
        The tests for the tool being generated.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        log_dir: str = 'tool_logs',
        tool_dir: str = 'tools',
        test_dir: str = 'tests',
        llm_call_func: Optional[Callable[[str, LLMConfig, Optional[str]], str]] = None,
    ):
        """
        Initializes the ToolGenerator with the specified directories and LLM configuration.

        Parameters:
        -----------
        llm_config : LLMConfig
            Configuration for the LLM backend.
        log_dir : str, optional
            The directory where log files are stored (default is 'tool_logs').
        tool_dir : str, optional
            The directory where tool scripts are saved (default is 'tools').
        test_dir : str, optional
            The directory where test scripts are saved (default is 'tests').
        """
        self.llm_config = llm_config
        self.design: str = ""
        self.code: str = ""
        self.tests: str = ""
        self.log_dir: str = log_dir
        self.tool_dir: str = tool_dir
        self.test_dir: str = test_dir
        self.llm_call = llm_call_func or llm_call

        # Create directories if they do not exist
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.tool_dir, exist_ok=True)
        os.makedirs(self.test_dir, exist_ok=True)

    def log_interaction(self, tool_name: str, stage: str, query: str, response: str) -> None:
        """
        Logs the interaction with the LLM to a JSON file.

        Parameters:
        -----------
        tool_name : str
            The name of the tool being generated.
        stage : str
            The stage of the tool generation process.
        query : str
            The query sent to the LLM.
        response : str
            The response received from the LLM.
        """
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
        """
        Loads the existing state of a tool from the log and tool files.

        Parameters:
        -----------
        tool_name : str
            The name of the tool whose state is to be loaded.
        """
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
        """
        Saves the generated code of a tool to a file.

        Parameters:
        -----------
        tool_name : str
            The name of the tool whose code is to be saved.
        """
        tool_file = os.path.join(self.tool_dir, f"{tool_name}.py")
        code_design = f"'''{self.design}\n'''\n\n{self.code}"

        with open(tool_file, 'w') as f:
            f.write(code_design)

    def generate_design(self, tool_name: str, tool_description: str) -> str:
        """
        Generates the design for a tool based on its description.

        Parameters:
        -----------
        tool_name : str
            The name of the tool being designed.
        tool_description : str
            The description of the tool.

        Returns:
        --------
        str
            The design of the tool.
        """
        if not self.design:
            query = f"Create a plan to design a python script for Description. Be clear and concise and don't worry about code yet, we're just planning \
                Description: {tool_description}"
            self.design = self.llm_call(query, self.llm_config)
            self.log_interaction(tool_name, "initial_design", query, self.design)

            for i in range(2):
                query = ("Please revise and improve the design below. Think critically and summarize all findings in the response. remember no code yet"
                         f"Remember the original design is for {tool_description}")
                self.design = self.llm_call(query, self.llm_config, context=f'Design: {self.design}')
                self.log_interaction(tool_name, f"design_revision_{i+1}", query, self.design)

        return self.design

    def install_dependencies(self) -> None:
        """
        Installs the dependencies required by the generated code.
        """
        # Extract import statements from the code
        import_lines = [line for line in self.code.split('\n') if line.startswith('import ') or line.startswith('from ')]
        for line in import_lines:
            parts = line.split()
            if parts[0] == 'import':
                package_name = parts[1].split('.')[0]
            elif parts[0] == 'from':
                package_name = parts[1].split('.')[0]
            self._install_package(package_name)

    def _install_package(self, package_name: str) -> None:
        """
        Installs a specific package using pip.

        Parameters:
        -----------
        package_name : str
            The name of the package to be installed.
        """
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        except subprocess.CalledProcessError:
            print(f"Failed to install {package_name}")

    def _get_keys_from_code(self, code: str) -> dict:
        """
        Extracts API keys from the generated code.

        Parameters:
        -----------
        code : str
            The generated code.

        Returns:
        --------
        dict
            A dictionary of API keys found in the code.
        """
        # Regex pattern to find lines like 'api_key = "your_api_key_here"'
        pattern = re.compile(r'(\w+_key)\s*=\s*[\'"]([^\'"]+)[\'"]')
        matches = pattern.findall(code)
        return dict(matches)

    def _update_env_file(self, keys: dict) -> None:
        """
        Updates the .env file with the extracted keys and modifies the code to use the .env file.

        Parameters:
        -----------
        keys : dict
            A dictionary of keys to be added to the .env file.
        """
        env_file = ".env"
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                env_lines = f.readlines()
            env_dict = dict(line.strip().split('=') for line in env_lines if '=' in line)
        else:
            env_dict = {}

        updated = False
        for key, value in keys.items():
            if key not in env_dict:
                env_dict[key] = value
                updated = True

        if updated:
            with open(env_file, 'w') as f:
                for key, value in env_dict.items():
                    f.write(f"{key}={value}\n")

            print(f"Updated {env_file} with new keys.")
        
        # Update the code to use the keys from the .env file
        load_dotenv_code = 'from dotenv import load_dotenv\nload_dotenv()\nimport os\n'
        for key in keys:
            self.code = re.sub(
                rf'(\b{key}\b\s*=\s*)[\'"][^\'"]*[\'"]',
                rf'\1os.getenv("{key.upper()}")',
                self.code
            )

        # Ensure that load_dotenv is at the beginning of the code
        if 'from dotenv import load_dotenv' not in self.code:
            self.code = load_dotenv_code + self.code

    def generate_code(self, tool_name: str) -> str:
        """
        Generates the code for a tool based on its design.

        Parameters:
        -----------
        tool_name : str
            The name of the tool being generated.

        Returns:
        --------
        str
            The generated code for the tool.
        """
        query = (f"Using the following design, write the Python code to implement it:\n\n{self.design}"
                 f"Remember to name the main function {tool_name}") + BASE_QUERY

        iteration = 1
        max_iterations = 10  # Limit the number of iterations to prevent infinite loops

        while iteration <= max_iterations:
            code = self.llm_call(query, self.llm_config)
            # Remove unwanted delimiters
            self.code = code[code.find("```python") + 9:code.rfind("```")]
            self.log_interaction(tool_name, f"code_generation_{iteration}", query, code)
            self.save_tool_code(tool_name)  # Save the code on every generation

            # Extract keys from the generated code
            keys = self._get_keys_from_code(self.code)
            if keys:
                self._update_env_file(keys)

            # Install dependencies before testing the code
            self.install_dependencies()

            try:
                exec(self.code)
                if len(self.code) != 0:
                    break
            except Exception as e:
                error_message = str(e)
                query = (
                    f"The following code has resulted in an error:\n\n{self.code}\n\n"
                    f"Error: {error_message}\n\n"
                    f"The code will have access to these environment variables: {', '.join(keys.keys())}" if keys  else ''
                    f"Remember to name the main function {tool_name}"
                ) + BASE_QUERY

                iteration += 1
                self.log_interaction(tool_name, f"code_error_{iteration}", query, error_message)

        if iteration > max_iterations:
            raise RuntimeError(f"Failed to generate working code after {max_iterations} iterations.")

        return self.code

    def save_test_code(self, tool_name: str) -> None:
        """
        Saves the generated test code for a tool to a file.

        Parameters:
        -----------
        tool_name : str
            The name of the tool whose test code is to be saved.
        """
        test_file = os.path.join(self.test_dir, f"{tool_name}-tests.py")
        with open(test_file, 'w') as f:
            f.write(self.tests)

    def generate_tests(self, tool_name: str) -> str:
        """
        Generates unit tests for the generated tool code.

        Parameters:
        -----------
        tool_name : str
            The name of the tool being tested.

        Returns:
        --------
        str
            The generated test code for the tool.
        """
        query = f"Given the following code, write 3 unit tests for it:\n\n{self.code} \
                    The assitant will respond with only the full python script. \
                        Comments may be provided within the script\
                              but should be formatted accordingly as the response will be run as is."
        tests = self.llm_call(query, self.llm_config)
        # Remove unwanted delimiters
        self.tests = tests[tests.find("```python")+9:tests.rfind("```")]

        self.log_interaction(tool_name, "test_generation", query, tests)
        self.save_test_code(tool_name)
        return self.tests

    def run_tests(self) -> bool:
        """
        Runs the generated unit tests for a tool.

        Returns:
        --------
        bool
            True if all tests pass, False otherwise.
        """
        full_code = f"{self.code}\n\n{self.tests}"
        
        with open("temp_test.py", "w") as f:
            f.write(full_code)
        
        result = subprocess.run(["python", "-m", "unittest", "temp_test.py"], capture_output=True, text=True)
        print(result.stdout)  # For debugging purposes
        print(result.stderr)  # For debugging purposes
        
        return result.returncode == 0

    def create_tool(self, tool_name: str, tool_description: str) -> str:
        """
        Creates a new tool by generating its design, code, and tests, and running the tests.

        Parameters:
        -----------
        tool_name : str
            The name of the tool being created.
        tool_description : str
            The description of the tool.

        Returns:
        --------
        str
            The final generated code for the tool.
        """
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
