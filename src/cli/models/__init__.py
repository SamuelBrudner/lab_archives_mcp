"""
LabArchives MCP Server - Models Package

This package contains all data models and value objects used throughout the
LabArchives MCP Server, including configuration models, scoping models,
and other structured data representations.
"""

# Import scoping models
from .scoping import FolderPath

# Create a shared module loader to avoid class identity issues
import sys
import os
import importlib.util

# Check if the models module is already loaded
models_module_name = "labarchives_mcp_models"
if models_module_name not in sys.modules:
    models_path = os.path.join(os.path.dirname(__file__), "..", "models.py")
    models_spec = importlib.util.spec_from_file_location(models_module_name, models_path)
    models_module = importlib.util.module_from_spec(models_spec)
    models_spec.loader.exec_module(models_module)
    sys.modules[models_module_name] = models_module
else:
    models_module = sys.modules[models_module_name]

# Export configuration classes
AuthenticationConfig = models_module.AuthenticationConfig
ScopeConfig = models_module.ScopeConfig  
OutputConfig = models_module.OutputConfig
LoggingConfig = models_module.LoggingConfig
ServerConfiguration = models_module.ServerConfiguration

__all__ = [
    'FolderPath',
    'AuthenticationConfig',
    'ScopeConfig', 
    'OutputConfig',
    'LoggingConfig',
    'ServerConfiguration'
]