from mcp.server.fastmcp import FastMCP
import subprocess
import json

# Initialize FastMCP Server for Kubernetes
mcp = FastMCP("k8s-mcp-server")

@mcp.tool()
def list_pods(namespace: str = "default") -> str:
    """List all pods in a given Kubernetes namespace and show their status."""
    try:
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
        pods = []
        for item in data.get("items", []):
            name = item["metadata"]["name"]
            status = item["status"]["phase"]
            pods.append(f"- **{name}**: {status}")
        return "\n".join(pods) if pods else "No pods found in this namespace."
    except Exception as e:
        return f"Error listing pods: {str(e)}"

@mcp.tool()
def get_pod_logs(pod_name: str, namespace: str = "default", tail_lines: int = 50) -> str:
    """Retrieve the last N lines of logs from a specific pod."""
    try:
        result = subprocess.run(
            ["kubectl", "logs", pod_name, "-n", namespace, f"--tail={tail_lines}"],
            capture_output=True, text=True, check=True
        )
        return result.stdout if result.stdout else "Logs are empty."
    except Exception as e:
        return f"Error retrieving logs: {str(e)}"

if __name__ == "__main__":
    mcp.run()
