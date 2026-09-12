# Social registration setup

The application supports OAuth registration and login through Google, LinkedIn, and Facebook. Copy `.env.example` to `.env`, provide credentials from each provider's developer console, and export those values before starting FastAPI.

## Callback URLs

Register these exact URLs with the providers (replace the origin in production):

- `http://127.0.0.1:8001/auth/google/callback`
- `http://127.0.0.1:8001/auth/linkedin/callback`
- `http://127.0.0.1:8001/auth/facebook/callback`

Set `PUBLIC_BASE_URL` to the same origin, without a trailing slash. Production providers normally require HTTPS; set `COOKIE_SECURE=true` there.

## Provider permissions

- Google: OpenID Connect scopes `openid email profile`.
- LinkedIn: enable **Sign In with LinkedIn using OpenID Connect** and scopes `openid profile email`.
- Facebook: enable **Facebook Login** and request `email,public_profile`.

On the first successful callback a local user is created and assigned the standard training cases. Later callbacks for the same provider account log that user in. Provider access tokens are used only to fetch the profile and are not persisted.
