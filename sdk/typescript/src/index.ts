/**
 * OmoiOS SDK - TypeScript client for the OmoiOS Agent Workspace Platform.
 */

// Types
export type {
  BindingKind,
  Credential,
  CreateCredentialRequest,
  VariableType,
  EnvironmentVariable,
  Environment,
  EnvironmentVersion,
  CreateEnvironmentRequest,
  CreateEnvironmentVersionRequest,
  Artifact,
  WebhookEvent,
  WebhookSubscription,
  WebhookDelivery,
  CreateWebhookRequest,
  WorkspaceSettings,
} from './types.js';

// Client
export { OmoiOSClient } from './client.js';
export { MockOmoiOSClient } from './mockClient.js';

// Errors
export {
  OmoiOSError,
  AuthError,
  NotFoundError,
  ValidationError,
  ServerError,
} from './errors.js';
