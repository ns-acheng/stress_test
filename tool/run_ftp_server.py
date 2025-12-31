import os
import sys
import logging
import argparse
import subprocess
import threading
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from util_input import start_input_monitor

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
try:
    from pyftpdlib.handlers import TLS_FTPHandler
except ImportError:
    TLS_FTPHandler = None
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
            logger.info(f"Receiving file: {filename}")
            return open(os.devnull, 'wb')
        return super().open(filename, mode)

    def remove(self, filename):
        logger.info(f"Deleting file: {filename}")
        return None

def generate_cert(cert_path, key_path):
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return
    try:
        # Try using OpenSSL CLI first
        cmd = [
            "openssl", "req", "-new", "-x509", "-days", "365", "-nodes",
            "-out", cert_path, "-keyout", key_path,
            "-subj", "/C=US/ST=Test/L=Test/O=Test/CN=localhost"
        ]
        subprocess.check_call(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        logger.info(f"Generated cert (CLI): {cert_path}, key: {key_path}")
    except Exception:
        # Fallback to pyopenssl if CLI fails
        try:
            from OpenSSL import crypto
            k = crypto.PKey()
            k.generate_key(crypto.TYPE_RSA, 2048)
            cert = crypto.X509()
            cert.get_subject().C = "US"
            cert.get_subject().ST = "Test"
            cert.get_subject().L = "Test"
            cert.get_subject().O = "Test"
            cert.get_subject().CN = "localhost"
            cert.set_serial_number(1000)
            cert.gmtime_adj_notBefore(0)
            cert.gmtime_adj_notAfter(365*24*60*60)
            cert.set_issuer(cert.get_subject())
            cert.set_pubkey(k)
            cert.sign(k, 'sha256')
            
            with open(cert_path, "wb") as f:
                f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
            with open(key_path, "wb") as f:
                f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))
            logger.info(f"Generated cert (PyOpenSSL): {cert_path}, key: {key_path}")
        except ImportError:
            logger.error("OpenSSL CLI not found and pyopenssl not installed.")
            sys.exit(1)
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
        if TLS_FTPHandler is None:
            logger.error("FTPS not supported (TLS_FTPHandler not found). Install pyopenssl?")
            sys.exit(1)
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
    logger.info("Press ESC to stop the server")

    stop_event = threading.Event()
    start_input_monitor(stop_event)

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Stopping FTP server...")
        server.close_all()

if __name__ == "__main__":
    main()
