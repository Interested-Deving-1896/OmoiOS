# OmoiOS Python SDK

Python SDK for the OmoiOS Agent Workspace Platform.

## Installation

```bash
pip install omoios-sdk
```

Or with uv:

```bash
uv add omoios-sdk
```

## Quick Start

```python
from omoios import MockOmoiOSClient

# Use mock client for development
client = MockOmoiOSClient()

# List credentials
credentials = client.list_credentials()
print(credentials)

# Create an environment
env = client.create_environment({"name": "staging", "description": "Staging environment"})
print(env)
```

## Development

```bash
cd sdk/python
uv sync
uv run pytest
```

## API Coverage

- Credentials (CRUD)
- Environments (versioned)
- Artifacts (upload/download)
- Webhooks (subscriptions & deliveries)
- Workspaces (settings)

## License

Apache License 2.0
