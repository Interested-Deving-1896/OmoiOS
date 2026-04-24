import { BaseResource } from './base.js';
import type { CreateCredentialRequest, Credential } from '../types.js';

/**
 * Resource for managing credentials.
 *
 * @example
 * const creds = await client.credentials.list('ws-1');
 * console.log(creds[0].name);
 */
export class CredentialsResource extends BaseResource {
  /**
   * List credentials in a workspace.
   *
   * @param workspaceId - Workspace ID to filter by
   * @returns List of credentials
   */
  async list(workspaceId: string): Promise<Credential[]> {
    const response = await this._client._request(
      'GET',
      '/api/v1/credentials',
      { searchParams: { workspace_id: workspaceId } }
    );
    return (await response.json()) as Credential[];
  }

  /**
   * Get a credential by ID.
   *
   * @param credentialId - Credential ID
   * @returns Credential object
   * @throws {NotFoundError} If credential doesn't exist
   */
  async get(credentialId: string): Promise<Credential> {
    const response = await this._client._request(
      'GET',
      `/api/v1/credentials/${credentialId}`
    );
    return (await response.json()) as Credential;
  }

  /**
   * Create a new credential.
   *
   * @param request - Create credential request
   * @returns Created credential
   */
  async create(request: CreateCredentialRequest): Promise<Credential> {
    const response = await this._client._request(
      'POST',
      '/api/v1/credentials',
      { body: JSON.stringify(request) }
    );
    return (await response.json()) as Credential;
  }

  /**
   * Delete a credential.
   *
   * @param credentialId - Credential ID to delete
   * @throws {NotFoundError} If credential doesn't exist
   */
  async delete(credentialId: string): Promise<void> {
    await this._client._request('DELETE', `/api/v1/credentials/${credentialId}`);
  }
}
