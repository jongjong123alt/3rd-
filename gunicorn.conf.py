"""One process preserves the existing in-memory login rate limiter."""
import os

bind = "0.0.0.0:" + os.environ.get("PORT", "8000")
workers = 1
worker_class = "gthread"
threads = 4
timeout = 180
accesslog = "-"
errorlog = "-"
# Do not trust arbitrary forwarding headers to change request security.
forwarded_allow_ips = "127.0.0.1,::1"
