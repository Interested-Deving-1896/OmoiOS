import type { OmoiOSClient } from '../client.js';

/**
 * Base class for all API resources.
 *
 * Provides a reference to the parent client for making HTTP requests.
 */
export class BaseResource {
  /** Reference to the parent HTTP client. */
  protected readonly _client: OmoiOSClient;

  /**
   * Initialize the resource with a client reference.
   *
   * @param client - The OmoiOS client instance
   */
  constructor(client: OmoiOSClient) {
    this._client = client;
  }
}
