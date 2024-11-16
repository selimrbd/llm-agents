import os
from pathlib import Path

from dotenv import load_dotenv

class MissingEnvironmentVariableError(Exception):

    def __init__(self, variable_name: str):
        self.variable_name = variable_name
        super().__init__(
            f"The environment variable '{variable_name}' is required but not set."
        )

def load_environment():
    """
    Load environment variables from .env file.
    Searches for .env file in the parent directories until root.
    """
    current_dir = Path.cwd()
    
    while current_dir != current_dir.parent:
        env_file = current_dir / '.env'
        if env_file.exists():
            load_dotenv(dotenv_path=env_file)
            return True
        current_dir = current_dir.parent
    
    return False

def get_environment_variable(variable_name: str) -> str:
    variable = os.getenv(variable_name)
    if variable is None:
        raise MissingEnvironmentVariableError(variable_name)
    return variable

