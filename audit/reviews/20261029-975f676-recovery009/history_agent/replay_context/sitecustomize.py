import socket
def deny(*a,**k): raise AssertionError("Independent audit forbids network")
socket.socket.connect=deny
socket.create_connection=deny
