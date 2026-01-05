
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util_cert import check_url_cert
from util_log import LogSetup

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_cert_check.py <url>")
        sys.exit(1)

    url = sys.argv[1]

    try:
        LogSetup().setup_logging()
    except:
        pass

    print(f"Checking certificate for: {url}")
    issuer = check_url_cert(url)

    if issuer:
        print(f"Issuer: {issuer}")
    else:
        print("Failed to retrieve certificate issuer.")

if __name__ == "__main__":
    main()
