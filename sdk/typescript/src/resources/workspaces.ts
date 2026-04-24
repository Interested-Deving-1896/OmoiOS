import { BaseResource } from './base.js';
import type { UpdateWorkspaceSettingsRequest, WorkspaceSettings } from '../types.js';

/**
 * Resource for managing workspace settings.
 *
 * @example
 * const settings = await client.workspaces.getSettings('ws-1');
 * console.log(settings.egress_allowlist);
 */
export class WorkspacesResource extends BaseResource {
  /**
   * Get workspace settings.
   *
   * @param workspaceId - Workspace ID
   * @returns Workspace settings
   * @throws {NotFoundError} If workspace doesn't exist
   */
  async getSettings(workspaceId: string): Promise<WorkspaceSettings> {
    const response = await this._client._request(
      'GET',
      `/api/v1/workspaces/${workspaceId}/settings`
    );
    return (await response.json()) as WorkspaceSettings;
  }

  /**
   * Update workspace settings.
   *
   * @param workspaceId - Workspace ID
   * @param request - Update settings request (only provided fields are updated)
   * @returns Updated workspace settings
   * @throws {NotFoundError} If workspace doesn't exist
   * @throws {ValidationError} If request is invalid
   */
  async updateSettings(
    workspaceId: string,
    request: UpdateWorkspaceSettingsRequest
  ): Promise<WorkspaceSettings> {
    const response = await this._client._request(
      'PUT',
      `/api/v1/workspaces/${workspaceId}/settings`,
      { body: JSON.stringify(request) }
    );
    return (await response.json()) as WorkspaceSettings;
  }
}
