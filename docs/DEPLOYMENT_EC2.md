# Deploying the ServiceNow MCP Server on AWS EC2 (Free Tier)

This guide takes the server from your laptop to a public HTTPS endpoint that
Claude Desktop, claude.ai, Claude Code, or any MCP client can connect to.

**Architecture:**

```
AI client (Claude) ──HTTPS──> Caddy (443, auto TLS) ──> MCP server (8080, Streamable HTTP)
                                        [ one EC2 t3.micro / t2.micro ]
                                                     │
                                                     └──HTTPS──> ServiceNow PDI
```

Why this shape:
- **Streamable HTTP** (`/mcp`) is the current MCP remote transport; SSE is deprecated.
  The server still supports SSE via `MCP_TRANSPORT=sse` if you need it.
- **Caddy** gives you a free, auto-renewing Let's Encrypt certificate. claude.ai
  and Claude Desktop require remote MCP servers to be HTTPS, so this is not optional.
- **Bearer token** (`MCP_AUTH_TOKEN`) protects the endpoint. Never expose the
  server without it — anyone who finds the URL could operate on your ServiceNow
  instance using the credentials the server holds.

---

## Common pitfalls (why earlier attempts fail)

1. **Binding to 127.0.0.1.** The old `server_sse.py` called `mcp.run(transport="sse", port=...)`
   without a host, and FastMCP binds `127.0.0.1` by default — reachable only from
   inside the EC2 box. The server now defaults to `MCP_HOST=0.0.0.0`. If you ever
   see the server running but `curl` from your laptop timing out, check this first.
2. **Security group not opened.** Ports 80/443 must be open to `0.0.0.0/0`.
3. **Plain HTTP.** Claude clients refuse non-HTTPS remote servers. Use the Caddy
   setup below; don't try to connect to `http://<ip>:8080/mcp` from claude.ai.
4. **Out of memory during `docker build`.** t2.micro has 1 GB RAM. Add swap
   (step 3) before building.

---

## Step 1 — Launch the EC2 instance

1. AWS Console → EC2 → **Launch instance**.
2. Name: `servicenow-mcp`.
3. AMI: **Ubuntu Server 24.04 LTS** (or Amazon Linux 2023).
4. Instance type: **t3.micro** or **t2.micro** (whichever shows "Free tier eligible"
   in your region; 750 hours/month for the first 12 months — one instance running
   24/7 stays free. Newer AWS accounts may be on the credit-based free plan instead;
   a t3.micro is still comfortably covered).
5. Key pair: create one (e.g. `mcp-key.pem`) and keep it safe.
6. Network settings → **Edit** security group rules:
   | Type  | Port | Source            | Purpose                        |
   |-------|------|-------------------|--------------------------------|
   | SSH   | 22   | My IP             | admin access                   |
   | HTTP  | 80   | 0.0.0.0/0         | Let's Encrypt cert issuance    |
   | HTTPS | 443  | 0.0.0.0/0         | MCP traffic                    |
   Do **not** open 8080 — the MCP server is only reached through Caddy.
7. Storage: default 8 GB gp3 is fine (free tier allows up to 30 GB).
8. Launch, then note the **public IPv4 address**.

> Public IPv4 note: AWS free tier includes 750 h/month of public IPv4 for the
> first 12 months. Skip Elastic IP for the demo; if you stop/start the instance
> the IP changes — just update DuckDNS (step 2).

## Step 2 — Get a free domain name (DuckDNS)

Let's Encrypt needs a DNS name, not a bare IP.

1. Go to <https://www.duckdns.org>, sign in (GitHub/Google), create a subdomain,
   e.g. `tina-mcp` → `tina-mcp.duckdns.org`.
2. Set its IP to your EC2 public IPv4 address.

## Step 3 — Prepare the instance

SSH in:

```bash
ssh -i mcp-key.pem ubuntu@<EC2_PUBLIC_IP>
```

Add swap (important on 1 GB instances), then install Docker:

```bash
# 2 GB swap so docker build doesn't OOM
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Docker + compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
newgrp docker
```

## Step 4 — Deploy

```bash
git clone https://github.com/alenthomas2468/servicenow-mcp-fast.git
cd servicenow-mcp-fast/deploy
```

Create `deploy/.env`:

```properties
# ServiceNow connection (PDI)
SERVICENOW_INSTANCE_URL=https://dev309229.service-now.com
SERVICENOW_AUTH_TYPE=basic
SERVICENOW_USERNAME=admin
SERVICENOW_PASSWORD=<your PDI password>

# MCP endpoint protection — generate with: openssl rand -hex 32
MCP_AUTH_TOKEN=<long random string>

# Your DuckDNS domain (used by Caddy for the TLS cert)
DOMAIN=tina-mcp.duckdns.org
```

Start everything:

```bash
docker compose up -d --build
docker compose logs -f     # watch until you see "Uvicorn running on http://0.0.0.0:8080"
```

Caddy obtains the certificate automatically on first request (needs port 80 open).

## Step 5 — Verify from your laptop

```bash
# Should be 401 (endpoint is protected)
curl -s -o /dev/null -w "%{http_code}\n" https://tina-mcp.duckdns.org/mcp

# Should return an MCP initialize result (HTTP 200)
curl -s https://tina-mcp.duckdns.org/mcp \
  -H "Authorization: Bearer <MCP_AUTH_TOKEN>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1"}},"id":1}'
```

Or use MCP Inspector: `npx @modelcontextprotocol/inspector`, transport
"Streamable HTTP", URL `https://tina-mcp.duckdns.org/mcp`, add an
`Authorization: Bearer <token>` header.

## Step 6 — Connect AI clients

**Claude Code:**

```bash
claude mcp add tina --transport http https://tina-mcp.duckdns.org/mcp \
  --header "Authorization: Bearer <MCP_AUTH_TOKEN>"
```

**Claude Desktop / claude.ai (custom connector):** Settings → Connectors →
Add custom connector → URL `https://tina-mcp.duckdns.org/mcp`. Custom
connectors authenticate via OAuth rather than a static header — for the demo,
either use Claude Code (headers supported), or temporarily run without
`MCP_AUTH_TOKEN` while restricting the security group to your own IP, or
implement full OAuth (below).

## Step 7 — Full OAuth (the proper long-term answer)

FastMCP ships OAuth providers, so upgrading from the static token is a few
lines in `server_sse.py`. Example with GitHub as the identity provider:

```python
from fastmcp.server.auth.providers.github import GitHubProvider

mcp.auth = GitHubProvider(
    client_id=os.environ["OAUTH_GITHUB_CLIENT_ID"],       # from a GitHub OAuth App
    client_secret=os.environ["OAUTH_GITHUB_CLIENT_SECRET"],
    base_url="https://tina-mcp.duckdns.org",              # public URL of this server
)
```

Register a GitHub OAuth App (callback URL
`https://tina-mcp.duckdns.org/auth/callback`), set the two env vars in
`deploy/.env`, and claude.ai/Claude Desktop connectors will show a GitHub
sign-in when connecting. Auth0, Google, Azure AD, and WorkOS providers work the
same way — for a Singtel deployment, Azure AD would be the natural choice.

---

## Operations

```bash
docker compose logs -f mcp        # server logs
docker compose restart mcp        # restart after config change
git pull && docker compose up -d --build   # deploy new code
```

`restart: unless-stopped` means everything survives an instance reboot.

## Scaling path (when it outgrows one instance)

The server is stateless (no local database; every tool call goes straight to
ServiceNow), which makes scaling straightforward:

1. **Push the image to ECR** instead of building on the box.
2. **ECS Fargate + Application Load Balancer**: run N copies of the container;
   the ALB terminates TLS (free ACM certificate) and replaces Caddy. Auto
   Scaling on CPU. This is the standard "serverless containers" path and needs
   zero code changes.
3. **Secrets**: move `SERVICENOW_PASSWORD` / `MCP_AUTH_TOKEN` from `.env` to
   AWS SSM Parameter Store or Secrets Manager.
4. If you enable sticky behavior problems behind the ALB, run FastMCP in
   stateless mode (`FastMCP("ServiceNow", stateless_http=True)`) so any
   replica can serve any request.

For the capstone demo, the single free-tier instance is the right scope; the
ECS/ALB design belongs in the report's "future work / scalability" section.
