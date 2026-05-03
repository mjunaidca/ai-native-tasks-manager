# deployments/

Kubernetes manifests for the AI-native tasks manager.

This directory holds **plain YAML** for a development cluster. Helm charts and
production hardening (Ingress, HPA, PDB, RBAC, NetworkPolicy, sealed secrets,
probes, FastAPI surface) are tracked in GitHub issues #1–#4 and intentionally
out of scope here.

---

## Layout

```
deployments/
  tasks-mcp/
    configmap.yaml      # TASKS_MCP_HOST/PORT/LOG_LEVEL
    deployment.yaml     # replicas:1, strategy:Recreate (in-memory store)
    service.yaml        # ClusterIP, name=tasks-mcp, port 8000
  tasks-agent/
    configmap.yaml      # provider, model names, TASKS_MCP_URL
    deployment.yaml     # replicas:1, sleep entrypoint, /tmp emptyDir
    secret.example.yaml # template only — DO NOT commit real values
```

Per `AGENTS.md`, manifests live under `deployments/` rather than inside each
service directory. Dockerfiles stay at the service root.

---

## Prerequisites

- A running Kubernetes cluster (any flavour). The current dev environment
  uses a single-node k3s cluster (`kubectl config current-context` →
  `default`).
- `kubectl` configured against that cluster.
- A GitHub Personal Access Token with `read:packages` scope. The published
  images live at:
  - `ghcr.io/mjunaidca/ai-native-tasks-manager/tasks-mcp:<sha>`
  - `ghcr.io/mjunaidca/ai-native-tasks-manager/tasks-agent:<sha>`
  - The `tasks-mcp` package is **private** on ghcr today, so an
    `imagePullSecret` is required even though the repo is public.
    Tracking this in issue #2.

---

## One-time cluster setup

Cluster bootstrap is intentionally separate from deployment so the same
manifests work against any cluster.

```bash
# 1. Namespace
kubectl create namespace tasks-manager

# 2. Image pull secret (uses your gh token; needs read:packages)
GH_TOKEN=$(gh auth token)
kubectl create secret docker-registry ghcr-pull \
  --namespace tasks-manager \
  --docker-server=ghcr.io \
  --docker-username=<your-gh-username> \
  --docker-password="$GH_TOKEN" \
  --docker-email=<your-email>

# 3. Agent runtime secrets (LLM API keys)
kubectl create secret generic tasks-agent-secrets \
  --namespace tasks-manager \
  --from-literal=GEMINI_API_KEY=... \
  --from-literal=OPENAI_API_KEY=...
```

Both secrets are applied **imperatively** and are never committed.
`tasks-agent/secret.example.yaml` is a template only and shows the expected
key names. Migration to sealed-secrets / SOPS is tracked in issue #3.

---

## Apply order

`tasks-mcp` must be reachable before `tasks-agent` starts, otherwise the
agent's first MCP call will fail.

```bash
# Tasks MCP server
kubectl apply -f deployments/tasks-mcp/ -n tasks-manager
kubectl rollout status deploy/tasks-mcp -n tasks-manager

# Tasks Manager Agent
kubectl apply -f deployments/tasks-agent/configmap.yaml \
              -f deployments/tasks-agent/deployment.yaml \
              -n tasks-manager
kubectl rollout status deploy/tasks-agent -n tasks-manager
```

The agent reads `TASKS_MCP_URL` from its ConfigMap; that URL points at the
in-cluster Service `tasks-mcp.tasks-manager.svc.cluster.local:8000/mcp`, so
the two pods talk over cluster DNS, never `localhost`.

---

## Verification

### Tasks MCP

```bash
# Pod healthy
kubectl get pods -n tasks-manager -l app=tasks-mcp
kubectl logs deploy/tasks-mcp -n tasks-manager --tail=20

# Smoke the live HTTP surface (13 automated checks)
kubectl port-forward svc/tasks-mcp 18000:8000 -n tasks-manager &
cd services/tasks-mcp
TASKS_MCP_URL=http://127.0.0.1:18000/mcp uv run python scripts/smoke.py
```

Expected: `PASS 1` … `PASS 13` then an informational line about restart
behaviour.

### Tasks Agent (end-to-end)

The v1 agent is a CLI. The Deployment runs `sleep infinity` and you drive
sessions via `kubectl exec`. This will be replaced when issue #4 lands a
FastAPI HTTP surface.

```bash
# Interactive session (default provider: gemini)
kubectl exec -it deploy/tasks-agent -n tasks-manager -- tasks-agent

# Override the provider for a single session
kubectl exec -it deploy/tasks-agent -n tasks-manager -- \
  env TASKS_AGENT_PROVIDER=openai tasks-agent

# Non-interactive smoke (capture + list)
printf 'capture: buy milk on 2026-05-04T17:00:00Z\nlist my tasks\n' | \
  kubectl exec -i deploy/tasks-agent -n tasks-manager -- tasks-agent
```

Expected behaviour:
- The agent connects to MCP and reports `Tasks Manager Agent ready ...`.
- It refuses to guess timezones — supply ISO-8601 UTC (`...Z`) datetimes.
- Capture / list / modify / resolve / remove flows round-trip through MCP.

---

## Configuration reference

### `tasks-mcp` env (ConfigMap `tasks-mcp-config`)

| Key                   | Default     | Notes                                  |
|-----------------------|-------------|----------------------------------------|
| `TASKS_MCP_HOST`      | `0.0.0.0`   |                                        |
| `TASKS_MCP_PORT`      | `8000`      | Must match the Service's `targetPort`. |
| `TASKS_MCP_LOG_LEVEL` | `INFO`      |                                        |

### `tasks-agent` env (ConfigMap `tasks-agent-config`)

| Key                          | Default                                                                    |
|------------------------------|----------------------------------------------------------------------------|
| `TASKS_AGENT_PROVIDER`       | `gemini`                                                                   |
| `TASKS_AGENT_GEMINI_MODEL`   | `gemini-3.1-flash-lite-preview`                                            |
| `TASKS_AGENT_OPENAI_MODEL`   | `gpt-4.1-mini`                                                             |
| `TASKS_MCP_URL`              | `http://tasks-mcp.tasks-manager.svc.cluster.local:8000/mcp`                |

### `tasks-agent` secrets (Secret `tasks-agent-secrets`, imperative)

| Key              | Notes                              |
|------------------|------------------------------------|
| `GEMINI_API_KEY` | Required when provider is `gemini` |
| `OPENAI_API_KEY` | Required when provider is `openai` |

---

## Design notes

- **Single replica, `Recreate` strategy.** `tasks-mcp` keeps state in
  memory and does not coordinate across pods. Lifting this requires
  persistence (out of scope for v1).
- **Images use `:latest` with `imagePullPolicy: Always`.** This is a
  dev cluster — convenience over reproducibility. CI republishes
  `:latest` (alongside `<short-sha>` and semver tags) on every push to
  `main`, so a `kubectl rollout restart` after CI is green pulls the
  new build. For production, switch to pinned SHA tags + `IfNotPresent`
  before going live.
- **Read-only root filesystem.** Both containers run as a non-root user
  with `readOnlyRootFilesystem: true` and all capabilities dropped. The
  agent mounts an `emptyDir` at `/tmp` because the OpenAI Agents SDK
  writes a sandbox there at startup.
- **No probes (yet).** Neither service exposes a `/healthz` or `/readyz`
  endpoint today. Tracked in issue #1.
- **No ServiceAccount / RBAC / NetworkPolicy.** Dev cluster only. Tracked
  in issue #2.
- **Agent runs `sleep infinity`.** The CLI has no HTTP surface yet, so
  the Deployment shape is a placeholder driven via `kubectl exec`.
  Replaced in issue #4.

---

## Rolling out a new build

After a push to `main` that touches `services/tasks-mcp/**` or
`services/tasks-agent/**`, the corresponding GitHub Actions workflow
rebuilds the image and republishes `:latest`. Once the workflow is
green:

```bash
# Pick whichever service(s) you rebuilt
kubectl rollout restart deploy/tasks-mcp   -n tasks-manager
kubectl rollout restart deploy/tasks-agent -n tasks-manager

# Watch the new pod come up
kubectl rollout status deploy/tasks-mcp   -n tasks-manager
kubectl rollout status deploy/tasks-agent -n tasks-manager
```

Because the manifests use `imagePullPolicy: Always`, the restart
forces a fresh pull from ghcr — you do not need to edit the manifest.

To confirm which build is running, check the image digest on the pod:

```bash
kubectl get pod -n tasks-manager -l app=tasks-mcp \
  -o jsonpath='{.items[0].status.containerStatuses[0].imageID}{"\n"}'
```

---

## Tear down

```bash
kubectl delete -f deployments/tasks-agent/deployment.yaml \
               -f deployments/tasks-agent/configmap.yaml \
               -n tasks-manager
kubectl delete -f deployments/tasks-mcp/ -n tasks-manager

# Optional: drop secrets and namespace
kubectl delete secret tasks-agent-secrets ghcr-pull -n tasks-manager
kubectl delete namespace tasks-manager
```

---

## Related issues

- [#1](https://github.com/mjunaidca/ai-native-tasks-manager/issues/1) — `tasks-mcp` health endpoints + probes
- [#2](https://github.com/mjunaidca/ai-native-tasks-manager/issues/2) — Helm + Ingress + HPA + PDB + RBAC + NetworkPolicy
- [#3](https://github.com/mjunaidca/ai-native-tasks-manager/issues/3) — Sealed-secrets / SOPS
- [#4](https://github.com/mjunaidca/ai-native-tasks-manager/issues/4) — `tasks-agent` FastAPI surface
