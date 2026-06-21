#!/bin/bash
# Setup proxy for /kolproject

# Add context to vhost.conf
cat >> /usr/local/lsws/conf/vhosts/srv933640.hstgr.cloud/vhost.conf << 'ENDPROXY'

context /kolproject {
  type                    proxy
  handler                 127.0.0.1:5001
  addDefaultCharset       off
}
ENDPROXY

# Restart LiteSpeed
systemctl restart lsws

echo "Proxy configured! Test: http://148.230.97.130/kolproject"
