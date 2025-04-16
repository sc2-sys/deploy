from pathlib import Path
import os
import json
from subprocess import run

def check_return_proxy():
    """
    Check if proxy environment variables are set in the system.
    Returns a dictionary with proxy variable names and their values.
    """

    proxy_vars = [
        'http_proxy',
        'https_proxy',
        'no_proxy'
    ]
    
    proxy_dict = {}
    
    for var in proxy_vars:
        lowercase_value = os.environ.get(var)
        uppercase_value = os.environ.get(var.upper())

        if lowercase_value:
            proxy_dict[var.upper()] = lowercase_value
        if uppercase_value:
            proxy_dict[var.upper()] = uppercase_value
    
    return proxy_dict

def configure_docker_proxy(debug=False):
    """
    Configure Docker to use proxy settings detected from the system.
    Sets up proxies in:
    1. Systemd drop-in file
    2. Docker daemon.json
    3. User ~/.docker/config.json
    """
    # Get proxy settings
    proxy_settings = check_return_proxy()
    if debug:
        print(f"Detected proxy settings: {proxy_settings}")
    
    # 1. Configure systemd drop-in file
    proxy_dir = Path("/etc/systemd/system/docker.service.d")
    proxy_conf = proxy_dir / "proxy.conf"
    
    run(f"sudo mkdir -p {proxy_dir}", shell=True, check=True)
        
    systemd_content = """[Service]
Environment="HTTP_PROXY={HTTP_PROXY}"
Environment="HTTPS_PROXY={HTTPS_PROXY}"
Environment="NO_PROXY={NO_PROXY}"
""".format(**proxy_settings)
        
    run(f"sudo tee {proxy_conf} > /dev/null", shell=True, input=systemd_content.encode(), check=True)
    
    # 2. Configure docker daemon.json
    daemon_json_path = Path("/etc/docker/daemon.json")
    daemon_config = {
        "proxies": {
            "http-proxy": proxy_settings['HTTP_PROXY'],
            "https-proxy": proxy_settings['HTTPS_PROXY'],
            "no-proxy": proxy_settings['NO_PROXY']
        }
    }
    
    daemon_json_content = json.dumps(daemon_config, indent=2)
    run(f"sudo mkdir -p {daemon_json_path.parent}", shell=True, check=True)
    run(f"sudo tee {daemon_json_path} > /dev/null", shell=True, input=daemon_json_content.encode(), check=True)
    
    # 3. Configure user docker config.json
    user_config_dir = Path(os.path.expanduser("~/.docker"))
    user_config_path = user_config_dir / "config.json"
    
    user_config = {
        "proxies": {
            "default": {
                "httpProxy": proxy_settings['HTTP_PROXY'],
                "httpsProxy": proxy_settings['HTTPS_PROXY'],
                "noProxy": proxy_settings['NO_PROXY']
            }
        }
    }
    
    user_config_content = json.dumps(user_config, indent=2)
    run(f"mkdir -p {user_config_dir}", shell=True, check=True)
    run(f"tee {user_config_path} > /dev/null", shell=True, input=user_config_content.encode(), check=True)
    
    # Reload and restart docker
    run("sudo systemctl daemon-reload", shell=True, check=True)
    run("sudo systemctl restart docker", shell=True, check=True)
    
    return True

def configure_containerd_proxy(debug=False):
    """Configure containerd daemon to use proxy settings detected form the system."""

    proxy_settings = check_return_proxy()

    proxy_dir = Path("/etc/systemd/system/containerd.service.d")
    proxy_conf = proxy_dir / "proxy.conf"

    run(f"sudo mkdir -p {proxy_dir}", shell=True, check=True)
    
    config_content = """[Service]
Environment="HTTP_PROXY={HTTP_PROXY}"
Environment="HTTPS_PROXY={HTTPS_PROXY}"
Environment="NO_PROXY={NO_PROXY}"
""".format(**proxy_settings)
        
    run(f"sudo tee {proxy_conf} > /dev/null", shell=True, input=config_content.encode(), check=True)

    run("sudo systemctl daemon-reload", shell=True, check=True)
    run("sudo systemctl restart containerd", shell=True, check=True)

def configure_kubelet_proxy(debug=False):
    """Configure kubelet daemon to use proxy settings detected form the system."""

    proxy_settings = check_return_proxy()

    proxy_dir = Path("/etc/systemd/system/kubelet.service.d")
    proxy_conf = proxy_dir / "proxy.conf"
    
    run(f"sudo mkdir -p {proxy_dir}", shell=True, check=True)
        
    config_content = """[Service]
Environment="HTTP_PROXY={HTTP_PROXY}"
Environment="HTTPS_PROXY={HTTPS_PROXY}"
Environment="NO_PROXY={NO_PROXY}"
""".format(**proxy_settings)
        
    run(f"sudo tee {proxy_conf} > /dev/null", shell=True, input=config_content.encode(), check=True)

    run("sudo systemctl daemon-reload", shell=True, check=True)
    run("sudo systemctl restart kubelet", shell=True, check=True)
