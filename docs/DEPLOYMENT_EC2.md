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
5. Key pair: select **"servicenow-mcp"** (your existing key pair) from the
   dropdown instead of creating a new one. If you no longer have the matching
   `.pem`/`.ppk` private-key file on this machine, AWS cannot re-issue it for
   an existing key pair — either locate your saved copy (see "Saving your key
   pair safely" below) or create a fresh key pair now and use that instead.
6. **Advanced details → User data**: paste the bootstrap script from
   [Step 3a](#step-3a--bootstrap-automatically-with-user-data) here so the
   instance configures itself on first boot instead of you SSH-ing in to run
   commands by hand.
7. Network settings → **Edit** security group rules:
   | Type  | Port | Source            | Purpose                        |
   |-------|------|-------------------|--------------------------------|
   | SSH   | 22   | My IP             | admin access                   |
   | HTTP  | 80   | 0.0.0.0/0         | Let's Encrypt cert issuance    |
   | HTTPS | 443  | 0.0.0.0/0         | MCP traffic                    |
   Do **not** open 8080 — the MCP server is only reached through Caddy.
8. Storage: default 8 GB gp3 is fine (free tier allows up to 30 GB).
9. Launch.

### Saving your key pair safely

Since you already have a key pair named `servicenow-mcp`, treat the private
key file as a permanent credential, not a throwaway download:

1. Locate the `.pem` file from when the key pair was first created — AWS only
   lets you download it once, at creation time.
2. Keep exactly one canonical copy in a password manager or an encrypted
   folder (e.g. `~/.ssh/servicenow-mcp.pem` with restricted permissions).
   On Linux/macOS: `chmod 400 ~/.ssh/servicenow-mcp.pem`.
3. Never commit it to git (it isn't in this repo, and shouldn't be).
4. If it's genuinely lost, don't try to "recover" it — delete the key pair in
   the EC2 console and create a new one. A lost private key with no backup is
   unrecoverable by design.

## Step 2 — Allocate an Elastic IP (persistent address)

A normal EC2 public IP changes every time you stop/start the instance, which
breaks DNS and forces you to re-point DuckDNS each time. An **Elastic IP**
fixes the address permanently to your account, at no extra cost as long as
it's attached to a running instance (AWS only bills unattached Elastic IPs).

1. EC2 Console → **Elastic IPs** → **Allocate Elastic IP address** → Allocate.
2. Select the new address → **Actions → Associate Elastic IP address** →
   choose your `servicenow-mcp` instance → Associate.
3. Note the Elastic IP — this is now your instance's permanent public address,
   and it survives stop/start/reboot (it's only released if you explicitly
   disassociate it or terminate the instance).

## Step 3 — Get a free domain name (DuckDNS)

Let's Encrypt needs a DNS name, not a bare IP.

1. Go to <https://www.duckdns.org>, sign in (GitHub/Google), create a subdomain,
   e.g. `tina-mcp` → `tina-mcp.duckdns.org`.
2. Set its IP to your **Elastic IP** from Step 2. Because the Elastic IP is
   static, you set this once and never have to touch it again — even across
   reboots or instance stop/start.

## Step 3a — Bootstrap automatically with user data

EC2 **user data** is a script that runs once, automatically, the first time
the instance boots — it replaces the manual "SSH in and run these commands"
steps for the base OS setup. Paste this into the **User data** box in Step 1.6:

```bash
#!/bin/bash
set -e

# 2 GB swap so `docker compose build` doesn't OOM on a 1 GB free-tier instance
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Docker + compose plugin
curl -fsSL https://get.docker.com | sh
usermod -aG docker ubuntu

# Clone the repo so it's ready to configure on first login
sudo -u ubuntu git clone https://github.com/alenthomas2468/servicenow-mcp-fast.git /home/ubuntu/servicenow-mcp-fast
```

What this does **not** do on purpose: it doesn't create `deploy/.env` or run
`docker compose up`, because that file holds your ServiceNow password and
`MCP_AUTH_TOKEN` — secrets don't belong in user data, which is readable by
anyone with `describe-instance-attribute` permission on the account and is
visible in the console. Create `deploy/.env` by hand after first login
(Step 4), or better, pull it from AWS Secrets Manager / SSM Parameter Store
in a follow-up script once you're past the demo stage (see the Scaling
section).

You can watch the user-data script's progress after launch with:

```bash
ssh -i servicenow-mcp.pem ubuntu@<ELASTIC_IP>
cat /var/log/cloud-init-output.log
```

## Step 4 — Log in and deploy

If you used the user-data script in Step 3a, swap, Docker, and the repo clone
are already done — just log in and configure secrets:

```bash
ssh -i servicenow-mcp.pem ubuntu@<ELASTIC_IP>
cd servicenow-mcp-fast/deploy
```

> Didn't use user data, or launched the instance before adding it? Run this
> once over SSH instead, then continue below:
> ```bash
> sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
> sudo mkswap /swapfile && sudo swapon /swapfile
> echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
> curl -fsSL https://get.docker.com | sudo sh
> sudo usermod -aG docker ubuntu && newgrp docker
> git clone https://github.com/alenthomas2468/servicenow-mcp-fast.git
> cd servicenow-mcp-fast/deploy
> ```

Create `deploy/.env`:

```properties
# ServiceNow connection (PDI) — service account used for static-token sessions.
# NOTE: the password must be the LITERAL password, not URL-encoded. An earlier
# deploy had %40 instead of @ here, which made every ServiceNow call 401.
SERVICENOW_INSTANCE_URL=https://dev313362.service-now.com
SERVICENOW_AUTH_TYPE=basic
SERVICENOW_USERNAME=admin
SERVICENOW_PASSWORD=<your-servicenow-password>

# MCP endpoint protection — generate with: openssl rand -hex 32
MCP_AUTH_TOKEN=<your-random-token>

# ServiceNow OAuth for claude.ai / Claude Desktop connectors (per-user sign-in).
# Values come from the Application Registry record — see Step 7.
SERVICENOW_OAUTH_CLIENT_ID=<client_id-from-application-registry>
SERVICENOW_OAUTH_CLIENT_SECRET=<client_secret-from-application-registry>
MCP_PUBLIC_URL=https://tina-mcp.duckdns.org

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
  -H "Authorization: Bearer <your-random-token>" \
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
claude mcp add tina --scope user --transport http https://tina-mcp.duckdns.org/mcp \
  --header "Authorization: Bearer <your-random-token>"
```

> **Windows/PowerShell:** run the command on **one line**. The `\` at the end of
> the line above is bash-only line continuation — in PowerShell it is treated as
> a literal argument, so the `--header` part silently never gets registered and
> Claude Code then fails with "needs authentication". Verify with
> `claude mcp list` (should show `tina ... ✔ Connected`). `--scope user` makes
> the server available in every project, not just the folder you ran it from.

**Claude Desktop / claude.ai (custom connector):** Settings → Connectors →
Add custom connector → URL `https://tina-mcp.duckdns.org/mcp`. Custom
connectors authenticate via OAuth, not static headers — with the ServiceNow
OAuth env vars set (Step 7), the connector shows a ServiceNow sign-in when
connecting, and every tool call then runs as **that user**, with their own
roles and ACLs. Both auth modes work at the same time on the same endpoint
(`MultiAuth`): header clients use the static token and act as the service
account; OAuth clients act as themselves.

## Step 7 — ServiceNow OAuth (per-user sign-in, implemented)

`src/servicenow_mcp/auth/endpoint_auth.py` wires FastMCP's `OAuthProxy` to
ServiceNow's OAuth endpoints (`/oauth_auth.do`, `/oauth_token.do`). The proxy
handles Dynamic Client Registration for claude.ai, issues its own JWTs to
clients, stores the upstream ServiceNow token encrypted (persisted in the
`mcp_oauth_state` docker volume), and refreshes it transparently.
`get_auth_manager()` then routes each tool call: OAuth session → the user's
own ServiceNow token (`DelegatedAuthManager`), static-token session → the
shared service account.

One-time setup on the instance (already done on dev313362):

1. **Application Registry record** — System OAuth → Application Registry →
   "Create an OAuth API endpoint for external clients":
   - Name: `ServiceNow MCP Remote (tina-mcp)`
   - Redirect URL: `https://tina-mcp.duckdns.org/auth/callback`
   - Grant type: authorization code (default lifespans are fine)
   Or create it via the REST table API (`oauth_entity`, `type=client`).
2. Put `client_id`/`client_secret` in `deploy/.env` as
   `SERVICENOW_OAUTH_CLIENT_ID` / `SERVICENOW_OAUTH_CLIENT_SECRET`, plus
   `MCP_PUBLIC_URL=https://tina-mcp.duckdns.org`.
3. `docker compose up -d --build`.

Scope note: this binds the deployment to ONE ServiceNow instance — each user
logs in with their own account *on that instance*. That per-user identity
(everyone gets their own ACLs instead of sharing admin) is the security win;
multi-instance would be a multi-tenant redesign.

---

## Operations

```bash
docker compose logs -f mcp        # server logs
docker compose up -d mcp          # apply .env changes (recreates the container)
git pull && docker compose up -d --build   # deploy new code
```

> **Gotcha:** `docker compose restart mcp` does **not** re-read `.env` — restart
> reuses the existing container with its original environment. After editing
> `.env` (e.g. adding/removing `MCP_AUTH_TOKEN`), always use `docker compose up -d mcp`
> so the container is recreated with the new values.

`restart: unless-stopped` means everything survives an instance reboot.

## Scaling path (when it outgrows one instance)

**Important constraint first:** an Elastic IP attaches to exactly *one*
instance. The Step 2/Caddy setup above is deliberately a single-box design —
it cannot itself "auto scale," because there's nowhere for a second instance's
traffic to go. Auto Scaling only makes sense once you put a **load balancer**
in front of a *pool* of instances (or containers) instead of pointing DNS
directly at one box's IP. That's a different, slightly larger architecture:

```
AI client ──HTTPS──> Application Load Balancer (ACM cert, free)
                              │  (health checks, round-robins traffic)
                    ┌─────────┴─────────┐
              EC2 instance A       EC2 instance B  ... (Auto Scaling Group)
              (mcp container)      (mcp container)
                    │                     │
                    └─────────┬───────────┘
                       HTTPS to ServiceNow PDI
```

Caddy and the Elastic IP disappear in this design — the ALB takes over both
jobs (TLS termination + routing), and stops any single instance from being a
fixed target.

The server is already stateless (no local database or in-memory session
state; every tool call goes straight to ServiceNow), so nothing in the
application code needs to change to run N copies of it. Steps to get there:

1. **Push the image to ECR** (Elastic Container Registry) instead of building
   on the box:
   ```bash
   aws ecr create-repository --repository-name servicenow-mcp
   docker build -t servicenow-mcp .
   docker tag servicenow-mcp:latest <account-id>.dkr.ecr.<region>.amazonaws.com/servicenow-mcp:latest
   docker push <account-id>.dkr.ecr.<region>.amazonaws.com/servicenow-mcp:latest
   ```
2. **Create a Launch Template** that pulls that image and runs it — this is
   the EC2-native equivalent of the user-data script from Step 3a, but ending
   in `docker run <ecr-image>` instead of a `git clone`. (If you'd rather skip
   managing EC2 instances entirely, **ECS Fargate** replaces the Launch
   Template + Auto Scaling Group with a Fargate Service — same idea, no
   servers to patch. Either path works; EC2 + ASG keeps you inside the same
   mental model as this guide, Fargate is less to operate.)
3. **Auto Scaling Group**: minimum 1–2 instances, scale-out policy on CPU
   (e.g. target 60%) or on `ALBRequestCountPerTarget`. Attach it to a new
   **Target Group**.
4. **Application Load Balancer**: internet-facing, HTTPS listener with a free
   **AWS Certificate Manager (ACM)** certificate for your domain, forwarding
   to the target group on port 8080. Point DuckDNS (or migrate to Route 53)
   at the ALB's DNS name, not an IP — ALBs don't have a single static IP.
5. **Secrets**: move `SERVICENOW_PASSWORD` / `MCP_AUTH_TOKEN` out of `.env`
   into AWS **SSM Parameter Store** or **Secrets Manager**, and have the
   Launch Template/task definition read them at boot — a hardcoded `.env`
   doesn't fit a design where instances are created and destroyed automatically.
6. **Health check**: point the target group's health check at `/mcp` (expect
   a 401 with no auth header, or add a lightweight `/healthz` route) so the
   ASG can tell a broken instance from a healthy one and replace it.

**Cost note:** this design steps outside the free tier — an ALB has an hourly
charge (no meaningful free-tier allowance) plus a second+ instance running.
Budget roughly US$16–20/month for one ALB + one extra t3.micro. For the
capstone, the single free-tier instance (Steps 1–7 above) is the right scope
to actually deploy and demo; write up this Auto Scaling Group + ALB design as
the "future work / scalability" section of your report, since it's the
architecturally correct next step even though standing it up isn't necessary
to prove the concept.
