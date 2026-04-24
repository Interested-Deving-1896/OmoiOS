/**
 * Abstract base client for OmoiOS API.
 */

import type {
  Artifact,
  CreateCredentialRequest,
  CreateEnvironmentRequest,
  CreateEnvironmentVersionRequest,
  CreateWebhookRequest,
  Credential,
  Environment,
  EnvironmentVersion,
  WebhookDelivery,
  WebhookSubscription,
  WorkspaceSettings,
} from './types.js';

/** Result of getEnvironment call. */
export interface GetEnvironmentResult {
  environment: Environment;
  latestVersion: EnvironmentVersion | null;
}

/**
 * Abstract base class for OmoiOS API clients.
 *
 * Implementations must provide concrete methods for all API operations.
 * This base class defines the interface for both real and mock clients.
 */
export abstract class OmoiOSClient {
  /** API base URL */
  protected readonly baseUrl: string;
  /** Optional API key for authentication */
  protected readonly apiKey?: string;

  /**
   * Initialize the client.
   * @param baseUrl - API base URL
   * @param apiKey - Optional API key for authentication
   */
  constructor(baseUrl: string, apiKey?: string) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  // Credentials

  /**
   * List credentials.
   * @param workspaceId - Optional workspace ID to filter by
   * @returns List of credentials
   */
  abstract listCredentials(workspaceId?: string): Credential[];

  /**
   * Get a credential by ID.
   * @param credentialId - Credential ID
   * @returns Credential object
   * @throws {NotFoundError} If credential doesn't exist
   */
  abstract getCredential(credentialId: string): Credential;

  /**
   * Create a new credential.
   * @param request - Create credential request
   * @returns Created credential
   */
  abstract createCredential(request: CreateCredentialRequest): Credential;

  /**
   * Delete a credential.
   * @param credentialId - Credential ID to delete
   * @throws {NotFoundError} If credential doesn't exist
   */
  abstract deleteCredential(credentialId: string): void;

  // Environments

  /**
   * List all environments.
   * @returns List of environments
   */
  abstract listEnvironments(): Environment[];

  /**
   * Get environment with latest version.
   * @param environmentId - Environment ID
   * @returns Object with environment and latestVersion
   * @throws {NotFoundError} If environment doesn't exist
   */
  abstract getEnvironment(environmentId: string): GetEnvironmentResult;

  /**
   * Create a new environment.
   * @param request - Create environment request
   * @returns Created environment
   */
  abstract createEnvironment(request: CreateEnvironmentRequest): Environment;

  /**
   * Create a new environment version.
   * @param environmentId - Environment ID
   * @param request - Create version request
   * @returns Created environment version
   * @throws {NotFoundError} If environment doesn't exist
   */
  abstract createEnvironmentVersion(
    environmentId: string,
    request: CreateEnvironmentVersionRequest
  ): EnvironmentVersion;

  // Artifacts

  /**
   * Upload an artifact.
   * @param fileContent - Raw file bytes
   * @param workspaceId - Optional workspace ID
   * @returns Created artifact
   */
  abstract uploadArtifact(
    fileContent: Buffer,
    workspaceId?: string
  ): Artifact;

  /**
   * List artifacts.
   * @param workspaceId - Optional workspace ID to filter by
   * @returns List of artifacts
   */
  abstract listArtifacts(workspaceId?: string): Artifact[];

  /**
   * Get an artifact by ID.
   * @param artifactId - Artifact ID
   * @returns Artifact object
   * @throws {NotFoundError} If artifact doesn't exist
   */
  abstract getArtifact(artifactId: string): Artifact;

  /**
   * Download artifact content.
   * @param artifactId - Artifact ID
   * @returns Raw file bytes
   * @throws {NotFoundError} If artifact doesn't exist
   */
  abstract downloadArtifact(artifactId: string): Buffer;

  /**
   * Delete an artifact.
   * @param artifactId - Artifact ID to delete
   * @throws {NotFoundError} If artifact doesn't exist
   */
  abstract deleteArtifact(artifactId: string): void;

  // Webhooks

  /**
   * List webhook subscriptions.
   * @returns List of webhook subscriptions
   */
  abstract listWebhooks(): WebhookSubscription[];

  /**
   * Create a webhook subscription.
   * @param request - Create webhook request
   * @returns Created webhook subscription
   */
  abstract createWebhook(request: CreateWebhookRequest): WebhookSubscription;

  /**
   * Delete a webhook subscription.
   * @param webhookId - Webhook ID to delete
   * @throws {NotFoundError} If webhook doesn't exist
   */
  abstract deleteWebhook(webhookId: string): void;

  /**
   * List webhook deliveries for a subscription.
   * @param subscriptionId - Subscription ID
   * @returns List of webhook deliveries
   * @throws {NotFoundError} If subscription doesn't exist
   */
  abstract listWebhookDeliveries(subscriptionId: string): WebhookDelivery[];

  // Workspace Settings

  /**
   * Get workspace settings.
   * @param workspaceId - Workspace ID
   * @returns Workspace settings
   * @throws {NotFoundError} If workspace doesn't exist
   */
  abstract getWorkspaceSettings(workspaceId: string): WorkspaceSettings;
}
