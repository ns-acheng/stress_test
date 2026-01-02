import OpenSSL.crypto as crypto
import socket
import ssl
import logging

logger = logging.getLogger()

def check_url_cert(url: str) -> str:
    try:
        hostname = url.strip()
        if hostname.startswith("https://"):
            hostname = hostname[8:]
        elif hostname.startswith("http://"):
            hostname = hostname[7:]

        hostname = hostname.split('/')[0]

        dst = (hostname, 443)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(dst)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        s = ctx.wrap_socket(s, server_hostname=dst[0])
        cert_bin = s.getpeercert(True)
        x509 = crypto.load_certificate(crypto.FILETYPE_ASN1, cert_bin)
        issuer = x509.get_issuer()

        components = [f"{k.decode()}={v.decode()}" for k, v in issuer.get_components()]
        issuer_str = ", ".join(components)
        logger.info(f"Cert Issuer for {hostname}: {issuer_str}")

        return issuer_str
    except Exception as e:
        logger.error(f"Error checking cert for {url}: {e}")
        return ""