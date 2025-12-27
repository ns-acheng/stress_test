import subprocess
import sys

def run_command(command, description):
    print(f"\n--- {description} ---")
    print(f"Command: {' '.join(command)}")
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
    except Exception as e:
        print(f"Error running command: {e}")

def main():
    print("Applying Power Settings Fixes for S0 Wake...")

    # 1. Disable Hibernation
    # This ensures the system stays in S0 and doesn't drop to S4 (Disk), which is harder to wake from.
    run_command(["powercfg", "/h", "off"], "Disable Hibernation")

    # 2. Unhide "Console lock display off timeout"
    # GUID: 8EC4B3A5-6868-48c2-BE75-4F3044BE88A7
    # Subgroup: 7516b95f-f776-4464-8c53-06167f40cc99 (Video)
    # This setting controls how long the screen stays on after a wake event if no user is present.
    print("\n--- Unhiding 'Console lock display off timeout' ---")
    run_command([
        "powercfg", "-attributes", "SUB_VIDEO", "8EC4B3A5-6868-48c2-BE75-4F3044BE88A7", "-ATTRIB_HIDE"
    ], "Unhide Attribute")

    # 3. Set "Console lock display off timeout" to 0 (No timeout) or a high value (e.g., 5 minutes)
    # We'll set it to 300 seconds (5 mins) for both AC and DC
    run_command([
        "powercfg", "/setacvalueindex", "SCHEME_CURRENT", "SUB_VIDEO", "8EC4B3A5-6868-48c2-BE75-4F3044BE88A7", "300"
    ], "Set Console Lock Timeout (AC) to 300s")
    
    run_command([
        "powercfg", "/setdcvalueindex", "SCHEME_CURRENT", "SUB_VIDEO", "8EC4B3A5-6868-48c2-BE75-4F3044BE88A7", "300"
    ], "Set Console Lock Timeout (DC) to 300s")

    # 4. Apply the changes
    run_command(["powercfg", "/setactive", "SCHEME_CURRENT"], "Apply Power Scheme Changes")

    print("\n--- Fixes Applied ---")
    print("1. Hibernation is OFF.")
    print("2. Console Lock Timeout is set to 5 minutes.")
    print("Please try running the stress test again.")

if __name__ == "__main__":
    main()
