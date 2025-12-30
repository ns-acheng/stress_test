import argparse
import logging
import os
import socket
import threading
import sys
import time
import paramiko

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from util_input import start_input_monitor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

class StubSFTPServer(paramiko.SFTPServerInterface):
    def __init__(self, server, *largs, **kwargs):
        super(StubSFTPServer, self).__init__(server, *largs, **kwargs)

    def list_folder(self, path):
        return []

    def stat(self, path):
        return paramiko.SFTPAttributes.from_stat(os.stat("."))

    def lstat(self, path):
        return paramiko.SFTPAttributes.from_stat(os.stat("."))

    def open(self, path, flags, attr):
        return paramiko.SFTPHandle(flags)

    def remove(self, path):
        return paramiko.SFTP_OK

    def rename(self, oldpath, newpath):
        return paramiko.SFTP_OK

    def mkdir(self, path, attr):
        return paramiko.SFTP_OK

    def rmdir(self, path):
        return paramiko.SFTP_OK

    def chattr(self, path, attr):
        return paramiko.SFTP_OK

    def symlink(self, target_path, path):
        return paramiko.SFTP_OK

    def readlink(self, path):
        return paramiko.SFTP_OK

class StubServer(paramiko.ServerInterface):
    def __init__(self, user, password):
        self.user = user
        self.password = password

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED

    def check_auth_password(self, username, password):
        if username == self.user and password == self.password:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_exec_request(self, channel, command):
        return True

def handle_client(client_sock, args, host_key):
    transport = paramiko.Transport(client_sock)
    transport.add_server_key(host_key)
    server = StubServer(args.user, args.password)
    try:
        transport.start_server(server=server)
        channel = transport.accept(20)
        if channel is None:
            return
        if channel.get_name() == "session":
            transport.set_subsystem_handler(
                "sftp", paramiko.SFTPServer, StubSFTPServer
            )
            channel.recv(1024) 
    except Exception as e:
        logger.error(f"Connection error: {e}")
    finally:
        transport.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=2222)
    parser.add_argument("--user", type=str, default="test")
    parser.add_argument("--password", type=str, default="password")
    parser.add_argument("--keyfile", type=str, default="host.key")
    args = parser.parse_args()

    if not os.path.exists(args.keyfile):
        key = paramiko.RSAKey.generate(2048)
        key.write_private_key_file(args.keyfile)
    
    host_key = paramiko.RSAKey(filename=args.keyfile)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', args.port))
    sock.listen(10)
    sock.settimeout(1.0)
    
    logger.info(f"SFTP Server listening on {args.port}")
    logger.info("Press ESC to stop the server")

    stop_event = threading.Event()
    start_input_monitor(stop_event)
    
    while not stop_event.is_set():
        try:
            client, addr = sock.accept()
        except socket.timeout:
            continue
        except OSError:
            break

        logger.info(f"Connection from {addr}")
        t = threading.Thread(
            target=handle_client, args=(client, args, host_key)
        )
        t.daemon = True
        t.start()
    
    logger.info("Stopping SFTP server...")
    sock.close()

if __name__ == "__main__":
    main()
