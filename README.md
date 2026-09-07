# k8s-mcp-server

> Read-only Model Context Protocol (MCP) server for debugging, analyzing, and diagnosing Kubernetes clusters directly from AI agents.

[![Glama Quality Score](https://glama.ai/mcp/servers/akkireddy-challa/k8s-mcp-server/badges/score.svg)](https://glama.ai/mcp/servers/akkireddy-challa/k8s-mcp-server)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)

---

## What is this?

`k8s-mcp-server` exposes Kubernetes cluster information through the [Model Context Protocol](https://modelcontextprotocol.io/), allowing AI agents (Claude, GPT-4, etc.) to inspect and diagnose your clusters safely.

All operations are **read-only** — no mutations, no deployments, no deletions. The server inspects cluster state and returns structured data to the AI agent.

---

## Available Tools

| Tool | Description |
|---|---|
| `list_namespaces` | Discover and list all namespaces available in the cluster |
| `list_pods` | List all pods in a namespace with their status, IP, and readiness |
| `get_pod_logs` | Retrieve stdout/stderr log output from a specific pod/container |
| `get_cluster_events` | Fetch Warning and Error events to diagnose crash loops and scheduling issues |

---

## Quick Start

### Prerequisites

- Python 3.11+
- `kubectl` installed and configured with cluster access
- A valid kubeconfig pointing to your target cluster (`~/.kube/config`)

### Run locally

```bash
git clone [https://github.com/akkireddy-challa/k8s-mcp-server.git](https://github.com/akkireddy-challa/k8s-mcp-server.git)
cd k8s-mcp-server
pip install -r requirements.txt
python server.py
```

### Run with Docker

```bash
docker run --rm \
  -v ~/.kube:/root/.kube:ro \
  ghcr.io/akkireddy-challa/k8s-mcp-server:latest
```

### Configure with Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "k8s": {
      "command": "python",
      "args": ["/path/to/k8s-mcp-server/server.py"]
    }
  }
}
```

---

## Example Usage

Once connected, you can ask your AI agent:

- *"List all namespaces in the cluster"*
- *"List all pods in the production namespace"*
- *"Show me the last 100 lines of logs from pod my-api-xyz"*
- *"Are there any Warning events in the default namespace?"*

---

## Security Model

- **Read-only**: only inspection, read, and log operations are exposed
- **Namespace-scoped**: tools accept a namespace parameter; default is `default`
- **No cluster credentials in prompts**: kubeconfig is read from the host filesystem, never passed through the MCP protocol
- **Recommended RBAC**: create a dedicated service account with minimal permissions

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: k8s-mcp-reader
rules:
- apiGroups: [""]
  resources: ["namespaces", "pods", "pods/log", "events"]
  verbs: ["get", "list"]
```

---

## Contributing

Contributions are welcome. Please open an issue before submitting a PR to discuss the change.

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-tool`
3. Commit your changes: `git commit -m 'feat: add describe_deployment tool'`
4. Push and open a Pull Request

---

## Roadmap

- [ ] `describe_deployment` — show deployment status and rollout history
- [ ] `check_node_health` — node conditions and resource pressure
- [ ] `list_services` — services and their endpoints
- [ ] `get_resource_usage` — top pods/nodes via metrics-server
- [ ] Multi-cluster support via kubeconfig contexts
- [ ] Unit tests with mocked responses
- [ ] GitHub Actions CI (lint, test, Docker build)

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

Built by [Akkireddy Challa](https://github.com/akkireddy-challa) — Platform Engineer at Telia, Stockholm.
