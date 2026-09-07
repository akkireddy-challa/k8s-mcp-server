"""
Kubernetes MCP Server
A Model Context Protocol server for debugging, analyzing, and diagnosing Kubernetes clusters.
"""

from typing import Optional
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from kubernetes import client, config

# Initialize FastMCP Server
mcp = FastMCP("k8s-mcp-server")


def _load_kube_config() -> None:
    """Load local kubeconfig or cluster configuration."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


@mcp.tool()
async def list_namespaces() -> str:
    """
    List all namespaces available in the Kubernetes cluster.

    Use this tool to discover cluster boundaries and verify target namespaces
    before querying pod or service resources.
    """
    _load_kube_config()
    v1 = client.CoreV1Api()
    namespaces = v1.list_namespace()
    names = [ns.metadata.name for ns in namespaces.items if ns.metadata and ns.metadata.name]
    return f"Namespaces ({len(names)}):\n" + "\n".join(f"- {name}" for name in names)


@mcp.tool()
async def list_pods(
    namespace: str = Field(
        default="default",
        description="Kubernetes namespace to list pods from. Defaults to 'default'.",
    ),
    label_selector: Optional[str] = Field(
        default=None,
        description="Optional Kubernetes label query (e.g. 'app=frontend' or 'tier=backend').",
    ),
) -> str:
    """
    List pods within a specific namespace with status and container readiness.

    Returns the pod name, status phase, restart counts, and IP address.
    """
    _load_kube_config()
    v1 = client.CoreV1Api()
    kwargs = {}
    if label_selector:
        kwargs["label_selector"] = label_selector

    pods = v1.list_namespaced_pod(namespace=namespace, **kwargs)
    if not pods.items:
        return f"No pods found in namespace '{namespace}'."

    results = []
    for p in pods.items:
        name = p.metadata.name if p.metadata else "unknown"
        phase = p.status.phase if p.status else "Unknown"
        pod_ip = p.status.pod_ip if p.status else "None"
        results.append(f"- {name} | Phase: {phase} | IP: {pod_ip}")

    return f"Pods in '{namespace}' ({len(results)}):\n" + "\n".join(results)


@mcp.tool()
async def get_pod_logs(
    pod_name: str = Field(
        description="The exact name of the pod to retrieve logs from.",
    ),
    namespace: str = Field(
        default="default",
        description="Kubernetes namespace containing the pod.",
    ),
    tail_lines: int = Field(
        default=100,
        description="Number of most recent log lines to fetch. Default is 100.",
    ),
    container: Optional[str] = Field(
        default=None,
        description="Specific container name if the pod contains multiple containers.",
    ),
) -> str:
    """
    Fetch stdout and stderr container logs from a specific pod for troubleshooting.

    Use this tool to diagnose crash loops, runtime errors, or startup failures.
    """
    _load_kube_config()
    v1 = client.CoreV1Api()
    kwargs = {"tail_lines": tail_lines}
    if container:
        kwargs["container"] = container

    try:
        logs = v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, **kwargs)
        return logs or "(No logs returned)"
    except Exception as e:
        return f"Error retrieving logs for pod {pod_name}: {str(e)}"


@mcp.tool()
async def get_cluster_events(
    namespace: Optional[str] = Field(
        default="default",
        description="Namespace to inspect for warning and error events. Pass 'all' or omit for all namespaces.",
    ),
    warning_only: bool = Field(
        default=True,
        description="When true, filters only Warning events (e.g. BackOff, FailedScheduling, Unhealthy).",
    ),
) -> str:
    """
    Retrieve Kubernetes cluster events to diagnose scheduling failures or unhealthy workloads.
    """
    _load_kube_config()
    v1 = client.CoreV1Api()
    if namespace and namespace.lower() != "all":
        events = v1.list_namespaced_event(namespace=namespace)
    else:
        events = v1.list_event_for_all_namespaces()

    matched = []
    for event in events.items:
        event_type = event.type or "Normal"
        if warning_only and event_type != "Warning":
            continue
        obj = event.involved_object.name if event.involved_object else "cluster"
        reason = event.reason or "UnknownReason"
        message = event.message or ""
        matched.append(f"[{event_type}] {obj} - {reason}: {message}")

    if not matched:
        return "No matching events found."

    return f"Events ({len(matched)}):\n" + "\n".join(matched[-50:])


if __name__ == "__main__":
    mcp.run(transport="stdio")
