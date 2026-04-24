/**
 * Tests for mock client.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { MockOmoiOSClient } from '../src/mockClient.js';
import { NotFoundError } from '../src/errors.js';
import type {
  BindingKind,
  CreateCredentialRequest,
  CreateEnvironmentRequest,
  CreateEnvironmentVersionRequest,
  CreateWebhookRequest,
  EnvironmentVariable,
  VariableType,
  WebhookEvent,
} from '../src/types.js';

describe('MockOmoiOSClient - Credentials', () => {
  it('listCredentials returns array of credentials', () => {
    const client = new MockOmoiOSClient();
    const creds = client.listCredentials();

    expect(Array.isArray(creds)).toBe(true);
    expect(creds.length).toBeGreaterThan(0);
    expect(creds[0].kind).toBe('bearer_secret');
    expect(creds[0].name).toBe('test-api-key');
  });

  it('listCredentials filters by workspaceId', () => {
    const client = new MockOmoiOSClient();
    const creds = client.listCredentials('ws_1');

    expect(creds.every((c) => c.workspace_id === 'ws_1')).toBe(true);
  });

  it('getCredential returns credential by id', () => {
    const client = new MockOmoiOSClient();
    const cred = client.getCredential('cred_1');

    expect(cred.id).toBe('cred_1');
    expect(cred.kind).toBe('bearer_secret');
    expect(typeof cred.created_at).toBe('string');
  });

  it('getCredential throws NotFoundError for invalid id', () => {
    const client = new MockOmoiOSClient();
    expect(() => client.getCredential('invalid_id')).toThrow(NotFoundError);
  });

  it('createCredential returns new credential', () => {
    const client = new MockOmoiOSClient();
    const request: CreateCredentialRequest = {
      kind: 'user_oauth' as BindingKind,
      name: 'oauth-token',
      value: 'secret-value',
      workspace_id: 'ws_1',
    };
    const cred = client.createCredential(request);

    expect(cred.kind).toBe('user_oauth');
    expect(cred.name).toBe('oauth-token');
    expect(cred.workspace_id).toBe('ws_1');
    expect(cred.id.startsWith('cred_')).toBe(true);
    expect(typeof cred.created_at).toBe('string');
  });

  it('deleteCredential removes credential', () => {
    const client = new MockOmoiOSClient();
    const request: CreateCredentialRequest = {
      kind: 'bearer_secret' as BindingKind,
      name: 'to-delete',
      value: 'secret',
    };
    const cred = client.createCredential(request);

    client.deleteCredential(cred.id);

    expect(() => client.getCredential(cred.id)).toThrow(NotFoundError);
  });
});

describe('MockOmoiOSClient - Environments', () => {
  it('listEnvironments returns array of environments', () => {
    const client = new MockOmoiOSClient();
    const envs = client.listEnvironments();

    expect(Array.isArray(envs)).toBe(true);
    expect(envs.length).toBeGreaterThan(0);
    expect(envs[0].name).toBe('staging');
  });

  it('getEnvironment returns environment with latest version', () => {
    const client = new MockOmoiOSClient();
    const result = client.getEnvironment('env_1');

    expect(result.environment.id).toBe('env_1');
    expect(result.latestVersion).not.toBeNull();
    expect(result.latestVersion?.environment_id).toBe('env_1');
  });

  it('getEnvironment throws NotFoundError for invalid id', () => {
    const client = new MockOmoiOSClient();
    expect(() => client.getEnvironment('invalid_id')).toThrow(NotFoundError);
  });

  it('createEnvironment returns new environment', () => {
    const client = new MockOmoiOSClient();
    const request: CreateEnvironmentRequest = {
      name: 'production',
      description: 'Production environment',
    };
    const env = client.createEnvironment(request);

    expect(env.name).toBe('production');
    expect(env.description).toBe('Production environment');
    expect(env.id.startsWith('env_')).toBe(true);
    expect(typeof env.created_at).toBe('string');
  });

  it('createEnvironmentVersion returns new version', () => {
    const client = new MockOmoiOSClient();
    const envRequest: CreateEnvironmentRequest = { name: 'test-env' };
    const env = client.createEnvironment(envRequest);

    const versionRequest: CreateEnvironmentVersionRequest = {
      variables: {
        VAR1: { type: 'string' as VariableType, value: 'value1' },
        SECRET: { type: 'secret' as VariableType, value: '***' },
      },
    };
    const version = client.createEnvironmentVersion(env.id, versionRequest);

    expect(version.environment_id).toBe(env.id);
    expect(version.version_number).toBe(1);
    expect(version.variables.VAR1.type).toBe('string');
  });

  it('createEnvironmentVersion increments version numbers', () => {
    const client = new MockOmoiOSClient();
    const env = client.createEnvironment({ name: 'versioned-env' });

    const v1 = client.createEnvironmentVersion(env.id, {
      variables: { V: { type: 'string' as VariableType, value: '1' } },
    });
    const v2 = client.createEnvironmentVersion(env.id, {
      variables: { V: { type: 'string' as VariableType, value: '2' } },
    });

    expect(v1.version_number).toBe(1);
    expect(v2.version_number).toBe(2);
  });
});

describe('MockOmoiOSClient - Artifacts', () => {
  it('uploadArtifact returns artifact', () => {
    const client = new MockOmoiOSClient();
    const content = Buffer.from('test file content');
    const artifact = client.uploadArtifact(content, 'ws_1');

    expect(artifact.workspace_id).toBe('ws_1');
    expect(artifact.size_bytes).toBe(content.length);
    expect(artifact.checksum.startsWith('sha256:')).toBe(true);
    expect(artifact.id.startsWith('art_')).toBe(true);
  });

  it('listArtifacts returns array of artifacts', () => {
    const client = new MockOmoiOSClient();
    const artifacts = client.listArtifacts();

    expect(Array.isArray(artifacts)).toBe(true);
    expect(artifacts.length).toBeGreaterThan(0);
  });

  it('listArtifacts filters by workspaceId', () => {
    const client = new MockOmoiOSClient();
    const artifacts = client.listArtifacts('ws_1');

    expect(artifacts.every((a) => a.workspace_id === 'ws_1')).toBe(true);
  });

  it('getArtifact returns artifact by id', () => {
    const client = new MockOmoiOSClient();
    const artifact = client.getArtifact('art_1');

    expect(artifact.id).toBe('art_1');
    expect(artifact.name).toBe('test-file.txt');
  });

  it('getArtifact throws NotFoundError for invalid id', () => {
    const client = new MockOmoiOSClient();
    expect(() => client.getArtifact('invalid_id')).toThrow(NotFoundError);
  });

  it('downloadArtifact returns buffer', () => {
    const client = new MockOmoiOSClient();
    const content = client.downloadArtifact('art_1');

    expect(Buffer.isBuffer(content)).toBe(true);
  });

  it('deleteArtifact removes artifact', () => {
    const client = new MockOmoiOSClient();
    const artifact = client.uploadArtifact(Buffer.from('content'), 'ws_1');

    client.deleteArtifact(artifact.id);

    expect(() => client.getArtifact(artifact.id)).toThrow(NotFoundError);
  });
});

describe('MockOmoiOSClient - Webhooks', () => {
  it('listWebhooks returns array of subscriptions', () => {
    const client = new MockOmoiOSClient();
    const webhooks = client.listWebhooks();

    expect(Array.isArray(webhooks)).toBe(true);
    expect(webhooks.length).toBeGreaterThan(0);
    expect(webhooks[0].url).toBe('https://example.com/webhook');
  });

  it('createWebhook returns new subscription', () => {
    const client = new MockOmoiOSClient();
    const request: CreateWebhookRequest = {
      url: 'https://myapp.com/webhook',
      events: ['spec.created' as WebhookEvent, 'task.started' as WebhookEvent],
      secret: 'webhook-secret',
    };
    const webhook = client.createWebhook(request);

    expect(webhook.url).toBe('https://myapp.com/webhook');
    expect(webhook.events).toContain('spec.created');
    expect(webhook.active).toBe(true);
    expect(webhook.id.startsWith('wh_')).toBe(true);
  });

  it('deleteWebhook removes webhook', () => {
    const client = new MockOmoiOSClient();
    const request: CreateWebhookRequest = {
      url: 'https://temp.com/webhook',
      events: ['task.completed' as WebhookEvent],
      secret: 'secret',
    };
    const webhook = client.createWebhook(request);

    client.deleteWebhook(webhook.id);

    const webhooks = client.listWebhooks();
    expect(webhooks.some((w) => w.id === webhook.id)).toBe(false);
  });

  it('listWebhookDeliveries returns array of deliveries', () => {
    const client = new MockOmoiOSClient();
    const deliveries = client.listWebhookDeliveries('wh_1');

    expect(Array.isArray(deliveries)).toBe(true);
    expect(deliveries.length).toBeGreaterThan(0);
    expect(deliveries[0].subscription_id).toBe('wh_1');
  });

  it('listWebhookDeliveries throws NotFoundError for invalid id', () => {
    const client = new MockOmoiOSClient();
    expect(() => client.listWebhookDeliveries('invalid_id')).toThrow(NotFoundError);
  });
});

describe('MockOmoiOSClient - Workspace Settings', () => {
  it('getWorkspaceSettings returns settings', () => {
    const client = new MockOmoiOSClient();
    const settings = client.getWorkspaceSettings('ws_1');

    expect(settings.workspace_id).toBe('ws_1');
    expect(settings.max_artifact_size_mb).toBe(100);
    expect(settings.egress_allowlist).toContain('api.github.com');
    expect(settings.allowed_binding_kinds).toContain('bearer_secret');
  });

  it('getWorkspaceSettings throws NotFoundError for invalid id', () => {
    const client = new MockOmoiOSClient();
    expect(() => client.getWorkspaceSettings('invalid_id')).toThrow(NotFoundError);
  });
});
