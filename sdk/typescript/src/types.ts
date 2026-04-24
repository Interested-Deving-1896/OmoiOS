/**
 * TypeScript types for OmoiOS API.
 */

/** Credential binding kinds. */
export type BindingKind = 'bearer_secret' | 'user_oauth' | 'github_app';

/** Environment variable types. */
export type VariableType = 'string' | 'secret' | 'json';

/** Webhook event types. */
export type WebhookEvent =
  | 'spec.created'
  | 'task.started'
  | 'task.completed'
  | 'session.created'
  | 'artifact.uploaded';

/** Credential resource. */
export interface Credential {
  /** Unique identifier */
  id: string;
  /** Workspace ID */
  workspace_id: string;
  /** Credential binding kind */
  kind: BindingKind;
  /** User-friendly name */
  name: string;
  /** Creation timestamp (ISO 8601) */
  created_at: string;
  /** Last rotation timestamp (ISO 8601) */
  rotated_at?: string | null;
}

/** Request to create a credential. */
export interface CreateCredentialRequest {
  /** Credential binding kind */
  kind: BindingKind;
  /** User-friendly name */
  name: string;
  /** Credential value (encrypted at rest) */
  value: string;
  /** Workspace ID (optional) */
  workspace_id?: string;
}

/** Environment variable definition. */
export interface EnvironmentVariable {
  /** Variable type */
  type: VariableType;
  /** Variable value */
  value: string | Record<string, unknown>;
}

/** Environment resource. */
export interface Environment {
  /** Unique identifier */
  id: string;
  /** Organization ID */
  org_id: string;
  /** Environment name */
  name: string;
  /** Optional description */
  description?: string | null;
  /** Creation timestamp (ISO 8601) */
  created_at: string;
  /** Last update timestamp (ISO 8601) */
  updated_at: string;
}

/** Environment version (immutable snapshot). */
export interface EnvironmentVersion {
  /** Unique identifier */
  id: string;
  /** Parent environment ID */
  environment_id: string;
  /** Version number (1, 2, 3...) */
  version_number: number;
  /** Environment variables */
  variables: Record<string, EnvironmentVariable>;
  /** Creation timestamp (ISO 8601) */
  created_at: string;
}

/** Request to create an environment. */
export interface CreateEnvironmentRequest {
  /** Environment name */
  name: string;
  /** Optional description */
  description?: string;
}

/** Request to create an environment version. */
export interface CreateEnvironmentVersionRequest {
  /** Environment variables */
  variables: Record<string, EnvironmentVariable>;
}

/** Artifact resource. */
export interface Artifact {
  /** Unique identifier */
  id: string;
  /** Workspace ID */
  workspace_id: string;
  /** Artifact name */
  name: string;
  /** Storage backend (local, s3) */
  storage_backend: string;
  /** Storage path */
  storage_path: string;
  /** SHA-256 checksum */
  checksum: string;
  /** File size in bytes */
  size_bytes: number;
  /** MIME content type */
  content_type?: string | null;
  /** Additional metadata */
  artifact_metadata?: Record<string, unknown> | null;
  /** Creation timestamp (ISO 8601) */
  created_at: string;
  /** Last update timestamp (ISO 8601) */
  updated_at: string;
}

/** Webhook subscription resource. */
export interface WebhookSubscription {
  /** Unique identifier */
  id: string;
  /** Organization ID */
  org_id: string;
  /** Webhook URL */
  url: string;
  /** Subscribed events */
  events: WebhookEvent[];
  /** Whether subscription is active */
  active: boolean;
  /** Creation timestamp (ISO 8601) */
  created_at: string;
}

/** Webhook delivery record. */
export interface WebhookDelivery {
  /** Unique identifier */
  id: string;
  /** Parent subscription ID */
  subscription_id: string;
  /** Event type */
  event: WebhookEvent;
  /** Event payload */
  payload: Record<string, unknown>;
  /** Delivery status */
  status: string;
  /** Number of delivery attempts */
  attempts: number;
  /** Next retry timestamp (ISO 8601) */
  next_retry_at?: string | null;
  /** Creation timestamp (ISO 8601) */
  created_at: string;
}

/** Request to create a webhook subscription. */
export interface CreateWebhookRequest {
  /** Webhook URL */
  url: string;
  /** Events to subscribe to */
  events: WebhookEvent[];
  /** Secret for signature verification */
  secret: string;
}

/** Workspace settings resource. */
export interface WorkspaceSettings {
  /** Unique identifier */
  id: string;
  /** Workspace ID */
  workspace_id: string;
  /** Allowed egress hostnames */
  egress_allowlist: string[];
  /** Maximum artifact size in MB */
  max_artifact_size_mb: number;
  /** Allowed credential binding kinds */
  allowed_binding_kinds: BindingKind[];
}
