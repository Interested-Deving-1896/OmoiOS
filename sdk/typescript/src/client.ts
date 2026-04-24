import {
  AuthError,
  NotFoundError,
  ServerError,
  ValidationError,
} from './errors.js';
import {
  ArtifactsResource,
  CredentialsResource,
  EnvironmentsResource,
  WebhooksResource,
  WorkspacesResource,
} from './resources/index.js';

/**
 * Options for the OmoiOS HTTP client.
 */
export interface OmoiOSClientOptions {
  /** API base URL (e.g., "https://api.omoios.dev") */
  baseUrl: string;
  /** API key for authentication (X-API-Key header) */
  apiKey?: string;
  /** JWT token for authentication (Authorization: Bearer header) */
  jwtToken?: string;
  /** HTTP request timeout in milliseconds (default: 30000) */
  timeout?: number;
}

/**
 * HTTP client for the OmoiOS Agent Workspace Platform.
 *
 * Uses native fetch (Node.js 18+) for HTTP requests. Supports both API key
 * and JWT token authentication.
 *
 * @example
 * const client = new OmoiOSClient({
 *   baseUrl: 'https://api.omoios.dev',
 *   apiKey: 'your-api-key',
 * });
 * const creds = await client.credentials.list('ws-1');
 * console.log(creds[0].name);
 */
export class OmoiOSClient {
  /** API base URL */
  readonly baseUrl: string;
  /** Optional API key */
  readonly apiKey: string | undefined;
  /** Optional JWT token */
  readonly jwtToken: string | undefined;
  /** Request timeout in milliseconds */
  readonly timeout: number;

  /** Credentials resource */
  readonly credentials: CredentialsResource;
  /** Environments resource */
  readonly environments: EnvironmentsResource;
  /** Artifacts resource */
  readonly artifacts: ArtifactsResource;
  /** Webhooks resource */
  readonly webhooks: WebhooksResource;
  /** Workspaces resource */
  readonly workspaces: WorkspacesResource;

  /**
   * Initialize the client.
   *
   * @param options - Client configuration options
   * @throws {Error} If neither apiKey nor jwtToken is provided
   */
  constructor(options: OmoiOSClientOptions) {
    if (!options.apiKey && !options.jwtToken) {
      throw new Error('Either apiKey or jwtToken must be provided');
    }

    this.baseUrl = options.baseUrl.replace(/\/$/, '');
    this.apiKey = options.apiKey;
    this.jwtToken = options.jwtToken;
    this.timeout = options.timeout ?? 30000;

    this.credentials = new CredentialsResource(this);
    this.environments = new EnvironmentsResource(this);
    this.artifacts = new ArtifactsResource(this);
    this.webhooks = new WebhooksResource(this);
    this.workspaces = new WorkspacesResource(this);
  }

  /**
   * Build request headers with authentication.
   *
   * @returns HTTP headers object
   */
  private _headers(): Record<string, string> {
    const headers: Record<string, string> = {};
    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    } else if (this.jwtToken) {
      headers['Authorization'] = `Bearer ${this.jwtToken}`;
    }
    return headers;
  }

  /**
   * Map HTTP error status codes to SDK exceptions.
   *
   * @param response - fetch Response object
   * @throws {AuthError} For 401 responses
   * @throws {NotFoundError} For 404 responses
   * @throws {ValidationError} For 400/422 responses
   * @throws {ServerError} For 5xx responses
   */
  private _handleErrors(response: Response): void {
    if (response.ok) {
      return;
    }

    if (response.status === 401) {
      throw new AuthError('Authentication failed');
    }
    if (response.status === 404) {
      throw new NotFoundError('Resource not found');
    }
    if (response.status === 400 || response.status === 422) {
      throw new ValidationError('Validation failed');
    }
    if (response.status >= 500) {
      throw new ServerError('Server error');
    }

    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  /**
   * Make an authenticated HTTP request.
   *
   * @param method - HTTP method (GET, POST, PUT, PATCH, DELETE)
   * @param path - API path (e.g., "/api/v1/credentials")
   * @param options - Request options
   * @returns fetch Response object
   * @throws {AuthError, NotFoundError, ValidationError, ServerError}
   */
  async _request(
    method: string,
    path: string,
    options: {
      searchParams?: Record<string, string>;
      body?: BodyInit;
      headers?: Record<string, string>;
    } = {}
  ): Promise<Response> {
    const url = new URL(path, this.baseUrl);
    if (options.searchParams) {
      for (const [key, value] of Object.entries(options.searchParams)) {
        url.searchParams.set(key, value);
      }
    }

    const headers: Record<string, string> = {
      ...this._headers(),
      ...options.headers,
    };

    if (options.body && typeof options.body === 'string') {
      headers['Content-Type'] = 'application/json';
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url.toString(), {
        method,
        headers,
        body: options.body,
        signal: controller.signal,
      });

      this._handleErrors(response);
      return response;
    } finally {
      clearTimeout(timeoutId);
    }
  }
}
