import os
import sys
import concurrent.futures

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util_traffic import check_url_alive
from util_log import LogSetup

log_helper = LogSetup()
logger = log_helper.setup_logging()

def load_urls(filepath):
    if not os.path.exists(filepath):
        return set()
    with open(filepath, 'r', encoding='utf-8') as f:
        # Strip whitespace and trailing slashes
        return set(line.strip().rstrip('/') for line in f if line.strip())

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    url_file = os.path.join(base_dir, "data", "url.txt")
    candidates_file = os.path.join(base_dir, "data", "url_candidates.txt")
    url_alive_file = os.path.join(base_dir, "data", "url_alive.txt")
    
    existing_urls = load_urls(url_file)
    logger.info(f"Loaded {len(existing_urls)} existing URLs from {url_file}")

    if not os.path.exists(candidates_file):
        logger.error(f"{candidates_file} not found.")
        return

    # Read all candidates
    with open(candidates_file, 'r', encoding='utf-8') as f:
        all_candidates = [line.strip().rstrip('/') for line in f if line.strip()]

    logger.info(f"Found {len(all_candidates)} URLs in {candidates_file} to process.")
    
    # Ensure url_alive.txt exists
    if not os.path.exists(url_alive_file):
        with open(url_alive_file, 'w', encoding='utf-8') as f:
            pass

    unique_alive_urls = set()
    
    batch_size = 500
    total_processed = 0
    
    while all_candidates:
        # Take a batch
        batch = all_candidates[:batch_size]
        remaining_candidates = all_candidates[batch_size:]
        
        logger.info(f"Processing batch of {len(batch)} URLs...")
        
        urls_to_check = []
        for url in batch:
            if url in existing_urls:
                continue
            if url in unique_alive_urls:
                continue
            urls_to_check.append(url)
            
        alive_in_batch = []
        
        if urls_to_check:
            with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
                future_to_url = {executor.submit(check_url_alive, url): url for url in urls_to_check}
                
                for future in concurrent.futures.as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        result = future.result()
                        if result:
                            final_url = result.rstrip('/')
                            
                            if final_url in existing_urls:
                                logger.info(f"ALIVE (Duplicate in DB): {url} -> {final_url}")
                                continue
                            
                            if final_url in unique_alive_urls:
                                logger.info(f"ALIVE (Duplicate in session): {url} -> {final_url}")
                                continue

                            unique_alive_urls.add(final_url)
                            alive_in_batch.append(final_url)
                            logger.info(f"ALIVE: {url} -> {final_url}")
                    except Exception as exc:
                        logger.error(f"{url} generated an exception: {exc}")

        # Flush alive to file
        if alive_in_batch:
            with open(url_alive_file, 'a', encoding='utf-8') as f:
                for v_url in alive_in_batch:
                    f.write(v_url + "\n")
            logger.info(f"Flushed {len(alive_in_batch)} alive URLs to {url_alive_file}")

        # Update candidates file (remove processed batch)
        with open(candidates_file, 'w', encoding='utf-8') as f:
            for url in remaining_candidates:
                f.write(url + "\n")
        
        logger.info(f"Removed {len(batch)} processed URLs from {candidates_file}. Remaining: {len(remaining_candidates)}")
        
        # Update loop variable
        all_candidates = remaining_candidates
        total_processed += len(batch)

    logger.info("Processing complete.")

if __name__ == "__main__":
    main()
