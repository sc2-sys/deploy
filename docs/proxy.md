# Proxy Configuration - Quick Setup

This repository automatically picks up the standard proxy environment variables already set on your machine (`http_proxy`, `https_proxy`, etc.) and passes them to containerd, Docker, and kubelet.

If you work behind a corporate proxy, add the following `no_proxy` rule so that internal-cluster traffic bypasses the proxy:

```
sudo nano /etc/environment
```

```
# append (or update) this line ↓
no_proxy=192.168.50.0/24,10.96.0.0/12,192.168.0.0/16,192.168.218.0/24,*.svc,*.cluster.local,localhost,127.0.0.1,sc2cr.io,sslip.io
```

Reload the environment and confirm the settings:

```
source /etc/environment
env | grep -i proxy
```

Once the new `no_proxy` value appears in the output, you're ready to run `sc2.deploy`.
