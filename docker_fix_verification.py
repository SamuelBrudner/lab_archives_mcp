#!/usr/bin/env python3
"""
Docker Console Script Fix Verification

This script verifies that the Docker console script bug fix is properly implemented.
The bug was that the `labarchives-mcp` command-line entrypoint was not functional 
inside the Docker container because the package wasn't installed after copying source files.

This verification checks:
1. Dockerfile contains the fix: `RUN pip install --no-cache-dir .` after COPY
2. setup.py defines the console script entry point correctly
3. The console script is functional when the package is installed
"""

import os
import sys
import subprocess
import re

def check_dockerfile_fix():
    """Verify Dockerfile contains the fix."""
    print("🔍 Checking Dockerfile for console script fix...")
    
    dockerfile_path = "src/cli/Dockerfile"
    if not os.path.exists(dockerfile_path):
        print(f"❌ ERROR: {dockerfile_path} not found")
        return False
    
    with open(dockerfile_path, 'r') as f:
        content = f.read()
    
    # Check for COPY . . command
    copy_pattern = r'COPY\s+\.\s+\.'
    copy_match = re.search(copy_pattern, content)
    if not copy_match:
        print("❌ ERROR: 'COPY . .' command not found in Dockerfile")
        return False
    
    # Check for pip install command after COPY
    lines = content.split('\n')
    copy_line_num = None
    install_line_num = None
    
    for i, line in enumerate(lines):
        if re.search(copy_pattern, line):
            copy_line_num = i
        if 'pip install --no-cache-dir .' in line:
            install_line_num = i
    
    if copy_line_num is None:
        print("❌ ERROR: COPY command not found")
        return False
    
    if install_line_num is None:
        print("❌ ERROR: 'pip install --no-cache-dir .' command not found")
        return False
    
    if install_line_num <= copy_line_num:
        print("❌ ERROR: pip install command should come AFTER COPY command")
        return False
    
    print(f"✅ COPY command found at line {copy_line_num + 1}")
    print(f"✅ pip install command found at line {install_line_num + 1}")
    print("✅ Commands are in correct order: COPY then pip install")
    return True

def check_setup_py_entry_point():
    """Verify setup.py defines the console script correctly."""
    print("\n🔍 Checking setup.py for console script entry point...")
    
    setup_py_path = "src/cli/setup.py"
    if not os.path.exists(setup_py_path):
        print(f"❌ ERROR: {setup_py_path} not found")
        return False
    
    with open(setup_py_path, 'r') as f:
        content = f.read()
    
    # Check for console_scripts entry
    if 'console_scripts' not in content:
        print("❌ ERROR: 'console_scripts' not found in setup.py")
        return False
    
    # Check for labarchives-mcp entry point
    entry_pattern = r'"labarchives-mcp=.*"'
    if not re.search(entry_pattern, content):
        print("❌ ERROR: 'labarchives-mcp' entry point not found in setup.py")
        return False
    
    print("✅ console_scripts section found")
    print("✅ labarchives-mcp entry point defined")
    return True

def check_console_script_functionality():
    """Verify the console script works when installed."""
    print("\n🔍 Checking console script functionality...")
    
    try:
        # Check if we're in the virtual environment
        venv_path = "src/cli/venv"
        if not os.path.exists(venv_path):
            print("❌ ERROR: Virtual environment not found")
            return False
        
        # Test labarchives-mcp --help
        os.chdir("src/cli")
        result = subprocess.run([
            "bash", "-c", 
            "source venv/bin/activate && labarchives-mcp --help"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ ERROR: labarchives-mcp --help failed with code {result.returncode}")
            print(f"stderr: {result.stderr}")
            return False
        
        if "LabArchives MCP Server" not in result.stdout:
            print("❌ ERROR: Console script output doesn't contain expected text")
            return False
        
        print("✅ Console script 'labarchives-mcp --help' executes successfully")
        print("✅ Console script output contains expected content")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Exception while testing console script: {e}")
        return False

def main():
    """Run all verification checks."""
    print("Docker Console Script Fix Verification")
    print("="*50)
    
    all_checks_passed = True
    
    # Run all checks
    if not check_dockerfile_fix():
        all_checks_passed = False
    
    if not check_setup_py_entry_point():
        all_checks_passed = False
    
    if not check_console_script_functionality():
        all_checks_passed = False
    
    # Final result
    print("\n" + "="*50)
    if all_checks_passed:
        print("🎉 ALL CHECKS PASSED!")
        print("✅ Docker console script bug fix is properly implemented")
        print("✅ The 'labarchives-mcp: command not found' error should be resolved")
        print("✅ Docker containers built from this Dockerfile will have working console script")
        return 0
    else:
        print("❌ SOME CHECKS FAILED!")
        print("❌ Docker console script fix needs attention")
        return 1

if __name__ == "__main__":
    sys.exit(main())