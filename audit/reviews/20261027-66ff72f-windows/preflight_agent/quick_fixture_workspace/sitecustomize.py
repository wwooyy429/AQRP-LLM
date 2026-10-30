import socket
def denied(*a,**k):raise AssertionError("Offline review prohibits network")
socket.socket.connect=denied
