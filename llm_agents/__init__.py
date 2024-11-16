from .config import load_environment

assert load_environment(), "Environment variables could not be loaded (no .env file found)"