import socket

def get_ip():
    """Get the actual local network IP address."""
    try:
        # Create a dummy UDP socket to determine primary network interface
        # This doesn't actually send any data - just uses OS routing table
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)  # Short timeout
        # Connect to a non-routable address
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # Fallback to hostname resolution
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"
