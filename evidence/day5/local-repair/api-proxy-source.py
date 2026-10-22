import socket,socketserver,select,threading
slots=threading.BoundedSemaphore(32)
class Relay(socketserver.BaseRequestHandler):
 def handle(self):
  if not slots.acquire(False): return
  try:
   with socket.create_connection(('safeheal-dev-control-plane',6443),timeout=10) as target:
    self.request.settimeout(10)
    while True:
     ready,_,_=select.select([self.request,target],[],[],300)
     if not ready: return
     for source in ready:
      data=source.recv(65536)
      if not data: return
      (target if source is self.request else self.request).sendall(data)
  except OSError: pass
  finally: slots.release()
class Server(socketserver.ThreadingTCPServer):
 allow_reuse_address=True
 daemon_threads=True
Server(('0.0.0.0',6443),Relay).serve_forever()
