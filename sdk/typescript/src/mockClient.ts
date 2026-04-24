import { NotFoundError } from './errors.js';
import type {
  Artifact,
  BindingKind,
  CreateCredentialRequest,
  CreateEnvironmentRequest,
  CreateEnvironmentVersionRequest,
  CreateWebhookRequest,
  Credential,
  Environment,
  EnvironmentVersion,
  GetEnvironmentResult,
  VariableType,
  WebhookDelivery,
  WebhookEvent,
  WebhookSubscription,
  WorkspaceSettings,
} from './types.js';
import { randomUUID, createHash } from 'crypto';

/**
 * Mock client that returns fixture data.
 *
 * Use this for development while the backend is being built.
 * All methods return typed fixture data.
 */
export class MockOmoiOSClient {
  private credentials: Map<string, Credential> = new Map();
  private environments: Map<string, Environment> = new Map();
  private environmentVersions: Map<string, EnvironmentVersion[]> = new Map();
  private artifacts: Map<string, Artifact> = new Map();
  private webhooks: Map<string, WebhookSubscription> = new Map();
  private webhookDeliveries: Map<string, WebhookDelivery[]> = new Map();
  private workspaceSettings: Map<string, WorkspaceSettings> = new Map();

  constructor() {
    this.initFixtures();
  }

  private initFixtures(): void {
    const now = new Date().toISOString();

    const cred: Credential = {
      id: 'cred_1',
      workspace_id: 'ws_1',
      kind: 'bearer_secret',
      name: 'test-api-key',
      created_at: now,
      rotated_at: null,
    };
    this.credentials.set(cred.id, cred);

    const env: Environment = {
      id: 'env_1',
      org_id: 'org_1',
      name: 'staging',
      description: 'Staging environment',
      created_at: now,
      updated_at: now,
    };
    this.environments.set(env.id, env);

    const version: EnvironmentVersion = {
      id: 'ver_1',
      environment_id: env.id,
      version_number: 1,
      variables: {
        DB_URL: { type: 'string' as VariableType, value: 'postgres://localhost:5432/staging' },
        API_KEY: { type: 'secret' as VariableType, value: '***' },
      },
      created_at: now,
    };
    this.environmentVersions.set(env.id, [version]);

    const artifact: Artifact = {
      id: 'art_1',
      workspace_id: 'ws_1',
      name: 'test-file.txt',
      storage_backend: 'local',
      storage_path: '/artifacts/art_1',
      checksum: 'sha256:' + 'a'.repeat(64),
      size_bytes: 1024,
      content_type: 'text/plain',
      artifact_metadata: { source: 'test' },
      created_at: now,
      updated_at: now,
    };
    this.artifacts.set(artifact.id, artifact);

    const webhook: WebhookSubscription = {
      id: 'wh_1',
      org_id: 'org_1',
      url: 'https://example.com/webhook',
      events: ['task.completed' as WebhookEvent, 'artifact.uploaded' as WebhookEvent],
      active: true,
      created_at: now,
    };
    this.webhooks.set(webhook.id, webhook);

    const delivery: WebhookDelivery = {
      id: 'wd_1',
      subscription_id: webhook.id,
      event: 'task.completed' as WebhookEvent,
      payload: { task_id: 'task_1', status: 'success' },
      status: 'delivered',
      attempts: 1,
      next_retry_at: null,
      created_at: now,
    };
    this.webhookDeliveries.set(webhook.id, [delivery]);

    const settings: WorkspaceSettings = {
      id: 'ws_settings_1',
      workspace_id: 'ws_1',
      egress_allowlist: ['api.github.com', 'pypi.org'],
      max_artifact_size_mb: 100,
      allowed_binding_kinds: ['bearer_secret' as BindingKind, 'user_oauth' as BindingKind],
    };
    this.workspaceSettings.set(settings.workspace_id, settings);
  }

  private generateId(prefix: string): string {
    return `${prefix}_${randomUUID().replace(/-/g, '').slice(0, 8)}`;
  }

  listCredentials(workspaceId?: string): Credential[] {
    const creds = Array.from(this.credentials.values());
    if (workspaceId) {
      return creds.filter((c) => c.workspace_id === workspaceId);
    }
    return creds;
  }

  getCredential(credentialId: string): Credential {
    const cred = this.credentials.get(credentialId);
    if (!cred) {
      throw new NotFoundError(`Credential not found: ${credentialId}`);
    }
    return cred;
  }

  createCredential(request: CreateCredentialRequest): Credential {
    const now = new Date().toISOString();
    const cred: Credential = {
      id: this.generateId('cred'),
      workspace_id: request.workspace_id ?? 'ws_1',
      kind: request.kind,
      name: request.name,
      created_at: now,
      rotated_at: null,
    };
    this.credentials.set(cred.id, cred);
    return cred;
  }

  deleteCredential(credentialId: string): void {
    if (!this.credentials.has(credentialId)) {
      throw new NotFoundError(`Credential not found: ${credentialId}`);
    }
    this.credentials.delete(credentialId);
  }

  listEnvironments(): Environment[] {
    return Array.from(this.environments.values());
  }

  getEnvironment(environmentId: string): GetEnvironmentResult {
    const env = this.environments.get(environmentId);
    if (!env) {
      throw new NotFoundError(`Environment not found: ${environmentId}`);
    }
    const versions = this.environmentVersions.get(environmentId) ?? [];
    const latest = versions[versions.length - 1] ?? null;
    return { environment: env, latestVersion: latest };
  }

  createEnvironment(request: CreateEnvironmentRequest): Environment {
    const now = new Date().toISOString();
    const env: Environment = {
      id: this.generateId('env'),
      org_id: 'org_1',
      name: request.name,
      description: request.description ?? null,
      created_at: now,
      updated_at: now,
    };
    this.environments.set(env.id, env);
    this.environmentVersions.set(env.id, []);
    return env;
  }

  createEnvironmentVersion(
    environmentId: string,
    request: CreateEnvironmentVersionRequest
  ): EnvironmentVersion {
    if (!this.environments.has(environmentId)) {
      throw new NotFoundError(`Environment not found: ${environmentId}`);
    }

    const versions = this.environmentVersions.get(environmentId) ?? [];
    const versionNumber = versions.length + 1;

    const now = new Date().toISOString();
    const version: EnvironmentVersion = {
      id: this.generateId('ver'),
      environment_id: environmentId,
      version_number: versionNumber,
      variables: request.variables,
      created_at: now,
    };
    versions.push(version);
    this.environmentVersions.set(environmentId, versions);
    return version;
  }

  uploadArtifact(fileContent: Buffer, workspaceId?: string): Artifact {
    const now = new Date().toISOString();
    const artifactId = this.generateId('art');
    const checksum = createHash('sha256').update(fileContent).digest('hex');

    const artifact: Artifact = {
      id: artifactId,
      workspace_id: workspaceId ?? 'ws_1',
      name: 'uploaded-file.bin',
      storage_backend: 'local',
      storage_path: `/artifacts/${artifactId}`,
      checksum: `sha256:${checksum}`,
      size_bytes: fileContent.length,
      content_type: 'application/octet-stream',
      artifact_metadata: null,
      created_at: now,
      updated_at: now,
    };
    this.artifacts.set(artifact.id, artifact);
    return artifact;
  }

  listArtifacts(workspaceId?: string): Artifact[] {
    const artifacts = Array.from(this.artifacts.values());
    if (workspaceId) {
      return artifacts.filter((a) => a.workspace_id === workspaceId);
    }
    return artifacts;
  }

  getArtifact(artifactId: string): Artifact {
    const artifact = this.artifacts.get(artifactId);
    if (!artifact) {
      throw new NotFoundError(`Artifact not found: ${artifactId}`);
    }
    return artifact;
  }

  downloadArtifact(artifactId: string): Buffer {
    if (!this.artifacts.has(artifactId)) {
      throw new NotFoundError(`Artifact not found: ${artifactId}`);
    }
    return Buffer.from('mock artifact content');
  }

  deleteArtifact(artifactId: string): void {
    if (!this.artifacts.has(artifactId)) {
      throw new NotFoundError(`Artifact not found: ${artifactId}`);
    }
    this.artifacts.delete(artifactId);
  }

  listWebhooks(): WebhookSubscription[] {
    return Array.from(this.webhooks.values());
  }

  createWebhook(request: CreateWebhookRequest): WebhookSubscription {
    const now = new Date().toISOString();
    const webhook: WebhookSubscription = {
      id: this.generateId('wh'),
      org_id: 'org_1',
      url: request.url,
      events: request.events,
      active: true,
      created_at: now,
    };
    this.webhooks.set(webhook.id, webhook);
    this.webhookDeliveries.set(webhook.id, []);
    return webhook;
  }

  deleteWebhook(webhookId: string): void {
    if (!this.webhooks.has(webhookId)) {
      throw new NotFoundError(`Webhook not found: ${webhookId}`);
    }
    this.webhooks.delete(webhookId);
    this.webhookDeliveries.delete(webhookId);
  }

  listWebhookDeliveries(subscriptionId: string): WebhookDelivery[] {
    if (!this.webhooks.has(subscriptionId)) {
      throw new NotFoundError(`Webhook subscription not found: ${subscriptionId}`);
    }
    return this.webhookDeliveries.get(subscriptionId) ?? [];
  }

  getWorkspaceSettings(workspaceId: string): WorkspaceSettings {
    const settings = this.workspaceSettings.get(workspaceId);
    if (!settings) {
      throw new NotFoundError(`Workspace not found: ${workspaceId}`);
    }
    return settings;
  }
}
