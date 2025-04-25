from pathlib import Path
import os
import json
from subprocess import run

def is_proxy_set():
    """
    Check if proxy environment variables are set in the system.
    Returns True if any proxy variables are set, False otherwise.
    """
    proxy_vars = [
        'http_proxy',
        'https_proxy',
        'no_proxy'
    ]
    
    for var in proxy_vars:
        if os.environ.get(var) or os.environ.get(var.upper()):
            return True
    
    return False


def get_proxy_var():
    """
    Get all proxy environment variables.
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


def configure_containerd_proxy(debug=False):
    """
    Configure containerd daemon to use proxy settings detected form the system.
    """

    proxy_settings = get_proxy_var()

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


def configure_kubelet_proxy(debug=False):
    """
    Configure kubelet daemon to use proxy settings detected form the system.
    """

    proxy_settings = get_proxy_var()

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


def configure_docker_proxy(debug=False):
    """
    Configure Docker to use proxy settings detected from the system.
    Sets up proxies in:
    1. Systemd drop-in file
    2. Docker daemon.json
    3. User ~/.docker/config.json
    """

    proxy_settings = get_proxy_var()
    
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
    
    # 2. Configure docker daemon.json (preserving existing settings)
    daemon_json_path = Path("/etc/docker/daemon.json")
    daemon_config = {}

    if daemon_json_path.exists():
        with open(daemon_json_path, 'r') as f:
            daemon_config = json.load(f)
    
    daemon_proxy_map = {
        "http-proxy": "HTTP_PROXY",
        "https-proxy": "HTTPS_PROXY", 
        "no-proxy": "NO_PROXY"
    }
    
    if 'proxies' in daemon_config:
        # Check for conflicts with existing settings
        for daemon_key, env_key in daemon_proxy_map.items():
            if daemon_key in daemon_config['proxies'] and daemon_config['proxies'][daemon_key] != proxy_settings[env_key]:
                raise ValueError(f"Existing proxy setting {daemon_key} in daemon.json differs from environment")
    else:
        # Add new proxy settings
        daemon_config['proxies'] = {k: proxy_settings[v] for k, v in daemon_proxy_map.items()}
    
    run(f"sudo mkdir -p {daemon_json_path.parent}", shell=True, check=True)
    run(f"sudo tee {daemon_json_path} > /dev/null", shell=True, 
        input=json.dumps(daemon_config, indent=2).encode(), check=True)
    
    # 3. Configure user docker config.json - preserve existing settings
    user_config_dir = Path(os.path.expanduser("~/.docker"))
    user_config_path = user_config_dir / "config.json"
    user_config = {}

    if user_config_path.exists():
        with open(user_config_path, 'r') as f:
            user_config = json.load(f)

    user_proxy_map = {
        "httpProxy": "HTTP_PROXY",
        "httpsProxy": "HTTPS_PROXY",
        "noProxy": "NO_PROXY"
    }
    
    if 'proxies' not in user_config:
        user_config['proxies'] = {}
    
    if 'default' in user_config['proxies']:
        # Check for conflicts with existing settings
        for config_key, env_key in user_proxy_map.items():
            if config_key in user_config['proxies']['default'] and user_config['proxies']['default'][config_key] != proxy_settings[env_key]:
                raise ValueError(f"Existing proxy setting {config_key} in config.json differs from environment")
    else:
        # Add new proxy settings
        user_config['proxies']['default'] = {k: proxy_settings[v] for k, v in user_proxy_map.items()}
    
    run(f"mkdir -p {user_config_dir}", shell=True, check=True)
    run(f"tee {user_config_path} > /dev/null", shell=True, 
        input=json.dumps(user_config, indent=2).encode(), check=True)

    run("sudo systemctl daemon-reload", shell=True, check=True)
    run("sudo systemctl restart docker", shell=True, check=True)
    