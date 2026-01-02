import os
import sys
import subprocess
import concurrent.futures
import logging
import re

# Add parent dir to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util_traffic import check_url_alive
from util_log import LogSetup

# Setup Logging
log_helper = LogSetup()
logger = log_helper.setup_logging()

# 1. Static Keyword Blocklist
BLOCKED_KEYWORDS = [
    "porn", "sex", "xxx", "adult", "hentai", "nude", "erotic", "escort", 
    "cam", "tube", "fuck", "dick", "pussy", "vagina", "penis", "incest",
    "taboo", "fetish", "kink", "bdsm", "gambling", "casino", "bet", "xvideos",
    "xnxx", "brazzers", "bangbros", "redtube", "youjizz", "youporn", "spankbang"
]

def is_safe_keyword(domain: str) -> bool:
    """Stage 1: Check for obvious adult keywords."""
    domain_lower = domain.lower()
    for kw in BLOCKED_KEYWORDS:
        if kw in domain_lower:
            return False
    return True

def is_safe_dns(domain: str) -> bool:
    """
    Stage 2: Check against Cloudflare Family DNS (1.1.1.3).
    Returns True if the domain resolves to a valid IP (not 0.0.0.0).
    """
    try:
        # Use nslookup to query 1.1.1.3
        # -timeout=2 sets a 2 second timeout
        cmd = ["nslookup", "-timeout=2", domain, "1.1.1.3"]
        
        # Suppress output, we only care about the result text
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        output = result.stdout
        
        # Cloudflare Family returns 0.0.0.0 for blocked content
        if "0.0.0.0" in output:
            return False
            
        # If it fails to resolve (NXDOMAIN), it's "safe" but dead. 
        # We'll let the liveness check handle dead sites, 
        # but strictly speaking, it's not "unsafe".
        return True
        
    except Exception:
        # If DNS check fails entirely, assume unsafe to be conservative
        return False

def clean_session_url(url: str) -> str:
    if '?' not in url:
        return url
        
    # Check query string for session/tracking indicators
    query_part = url.split('?', 1)[1].lower()
    
    SESSION_INDICATORS = [
        "session", "sid", "phpsessid", "jsessionid", "token", 
        "auth", "login", "user", "id=", "utm_", "gclid", "_ga"
    ]
    
    for indicator in SESSION_INDICATORS:
        if indicator in query_part:
            return url.split('?', 1)[0]
            
    return url

def process_candidate(raw_line: str) -> str | None:
    """
    Runs the full pipeline on a single candidate line.
    Returns the final URL if safe and alive, else None.
    """
    # Handle CSV formats like "1,google.com" or just "google.com"
    parts = raw_line.strip().split(',')
    domain = parts[-1].strip() # Take the last part (usually domain)
    
    if not domain:
        return None

    # Normalize
    if "://" in domain:
        domain = domain.split("://")[1]
    domain = domain.split("/")[0]

    # 1. Keyword Check
    if not is_safe_keyword(domain):
        return None

    # 2. DNS Safety Check
    if not is_safe_dns(domain):
        logger.warning(f"Blocked by Safe DNS: {domain}")
        return None

    # 3. Liveness Check
    # Try HTTPS first
    url = f"https://{domain}"
    final_url = check_url_alive(url)
    
    if not final_url:
        # Fallback to HTTP
        url = f"http://{domain}"
        final_url = check_url_alive(url)

    if final_url:
        return clean_session_url(final_url)

    return None

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates_file = os.path.join(base_dir, "data", "url_candidates.txt")
    target_file = os.path.join(base_dir, "data", "url.txt")
    output_file = os.path.join(base_dir, "data", "urlnew.txt")

    if not os.path.exists(candidates_file):
        logger.error(f"Candidate file not found: {candidates_file}")
        logger.info("Please create 'data/url_candidates.txt' with a list of domains.")
        return

    # Load existing to avoid duplicates
    existing_urls = set()
    if os.path.exists(target_file):
        with open(target_file, 'r', encoding='utf-8') as f:
            existing_urls = {line.strip() for line in f if line.strip()}
    
    logger.info(f"Loaded {len(existing_urls)} existing URLs.")

    # Read candidates
    with open(candidates_file, 'r', encoding='utf-8') as f:
        candidates = [line.strip() for line in f if line.strip()]

    logger.info(f"Processing {len(candidates)} candidates...")

    new_urls = []
    concurrency = 100 # DNS checks can be slow, run in parallel
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_domain = {
            executor.submit(process_candidate, line): line 
            for line in candidates
        }
        
        completed = 0
        for future in concurrent.futures.as_completed(future_to_domain):
            completed += 1
            if completed % 500 == 0:
                print(f"Progress: {completed}/{len(candidates)}", end='\r')
                
            result = future.result()
            if result:
                # Check if we already have this URL
                if result not in existing_urls:
                    new_urls.append(result)
                    existing_urls.add(result) # Prevent duplicates within this batch
                    logger.info(f"Added: {result}")
                else:
                    logger.info(f"Duplicate skipped: {result}")

    if new_urls:
        logger.info(f"Writing {len(new_urls)} new safe URLs to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            for u in new_urls:
                f.write(f"{u}\n")
    else:
        logger.info("No new valid URLs found.")

if __name__ == "__main__":
    main()
