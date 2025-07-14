---
name: 🐞 Bug Report
about: Create a report to help us improve the LabArchives MCP Server
title: "[BUG] "
labels: ["bug", "triage"]
assignees: ''

---

## Describe the bug
A clear and concise description of what the bug is.

## Steps to reproduce
List the steps to reproduce the behavior. Include CLI commands, configuration, and any relevant context.

**Example:**
1. Go to '...'
2. Run '...'
3. See error

## Expected behavior
A clear and concise description of what you expected to happen.

## Actual behavior
What actually happened? Paste error messages, logs, or screenshots if available.

## Environment
Please provide details about your environment:

- **OS:** [e.g. Ubuntu 22.04, macOS 14.5, Windows 11]
- **Python version:** [e.g. 3.11.8, 3.12.0]
- **LabArchives MCP Server version:** [e.g. 0.1.0]
- **Deployment method:** [CLI, Docker, Claude Desktop, etc.]
- **LabArchives region:** [e.g. api.labarchives.com, auapi.labarchives.com]

## Relevant configuration
<!-- Optional: Paste relevant CLI arguments, environment variables, or configuration files -->
<!-- ⚠️ IMPORTANT: Please redact any sensitive information like API keys, passwords, or tokens -->

```bash
# Example CLI command used
labarchives-mcp --access-key-id YOUR_KEY_ID --scope notebook:12345

# Example environment variables
export LABARCHIVES_ACCESS_KEY_ID=YOUR_KEY_ID
export LABARCHIVES_API_BASE_URL=https://api.labarchives.com
```

## Relevant logs and error output
<!-- Optional: Paste any relevant log output or error messages -->
<!-- Use code blocks for readability -->

```
[2024-01-01 12:00:00] ERROR: Authentication failed
[2024-01-01 12:00:00] DEBUG: API response: 401 Unauthorized
```

## Additional context
<!-- Optional: Add any other context about the problem here -->
<!-- Include links to related issues, discussions, or documentation -->

- Related to error handling flows documented in the technical specification
- May be related to LabArchives API rate limiting or authentication issues
- Consider impact on audit logging and compliance requirements
- Link to relevant Claude Desktop integration documentation if applicable

<!-- 
This template supports the project's comprehensive error handling and recovery flows,
community-driven maintenance goals, and audit logging requirements as outlined in
the technical specifications.
-->