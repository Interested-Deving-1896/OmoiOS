import { BaseResource } from './base.js';
import type {
  CreateWebhookRequest,
  WebhookDelivery,
  WebhookSubscription,
} from '../types.js';

/**
 * Resource for managing webhook subscriptions.
 *
 * @example
 * const webhooks = await client.webhooks.list('org-1');
 * console.log(webhooks[0].url);
 */
export class WebhooksResource extends BaseResource {
  /**
   * List webhook subscriptions for an organization.
   *
   * @param orgId - Organization ID to filter by
   * @param activeOnly - Only return active subscriptions
   * @param limit - Maximum results
   * @param offset - Results to skip
   * @returns List of webhook subscriptions
   */
  async list(
    orgId: string,
    activeOnly = true,
    limit = 100,
    offset = 0
  ): Promise<WebhookSubscription[]> {
    const response = await this._client._request(
      'GET',
      '/api/v1/webhooks/subscriptions',
      {
        searchParams: {
          org_id: orgId,
          active_only: String(activeOnly),
          limit: String(limit),
          offset: String(offset),
        },
      }
    );
    return (await response.json()) as WebhookSubscription[];
  }

  /**
   * Get a webhook subscription by ID.
   *
   * @param subscriptionId - Subscription ID
   * @returns Subscription metadata
   * @throws {NotFoundError} If subscription doesn't exist
   */
  async get(subscriptionId: string): Promise<WebhookSubscription> {
    const response = await this._client._request(
      'GET',
      `/api/v1/webhooks/subscriptions/${subscriptionId}`
    );
    return (await response.json()) as WebhookSubscription;
  }

  /**
   * Create a webhook subscription.
   *
   * @param orgId - Organization ID
   * @param request - Create webhook request
   * @returns Created webhook subscription
   */
  async create(
    orgId: string,
    request: CreateWebhookRequest
  ): Promise<WebhookSubscription> {
    const response = await this._client._request(
      'POST',
      '/api/v1/webhooks/subscriptions',
      {
        searchParams: { org_id: orgId },
        body: JSON.stringify(request),
      }
    );
    return (await response.json()) as WebhookSubscription;
  }

  /**
   * Update a webhook subscription.
   *
   * @param subscriptionId - Subscription ID
   * @param updates - Fields to update
   * @returns Updated subscription metadata
   * @throws {NotFoundError} If subscription doesn't exist
   */
  async update(
    subscriptionId: string,
    updates: {
      url?: string;
      events?: string[];
      secret?: string;
      active?: boolean;
    }
  ): Promise<WebhookSubscription> {
    const response = await this._client._request(
      'PATCH',
      `/api/v1/webhooks/subscriptions/${subscriptionId}`,
      { body: JSON.stringify(updates) }
    );
    return (await response.json()) as WebhookSubscription;
  }

  /**
   * Delete a webhook subscription.
   *
   * @param subscriptionId - Subscription ID to delete
   * @throws {NotFoundError} If subscription doesn't exist
   */
  async delete(subscriptionId: string): Promise<void> {
    await this._client._request(
      'DELETE',
      `/api/v1/webhooks/subscriptions/${subscriptionId}`
    );
  }

  /**
   * List webhook deliveries for a subscription.
   *
   * @param subscriptionId - Subscription ID
   * @param statusFilter - Optional status filter
   * @param limit - Maximum results
   * @param offset - Results to skip
   * @returns List of webhook deliveries
   * @throws {NotFoundError} If subscription doesn't exist
   */
  async listDeliveries(
    subscriptionId: string,
    statusFilter?: string,
    limit = 100,
    offset = 0
  ): Promise<WebhookDelivery[]> {
    const searchParams: Record<string, string> = {
      limit: String(limit),
      offset: String(offset),
    };
    if (statusFilter) {
      searchParams.status_filter = statusFilter;
    }

    const response = await this._client._request(
      'GET',
      `/api/v1/webhooks/subscriptions/${subscriptionId}/deliveries`,
      { searchParams }
    );
    return (await response.json()) as WebhookDelivery[];
  }

  /**
   * Trigger a test webhook delivery.
   *
   * @param subscriptionId - Subscription ID
   * @param event - Event type to test
   * @param payload - Test payload
   * @returns Delivery result
   */
  async test(
    subscriptionId: string,
    event: string,
    payload: Record<string, unknown> = {}
  ): Promise<{ subscription_id: string; event: string; success: boolean }> {
    const response = await this._client._request(
      'POST',
      `/api/v1/webhooks/subscriptions/${subscriptionId}/test`,
      { body: JSON.stringify({ event, payload }) }
    );
    return (await response.json()) as {
      subscription_id: string;
      event: string;
      success: boolean;
    };
  }
}
