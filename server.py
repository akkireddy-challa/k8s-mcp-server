"""
Kubernetes MCP Server
A read-only Model Context Protocol server providing rich diagnostics, resource
inspection, and log streaming for Kubernetes clusters.
"""

from typing import Optional
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from kubernetes import client, config

mcp = FastMCP(
    "k8s-mcp-server",
    instructions=(
        "Use this server to safely inspect, troubleshoot, and diagnose Kubernetes "
        "cluster resources. All tools are strictly read-only. Always check namespaces "
        "first when the target namespace is unknown or ambiguous."
    ),
)


def _load_kube_config() -> None:
    """Load in-cluster service account credentials or fallback to local kubeconfig."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


@mcp.tool()
async def list_namespaces() -> str:
    """
    List all namespaces present in the connected Kubernetes cluster.

    ### Usage Guidelines
    - Call this tool first when discovering available cluster domains or when
      the user does not supply an explicit namespace.
    - Do not use this tool to inspect workload health; use `list_pods` instead.

    ### Behavioral Transparency
    - Read-only operation.
    - Scans cluster-wide namespace resources using CoreV1Api.
    - Returns an alphabetically sorted list of namespace names with total count.
    """
    _load_kube_config()
    v1 = client.CoreV1Api()
    namespaces = v1.list_namespace()
    names = sorted(
        [ns.metadata.name for ns in namespaces.items if ns.metadata and ns.metadata.name]
    )
    if not names:
        return "No namespaces found or insufficient RBAC read permissions."
    return f"Cluster Namespaces ({len(names)} total):\n" + "\n".join(f"- {n}" for n in names)


@mcp.tool()
async def list_pods(
    namespace: str = Field(
        default="default",
        description="Target Kubernetes namespace (e.g. 'kube-system', 'production', or 'default').",
    ),
    label_selector: Optional[str] = Field(
        default=None,
        description="Kubernetes label query expression to filter pods (e.g. 'app=frontend' or 'tier=backend').",
    ),
) -> str:
    """
    List pods within a specified namespace along with their lifecycle phase and IP address.

    ### Usage Guidelines
    - Use this tool when identifying running workloads, crash loops, or verifying pod readiness.
    - If troubleshooting a failing pod, pass its name to `get_pod_logs` or call `get_cluster_events`.

    ### Behavioral Transparency
    - Read-only operation.
    - Omits internal container state arrays; highlights high-level phase (Running, Pending, Failed).
    """
    _load_kube_config()
    v1 = client.CoreV1Api()
    kwargs = {}
    if label_selector:
        kwargs["label_selector"] = label_selector

    pods = v1.list_namespaced_pod(namespace=namespace, **kwargs)
    if not pods.items:
        return f"No pods found in namespace '{namespace}' matching selector '{label_selector or 'none'}'."

    results = []
    for p in pods.items:
        name = p.metadata.name if p.metadata else "unknown"
        phase = p.status.phase if p.status else "Unknown"
        ip = p.status.pod_ip if p.status else "Pending"
        results.append(f"- Pod: {name} | Status: {phase} | IP: {ip}")

    return f"Pods in namespace '{namespace}' ({len(results)} found):\n" + "\n".join(results)


@mcp.tool()
async def get_pod_logs(
    pod_name: str = Field(
        description="Exact identifier name of the pod whose logs should be extracted (e.g. 'nginx-7854ff8877-abcde').",
    ),
    namespace: str = Field(
        default="default",
        description="Kubernetes namespace where the target pod resides. Defaults to 'default'.",
    ),
    tail_lines: int = Field(
        default=100,
        ge=1,
        le=2000,
        description="Number of most recent log lines to fetch. Constrained between 1 and 2000. Defaults to 100.",
    ),
    container: Optional[str] = Field(
        default=None,
        description="Specific container name within a multi-container pod. If omitted, Kubernetes selects the primary container.",
    ),
) -> str:
    """
    Extract stdout and stderr log streams from a pod container for diagnostics.

    ### Usage Guidelines
    - Use when investigating application crashes, HTTP 500 errors, or startup exceptions.
    - Keep `tail_lines` small (e.g. 50–200) to avoid overloading LLM token context.

    ### Behavioral Transparency
    - Read-only query.
    - Returns raw text log lines or a descriptive error if the pod or container does not exist.
    """
    _load_kube_config()
    v1 = client.CoreV1Api()
    kwargs = {"tail_lines": tail_lines}
    if container:
        kwargs["container"] = container

    try:
        logs = v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, **kwargs)
        return logs or f"(No log lines recorded for pod '{pod_name}')"
    except Exception as e:
        return f"Failed to retrieve logs for pod '{pod_name}' in namespace '{namespace}': {str(e)}"


@mcp.tool()
async def get_cluster_events(
    namespace: Optional[str] = Field(
        default="default",
        description="Namespace to query for events. Pass a specific namespace or 'all' to inspect entire cluster.",
    ),
    warning_only: bool = Field(
        default=True,
        description="When true, filters only Warning events (e.g. BackOff, FailedScheduling, Unhealthy).",
    ),
) -> str:
    """
    Retrieve Kubernetes cluster events to diagnose scheduling failures, node pressure, or eviction warnings.

    ### Usage Guidelines
    - Call this tool when pods remain stuck in 'Pending' or 'CrashLoopBackOff' states.
    - Use `warning_only=True` to eliminate normal informational noise during triage.

    ### Behavioral Transparency
    - Read-only query.
    - Returns up to the 50 most recent events formatted with event type, target resource, reason, and message.
    """
    _load_kube_config()
    v1 = client.CoreV1Api()
    if namespace and namespace.lower() != "all":
        events = v1.list_namespaced_event(namespace=namespace)
    else:
        events = v1.list_event_for_all_namespaces()

    matched = []
    for event in events.items:
        etype = event.type or "Normal"
        if warning_only and etype != "Warning":
            continue
        obj = event.involved_object.name if event.involved_object else "cluster"
        reason = event.reason or "UnknownReason"
        msg = event.message or ""
        matched.append(f"[{etype}] {obj} ({reason}): {msg}")

    if not matched:
        return f"No matching events found for namespace '{namespace or 'all'}ld (warning_only={warning_only})."

    return f"Events ({len(matched)} matching):\n" + "\n".join(matched[-50:])


@mcp.tool()
async def list_deployments(
    namespace: str = Field(
        default="default",
        description="Target Kubernetes namespace to list deployments from. Defaults to 'default'.",
    ),
) -> str:
    """
    List deployments in a namespace with desired vs available replica counts.

    ### Usage Guidelines
    - Use this tool to verify rollout status and check whether workloads meet desired scale.
    - When replicas show 0 available, use `list_pods` and `get_cluster_events` to locate the failure.

    ### Behavioral Transparency
    - Read-only operation using AppsV1Api.
    - Returns name, desired replicas, and ready replica count.
    """
    _load_kube_config()
    apps_v1 = client.AppsV1Api()
    deployments = apps_v1.list_namespaced_deployment(namespace=namespace)
    if not deployments.items:
        return f"No deployments found in namespace '{namespace}'."

    results = []
    for d in deployments.items:
        name = d.metadata.name if d.metadata else "unknown"
        replicas = d.spec.replicas if d.spec else 0
        ready = d.status.ready_replicas if (d.status and d.status.ready_replicas) else 0
        results.append(f"- Deployment: {name} | Replicas: {ready}/{replicas} Ready")

    return f"Deployments in namespace '{namespace}' ({len(results)} found):\n" + "\n".join(results)


@mcp.tool()
async def list_services(
    namespace: str = Field(
        default="default",
        description="Target Kubernetes namespace to inspect services in. Defaults to 'default'.",
    ),
) -> str:
    """
    List Kubernetes services, exposed ports, and service types within a namespace.

    ### Usage Guidelines
    - Use this tool when checking network ingress, internal DNS resolution, or service endpoints.
    - Complement with `list_pods` to confirm underlying backend endpoints exist.

    ### Behavioral Transparency
    - Read-only query using CoreV1Api.
    - Lists service name, type (ClusterIP, NodePort, LoadBalancer), and mapped ports.
    """
    _load_kube_config()
    v1 = client.CoreV1Api()
    services = v1.list_namespaced_service(namespace=namespace)
    if not services.items:
        return f"No services found in namespace '{namespace}'."

    results = []
    for s in services.items:
        name = s.metadata.name if s.metadata else "unknown"
        stype = s.spec.type if s.spec else "ClusterIP"
        ports = [f"{p.port}:{p.target_port}/{p.protocol}" for p in (s.spec.ports or [])] if s.spec else []
        results.append(f"- Service: {name} | Type: {stype} | Ports: {', '.join(ports) or 'None'}")

    return f"Services in namespace '{namespace}' ({len(results)} found):\n" + "\n".join(results)


if __name__ == "__main__":
    mcp.run(transport="stdio")
