import anthropic
import time
import subprocess
import unittest
import types
import os
import json
from typing import Dict, Any, Callable, Optional
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ToolLibrary:
    """
    A class to manage a library of tools (functions) with persistent storage.

    Attributes:
        tools (Dict[str, Callable]): A dictionary of tool names to their corresponding functions.
        storage_file (str): The file path for persistent storage of tools.
    """

    def __init__(self, storage_file: str = 'tools.json'):
        """
        Initialize the ToolLibrary.

        Args:
            storage_file (str): The file path for persistent storage of tools.
        """
        self.tools: Dict[str, Callable] = {}
        self.storage_file: str = storage_file
        self.load_tools()

    def add_tool(self, name: str, function: Callable, code: str) -> None:
        """
        Add a new tool to the library.

        Args:
            name (str): The name of the tool.
            function (Callable): The function implementing the tool.
            code (str): The source code of the function.
        """
        if name in self.tools:
            logger.warning(f"Overwriting existing tool: {name}")
        self.tools[name] = function
        logger.info(f"Added tool: {name}")
        self.save_tools(name, code)

    def get_tool(self, name: str) -> Optional[Callable]:
        """
        Retrieve a tool from the library.

        Args:
            name (str): The name of the tool to retrieve.

        Returns:
            Optional[Callable]: The tool function if found, None otherwise.
        """
        if name not in self.tools:
            self.load_tool(name)
        tool = self.tools.get(name)
        if not tool:
            logger.warning(f"Tool not found: {name}")
        return tool

    def list_tools(self) -> list:
        """
        List all tools in the library.

        Returns:
            list: A list of tool names.
        """
        return list(self.tools.keys())

    def remove_tool(self, name: str) -> None:
        """
        Remove a tool from the library.

        Args:
            name (str): The name of the tool to remove.
        """
        if name in self.tools:
            del self.tools[name]
            logger.info(f"Removed tool: {name}")
            self.save_tools()
        else:
            logger.warning(f"Cannot remove non-existent tool: {name}")

    def save_tools(self, name: Optional[str] = None, code: Optional[str] = None) -> None:
        """
        Save tools to persistent storage.

        Args:
            name (Optional[str]): The name of a specific tool to save.
            code (Optional[str]): The code of a specific tool to save.
        """
        if os.path.exists(self.storage_file):
            with open(self.storage_file, 'r') as f:
                tools_data = json.load(f)
        else:
            tools_data = {}

        if name and code:
            tools_data[name] = code

        with open(self.storage_file, 'w') as f:
            json.dump(tools_data, f, indent=2)

    def load_tools(self) -> None:
        """
        Load all tools from persistent storage.
        """
        if os.path.exists(self.storage_file):
            with open(self.storage_file, 'r') as f:
                tools_data = json.load(f)
            for name, code in tools_data.items():
                self.load_tool(name, code)

    def load_tool(self, name: str, code: Optional[str] = None) -> None:
        """
        Load a specific tool from persistent storage or provided code.

        Args:
            name (str): The name of the tool to load.
            code (Optional[str]): The code of the tool to load, if provided.
        """
        if code is None:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    tools_data = json.load(f)
                code = tools_data.get(name)
            
        if code:
            module = types.ModuleType(name)
            exec(code, module.__dict__)
            function = getattr(module, name)
            self.tools[name] = function
            logger.info(f"Loaded tool: {name}")
        else:
            logger.warning(f"Could not load tool: {name}")

class ToolGenerator:
    """
    A class to generate tools using the Anthropic API.

    Attributes:
        client (anthropic.Anthropic): The Anthropic API client.
        design (str): The current tool design.
        code (str): The current tool code.
        tests (str): The current tool tests.
        log_dir (str): The directory for logging API interactions.
    """

    def __init__(self, api_key: str, log_dir: str = 'tool_logs'):
        """
        Initialize the ToolGenerator.

        Args:
            api_key (str): The Anthropic API key.
            log_dir (str): The directory for logging API interactions.
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.design: str = ""
        self.code: str = ""
        self.tests: str = ""
        self.log_dir: str = log_dir
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def log_interaction(self, tool_name: str, stage: str, query: str, response: str) -> None:
        """
        Log an interaction with the Anthropic API.

        Args:
            tool_name (str): The name of the tool being generated.
            stage (str): The stage of tool generation (e.g., 'design', 'code').
            query (str): The query sent to the API.
            response (str): The response received from the API.
        """
        tool_log_dir = os.path.join(self.log_dir, tool_name)
        if not os.path.exists(tool_log_dir):
            os.makedirs(tool_log_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(tool_log_dir, f"{stage}_{timestamp}.json")
        
        log_data = {
            "timestamp": timestamp,
            "stage": stage,
            "query": query,
            "response": response
        }
        
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)

    def generate_design(self, tool_name: str, tool_description: str) -> str:
        """
        Generate a design for a tool using the Anthropic API.

        Args:
            tool_name (str): The name of the tool.
            tool_description (str): A description of the tool's functionality.

        Returns:
            str: The generated tool design.
        """
        query = f"Design a Python script that will execute the following function: {tool_description}"
        messages = [{"role": "human", "content": query}]

        # Initial design
        response = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            messages=messages
        )
        self.design = response.content[0].text
        self.log_interaction(tool_name, "initial_design", query, self.design)

        # Revise design 3 times
        for i in range(3):
            messages.append({"role": "assistant", "content": self.design})
            query = "Please revise and improve this design."
            messages.append({"role": "human", "content": query})
            
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                messages=messages
            )
            self.design = response.content[0].text
            self.log_interaction(tool_name, f"design_revision_{i+1}", query, self.design)

        return self.design

    def generate_code(self, tool_name: str) -> str:
        """
        Generate code for a tool using the Anthropic API.

        Args:
            tool_name (str): The name of the tool.

        Returns:
            str: The generated tool code.
        """
        query = f"Using the following design, write the Python code to implement it:\n\n{self.design}"
        messages = [{"role": "human", "content": query}]

        iteration = 1
        while True:
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2000,
                messages=messages
            )
            self.code = response.content[0].text
            self.log_interaction(tool_name, f"code_generation_{iteration}", query, self.code)

            # Try to run the code
            try:
                exec(self.code)
                break  # If no errors, exit the loop
            except Exception as e:
                messages.append({"role": "assistant", "content": self.code})
                query = f"The code resulted in an error: {str(e)}. Please fix the code and try again."
                messages.append({"role": "human", "content": query})
                iteration += 1

        return self.code

    def generate_tests(self, tool_name: str) -> str:
        """
        Generate tests for a tool using the Anthropic API.

        Args:
            tool_name (str): The name of the tool.

        Returns:
            str: The generated tool tests.
        """
        query = f"Given the following code, write 3 unit tests for it:\n\n{self.code}"
        messages = [{"role": "human", "content": query}]

        response = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            messages=messages
        )
        self.tests = response.content[0].text
        self.log_interaction(tool_name, "test_generation", query, self.tests)
        return self.tests

    def run_tests(self) -> bool:
        """
        Run the generated tests for a tool.

        Returns:
            bool: True if all tests pass, False otherwise.
        """
        # Combine code and tests
        full_code = f"{self.code}\n\n{self.tests}"
        
        # Write to a temporary file
        with open("temp_test.py", "w") as f:
            f.write(full_code)
        
        # Run the tests
        result = subprocess.run(["python", "-m", "unittest", "temp_test.py"], capture_output=True, text=True)
        
        return result.returncode == 0  # Return True if all tests pass

    def create_tool(self, tool_name: str, tool_description: str) -> str:
        """
        Create a complete tool including design, code, and tests.

        Args:
            tool_name (str): The name of the tool.
            tool_description (str): A description of the tool's functionality.

        Returns:
            str: The final generated code for the tool.
        """
        self.generate_design(tool_name, tool_description)
        self.generate_code(tool_name)
        self.generate_tests(tool_name)

        test_iteration = 1
        while not self.run_tests():
            self.generate_code(tool_name)
            self.generate_tests(tool_name)
            test_iteration += 1

        return self.code

class DependencyManager:
    """
    Manages dependencies for tools.

    Attributes:
        installed_packages (List[str]): List of currently installed packages.
    """

    def __init__(self):
        """Initialize the DependencyManager."""
        self.installed_packages: List[str] = self._get_installed_packages()

    def _get_installed_packages(self) -> List[str]:
        """Get a list of installed packages."""
        return [pkg.key for pkg in importlib.metadata.distributions()]

    def install_package(self, package_name: str) -> bool:
        """
        Install a package using pip.

        Args:
            package_name (str): The name of the package to install.

        Returns:
            bool: True if installation was successful, False otherwise.
        """
        if package_name in self.installed_packages:
            return True

        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            self.installed_packages.append(package_name)
            return True
        except subprocess.CalledProcessError:
            print(f"Failed to install {package_name}")
            return False

class UserInterventionManager:
    """Manages user interventions during tool creation and execution."""

    @staticmethod
    def request_decision(question: str, options: List[str]) -> str:
        """
        Request a decision from the user.

        Args:
            question (str): The question to ask the user.
            options (List[str]): A list of possible options.

        Returns:
            str: The user's chosen option.
        """
        print(question)
        for i, option in enumerate(options, 1):
            print(f"{i}. {option}")
        
        while True:
            try:
                choice = int(input("Enter the number of your choice: "))
                if 1 <= choice <= len(options):
                    return options[choice - 1]
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a number.")

class Agent:
    """
    An agent that manages tool creation and usage.

    Attributes:
        tool_generator (ToolGenerator): The tool generator instance.
        tool_library (ToolLibrary): The tool library instance.
        dependency_manager (DependencyManager): The dependency manager instance.
        user_intervention_manager (UserInterventionManager): The user intervention manager instance.
    """

    def __init__(self, anthropic_api_key: str):
        """
        Initialize the Agent.

        Args:
            anthropic_api_key (str): The Anthropic API key.
        """
        self.tool_generator = ToolGenerator(anthropic_api_key)
        self.tool_library = ToolLibrary()
        self.dependency_manager = DependencyManager()
        self.user_intervention_manager = UserInterventionManager()

    def create_tool(self, name: str, description: str) -> None:
        """
        Create a new tool and add it to the tool library.

        Args:
            name (str): The name of the tool.
            description (str): A description of the tool's functionality.
        """
        code = self.tool_generator.create_tool(name, description)
        
        # Check for imports and install dependencies
        self._handle_dependencies(code)
        
        # Create a new module to execute the code in
        module = types.ModuleType(name)
        exec(code, module.__dict__)
        
        # Get the function from the module
        function = getattr(module, name)
        
        # Add the function to the tool library
        self.tool_library.add_tool(name, function, code)

    def _handle_dependencies(self, code: str) -> None:
        """
        Handle dependencies for the generated code.

        Args:
            code (str): The generated code to check for dependencies.
        """
        import_lines = [line.strip() for line in code.split('\n') if line.strip().startswith('import') or line.strip().startswith('from')]
        for line in import_lines:
            package = line.split()[1].split('.')[0]
            if package not in self.dependency_manager.installed_packages:
                decision = self.user_intervention_manager.request_decision(
                    f"The tool requires the '{package}' package. Do you want to install it?",
                    ["Yes", "No"]
                )
                if decision == "Yes":
                    self.dependency_manager.install_package(package)
                else:
                    print(f"Warning: The tool may not function correctly without the '{package}' package.")

    def use_tool(self, name: str, *args: Any, **kwargs: Any) -> Union[Any, None]:
        """
        Use a tool from the tool library.

        Args:
            name (str): The name of the tool to use.
            *args: Positional arguments to pass to the tool.
            **kwargs: Keyword arguments to pass to the tool.

        Returns:
            Union[Any, None]: The result of the tool execution, or None if execution failed.
        """
        tool = self.tool_library.get_tool(name)
        if tool:
            try:
                return tool(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error using tool {name}: {str(e)}")
                decision = self.user_intervention_manager.request_decision(
                    f"An error occurred while using the '{name}' tool. What would you like to do?",
                    ["Retry", "Debug", "Skip"]
                )
                if decision == "Retry":
                    return self.use_tool(name, *args, **kwargs)
                elif decision == "Debug":
                    print(f"Debug information for '{name}':")
                    print(f"Error: {str(e)}")
                    print(f"Tool code:\n{self.tool_library.get_tool_code(name)}")
                    return None
                else:
                    return None
        else:
            raise ValueError(f"Tool '{name}' not found in the library.")

# Example usage
if __name__ == "__main__":
    agent = Agent("your_anthropic_api_key_here")
    
    # Create a new tool
    agent.create_tool(
        "advanced_math",
        "Create a function that performs advanced mathematical operations using the numpy library"
    )
    
    # Use the tool
    result = agent.use_tool("advanced_math", operation="matrix_multiplication", matrix1=[[1, 2], [3, 4]], matrix2=[[5, 6], [7, 8]])
    if result is not None:
        print(f"Result of matrix multiplication: {result}")

    # List all tools
    print("Available tools:", agent.list_tools())