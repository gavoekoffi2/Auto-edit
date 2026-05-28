# Exposing the AutoEdit backend over HTTPS

Your VPS already terminates TLS for `srv1305401.hstgr.cloud` (valid certificate)
and currently routes to a small Node "health stub". To make signup work, route
`/api/` to the AutoEdit FastAPI backend (running in Docker on port 8000) and the
rest to the frontend.

> Diagnostic shortcut: `curl https://srv1305401.hstgr.cloud/api/health`
> - `{"ok":true,...}`  → still the old stub (not wired yet)
> - `{"status":"healthy",...}` → AutoEdit backend is live ✅

---

## Option A — you already use Caddy

Add to your `Caddyfile`:

```caddy
srv1305401.hstgr.cloud {
    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }
    handle {
        reverse_proxy 127.0.0.1:3000
    }
}
```

Then: `sudo systemctl reload caddy`

---

## Option B — you already use Nginx on the host

In your server block for `srv1305401.hstgr.cloud`:

```nginx
location /api/ {
    proxy_pass         http://127.0.0.1:8000;
    proxy_set_header   Host $host;
    proxy_set_header   X-Real-IP $remote_addr;
    proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;
    client_max_body_size 500M;
}

location / {
    proxy_pass http://127.0.0.1:3000;
    proxy_set_header Host $host;
}
```

Then: `sudo nginx -t && sudo systemctl reload nginx`

---

## Option C — no existing proxy you want to keep

The Docker stack already ships an nginx that serves both the frontend and the
API on host port 80. Free ports 80/443 (stop the old service), put a TLS
terminator in front (Caddy/Certbot), and proxy to `127.0.0.1:80`.

---

## After wiring

1. `curl https://srv1305401.hstgr.cloud/api/health` → expect `{"status":"healthy"...}`
2. The Netlify frontend is built with
   `VITE_API_URL=https://srv1305401.hstgr.cloud/api`, so signup will hit
   `https://srv1305401.hstgr.cloud/api/v1/auth/signup`.
3. Make sure the backend `.env` `CORS_ORIGINS` contains the Netlify origin
   `https://tubular-nasturtium-cfb67e.netlify.app` (deploy.sh sets this).
