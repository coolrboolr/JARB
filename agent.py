import importlib.metadata
import os
import subprocess
import sys
import types
from typing import List
import logging

from tool_generator import ToolGenerator
from tool_library import ToolLibrary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, anthropic_api_key: str):
        self.tool_generator = ToolGenerator(anthropic_api_key)
        self.tool_library = ToolLibrary()
        self.dependency_manager = DependencyManager()
        self.user_intervention_manager = UserInterventionManager()

    def create_tool(self, name: str, description: str) -> None:
        code = self.tool_generator.create_tool(name, description)
        logger.info(f"Generated code for {name}:\n{code}")
        self._handle_dependencies(code)
        
        module = types.ModuleType(name)
        exec(code, module.__dict__)

        # Find the first function defined in the module
        function = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if callable(attr) and not attr_name.lower().startswith("test"):
                function = attr
                break

        if function:
            self.tool_library.add_tool(name, function, code)
        else:
            logger.error(f"No function found in the generated code for {name}.")

    
    def use_tool(self, tool_name: str, **kwargs):
        tool = self.tool_library.get_tool(tool_name)
        if not tool:
            raise FileNotFoundError(f"The tool {tool_name} does not exist or could not be loaded.")
        return tool(**kwargs)
    
    def _handle_dependencies(self, code: str) -> None:
        # Extract import statements from the code
        import_lines = [line for line in code.split('\n') if line.startswith('import ') or line.startswith('from ')]
        for line in import_lines:
            parts = line.split()
            if parts[0] == 'import':
                package_name = parts[1].split('.')[0]
            elif parts[0] == 'from':
                package_name = parts[1].split('.')[0]
            self.dependency_manager.install_package(package_name)


class UserInterventionManager:
    @staticmethod
    def request_decision(question: str, options: List[str]) -> str:
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

class DependencyManager:
    def __init__(self):
        self.installed_packages: List[str] = self._get_installed_packages()

    def _get_installed_packages(self) -> List[str]:
        return [pkg.metadata['Name'] for pkg in importlib.metadata.distributions()]

    def install_package(self, package_name: str) -> bool:
        if package_name in self.installed_packages:
            return True

        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            self.installed_packages.append(package_name)
            return True
        except subprocess.CalledProcessError:
            print(f"Failed to install {package_name}")
            return False
