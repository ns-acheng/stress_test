import requests
from requests.exceptions import RequestException
import sys

browser_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
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
        print(f"Error: The file '{filename}' was not found in the current directory.")
        return None

def check_url_alive(url):
    try:
        response = requests.head(url, timeout=5, allow_redirects=True, headers=browser_headers)
        if response.status_code < 400:
            return True
        elif response.status_code == 403:
            return True
        return False
    except Exception:
        return False

def check_urls_and_write_status(urls):
    if not urls:
        print("No URLs were provided or read from the file. Exiting.")
        return

    output_filename = r'data\url_alive.txt' 
    total_urls = len(urls)
    flush_interval = 50
    alive_count = 0
    print(f"Output will be written to '{output_filename}' and flushed every {flush_interval} checks.")

    with open(output_filename, 'w') as f:
        for index, url in enumerate(urls):
            is_alive = False
            status_code_detail = "N/A"

            try:
                response = requests.head(url, timeout=5, allow_redirects=True, headers=browser_headers)
                if response.status_code < 400:
                    is_alive = True
                elif response.status_code == 403:
                    is_alive = True 
                
                status_code_detail = f"HTTP Code: {response.status_code}"

            except Exception as e:
                status_code_detail = f"Unexpected Error: {type(e).__name__}"

            status_text = "ALIVE" if is_alive else "DEAD"
            print(f"[{index + 1}/{total_urls}] {url} -> {status_text} ({status_code_detail})")
            sys.stdout.flush()
            if is_alive:
                f.write(f"{url}\n")
                alive_count += 1
                
                if (index + 1) % flush_interval == 0:
                    f.flush()
                    print(f"--- File '{output_filename}' flushed at check #{index + 1}. ---")

    print(f"\nAll checks complete. Wrote {alive_count} ALIVE URLs to '{output_filename}'.")


if __name__ == "__main__":
    input_file = r'data\urlnew.txt'
    urls_to_check = read_urls_from_file(input_file)
    if urls_to_check is not None:
        check_urls_and_write_status(urls_to_check)
