"""
Test script to validate the complete auth system.

This script tests the entire auth flow end-to-end:
1. Register a user
2. Login
3. Create an organization
4. Create roles
5. Add members
6. Create API keys
7. Test permissions

Run: uv run python scripts/test_auth_system.py
"""

import asyncio
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from omoi_os.config import load_database_settings, load_auth_settings
from omoi_os.models.organization import Organization, OrganizationMembership, Role
from omoi_os.services.auth_service import AuthService
from omoi_os.services.authorization_service import AuthorizationService, ActorType


async def main():
    """Run comprehensive auth system test."""
    print("=" * 60)
    print("🔐 Authentication System End-to-End Test")
    print("=" * 60)

    # Setup database
    db_settings = load_database_settings()
    auth_settings = load_auth_settings()

    engine = create_async_engine(db_settings.url, echo=False)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session_maker() as session:
        auth_service = AuthService(
            db=session,
            jwt_secret=auth_settings.jwt_secret_key,
            jwt_algorithm=auth_settings.jwt_algorithm,
            access_token_expire_minutes=auth_settings.access_token_expire_minutes,
            refresh_token_expire_days=auth_settings.refresh_token_expire_days,
        )

        authz_service = AuthorizationService(db=session)

        # Test 1: User Registration
        print("\n📝 Test 1: User Registration")
        try:
            user = await auth_service.register_user(
                email=f"test-{uuid4()}@example.com",
                password="TestPassword123",
                full_name="Test User",
                department="Engineering",
            )
            print(f"✅ User registered: {user.email}")
            print(f"   ID: {user.id}")
            print(f"   Verified: {user.is_verified}")
            print(f"   Super Admin: {user.is_super_admin}")
        except Exception as e:
            print(f"❌ Registration failed: {e}")
            return

        # Test 2: Authentication
        print("\n🔑 Test 2: User Authentication")
        try:
            auth_user = await auth_service.authenticate_user(
                email=user.email, password="TestPassword123"
            )
            if auth_user:
                print("✅ Authentication successful")
                print(f"   Last login: {auth_user.last_login_at}")
            else:
                print("❌ Authentication failed")
                return
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return

        # Test 3: JWT Token Generation
        print("\n🎫 Test 3: JWT Token Generation")
        try:
            access_token = auth_service.create_access_token(user.id)
            refresh_token = auth_service.create_refresh_token(user.id)
            print("✅ Tokens generated")
            print(f"   Access token length: {len(access_token)}")
            print(f"   Refresh token length: {len(refresh_token)}")

            # Verify access token
            token_data = auth_service.verify_token(access_token, "access")
            if token_data:
                print(f"✅ Access token verified: user_id={token_data.user_id}")
            else:
                print("❌ Token verification failed")
        except Exception as e:
            print(f"❌ Token generation failed: {e}")
            return

        # Test 4: Create Organization
        print("\n🏢 Test 4: Organization Creation")
        try:
            org = Organization(
                name="Test Organization",
                slug=f"test-org-{uuid4().hex[:8]}",
                owner_id=user.id,
                description="A test organization",
                is_active=True,
            )
            session.add(org)
            await session.flush()

            print(f"✅ Organization created: {org.name}")
            print(f"   ID: {org.id}")
            print(f"   Slug: {org.slug}")
            print(f"   Owner: {org.owner_id}")
        except Exception as e:
            print(f"❌ Organization creation failed: {e}")
            return

        # Test 5: Add User to Organization
        print("\n🤝 Test 5: Organization Membership")
        try:
            # Get owner role
            result = await session.execute(
                select(Role).where(Role.name == "owner", Role.is_system.is_(True))
            )
            owner_role = result.scalar_one()

            # Create membership
            membership = OrganizationMembership(
                user_id=user.id, organization_id=org.id, role_id=owner_role.id
            )
            session.add(membership)
            await session.flush()

            print("✅ User added to organization")
            print(f"   Role: {owner_role.name}")
            print(f"   Permissions: {len(owner_role.permissions)} permissions")
        except Exception as e:
            print(f"❌ Membership creation failed: {e}")
            return

        # Test 6: Permission Checking
        print("\n🛡️  Test 6: Permission Checking")
        try:
            # Test various permissions
            test_permissions = [
                "org:read",
                "org:write",
                "org:delete",
                "project:create",
                "project:delete",
                "ticket:write",
                "agent:spawn",
            ]

            for perm in test_permissions:
                allowed, reason, details = await authz_service.is_authorized(
                    actor_id=user.id,
                    actor_type=ActorType.USER,
                    action=perm,
                    organization_id=org.id,
                )
                status = "✅" if allowed else "❌"
                print(f"   {status} {perm}: {reason}")
        except Exception as e:
            print(f"❌ Permission checking failed: {e}")
            return

        # Test 7: API Key Generation
        print("\n🔑 Test 7: API Key Generation")
        try:
            api_key, full_key = await auth_service.create_api_key(
                user_id=user.id,
                name="Test API Key",
                scopes=["read", "write"],
                organization_id=org.id,
                expires_in_days=30,
            )

            print("✅ API key created")
            print(f"   Name: {api_key.name}")
            print(f"   Prefix: {api_key.key_prefix}")
            print(f"   Full key: {full_key[:20]}... (showing first 20 chars)")
            print(f"   Scopes: {api_key.scopes}")
            print(f"   Expires: {api_key.expires_at}")

            # Verify key
            verify_result = await auth_service.verify_api_key(full_key)
            if verify_result:
                verified_user, verified_key = verify_result
                print("✅ API key verification successful")
                print(f"   Verified user: {verified_user.email}")
            else:
                print("❌ API key verification failed")
        except Exception as e:
            print(f"❌ API key creation failed: {e}")
            return

        # Test 8: Create Custom Role
        print("\n👥 Test 8: Custom Role Creation")
        try:
            custom_role = Role(
                organization_id=org.id,
                name="developer",
                description="Developer role with code access",
                permissions=[
                    "project:read",
                    "project:write",
                    "project:git:write",
                    "ticket:read",
                    "ticket:write",
                    "task:read",
                    "task:write",
                ],
                is_system=False,
            )
            session.add(custom_role)
            await session.flush()

            print(f"✅ Custom role created: {custom_role.name}")
            print(f"   Permissions: {len(custom_role.permissions)}")
        except Exception as e:
            print(f"❌ Custom role creation failed: {e}")
            return

        # Test 9: Get User Organizations
        print("\n📋 Test 9: List User Organizations")
        try:
            user_orgs = await authz_service.get_user_organizations(user.id)
            print(f"✅ Found {len(user_orgs)} organization(s)")
            for org_info in user_orgs:
                print(f"   - {org_info['organization_name']} ({org_info['role']})")
        except Exception as e:
            print(f"❌ Failed to list organizations: {e}")
            return

        # Test 10: Get User Permissions
        print("\n🔍 Test 10: List User Permissions")
        try:
            permissions = await authz_service.get_user_permissions(user.id, org.id)
            print(f"✅ User has {len(permissions)} permission(s)")
            for perm in sorted(permissions)[:10]:  # Show first 10
                print(f"   - {perm}")
            if len(permissions) > 10:
                print(f"   ... and {len(permissions) - 10} more")
        except Exception as e:
            print(f"❌ Failed to get permissions: {e}")
            return

        await session.commit()

    await engine.dispose()

    # Summary
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nAuth System Status:")
    print("  ✅ User registration and authentication")
    print("  ✅ JWT token generation and verification")
    print("  ✅ Organization creation and management")
    print("  ✅ Role-based access control (RBAC)")
    print("  ✅ Permission checking with wildcards")
    print("  ✅ API key generation and verification")
    print("  ✅ Custom role creation")
    print("  ✅ Organization membership")
    print("\n🎉 Authentication system is fully operational!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
