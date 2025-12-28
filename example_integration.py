"""
Example: Integrating Service-Based Wake into Existing Stress Test

This shows how to integrate enter_s0_with_service() into your 
existing stress test without major code changes.
"""

import logging
import sys
import io
from util_power import enter_s0_with_service, _is_service_running

# Force UTF-8 encoding for stdout/stderr
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Your existing stress test setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('StressTest')


def setup_test_environment():
    """Setup test environment - called once at start."""
    logger.info("Setting up test environment...")
    
    # Check if service is ready (optional pre-check)
    if not _is_service_running():
        logger.info("Service not running - will auto-install on first wake")
    else:
        logger.info("Service already running")
    
    # Your existing setup code here
    pass


def run_single_iteration(iteration_num, sleep_duration=10):
    """
    Run a single stress test iteration with S0 sleep.
    
    This is where you would normally do:
        util_power.enter_s0_and_wake(sleep_duration)
    
    Now just replace with:
        enter_s0_with_service(sleep_duration)
    """
    logger.info(f"Starting iteration {iteration_num}")
    
    # Your pre-sleep test operations
    logger.info("Running pre-sleep tests...")
    # ... your test code ...
    
    # Enter S0 with automatic wake
    logger.info(f"Entering S0 for {sleep_duration}s...")
    wake_success = enter_s0_with_service(sleep_duration)
    
    if wake_success:
        logger.info("[OK] Wake successful - continuing tests")
    else:
        logger.warning("[WARN] Wake timeout - display manually restored")
        # Test can still continue - display is guaranteed to be on
    
    # Your post-wake test operations
    logger.info("Running post-wake tests...")
    # ... your test code ...
    
    logger.info(f"Iteration {iteration_num} complete")
    return wake_success


def run_stress_test(iterations=10, sleep_duration=10):
    """
    Main stress test loop.
    
    Minimal changes needed:
    1. Import enter_s0_with_service
    2. Replace enter_s0_and_wake() calls
    3. Optionally track wake success
    """
    logger.info("="*60)
    logger.info(f"Starting stress test: {iterations} iterations")
    logger.info(f"S0 sleep duration: {sleep_duration}s per iteration")
    logger.info("="*60)
    
    setup_test_environment()
    
    success_count = 0
    fail_count = 0
    
    for i in range(1, iterations + 1):
        try:
            success = run_single_iteration(i, sleep_duration)
            
            if success:
                success_count += 1
            else:
                fail_count += 1
                
        except KeyboardInterrupt:
            logger.warning("\nTest interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in iteration {i}: {e}")
            fail_count += 1
    
    # Report results
    logger.info("="*60)
    logger.info("STRESS TEST COMPLETE")
    logger.info(f"Total iterations: {iterations}")
    logger.info(f"Successful wakes: {success_count}")
    logger.info(f"Failed wakes: {fail_count}")
    logger.info(f"Success rate: {100*success_count/iterations:.1f}%")
    logger.info("="*60)
    
    return success_count, fail_count


def main():
    """Entry point."""
    # Run 5 iterations with 10 second sleep
    run_stress_test(iterations=5, sleep_duration=10)


if __name__ == '__main__':
    main()
