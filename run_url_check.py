import os
from util_traffic import check_url_alive
from util_log import LogSetup

log_helper = LogSetup()
logger = log_helper.setup_logging()

def load_urls(filepath):
    if not os.path.exists(filepath):
        return set()
    with open(filepath, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def main():
    url_file = os.path.join("data", "url.txt")
    url_new_file = os.path.join("data", "urlnew.txt")
    
    existing_urls = load_urls(url_file)
    logger.info(f"Loaded {len(existing_urls)} existing URLs from {url_file}")

    raw_new_urls = []
    if os.path.exists(url_new_file):
        with open(url_new_file, 'r', encoding='utf-8') as f:
            raw_new_urls = [line.strip() for line in f if line.strip()]
    else:
        logger.error(f"{url_new_file} not found.")
        return

    logger.info(f"Found {len(raw_new_urls)} URLs in {url_new_file} to process.")
    
    valid_urls = []
    processed_count = 0
    alive_count = 0
    skipped_count = 0
    
    seen_urls = set()

    with open(url_new_file, 'w', encoding='utf-8') as f:
        f.write("")

    total_to_process = len(raw_new_urls)

    for url in raw_new_urls:
        processed_count += 1
        
        if url in existing_urls:
            skipped_count += 1
            logger.info(f"[{processed_count}/{total_to_process}] SKIPPED (Duplicate in url.txt): {url}")
            continue

        if url in seen_urls:
            skipped_count += 1
            logger.info(f"[{processed_count}/{total_to_process}] SKIPPED (Duplicate in batch): {url}")
            continue
        
        seen_urls.add(url)
        
        is_alive = check_url_alive(url)
        
        if is_alive:
            valid_urls.append(url)
            alive_count += 1
            logger.info(f"[{processed_count}/{total_to_process}] ALIVE: {url}")
        else:
            logger.info(f"[{processed_count}/{total_to_process}] DEAD: {url}")

        if len(valid_urls) >= 50:
            logger.info(f"Flushing {len(valid_urls)} URLs to {url_new_file}...")
            with open(url_new_file, 'a', encoding='utf-8') as f:
                for v_url in valid_urls:
                    f.write(v_url + "\n")
            valid_urls = []

    if valid_urls:
        logger.info(f"Flushing remaining {len(valid_urls)} URLs to {url_new_file}...")
        with open(url_new_file, 'a', encoding='utf-8') as f:
            for v_url in valid_urls:
                f.write(v_url + "\n")

    logger.info("Processing complete.")
    logger.info(f"Total Processed: {processed_count}")
    logger.info(f"Total Alive & New: {alive_count}")
    logger.info(f"Total Skipped (Duplicate): {skipped_count}")

if __name__ == "__main__":
    main()
