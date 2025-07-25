"""
LabArchives MCP Server - Models Package

This package contains all data models and value objects used throughout the
LabArchives MCP Server, including configuration models, scoping models,
and other structured data representations.
"""

# Import scoping models
from .scoping import FolderPath

# Import configuration models
import os
import importlib.util

# Load models.py to get configuration classes
models_path = os.path.join(os.path.dirname(__file__), "..", "models.py")
models_spec = importlib.util.spec_from_file_location("config_models", models_path)
config_models = importlib.util.module_from_spec(models_spec)
models_spec.loader.exec_module(config_models)

# Export configuration classes
AuthenticationConfig = config_models.AuthenticationConfig
ScopeConfig = config_models.ScopeConfig  
OutputConfig = config_models.OutputConfig
LoggingConfig = config_models.LoggingConfig
ServerConfiguration = config_models.ServerConfiguration

__all__ = [
    'FolderPath',
    'AuthenticationConfig',
    'ScopeConfig', 
    'OutputConfig',
    'LoggingConfig',
    'ServerConfiguration'
]