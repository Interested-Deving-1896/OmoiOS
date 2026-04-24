import { BaseResource } from './base.js';
import type {
  CreateEnvironmentRequest,
  CreateEnvironmentVersionRequest,
  Environment,
  EnvironmentVersion,
} from '../types.js';

/**
 * Resource for managing environments.
 *
 * @example
 * const envs = await client.environments.list('org-1');
 * console.log(envs[0].name);
 */
export class EnvironmentsResource extends BaseResource {
  /**
   * List environments in an organization.
   *
   * @param orgId - Organization ID to filter by
   * @returns List of environments
   */
  async list(orgId: string): Promise<Environment[]> {
    const response = await this._client._request(
      'GET',
      '/api/v1/environments',
      { searchParams: { org_id: orgId } }
    );
    return (await response.json()) as Environment[];
  }

  /**
   * Get environment by ID with its latest version.
   *
   * @param environmentId - Environment ID
   * @returns Object with environment and latestVersion
   * @throws {NotFoundError} If environment doesn't exist
   */
  async get(environmentId: string): Promise<{
    environment: Environment;
    latest_version: EnvironmentVersion | null;
  }> {
    const response = await this._client._request(
      'GET',
      `/api/v1/environments/${environmentId}`
    );
    return (await response.json()) as {
      environment: Environment;
      latest_version: EnvironmentVersion | null;
    };
  }

  /**
   * Create a new environment.
   *
   * @param request - Create environment request
   * @returns Created environment
   */
  async create(request: CreateEnvironmentRequest): Promise<Environment> {
    const response = await this._client._request(
      'POST',
      '/api/v1/environments',
      { body: JSON.stringify(request) }
    );
    return (await response.json()) as Environment;
  }

  /**
   * Create a new environment version.
   *
   * @param environmentId - Environment ID
   * @param request - Create version request
   * @returns Created environment version
   * @throws {NotFoundError} If environment doesn't exist
   */
  async createVersion(
    environmentId: string,
    request: CreateEnvironmentVersionRequest
  ): Promise<EnvironmentVersion> {
    const response = await this._client._request(
      'POST',
      `/api/v1/environments/${environmentId}/versions`,
      { body: JSON.stringify(request) }
    );
    return (await response.json()) as EnvironmentVersion;
  }
}
