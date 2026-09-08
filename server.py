import os
import logging
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from kubernetes import client, config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("k8s-mcp-server")

# Initialize FastMCP Server
mcp = FastMCP(
    name="k8s-mcp-server",
    instructions=(
        "Production-grade MCP server for Kubernetes cluster diagnostics, workload health, "
        "and pod event inspection. Enforces strict read-only cluster observation."
    ),
)


def _init_k8s_client():
    """Initializes Kubernetes client from in-cluster service account or local kubeconfig."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


# ==============================================================================
# Cluster Health & Node Inspection
# ==============================================================================


@mcp.tool()
async def get_cluster_nodes() -> List[Dict[str, Any]]:
    """
    List all cluster nodes with internal IP addresses, roles, Kubernetes versions, and ready states.

    ### Usage Guidelines
    - Diagnostic discovery tool for inspecting node capacity and Kubernetes control plane versions.
    """
    _init_k8s_client()
    core_api = client.CoreV1Api()
    nodes = core_api.list_node()

    results = []
    for node in nodes.items:
        conditions = {c.type: c.status for c in node.status.conditions}
        ready_status = conditions.get("Ready", "Unknown")

        roles = [
            label.split("/")[-1]
            for label in node.metadata.labels
            if label.startswith("node-role.kubernetes.io/")
        ]

        results.append(
            {
                "name": node.metadata.name,
                "status": "Ready" if ready_status == "True" else "NotReady",
                "roles": roles or ["worker"],
                "kubelet_version": node.status.node_info.kubelet_version,
                "os_image": node.status.node_info.os_image,
                "capacity": {
                    "cpu": node.status.capacity.get("cpu"),
                    "memory": node.status.capacity.get("memory"),
                    "pods": node.status.capacity.get("pods"),
                },
            }
        )
    return results


# ==============================================================================
# Pod Diagnostics & Log Streaming
# ==============================================================================


@mcp.tool()
async def get_pod_diagnostics(
    namespace: str = Field(
        default="default",
        description="Target Kubernetes namespace containing the pods to inspect.",
    ),
    label_selector: Optional[str] = Field(
        default=None,
        description="Kubernetes label selector expression (e.g. 'app=api' or 'tier=backend').",
    ),
) -> List[Dict[str, Any]]:
    """
    Inspect pod health across a namespace, detecting restart counts, OOMKills, and CrashLoopBackOffs.

    ### Usage Guidelines
    - Evaluates container state transitions and abnormal restart loops for incident debugging.
    """
    _init_k8s_client()
    core_api = client.CoreV1Api()
    kwargs = {}
    if label_selector:
        kwargs["label_selector"] = label_selector

    pods = core_api.list_namespaced_pod(namespace=namespace, **kwargs)

    diagnostics = []
    for pod in pods.items:
        containers_summary = []
        has_abnormal_state = False

        if pod.status.container_statuses:
            for c in pod.status.container_statuses:
                state_str = "Running"
                reason = None
                if c.state.waiting:
                    state_str = "Waiting"
                    reason = c.state.waiting.reason
                    has_abnormal_state = True
                elif c.state.terminated:
                    state_str = "Terminated"
                    reason = c.state.terminated.reason
                    if c.state.terminated.exit_code != 0:
                        has_abnormal_state = True

                containers_summary.append(
                    {
                        "name": c.name,
                        "ready": c.ready,
                        "restart_count": c.restart_count,
                        "state": state_str,
                        "reason": reason,
                    }
                )

        diagnostics.append(
            {
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "pod_ip": pod.status.pod_ip,
                "node_name": pod.spec.node_name,
                "abnormal_state": has_abnormal_state,
                "containers": containers_summary,
            }
        )
    return diagnostics


@mcp.tool()
async def get_pod_logs(
    namespace: str = Field(
        description="Kubernetes namespace containing the target pod.",
    ),
    pod_name: str = Field(
        description="Exact metadata name of the pod to extract stdout/stderr logs from.",
    ),
    container_name: Optional[str] = Field(
        default=None,
        description="Target container name within multi-container pods. Defaults to primary container.",
    ),
    tail_lines: int = Field(
        default=100,
        ge=10,
        le=500,
        description="Number of most recent log lines to retrieve (between 10 and 500).",
    ),
    previous: bool = Field(
        default=False,
        description="If true, prints the logs for the previous instance of the container if it crashed.",
    ),
) -> Dict[str, Any]:
    """
    Retrieve real-time or post-crash container logs from a specific pod.

    ### Usage Guidelines
    - Crucial for diagnosing root causes during CrashLoopBackOff or application startup failures.
    """
    _init_k8s_client()
    core_api = client.CoreV1Api()
    kwargs: Dict[str, Any] = {
        "namespace": namespace,
        "name": pod_name,
        "tail_lines": tail_lines,
        "previous": previous,
    }
    if container_name:
        kwargs["container"] = container_name

    try:
        logs = core_api.read_namespaced_pod_log(**kwargs)
        return {
            "pod_name": pod_name,
            "namespace": namespace,
            "container": container_name or "primary",
            "lines_retrieved": len(logs.splitlines()),
            "logs": logs,
        }
    except client.exceptions.ApiException as e:
        return {
            "error": True,
            "status": e.status,
            "reason": e.reason,
            "message": e.body,
        }


# ==============================================================================
# Events & Ingress Inspection
# ==============================================================================


@mcp.tool()
async def list_warning_events(
    namespace: Optional[str] = Field(
        default=None,
        description="Target namespace to filter warning events. If omitted, queries cluster-wide events.",
    ),
) -> List[Dict[str, Any]]:
    """
    Query recent Warning events across pods, PVCs, nodes, and deployments.

    ### Usage Guidelines
    - Surfaces FailedScheduling, FailedMount, BackOff, and Unhealthy probe warnings.
    """
    _init_k8s_client()
    core_api = client.CoreV1Api()
    field_selector = "type=Warning"

    if namespace:
        events = core_api.list_namespaced_event(namespace=namespace, field_selector=field_selector)
    else:
        events = core_api.list_event_for_all_namespaces(field_selector=field_selector)

    results = []
    for ev in events.items:
        results.append(
            {
                "namespace": ev.metadata.namespace,
                "reason": ev.reason,
                "message": ev.message,
                "involved_object": f"{ev.involved_object.kind}/{ev.involved_object.name}",
                "count": ev.count,
                "first_timestamp": ev.first_timestamp.isoformat() if ev.first_timestamp else None,
                "last_timestamp": ev.last_timestamp.isoformat() if ev.last_timestamp else None,
            }
        )
    return results


@mcp.tool()
async def list_ingresses(
    namespace: Optional[str] = Field(
        default=None,
        description="Target namespace to list ingress routes from. If omitted, scans across all namespaces.",
    ),
) -> List[Dict[str, Any]]:
    """
    Inspect HTTP/HTTPS routing configurations, ingress classes, hosts, and TLS certificates.

    ### Usage Guidelines
    - Useful for network troubleshooting, DNS routing audits, and TLS certificate inspection.
    """
    _init_k8s_client()
    networking_api = client.NetworkingV1Api()

    if namespace:
        ingresses = networking_api.list_namespaced_ingress(namespace=namespace)
    else:
        ingresses = networking_api.list_ingress_for_all_namespaces()

    results = []
    for ing in ingresses.items:
        rules = []
        if ing.spec.rules:
            for rule in ing.spec.rules:
                paths = []
                if rule.http and rule.http.paths:
                    for p in rule.http.paths:
                        paths.append(
                            {
                                "path": p.path,
                                "path_type": p.path_type,
                                "service": p.backend.service.name if p.backend.service else None,
                                "port": p.backend.service.port.number if p.backend.service and p.backend.service.port else None,
                            }
                        )
                rules.append({"host": rule.host, "paths": paths})

        tls_hosts = []
        if ing.spec.tls:
            for tls in ing.spec.tls:
                tls_hosts.extend(tls.hosts or [])

        results.append(
            {
                "name": ing.metadata.name,
                "namespace": ing.metadata.namespace,
                "ingress_class_name": ing.spec.ingress_class_name,
                "rules": rules,
                "tls_hosts": tls_hosts,
            }
        )
    return results


if __name__ == "__main__":
    mcp.run(transport="stdio")
