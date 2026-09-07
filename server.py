from typing import Annotated, Optional
from pydantic import Field
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
import subprocess
import json

# Initialize FastMCP Server for Kubernetes
# This server is READ-ONLY: it never creates, modifies, or deletes cluster resources.
mcp = FastMCP("k8s-mcp-server")

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def _run_kubectl(args: list[str]) -> subprocess.CompletedProcess:
    """Run a kubectl command and return the completed process, raising on non-zero exit."""
    return subprocess.run(args, capture_output=True, text=True, check=True)


@mcp.tool(annotations=READ_ONLY)
def list_pods(
    namespace: Annotated[str, Field(description="Kubernetes namespace to list pods from.")] = "default",
) -> str:
    """List all pods in a given Kubernetes namespace along with pod phase and per-container ready state.

    This is a read-only operation (runs `kubectl get pods -n <namespace> -o json`) and never
    mutates cluster state.

    Returns a newline-separated list formatted as:
        - <pod-name>: phase=<Phase> containers=[<container>: ready=<bool> restarts=<n>, ...]

    Example:
        - web-7f9c: phase=Running containers=[web: ready=True restarts=0]
        - worker-2a1b: phase=Running containers=[worker: ready=False restarts=5]

    If no pods are found, returns "No pods found in this namespace."
    On failure, returns a string prefixed with "Error listing pods:" containing the kubectl error.
    """
    try:
        result = _run_kubectl(["kubectl", "get", "pods", "-n", namespace, "-o", "json"])
        data = json.loads(result.stdout)
        pods = []
        for item in data.get("items", []):
            name = item["metadata"]["name"]
            phase = item["status"].get("phase", "Unknown")
            container_statuses = item["status"].get("containerStatuses", [])
            containers = [
                f"{c['name']}: ready={c.get('ready', False)} restarts={c.get('restartCount', 0)}"
                for c in container_statuses
            ]
            containers_str = ", ".join(containers) if containers else "no container status"
            pods.append(f"- {name}: phase={phase} containers=[{containers_str}]")
        return "\n".join(pods) if pods else "No pods found in this namespace."
    except Exception as e:
        return f"Error listing pods: {str(e)}"


@mcp.tool(annotations=READ_ONLY)
def get_pod_logs(
    pod_name: Annotated[str, Field(description="Name of the pod to fetch logs from.")],
    namespace: Annotated[str, Field(description="Kubernetes namespace the pod lives in.")] = "default",
    tail_lines: Annotated[int, Field(description="Number of most recent log lines to retrieve.", ge=1, le=10000)] = 50,
    container: Annotated[
        Optional[str],
        Field(description="Container name to fetch logs from. Required if the pod has more than one container."),
    ] = None,
) -> str:
    """Retrieve the last N lines of logs from a specific pod (optionally a specific container).

    Read-only: runs `kubectl logs <pod> -n <namespace> --tail=<n> [-c <container>]`.

    If the pod has multiple containers and `container` is not specified, kubectl will error;
    pass `container` explicitly in that case.

    Returns raw log text, or "Logs are empty." if there is no output.
    On failure, returns a string prefixed with "Error retrieving logs:" containing the kubectl error.
    """
    try:
        args = ["kubectl", "logs", pod_name, "-n", namespace, f"--tail={tail_lines}"]
        if container:
            args.extend(["-c", container])
        result = _run_kubectl(args)
        return result.stdout if result.stdout else "Logs are empty."
    except Exception as e:
        return f"Error retrieving logs: {str(e)}"


@mcp.tool(annotations=READ_ONLY)
def describe_pod(
    pod_name: Annotated[str, Field(description="Name of the pod to describe.")],
    namespace: Annotated[str, Field(description="Kubernetes namespace the pod lives in.")] = "default",
) -> str:
    """Return detailed information about a pod: conditions, events, resource requests/limits, and volumes.

    Read-only: runs `kubectl describe pod <pod_name> -n <namespace>`.

    Useful for diagnosing scheduling failures, image pull errors, OOMKills, and CrashLoopBackOff
    root causes that aren't visible from `list_pods` alone.

    Returns the raw kubectl describe output as text.
    On failure, returns a string prefixed with "Error describing pod:" containing the kubectl error.
    """
    try:
        result = _run_kubectl(["kubectl", "describe", "pod", pod_name, "-n", namespace])
        return result.stdout if result.stdout else "No description output returned."
    except Exception as e:
        return f"Error describing pod: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
