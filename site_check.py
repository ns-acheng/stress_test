import requests
from requests.exceptions import RequestException
import os
import sys # Needed for sys.stdout.flush()

def read_urls_from_file(filename):
    """
    Reads a list of URLs from a specified file.
    """
    urls = []
    try:
        # Using 'utf-8' encoding for general compatibility on Windows
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url:
                    urls.append(url)
        return urls
    except FileNotFoundError:
        print(f"Error: The file '{filename}' was not found in the current directory.")
        return None

def check_urls_and_write_status(urls):
    """
    Checks the HTTP status of a list of URLs and writes only the ALIVE URLs 
    (one per line) to 'alive.txt', flushing the file every 50 sites.
    """
    if not urls:
        print("No URLs were provided or read from the file. Exiting.")
        return

    output_filename = 'alive.txt' 
    total_urls = len(urls)
    flush_interval = 50
    alive_count = 0
    
    print(f"Starting URL checks on {total_urls} URLs.")
    print(f"Output will be written to '{output_filename}' and flushed every {flush_interval} checks.")

    # Define the custom User-Agent header
    browser_headers = {
        # Updated User-Agent as requested by the user
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
    }

    # Open the file once, using 'w' (write mode) to start fresh
    with open(output_filename, 'w') as f:
        for index, url in enumerate(urls):
            is_alive = False
            status_code_detail = "N/A"

            try:
                # Use HEAD method with browser headers and timeout
                response = requests.head(url, timeout=5, allow_redirects=True, headers=browser_headers)
                
                # ALIVE check: Success (2xx, 3xx) or Accessible (403 Forbidden)
                if response.status_code < 400:
                    is_alive = True
                elif response.status_code == 403:
                    is_alive = True 
                
                status_code_detail = f"HTTP Code: {response.status_code}"
                
            except RequestException as e:
                status_code_detail = f"Connection Error: {type(e).__name__}"
            
            except Exception as e:
                status_code_detail = f"Unexpected Error: {type(e).__name__}"

            
            # --- Output & Flush Logic ---
            
            # Console Output (Immediate Feedback)
            status_text = "ALIVE" if is_alive else "DEAD"
            print(f"[{index + 1}/{total_urls}] {url} -> {status_text} ({status_code_detail})")
            sys.stdout.flush() # Ensure the console output appears immediately

            # File Output (Only ALIVE URLs)
            if is_alive:
                f.write(f"{url}\n")
                alive_count += 1
                
                # Flush the file buffer every 50 sites
                if (index + 1) % flush_interval == 0:
                    f.flush()
                    print(f"--- File '{output_filename}' flushed at check #{index + 1}. ---")

    print(f"\nAll checks complete. Wrote {alive_count} ALIVE URLs to '{output_filename}'.")


# --- MAIN EXECUTION ---
input_file = 'url.txt'

urls_to_check = read_urls_from_file(input_file)

if urls_to_check is not None:
    check_urls_and_write_status(urls_to_check)