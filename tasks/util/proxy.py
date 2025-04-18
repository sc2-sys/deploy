import os
import subprocess
import tempfile
import logging
from pathlib import Path

from subprocess import run, CalledProcessError
import re

logger = logging.getLogger(__name__)

def get_proxy_settings():
    """Detect proxy settings from environment and system configuration.
    
    Checks for proxy settings in:
    1. Current environment variables
    2. /etc/environment file
    
    Returns:
        dict: Dictionary containing proxy settings
    """
    proxy_settings = {
        'http_proxy': '',
        'https_proxy': '',
        'ftp_proxy': '',
        'no_proxy': ''
    }

    # Check current environment variables (case insensitive)
    for env_var in os.environ:
        lower_var = env_var.lower()
        if lower_var in proxy_settings:
            proxy_settings[lower_var] = os.environ[env_var]
        elif lower_var == 'http_proxy':
            proxy_settings['http_proxy'] = os.environ[env_var]
        elif lower_var == 'https_proxy':
            proxy_settings['https_proxy'] = os.environ[env_var]
        elif lower_var == 'ftp_proxy':
            proxy_settings['ftp_proxy'] = os.environ[env_var]
        elif lower_var == 'no_proxy':
            proxy_settings['no_proxy'] = os.environ[env_var]

    # Check /etc/environment if values are still empty
    if not all(proxy_settings.values()):
        try:
            if Path('/etc/environment').exists():
                with open('/etc/environment', 'r') as f:
                    for line in f:
                        # Look for proxy settings
                        match = re.match(r'^(https?_proxy|ftp_proxy|no_proxy)="?(.*?)"?$', 
                                        line.strip(), re.IGNORECASE)
                        if match:
                            key, value = match.groups()
                            proxy_settings[key.lower()] = value
        except Exception as e:
            logger.warning(f"Failed to read /etc/environment: {e}")
    
    logger.debug(f"Detected proxy settings: {proxy_settings}")
    return proxy_settings

def configure_docker_proxy():
    """Configure Docker daemon to use proxy settings detected form the system."""

    proxy_settings = get_proxy_settings()

    proxy_dir = Path("/etc/systemd/system/docker.service.d")
    proxy_conf = proxy_dir / "proxy.conf"
    
    try:
        run(f"sudo mkdir -p {proxy_dir}", shell=True, check=True)
        
        config_content = """[Service]
Environment="HTTP_PROXY={http_proxy}"
Environment="HTTPS_PROXY={https_proxy}"
Environment="FTP_PROXY={ftp_proxy}"
Environment="NO_PROXY={no_proxy}"
""".format(**proxy_settings)
        
        run(f"sudo tee {proxy_conf}", shell=True, input=config_content.encode(), check=True)

        run("sudo systemctl daemon-reload", shell=True, check=True)
        run("sudo systemctl restart docker", shell=True, check=True)
        
        logger.info("Docker proxy configuration applied successfully")
        return True
        
    except CalledProcessError as e:
        logger.error(f"Failed to configure Docker proxy: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error configuring Docker proxy: {e}")
        return False

def configure_containerd_proxy():
    """Configure containerd daemon to use proxy settings detected form the system."""

    proxy_settings = get_proxy_settings()

    proxy_dir = Path("/etc/systemd/system/containerd.service.d")
    proxy_conf = proxy_dir / "proxy.conf"
    
    try:
        run(f"sudo mkdir -p {proxy_dir}", shell=True, check=True)
        
        config_content = """[Service]
Environment="HTTP_PROXY={http_proxy}"
Environment="HTTPS_PROXY={https_proxy}"
Environment="FTP_PROXY={ftp_proxy}"
Environment="NO_PROXY={no_proxy}"
""".format(**proxy_settings)
        
        run(f"sudo tee {proxy_conf}", shell=True, input=config_content.encode(), check=True)

        run("sudo systemctl daemon-reload", shell=True, check=True)
        run("sudo systemctl restart containerd", shell=True, check=True)
        
        logger.info("containerd proxy configuration applied successfully")
        return True
        
    except CalledProcessError as e:
        logger.error(f"Failed to configure containerd proxy: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error configuring Docker proxy: {e}")
        return False

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
    
    proxy_configs = [
        "/etc/systemd/system/docker.service.d/proxy.conf",
        "/etc/systemd/system/containerd.service.d/proxy.conf",
        "/etc/systemd/system/kubelet.service.d/proxy.conf",
        # Add other proxy files as needed
    ]
    
    for config in proxy_configs:
        try:
            os.remove(config)
            logger.info(f"Removed {config}")
        except FileNotFoundError:
            logger.info(f"{config} not found, skipping")
    
    run("sudo systemctl daemon-reload", shell=True, check=True)
    logger.info("Proxy configurations cleaned up")

def configure_all_proxies():
    """Apply all proxy configurations."""
    
    configure_docker_proxy()
    configure_containerd_proxy()
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