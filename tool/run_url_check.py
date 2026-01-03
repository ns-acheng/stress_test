import os
import sys
import concurrent.futures
import subprocess
import threading
import argparse
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util_traffic import check_url_alive
from util_log import LogSetup
from util_input import start_input_monitor

log_helper = LogSetup()
logger = log_helper.setup_logging()

BLOCKED_KEYWORDS = [
    "porn", "sex", "xxx", "adult", "hentai", "nude", "erotic", "escort", 
    "cam", "tube", "fuck", "dick", "pussy", "vagina", "penis", "incest",
    "taboo", "fetish", "kink", "bdsm", "gambling", "casino", "bet", "xvideos",
    "xnxx", "brazzers", "bangbros", "redtube", "youjizz", "youporn", "spankbang",
    "chaturbate", "livejasmin", "myfreecams", "strip", "whore", "slut", "milf",
    "amateur", "webcam", "dating", "hookup", "swingers", "poker", "slots",
    "roulette", "blackjack", "lottery", "betting", "sportsbook", "drugs",
    "cannabis", "weed", "marijuana", "hemp", "cbd", "vape", "tobacco",
    "alcohol", "liquor", "beer", "wine", "spirits", "weapon", "gun", "ammo",
    "firearm", "knife", "sword", "bomb", "explosive", "terror", "isis",
    "al-qaeda", "jihad", "nazi", "white-supremacy", "hate", "racist",
    "extremist", "radical", "violence", "gore", "blood", "death", "suicide",
    "kill", "murder", "torture", "abuse", "rape", "assault", "crime",
    "illegal", "warez", "crack", "hack", "cheat", "torrent", "magnet",
    "pirate", "proxy", "vpn", "anonymizer", "tor", "darkweb", "onion"
]

def is_safe_keyword(domain: str) -> bool:
    domain_lower = domain.lower()
    for kw in BLOCKED_KEYWORDS:
        if kw in domain_lower:
            return False
    return True

def is_safe_dns(domain: str) -> bool:
    try:
        cmd = ["nslookup", "-timeout=2", domain, "1.1.1.3"]
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        output = result.stdout
        if "0.0.0.0" in output:
            return False

        return True
        
    except Exception:
        return False

def clean_session_url(url: str) -> str:
    if '?' not in url:
        return url

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
    parts = raw_line.strip().split(',')
    domain = parts[-1].strip() 
    
    if not domain:
        return None

    if "://" in domain:
        domain = domain.split("://")[1]
    domain = domain.split("/")[0]

    if not is_safe_keyword(domain):
        return None

    if not is_safe_dns(domain):
        logger.warning(f"Blocked by Safe DNS: {domain}")
        return None

    url = f"https://{domain}"
    final_url = check_url_alive(url)
    
    if not final_url:
        url = f"http://{domain}"
        final_url = check_url_alive(url)

    if final_url:
        return clean_session_url(final_url)

    return None

def load_urls(filepath):
    if not os.path.exists(filepath):
        return set()
    with open(filepath, 'r', encoding='utf-8') as f:
        return set(line.strip().rstrip('/') for line in f if line.strip())

def main():
    parser = argparse.ArgumentParser(description="Check URLs for safety and liveness.")
    parser.add_argument("--limit", type=int, default=1000, help="Max number of URLs to process")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    url_file = os.path.join(base_dir, "data", "url.txt")
    url_new_file = os.path.join(base_dir, "data", "urlnew.txt")
    url_alive_file = os.path.join(base_dir, "data", "url_alive.txt")
    
    stop_event = threading.Event()
    start_input_monitor(stop_event)

    existing_urls = load_urls(url_file)
    logger.info(f"Loaded {len(existing_urls)} existing URLs from {url_file}")

    if not os.path.exists(url_new_file):
        logger.error(f"{url_new_file} not found.")
        return

    # Read all candidates
    with open(url_new_file, 'r', encoding='utf-8') as f:
        all_candidates = [line.strip().rstrip('/') for line in f if line.strip()]

    logger.info(f"Found {len(all_candidates)} URLs in {url_new_file} to process.")
    
    # Ensure url_alive.txt exists
    if not os.path.exists(url_alive_file):
        with open(url_alive_file, 'w', encoding='utf-8') as f:
            pass

    unique_alive_urls = set()

    limit = min(args.limit, len(all_candidates))
    candidates_to_process = all_candidates[:limit]
    remaining_candidates = all_candidates[limit:]
    
    logger.info(f"Will process {limit} URLs (Limit: {args.limit})")

    batch_size = 100
    processed_count = 0

    for i in range(0, len(candidates_to_process), batch_size):
        if stop_event.is_set():
            logger.warning("Stop event detected. Halting processing.")
            remaining_candidates = candidates_to_process[i:] + remaining_candidates
            break

        batch = candidates_to_process[i : i + batch_size]
        logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} URLs)...")
        
        alive_in_batch = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=70) as executor:
            future_to_url = {executor.submit(process_candidate, url): url for url in batch}
            
            for future in concurrent.futures.as_completed(future_to_url):
                if stop_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                url = future_to_url[future]
                try:
                    result = future.result()
                    if result:
                        final_url = result.rstrip('/')
                        
                        if final_url in existing_urls:
                            logger.info(f"Duplicate in DB: {final_url}")
                            continue
                        
                        if final_url in unique_alive_urls:
                            logger.info(f"Duplicate in session: {final_url}")
                            continue

                        unique_alive_urls.add(final_url)
                        alive_in_batch.append(final_url)
                        logger.info(f"SAFE & ALIVE: {final_url}")
                except Exception as exc:
                    logger.error(f"{url} generated an exception: {exc}")

        if alive_in_batch:
            with open(url_alive_file, 'a', encoding='utf-8') as f:
                for v_url in alive_in_batch:
                    f.write(v_url + "\n")
            logger.info(f"Flushed {len(alive_in_batch)} alive URLs to {url_alive_file}")
        
        processed_count += len(batch)

    # Update url_new.txt (remove processed batch)
    logger.info(f"Updating {url_new_file}...")
    with open(url_new_file, 'w', encoding='utf-8') as f:
        for url in remaining_candidates:
            f.write(url + "\n")
            
    logger.info(f"Done. Processed {processed_count} URLs. Remaining: {len(remaining_candidates)}")

if __name__ == "__main__":
    main()
