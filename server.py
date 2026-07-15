import os
import sys
from fastmcp import FastMCP
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# Initialize FastMCP Server
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
def get_cluster_context() -> str:
    """Returns the active Kubernetes context details."""
    if not v1:
        return "Error: Kubernetes client not initialized. Local kubeconfig not found."
    try:
        contexts, active_context = config.list_kube_config_contexts()
        if not active_context:
            return "Connected to: In-Cluster Configuration (Pod ServiceAccount)"
        
        # Fixed: Removed syntax issue with trailing comma in the dict lookup
        context_info = active_context.get('context', {})
        
        # Fixed: Added curly braces to properly evaluate f-string variables
        return f"Active Context: {active_context.get('name')}\nCluster: {context_info.get('cluster')}\nAuth User: {context_info.get('user')}\nNamespace: {context_info.get('namespace', 'default')}"
    except Exception as e:
        return f"Failed to fetch context info: {str(e)}"

@mcp.tool()
def list_pods(namespace: str = "default") -> str:
    """List all pods in a given Kubernetes namespace. Returns pod name, status, restarts, and IP."""
    if not v1:
        return "Error: Kubernetes client not initialized."
    try:
        pods = v1.list_namespaced_pod(namespace=namespace)
        pod_list = []
        for pod in pods.items:
            restarts = 0
            if pod.status.container_statuses:
                restarts = sum(cs.restart_count for cs in pod.status.container_statuses)
            # Fixed: Added evaluation brackets for variables inside the f-string
            pod_list.append(
                f"Name: {pod.metadata.name} | Status: {pod.status.phase} | Restarts: {restarts} | IP: {pod.status.pod_ip}"
            )
        return "\n".join(pod_list) if pod_list else "No pods found in this namespace."
    except ApiException as e:
        return f"K8s API Error: {e.reason}"

if __name__ == "__main__":
    mcp.run()
