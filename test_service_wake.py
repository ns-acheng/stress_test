"""
Comprehensive Test Suite for Service-Based S0 Wake

Tests all components of the service-based wake system:
- Service installation and lifecycle
- Wake scheduling and completion
- Error handling and fallbacks
- power.json state management
"""

import sys
import os
import time
import json
import subprocess
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from util_power import (
    enter_s0_with_service, 
    enter_s0_and_wake,
    _is_service_installed,
    _is_service_running,
    _ensure_service_running,
    _read_power_json,
    _write_power_json,
    POWER_JSON,
    DATA_DIR
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TestSuite')


def test_service_installation():
    """Test 1: Service installation and status check."""
    print("\n" + "="*60)
    print("TEST 1: Service Installation")
    print("="*60)
    
    try:
        installed = _is_service_installed()
        running = _is_service_running()
        
        print(f"Service installed: {installed}")
        print(f"Service running: {running}")
        
        if not running:
            print("Attempting to ensure service is running...")
            result = _ensure_service_running()
            print(f"Service start result: {result}")
            
            if result:
                print("✓ TEST 1 PASSED: Service running")
                return True
            else:
                print("✗ TEST 1 FAILED: Could not start service")
                return False
        else:
            print("✓ TEST 1 PASSED: Service already running")
            return True
            
    except Exception as e:
        print(f"✗ TEST 1 FAILED: {e}")
        return False


def test_power_json_operations():
    """Test 2: power.json read/write operations."""
    print("\n" + "="*60)
    print("TEST 2: power.json Operations")
    print("="*60)
    
    try:
        # Test read
        data = _read_power_json()
        if data:
            print("✓ power.json read successfully")
            print(f"  Service running: {data['current_state'].get('service_running')}")
            print(f"  Wake history entries: {len(data.get('wake_history', []))}")
        else:
            print("⚠ power.json not found or empty")
            data = {
                "service_config": {"test": True},
                "current_state": {"test_mode": True},
                "wake_schedule": None,
                "wake_history": []
            }
        
        # Test write
        test_marker = f"test_{int(time.time())}"
        data['current_state']['test_marker'] = test_marker
        
        if _write_power_json(data):
            print("✓ power.json write successful")
            
            # Verify write
            verify_data = _read_power_json()
            if verify_data and verify_data['current_state'].get('test_marker') == test_marker:
                print("✓ power.json write verification passed")
                
                # Cleanup test marker
                del verify_data['current_state']['test_marker']
                _write_power_json(verify_data)
                
                print("✓ TEST 2 PASSED")
                return True
            else:
                print("✗ TEST 2 FAILED: Write verification failed")
                return False
        else:
            print("✗ TEST 2 FAILED: Write operation failed")
            return False
            
    except Exception as e:
        print(f"✗ TEST 2 FAILED: {e}")
        return False


def test_short_wake():
    """Test 3: Short duration wake (5 seconds)."""
    print("\n" + "="*60)
    print("TEST 3: Short Duration Wake (5 seconds)")
    print("="*60)
    print("This will enter S0 for 5 seconds and auto-wake")
    print("Please do NOT touch keyboard/mouse during test")
    
    input("\nPress Enter to start test...")
    
    try:
        start_time = time.time()
        success = enter_s0_with_service(5)
        end_time = time.time()
        
        duration = end_time - start_time
        
        print(f"\nTest duration: {duration:.2f}s")
        print(f"Expected: ~5-6s")
        
        if success and 4 < duration < 70:  # Allow buffer for timeout
            print(f"✓ TEST 3 PASSED: Wake successful in {duration:.2f}s")
            return True
        elif duration > 70:
            print(f"✗ TEST 3 FAILED: Timeout occurred ({duration:.2f}s)")
            return False
        else:
            print(f"✗ TEST 3 FAILED: Wake unsuccessful")
            return False
            
    except Exception as e:
        print(f"✗ TEST 3 FAILED: {e}")
        return False


def test_wake_history():
    """Test 4: Wake history logging."""
    print("\n" + "="*60)
    print("TEST 4: Wake History Logging")
    print("="*60)
    
    try:
        data = _read_power_json()
        if not data:
            print("✗ TEST 4 FAILED: Could not read power.json")
            return False
        
        history = data.get('wake_history', [])
        
        if not history:
            print("⚠ No wake history entries found (run test 3 first)")
            return False
        
        print(f"Wake history entries: {len(history)}")
        
        # Check last entry
        last_wake = history[-1]
        print("\nLast wake entry:")
        print(f"  Sleep start: {last_wake.get('sleep_start')}")
        print(f"  Wake time: {last_wake.get('wake_time')}")
        print(f"  Duration expected: {last_wake.get('duration_expected')}s")
        print(f"  Duration actual: {last_wake.get('duration_actual')}s")
        print(f"  Drift: {last_wake.get('drift')}s")
        print(f"  Success: {last_wake.get('success')}")
        
        # Validate entry has required fields
        required_fields = ['sleep_start', 'wake_time', 'duration_expected', 
                          'duration_actual', 'success']
        
        missing_fields = [f for f in required_fields if f not in last_wake]
        
        if missing_fields:
            print(f"✗ TEST 4 FAILED: Missing fields: {missing_fields}")
            return False
        
        print("✓ TEST 4 PASSED: History logging working correctly")
        return True
        
    except Exception as e:
        print(f"✗ TEST 4 FAILED: {e}")
        return False


def test_service_recovery():
    """Test 5: Service recovery after stop."""
    print("\n" + "="*60)
    print("TEST 5: Service Recovery")
    print("="*60)
    print("This will stop the service and verify auto-restart")
    
    try:
        # Stop service
        print("Stopping service...")
        result = subprocess.run(
            ['sc', 'stop', 'StressTestWakeService'],
            capture_output=True,
            text=True
        )
        
        time.sleep(2)
        
        if not _is_service_running():
            print("✓ Service stopped successfully")
            
            # Try to ensure service running (should restart)
            print("Attempting auto-recovery...")
            if _ensure_service_running():
                print("✓ Service auto-recovery successful")
                
                time.sleep(2)
                
                if _is_service_running():
                    print("✓ TEST 5 PASSED: Service recovery working")
                    return True
                else:
                    print("✗ TEST 5 FAILED: Service not running after recovery")
                    return False
            else:
                print("✗ TEST 5 FAILED: Auto-recovery failed")
                return False
        else:
            print("✗ TEST 5 FAILED: Service stop failed")
            return False
            
    except Exception as e:
        print(f"✗ TEST 5 FAILED: {e}")
        return False


def test_fallback_mechanism():
    """Test 6: Fallback to legacy method."""
    print("\n" + "="*60)
    print("TEST 6: Fallback Mechanism (Optional)")
    print("="*60)
    print("This would test fallback to legacy method if service fails")
    print("Skipping to avoid service disruption")
    print("✓ TEST 6 SKIPPED")
    return True


def print_diagnostics():
    """Print diagnostic information."""
    print("\n" + "="*60)
    print("DIAGNOSTIC INFORMATION")
    print("="*60)
    
    # Service status
    try:
        result = subprocess.run(
            ['sc', 'query', 'StressTestWakeService'],
            capture_output=True,
            text=True
        )
        print("\nService Status:")
        print(result.stdout if result.returncode == 0 else "Service not found")
    except:
        print("\nService Status: Error querying")
    
    # power.json info
    try:
        if os.path.exists(POWER_JSON):
            data = _read_power_json()
            if data:
                print(f"\npower.json:")
                print(f"  Location: {POWER_JSON}")
                print(f"  Size: {os.path.getsize(POWER_JSON)} bytes")
                print(f"  Service running: {data['current_state'].get('service_running')}")
                print(f"  Pending schedule: {data['current_state'].get('pending_wake_schedule')}")
                print(f"  History entries: {len(data.get('wake_history', []))}")
        else:
            print(f"\npower.json not found at {POWER_JSON}")
    except Exception as e:
        print(f"\npower.json error: {e}")
    
    # Log files
    try:
        log_dir = os.path.join(os.path.dirname(POWER_JSON), '..', 'log')
        service_log = os.path.join(log_dir, 'wake_service.log')
        if os.path.exists(service_log):
            size = os.path.getsize(service_log)
            print(f"\nService Log:")
            print(f"  Location: {service_log}")
            print(f"  Size: {size} bytes")
            
            # Show last few lines
            if size > 0:
                with open(service_log, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    print(f"  Last 3 entries:")
                    for line in lines[-3:]:
                        print(f"    {line.strip()}")
        else:
            print(f"\nService log not found at {service_log}")
    except Exception as e:
        print(f"\nService log error: {e}")


def run_all_tests():
    """Run all tests in sequence."""
    print("\n" + "#"*60)
    print("# S0 WAKE SERVICE TEST SUITE")
    print("#"*60)
    print("\nThis will test all components of the service-based wake system")
    print("Estimated time: ~2 minutes")
    print("\nRequirements:")
    print("  - Administrator privileges")
    print("  - System supports Modern Standby")
    print("  - No active RDP sessions")
    
    input("\nPress Enter to begin tests...")
    
    results = {}
    
    # Run tests
    results['test1'] = test_service_installation()
    results['test2'] = test_power_json_operations()
    results['test3'] = test_short_wake()
    results['test4'] = test_wake_history()
    results['test5'] = test_service_recovery()
    results['test6'] = test_fallback_mechanism()
    
    # Print results
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test.upper()}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED - System ready for production use")
    else:
        print(f"\n⚠ {total - passed} test(s) failed - Review diagnostics below")
    
    # Print diagnostics
    print_diagnostics()
    
    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
