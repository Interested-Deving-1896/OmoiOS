# OmoiOS TypeScript SDK

TypeScript SDK for the OmoiOS Agent Workspace Platform.

## Installation

```bash
pnpm add @omoios/sdk
```

Or with npm:

```bash
npm install @omoios/sdk
```

## Quick Start

```typescript
import { MockOmoiOSClient } from '@omoios/sdk';

// Use mock client for development
const client = new MockOmoiOSClient();

// List credentials
const credentials = client.listCredentials();
console.log(credentials);

// Create an environment
const env = client.createEnvironment({ name: 'staging', description: 'Staging environment' });
console.log(env);
```

## Development

```bash
cd sdk/typescript
pnpm install
pnpm test
```

## API Coverage

- Credentials (CRUD)
- Environments (versioned)
- Artifacts (upload/download)
- Webhooks (subscriptions & deliveries)
- Workspaces (settings)

## License

Apache License 2.0
