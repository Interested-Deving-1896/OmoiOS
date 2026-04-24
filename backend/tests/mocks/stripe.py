"""Mock Stripe service for testing.

Provides in-memory payment operations without actual Stripe API calls.
"""

from uuid import uuid4


class MockStripeService:
    """Mock Stripe service with in-memory state tracking.

    Simulates Stripe operations (customers, subscriptions, charges)
    in memory for testing without making actual API calls.
    """

    def __init__(self):
        """Initialize the mock Stripe service."""
        self.customers: dict[str, dict] = {}
        self.subscriptions: dict[str, dict] = {}
        self.charges: list[dict] = []
        self.operations: list[dict] = []

    @property
    def is_configured(self) -> bool:
        """Always returns True for mock."""
        return True

    async def create_customer(
        self,
        email: str,
        name: str | None = None,
        **kwargs,
    ) -> dict:
        """Create a mock customer in memory.

        Args:
            email: Customer email address
            name: Optional customer name
            **kwargs: Additional customer metadata

        Returns:
            Mock customer object
        """
        customer_id = f"cus_{uuid4().hex[:16]}"
        customer = {
            "id": customer_id,
            "email": email,
            "name": name,
            **kwargs,
        }
        self.customers[customer_id] = customer
        self.operations.append(
            {
                "type": "create_customer",
                "customer_id": customer_id,
                "email": email,
                "name": name,
            }
        )
        return customer

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        **kwargs,
    ) -> dict:
        """Create a mock subscription in memory.

        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID
            **kwargs: Additional subscription options

        Returns:
            Mock subscription object
        """
        subscription_id = f"sub_{uuid4().hex[:16]}"
        subscription = {
            "id": subscription_id,
            "customer": customer_id,
            "price": price_id,
            "status": "active",
            **kwargs,
        }
        self.subscriptions[subscription_id] = subscription
        self.operations.append(
            {
                "type": "create_subscription",
                "subscription_id": subscription_id,
                "customer_id": customer_id,
                "price_id": price_id,
            }
        )
        return subscription

    async def create_checkout_session(self, **kwargs) -> dict:
        """Create a mock checkout session.

        Args:
            **kwargs: Checkout session configuration

        Returns:
            Mock checkout session object
        """
        session_id = f"cs_{uuid4().hex[:16]}"
        session = {
            "id": session_id,
            "url": f"https://mock.stripe.com/checkout/{session_id}",
            **kwargs,
        }
        self.operations.append(
            {
                "type": "create_checkout_session",
                "session_id": session_id,
                **kwargs,
            }
        )
        return session

    async def cancel_subscription(self, subscription_id: str) -> dict:
        """Cancel a subscription in memory.

        Args:
            subscription_id: ID of the subscription to cancel

        Returns:
            Updated subscription object

        Raises:
            AssertionError: If subscription not found
        """
        if subscription_id not in self.subscriptions:
            raise AssertionError(f"Subscription '{subscription_id}' not found")
        self.subscriptions[subscription_id]["status"] = "canceled"
        self.operations.append(
            {
                "type": "cancel_subscription",
                "subscription_id": subscription_id,
            }
        )
        return self.subscriptions[subscription_id]

    def assert_customer_created(self, email: str | None = None) -> None:
        """Assert that a customer was created.

        Args:
            email: Optional specific email to check

        Raises:
            AssertionError: If no customer was created
        """
        if not self.customers:
            raise AssertionError("No customers were created")
        if email:
            for customer in self.customers.values():
                if customer.get("email") == email:
                    return
            raise AssertionError(f"No customer created with email '{email}'")

    def reset(self) -> None:
        """Clear all state."""
        self.customers.clear()
        self.subscriptions.clear()
        self.charges.clear()
        self.operations.clear()
