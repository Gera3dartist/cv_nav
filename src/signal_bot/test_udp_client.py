import socket

UDP_IP = "192.168.0.17"
UDP_PORT = 4243

# CoT event XML
cot = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<event version=\"2.0\" type=\"a-h-G-U-C-F\" uid=\"test-marker\" how=\"h-g-i-g-o\" time=\"2025-12-19T21:30:00Z\" start=\"2025-12-19T21:30:00Z\" stale=\"2025-12-19T21:35:00Z\">
  <point lat=\"48.567123\" lon=\"39.87897\" hae=\"0\" ce=\"50\" le=\"50\" />
</event>"""

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(cot.encode(), (UDP_IP, UDP_PORT))
print(f"Sent CoT to {UDP_IP}:{UDP_PORT}")
sock.close()
