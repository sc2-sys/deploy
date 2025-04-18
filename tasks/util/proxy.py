import os
import subprocess
import tempfile
import logging
from pathlib import Path

from subprocess import run, CalledProcessError
import re
from tasks.util.env import print_dotted_line

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

    return proxy_settings

def configure_docker_proxy(debug=False):
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
        
        run(f"sudo tee {proxy_conf} > /dev/null", shell=True, input=config_content.encode(), check=True)

        run("sudo systemctl daemon-reload", shell=True, check=True)
        run("sudo systemctl restart docker", shell=True, check=True)
        
        return True
        
    except CalledProcessError as e:
        print(f"Failed to configure Docker proxy: {e}", flush=True)
    except Exception as e:
        print(f"Unexpected error configuring Docker proxy: {e}", flush=True)

def configure_containerd_proxy(debug=False):
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
        
        run(f"sudo tee {proxy_conf} > /dev/null", shell=True, input=config_content.encode(), check=True)

        run("sudo systemctl daemon-reload", shell=True, check=True)
        run("sudo systemctl restart containerd", shell=True, check=True)
        
        return True
        
    except CalledProcessError as e:
        print(f"Failed to configure containerd proxy: {e}", flush=True)
    except Exception as e:
        print(f"Unexpected error configuring containerd proxy: {e}", flush=True)

def configure_kubelet_proxy(debug=False):
    """Configure kubelet daemon to use proxy settings detected form the system."""

    proxy_settings = get_proxy_settings()

    proxy_dir = Path("/etc/systemd/system/kubelet.service.d")
    proxy_conf = proxy_dir / "proxy.conf"
    
    try:
        run(f"sudo mkdir -p {proxy_dir}", shell=True, check=True)
        
        config_content = """[Service]
Environment="HTTP_PROXY={http_proxy}"
Environment="HTTPS_PROXY={https_proxy}"
Environment="FTP_PROXY={ftp_proxy}"
Environment="NO_PROXY={no_proxy}, 192.168.50.49, 10.96.0.0/12, 192.168.0.0/16"
""".format(**proxy_settings)
        
        run(f"sudo tee {proxy_conf} > /dev/null", shell=True, input=config_content.encode(), check=True)

        run("sudo systemctl daemon-reload", shell=True, check=True)
        run("sudo systemctl restart kubelet", shell=True, check=True)
        
        return True
        
    except CalledProcessError as e:
        print(f"Failed to configure kubelet proxy: {e}", flush=True)
    except Exception as e:
        print(f"Unexpected error configuring kubelet proxy: {e}", flush=True)

def cleanup_proxy_configs(debug=False):
    """Remove all proxy configurations."""
    
    # print_dotted_line("Cleaning up proxies")

    proxy_configs = [
        "/etc/systemd/system/docker.service.d/proxy.conf",
        "/etc/systemd/system/containerd.service.d/proxy.conf",
        "/etc/systemd/system/kubelet.service.d/proxy.conf",
        # Add other proxy files as needed
    ]
    
    # Remove each proxy configuration file
    for config in proxy_configs:
        config_path = Path(config)
        if config_path.exists():
            try:
                run(f"sudo rm {config}", shell=True, check=True)
                print(f"✓ {config} file deleted!", flush=True)
                
                # Also try to remove the parent directory if it's empty
                parent_dir = config_path.parent
                if parent_dir.exists() and not any(parent_dir.iterdir()):
                    run(f"sudo rmdir {parent_dir}", shell=True, check=True)
                    print(f"✓ Empty directory {parent_dir} removed", flush=True)

            except CalledProcessError as e:
                print(f"✗ Failed to remove {config}: {e}", flush=True)

        else:
            print(f"- {config} not found, skipping", flush=True)
    
    # Reload systemd
    try:
        run("sudo systemctl daemon-reload", shell=True, check=True)
        print("✓ Systemd daemon reloaded", flush=True)
    except CalledProcessError as e:
        print(f"✗ Failed to reload systemd: {e}", flush=True)
        
    print("Success!")

def configure_all_proxies(debug=False):
    """Apply all proxy configurations."""

    print_dotted_line("Configuring proxies")

    configure_docker_proxy(debug=debug)
    configure_containerd_proxy(debug=debug)
    configure_kubelet_proxy(debug=debug)
    # Add other proxy configurations as needed
    
    print("Success!")