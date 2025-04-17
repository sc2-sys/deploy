import os
import subprocess
import tempfile
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Define your proxy settings
HTTP_PROXY = "http://133.9.80.129:3128"
HTTPS_PROXY = "http://133.9.80.129:3128"
FTP_PROXY = "http://133.9.80.129:3128"
NO_PROXY = "localhost,127.0.0.1,10.96.0.0/12,192.168.0.0/16,.svc,.cluster.local"

def configure_docker_proxy():
    """Configure Docker daemon to use proxy settings."""
    proxy_dir = Path("/etc/systemd/system/docker.service.d")
    proxy_conf = proxy_dir / "proxy.conf"
    
    # Create the directory if it doesn't exist
    proxy_dir.mkdir(parents=True, exist_ok=True)
    
    # Create proxy configuration
    config_content = """[Service]
Environment="HTTP_PROXY={}"
Environment="HTTPS_PROXY={}"
Environment="FTP_PROXY={}"
Environment="NO_PROXY={}"
""".format(HTTP_PROXY, HTTPS_PROXY, FTP_PROXY, NO_PROXY)
    
    # Write configuration file
    with open(proxy_conf, 'w') as f:
        f.write(config_content)
    
    # Reload systemd and restart Docker
    subprocess.run(["systemctl", "daemon-reload"])
    subprocess.run(["systemctl", "restart", "docker"])
    
    logger.info("Docker proxy configuration applied")

def configure_containerd_proxy():
    """Configure containerd to use proxy settings."""
    proxy_dir = Path("/etc/systemd/system/containerd.service.d")
    proxy_conf = proxy_dir / "proxy.conf"
    
    # Create directory if it doesn't exist
    proxy_dir.mkdir(parents=True, exist_ok=True)
    
    # Create proxy configuration content
    config_content = """[Service]
Environment="HTTP_PROXY={}"
Environment="HTTPS_PROXY={}"
Environment="FTP_PROXY={}"
""".format(HTTP_PROXY, HTTPS_PROXY, FTP_PROXY)
    
    # Write configuration file
    with open(proxy_conf, 'w') as f:
        f.write(config_content)
    
    # Reload systemd and restart containerd
    subprocess.run(["systemctl", "daemon-reload"])
    subprocess.run(["systemctl", "restart", "containerd"])
    
    logger.info("Containerd proxy configuration applied")

def configure_go_proxy():
    """Configure Go to use proxy settings."""
    # Set environment variables for Go
    go_env = {
        "GOPROXY": "https://proxy.golang.org,direct",
        "HTTP_PROXY": HTTP_PROXY,
        "HTTPS_PROXY": HTTPS_PROXY
    }
    
    # Update environment file to make settings persistent
    with open("/etc/environment", "a") as f:
        for key, value in go_env.items():
            f.write(f"{key}={value}\n")
    
    # Apply to current environment
    os.environ.update(go_env)
    
    logger.info("Go proxy configuration applied")

def configure_kubelet_proxy():
    """Configure kubelet to use proxy settings."""
    proxy_dir = Path("/etc/systemd/system/kubelet.service.d")
    proxy_conf = proxy_dir / "proxy.conf"
    
    # Create directory if it doesn't exist
    proxy_dir.mkdir(parents=True, exist_ok=True)
    
    # Create proxy configuration content
    config_content = """[Service]
Environment="HTTP_PROXY={}"
Environment="HTTPS_PROXY={}"
Environment="FTP_PROXY={}"
""".format(HTTP_PROXY, HTTPS_PROXY, FTP_PROXY)
    
    # Write configuration file
    with open(proxy_conf, 'w') as f:
        f.write(config_content)
    
    # Reload systemd
    subprocess.run(["systemctl", "daemon-reload"])
    # Only restart kubelet if it's running
    try:
        subprocess.run(["systemctl", "is-active", "--quiet", "kubelet"])
        subprocess.run(["systemctl", "restart", "kubelet"])
    except:
        logger.info("Kubelet not running, no restart needed")
    
    logger.info("Kubelet proxy configuration applied")

def cleanup_proxy_configs():
    """Remove all proxy configurations."""
    # List of proxy configuration files to remove
    proxy_configs = [
        "/etc/systemd/system/docker.service.d/proxy.conf",
        "/etc/systemd/system/containerd.service.d/proxy.conf",
        "/etc/systemd/system/kubelet.service.d/proxy.conf",
        # Add other proxy files as needed
    ]
    
    # Remove each configuration file
    for config in proxy_configs:
        try:
            os.remove(config)
            logger.info(f"Removed {config}")
        except FileNotFoundError:
            logger.info(f"{config} not found, skipping")
    
    # Reload systemd
    subprocess.run(["systemctl", "daemon-reload"])
    
    logger.info("Proxy configurations cleaned up")

def configure_all_proxies():
    """Apply all proxy configurations."""
    configure_docker_proxy()
    configure_containerd_proxy()
    configure_go_proxy()
    configure_kubelet_proxy()
    # Add other proxy configurations as needed
    
    logger.info("All proxy configurations applied")

# Example usage:
# if __name__ == "__main__":
#     import argparse
    
#     parser = argparse.ArgumentParser(description="Manage proxy configurations")
#     parser.add_argument("--apply", action="store_true", help="Apply all proxy configurations")
#     parser.add_argument("--cleanup", action="store_true", help="Remove all proxy configurations")
    
#     args = parser.parse_args()
    
#     if args.apply:
#         configure_all_proxies()
#     elif args.cleanup:
#         cleanup_proxy_configs()
#     else:
#         parser.print_help()