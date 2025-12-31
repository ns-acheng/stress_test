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
    url_new_file = os.path.join(base_dir, "data", "urlnew.txt")
    
    existing_urls = load_urls(url_file)
    logger.info(f"Loaded {len(existing_urls)} existing URLs from {url_file}")

    raw_new_urls = []
    if os.path.exists(url_new_file):
        with open(url_new_file, 'r', encoding='utf-8') as f:
            raw_new_urls = [line.strip().rstrip('/') for line in f if line.strip()]
    else:
        logger.error(f"{url_new_file} not found.")
        return

    logger.info(f"Found {len(raw_new_urls)} URLs in {url_new_file} to process.")
    
    valid_urls = []
    processed_count = 0
    alive_count = 0
    skipped_count = 0
    
    seen_urls = set()
    urls_to_check = []

    total_raw = len(raw_new_urls)
    for i, url in enumerate(raw_new_urls):
        if url in existing_urls:
            skipped_count += 1
            logger.info(f"[{i+1}/{total_raw}] SKIPPED (Duplicate in url.txt): {url}")
            continue
        if url in seen_urls:
            skipped_count += 1
            logger.info(f"[{i+1}/{total_raw}] SKIPPED (Duplicate in batch): {url}")
            continue
        seen_urls.add(url)
        urls_to_check.append(url)

    url_alive_file = os.path.join(base_dir, "data", "url_alive.txt")
    with open(url_alive_file, 'w', encoding='utf-8') as f:
        f.write("")

    total_to_check = len(urls_to_check)
    logger.info(f"Starting check for {total_to_check} unique URLs with 50 threads...")
    
    unique_alive_urls = set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        future_to_url = {executor.submit(check_url_alive, url): url for url in urls_to_check}
        
        completed_checks = 0
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            completed_checks += 1
            processed_count += 1 # This is actually skipped + checked
            
            try:
                result = future.result()
                is_alive = bool(result)
                final_url = result if is_alive else url
            except Exception as exc:
                logger.error(f"{url} generated an exception: {exc}")
                is_alive = False
                final_url = url

            if is_alive:
                final_url = final_url.rstrip('/')

                if final_url in existing_urls:
                    logger.info(f"[{completed_checks}/{total_to_check}] ALIVE (Duplicate in DB): {url} -> {final_url}")
                    continue
                
                if final_url in unique_alive_urls:
                    logger.info(f"[{completed_checks}/{total_to_check}] ALIVE (Duplicate in batch): {url} -> {final_url}")
                    continue

                unique_alive_urls.add(final_url)
                valid_urls.append(final_url)
                alive_count += 1
                msg = f"[{completed_checks}/{total_to_check}] ALIVE: {url}"
                if final_url != url:
                    msg += f" -> {final_url}"
                logger.info(msg)
            else:
                logger.info(f"[{completed_checks}/{total_to_check}] DEAD: {url}")

            if len(valid_urls) >= 50:
                logger.info(f"Flushing {len(valid_urls)} URLs to {url_alive_file}...")
                with open(url_alive_file, 'a', encoding='utf-8') as f:
                    for v_url in valid_urls:
                        f.write(v_url + "\n")
                valid_urls = []

    if valid_urls:
        logger.info(f"Flushing remaining {len(valid_urls)} URLs to {url_alive_file}...")
        with open(url_alive_file, 'a', encoding='utf-8') as f:
            for v_url in valid_urls:
                f.write(v_url + "\n")

    logger.info("Processing complete.")
    logger.info(f"Total Processed (Raw): {total_raw}")
    logger.info(f"Total Checked: {total_to_check}")
    logger.info(f"Total Alive: {alive_count}")
    logger.info(f"Total Skipped (Duplicate): {skipped_count}")
    logger.info(f"Alive URLs written to: {url_alive_file}")

if __name__ == "__main__":
    main()
