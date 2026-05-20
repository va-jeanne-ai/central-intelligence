"""
Authentication package for Central Intelligence.

Provides Supabase client initialization, FastAPI dependencies for
extracting the current user from a Bearer token, and all auth-related
route handlers.

When ``SUPABASE_URL`` is not configured in the environment the entire
package operates in **mock mode**: every endpoint returns pre-canned
responses and every protected route resolves to a synthetic admin user.
This lets frontend development and CI pipelines proceed without a live
Supabase project.
"""
