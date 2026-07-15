import os
import sys
from mcp.server.fastmcp import FastMCP
from kubernetes import client, config
from kubernetes.client.rest import ApiException

mcp = FastMCP("k8s-platform-mcp")

try:
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        config.load_incluster_config()
    else:
        config.load_kube_config()
    v1 = client.CoreV1Api()
except Exception as e:
    v1 = None

@mcp.tool()
def list_pods(namespace: str = "default") -> str:
    """List all pods in a given Kubernetes namespace."""
    if not v1:
        return "Error: Kubernetes client not initialized."
    try:
        pods = v1.list_namespaced_pod(namespace=namespace)
        items = [f"Pod: {p.metadata.name} | Status: {p.status.phase}" for p in pods.items]
        return "\n".join(items) if items else "No pods found."
    except ApiException as e:
        return f"K8s API Error: {e.reason}"

@mcp.tool()
def get_pod_logs(pod_name: str, namespace: str = "default", tail_lines: int = 50) -> str:
    """Fetch logs of a specific pod."""
    if not v1:
        return "Error: Kubernetes client not initialized."
    try:
        return v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, tail_lines=tail_lines)
    except ApiException as e:
        return f"Error: {e.reason}"

if __name__ == "__main__":
    mcp.run()