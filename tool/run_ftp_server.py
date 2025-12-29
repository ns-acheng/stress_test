import os
import sys
import logging
import argparse
import subprocess
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler, TLS_FTPHandler
from pyftpdlib.servers import ThreadedFTPServer
from pyftpdlib.filesystems import AbstractedFS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

class BlackholeFS(AbstractedFS):
    def open(self, filename, mode):
        if 'w' in mode or 'a' in mode:
            return open(os.devnull, 'wb')
        return super().open(filename, mode)

def generate_cert(cert_path, key_path):
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return
    try:
        cmd = [
            "openssl", "req", "-new", "-x509", "-days", "365", "-nodes",
            "-out", cert_path, "-keyout", key_path,
            "-subj", "/C=US/ST=Test/L=Test/O=Test/CN=localhost"
        ]
        subprocess.check_call(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        logger.info(f"Generated cert: {cert_path}, key: {key_path}")
    except Exception as e:
        logger.error(f"Failed to generate cert: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=21)
    parser.add_argument("--user", type=str, default="test")
    parser.add_argument("--password", type=str, default="password")
    parser.add_argument("--directory", type=str, default=".")
    parser.add_argument("--ftps", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.directory):
        os.makedirs(args.directory)

    authorizer = DummyAuthorizer()
    authorizer.add_user(
        args.user, args.password, args.directory, perm='elradfmwMT'
    )

    if args.ftps:
        cert_file = "cert.pem"
        key_file = "key.pem"
        generate_cert(cert_file, key_file)
        handler = TLS_FTPHandler
        handler.certfile = cert_file
        handler.keyfile = key_file
        handler.tls_control_required = True
        handler.tls_data_required = True
    else:
        handler = FTPHandler

    handler.authorizer = authorizer
    handler.abstracted_fs = BlackholeFS

    server = ThreadedFTPServer(('0.0.0.0', args.port), handler)
    logger.info(f"Starting {'FTPS' if args.ftps else 'FTP'} on {args.port}")
    server.serve_forever()

if __name__ == "__main__":
    main()
