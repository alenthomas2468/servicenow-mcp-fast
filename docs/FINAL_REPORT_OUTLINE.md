# Final Capstone Report — Structure and Content Plan

Working outline for the ICT3902C final report on the TINA ServiceNow MCP
Server. Column three says where the content already exists (your combined
T1/T2 milestone reports in `Combined_Converted_Reports.md`) versus what must
be newly written in Trimester 3.

> Note on AI usage: your milestone reports carry an AI-usage disclosure
> (spelling/grammar/diagrams only). Keep the final report consistent with that —
> use this outline as a plan and write the prose yourself.

## Proposed structure

| # | Section | Source |
|---|---------|--------|
| — | Title page, declaration, acknowledgements, abstract | New (abstract last) |
| 1 | Introduction: TINA, the navigation-overhead problem, why MCP | T1 §1–2, T2 §2 — merge, remove trimester framing |
| 2 | Literature review | T2 §2 "Related Work" is nearly final — reuse |
| 3 | Requirements & constraints: firewall, SSL inspection, PDI-vs-TINA split, device restrictions | T2 §5 — reframe from "challenges I hit" to "constraints that drove the design" |
| 4 | System design & architecture | Partly T2 §4; needs new architecture content (below) |
| 5 | Implementation | T2 §4 + new T3 work (below) |
| 6 | Deployment | New — this is the T3 centrepiece |
| 7 | Testing & evaluation | T2 §4 testing + new evaluation (below) |
| 8 | Business value & use cases | New — see `docs/BUSINESS_USE_CASES` section of README or report draft |
| 9 | Discussion: limitations, security considerations, scalability | New |
| 10 | Conclusion & future work | New |
| — | References | T1+T2 lists merged, IEEE style |
| — | Appendices: tool catalogue, .env reference, deployment runbook | Generate from repo |

## New content the final report needs (gap list)

**Section 4 — Architecture (new material):**
- End-to-end architecture diagram: AI client → HTTPS/Streamable HTTP → Caddy →
  FastMCP server on EC2 → ServiceNow REST Table API → TINA/PDI.
- Layered code architecture: entry points (`server.py` stdio, `server_sse.py`
  remote) → tool modules → helpers/http_client → auth manager.
- Two security layers, clearly separated: (a) MCP endpoint auth (bearer
  token / OAuth — who may talk to the server) and (b) ServiceNow auth
  (basic/OAuth/API-key — what the server may do in ServiceNow).
- Design decisions table: FastMCP over raw SDK, stdio+HTTP dual transport,
  env-driven config, stateless server.

**Section 5 — Implementation additions since T2:**
- The TINA-specific tool suite now in the repo: network elements, VRFs,
  PE Router RFS instances/orders, Elite IPVPN CFS instances/orders, generic
  table query tools, table schema inspection (~100 tools total — count them
  with MCP Inspector for an exact figure).
- Streamable HTTP entry point, host binding, bearer-token endpoint auth.

**Section 6 — Deployment (write while you do it):**
- Follow `docs/DEPLOYMENT_EC2.md`; screenshot each milestone (EC2 console,
  DuckDNS, `docker compose ps`, Inspector connected, Claude Desktop calling a
  tool against the PDI).
- Cost analysis: free-tier coverage, what it would cost after (t3.micro
  ≈ US$8/month on-demand).
- Scalability design: ECS Fargate + ALB diagram for the "wider rollout" story.

**Section 7 — Evaluation (examiners weight this heavily; plan ~2 weeks):**
- Functional: pass/fail matrix over the tool suite against the PDI
  (create/read/update per module).
- Task-level: 10–15 realistic natural-language tasks ("resolve the oldest P2
  incident about X", "which VRFs belong to customer Y?") — did the AI pick the
  right tools and complete the task? Report success rate and typical failure modes.
- Performance: tool-call latency local-stdio vs cloud-HTTP (simple table).
- Security: what the bearer token/OAuth protects against; residual risks
  (server holds privileged ServiceNow credentials; least-privilege service
  account recommended).

**Section 9 — Discussion points to include:**
- Cloud-to-TINA connectivity remains blocked by corporate network policy —
  validated against PDI only; state this honestly and describe the approved-path
  options (private link, on-prem deployment of the same container).
- Single shared ServiceNow credential = no per-user audit trail in ServiceNow;
  future work: OAuth token pass-through so actions run as the requesting user.
- LLM risk: destructive tools (update/delete) exposed to a probabilistic agent;
  mitigations: read-only tool subsets, human-in-the-loop confirmation.

## Suggested writing order

1. Deployment (§6) while doing it — screenshots are perishable.
2. Evaluation (§7) — needs the deployment live.
3. Architecture/Implementation (§4–5) — mostly assembly from milestones + repo.
4. Discussion/Conclusion (§9–10), then Introduction polish, then Abstract last.
