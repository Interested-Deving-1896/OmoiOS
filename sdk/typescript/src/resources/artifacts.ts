import { BaseResource } from './base.js';
import type { Artifact } from '../types.js';

/**
 * Resource for managing artifacts.
 *
 * @example
 * const artifacts = await client.artifacts.list('ws-1');
 * console.log(artifacts[0].name);
 */
export class ArtifactsResource extends BaseResource {
  /**
   * Upload an artifact.
   *
   * @param fileContent - Raw file bytes
   * @param workspaceId - Workspace ID
   * @param filename - Name for the uploaded file
   * @param contentType - MIME type override (optional)
   * @param metadata - JSON-serializable metadata (optional)
   * @returns Created artifact metadata
   */
  async upload(
    fileContent: Buffer,
    workspaceId: string,
    filename = 'uploaded-file.bin',
    contentType?: string,
    metadata?: Record<string, unknown>
  ): Promise<Artifact> {
    const formData = new FormData();
    formData.append('workspace_id', workspaceId);
    formData.append(
      'file',
      new Blob([new Uint8Array(fileContent)]),
      filename
    );
    if (contentType) {
      formData.append('content_type', contentType);
    }
    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata));
    }

    const response = await this._client._request(
      'POST',
      '/api/v1/artifacts/upload',
      { body: formData }
    );
    return (await response.json()) as Artifact;
  }

  /**
   * List artifacts in a workspace.
   *
   * @param workspaceId - Workspace ID to filter by
   * @param limit - Maximum number of results (1-1000)
   * @param offset - Number of results to skip
   * @returns List of artifacts
   */
  async list(
    workspaceId: string,
    limit = 100,
    offset = 0
  ): Promise<Artifact[]> {
    const response = await this._client._request(
      'GET',
      '/api/v1/artifacts',
      {
        searchParams: {
          workspace_id: workspaceId,
          limit: String(limit),
          offset: String(offset),
        },
      }
    );
    return (await response.json()) as Artifact[];
  }

  /**
   * Get artifact metadata by ID.
   *
   * @param artifactId - Artifact ID
   * @returns Artifact metadata
   * @throws {NotFoundError} If artifact doesn't exist
   */
  async get(artifactId: string): Promise<Artifact> {
    const response = await this._client._request(
      'GET',
      `/api/v1/artifacts/${artifactId}`
    );
    return (await response.json()) as Artifact;
  }

  /**
   * Download artifact content.
   *
   * @param artifactId - Artifact ID
   * @returns Raw file bytes
   * @throws {NotFoundError} If artifact doesn't exist
   */
  async download(artifactId: string): Promise<Buffer> {
    const response = await this._client._request(
      'GET',
      `/api/v1/artifacts/${artifactId}/download`
    );
    return Buffer.from(await response.arrayBuffer());
  }

  /**
   * Delete an artifact.
   *
   * @param artifactId - Artifact ID to delete
   * @throws {NotFoundError} If artifact doesn't exist
   */
  async delete(artifactId: string): Promise<void> {
    await this._client._request('DELETE', `/api/v1/artifacts/${artifactId}`);
  }
}
