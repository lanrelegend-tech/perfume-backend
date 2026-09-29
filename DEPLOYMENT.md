# Production Deployment

Configure `api.orentemist.online` as a custom domain for the Render service and create a DNS CNAME record pointing that host to the Render hostname. Configure `www.orentemist.online` as the Vercel frontend domain.

Set the Render environment variables from `.env.example`. In particular, use `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS=api.orentemist.online`, `FRONTEND_URL=https://www.orentemist.online`, and `AUTH_COOKIE_SAMESITE=Lax`.

After DNS resolves, set `NEXT_PUBLIC_API_URL=https://api.orentemist.online/api` in Vercel and redeploy both services. Keep `AUTH_COOKIE_SAMESITE=None` only while the frontend and API are on unrelated sites such as Vercel and Render.
