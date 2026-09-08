# k8s-mcp-server

> Production-ready Kubernetes diagnostics and cluster observability MCP server for AI agents.

[![Glama Quality Score](https://glama.ai/mcp/servers/akkireddy-challa/k8s-mcp-server/badges/score.svg)](https://glama.ai/mcp/servers/akkireddy-challa/k8s-mcp-server)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-v1.30+-326CE5.svg)](https://kubernetes.io/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)

---

## What is this?

`k8s-mcp-server` is a Model Context Protocol (MCP) server providing automated, read-only diagnostic tools for inspecting Kubernetes clusters. It allows AI agents to troubleshoot pod crashes, inspect ingress routes, and analyze cluster-wide warning events safely.

---

## Available Tools

| Tool | Category | Description |
|---|---|---|
| `get_cluster_nodes` | Infrastructure | Lists nodes, readiness states, roles, and kubelet versions. |
| `get_pod_diagnostics` | Workloads | Detects abnormal pod phases, restart loops, and CrashLoopBackOffs. |
| `get_pod_logs` | Observability | Retrieves container stdout/stderr logs with tail limits and crash inspection. |
| `list_warning_events` | Diagnostics | Aggregates FailedScheduling, FailedMount, and BackOff warning events. |
| `list_ingresses` | Networking | Audits HTTP routing rules, host headers, and TLS certificates. |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Active Kubernetes cluster access (`~/.kube/config` or in-cluster ServiceAccount)
- Read-only RBAC privileges (`get`, `list` on core and networking API groups)

### Run Locally

```bash
git clone https://github.com/akkireddy-challa/k8s-mcp-server.git
cd k8s-mcp-server
pip install -r requirements.txt
python server.py
```

### Claude Desktop Configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kubernetes": {
      "command": "python",
      "args": ["/path/to/k8s-mcp-server/server.py"],
      "env": {
        "KUBECONFIG": "/Users/<username>/.kube/config"
      }
    }
  }
}
```

---

## Security Model

- **Strictly Read-Only**: Enforces GET and LIST operations only.
- **Zero-Secret Exposure**: Secrets and config maps are never inspected or surfaced to LLM context.
- **Flexible Auth**: Supports standard `~/.kube/config` context or in-cluster pod ServiceAccounts.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

Built by [Akkireddy Challa](https://github.com/akkireddy-challa) — Platform Engineer at Telia, Stockholm.
