# /tasks/util/proxy.py
import os
import subprocess
import tempfile
import logging

logger = logging.getLogger(__name__)

# Define your proxy settings here or load from environment
HTTP_PROXY = os.environ.get('HTTP_PROXY', '')
HTTPS_PROXY = os.environ.get('HTTPS_PROXY', '')
NO_PROXY = os.environ.get('NO_PROXY', '')

def configure_docker_proxy():
    """Configure Docker daemon to use proxy settings."""
    proxy_conf = """[Service]
Environment="HTTP_PROXY={}"
Environment="HTTPS_PROXY={}"
Environment="NO_PROXY={}"
""".format(HTTP_PROXY, HTTPS_PROXY, NO_PROXY)
    
    # Create the directory if it doesn't exist
    os.makedirs('/etc/systemd/system/docker.service.d', exist_ok=True)
    
    # Write the proxy configuration
    with open('/etc/systemd/system/docker.service.d/proxy.conf', 'w') as f:
        f.write(proxy_conf)
    
    # Reload systemd and restart Docker
    subprocess.run(['systemctl', 'daemon-reload'])
    subprocess.run(['systemctl', 'restart', 'docker'])
    
    logger.info("Docker proxy configuration applied")

def configure_git_proxy():
    """Configure Git to use proxy settings."""
    if HTTP_PROXY:
        subprocess.run(['git', 'config', '--global', 'http.proxy', HTTP_PROXY])
    if HTTPS_PROXY:
        subprocess.run(['git', 'config', '--global', 'https.proxy', HTTPS_PROXY])
    
    logger.info("Git proxy configuration applied")

# Add more proxy configuration functions as needed

def configure_all_proxies():
    """Apply all proxy configurations."""
    configure_docker_proxy()
    configure_git_proxy()
    # Call other proxy configuration functions
    
    logger.info("All proxy configurations applied")