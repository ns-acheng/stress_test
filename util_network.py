import requests
import sys
import os

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
}

def read_urls_from_file(filename):
    urls = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url:
                    urls.append(url)
        return urls
    except FileNotFoundError:
        print(f"Error: The file '{filename}' was not found.")
        return None

def check_url_alive(url):
    try:
        response = requests.head(
            url, timeout=5, allow_redirects=True, headers=headers
        )
        if response.status_code < 400 or response.status_code == 403:
            return True
        return False
    except Exception:
        return False

def check_urls_and_write_status(urls):
    if not urls:
        print("No URLs provided. Exiting.")
        return

    existing_urls = set()
    target_check_file = 'url.txt'
    
    if not os.path.exists(target_check_file):
        target_check_file = r'data\url.txt'

    try:
        with open(target_check_file, 'r', encoding='utf-8') as f:
            existing_urls = {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        print("Warning: 'url.txt' not found for deduplication.")

    out_file = r'data\url_alive.txt'
    total_urls = len(urls)
    flush_interval = 50
    alive_count = 0
    print(f"Writing to '{out_file}', flush every {flush_interval}.")

    with open(out_file, 'w') as f:
        for index, url in enumerate(urls):
            if url in existing_urls:
                print(f"[{index + 1}/{total_urls}] {url} -> DUPLICATE (Skipping)")
                continue

            is_alive = check_url_alive(url)
            status_text = "ALIVE" if is_alive else "DEAD"
            
            print(f"[{index + 1}/{total_urls}] {url} -> {status_text}")
            sys.stdout.flush()
            
            if is_alive:
                f.write(f"{url}\n")
                alive_count += 1
                
                if (index + 1) % flush_interval == 0:
                    f.flush()
                    print(f"--- Flushed at #{index + 1} ---")

    print(f"\nComplete. Wrote {alive_count} ALIVE URLs to '{out_file}'.")

if __name__ == "__main__":
    input_file = r'data\urlnew.txt'
    urls_to_check = read_urls_from_file(input_file)
    if urls_to_check is not None:
        check_urls_and_write_status(urls_to_check)