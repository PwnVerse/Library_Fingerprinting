#!/usr/bin/env python3
import subprocess
import os
import time
import select
from typing import Optional, Tuple, Dict
from collections import deque

def setup_openssl_env(openssl_path: str):
    # Create a new environment dict instead of modifying the existing one
    env = dict(os.environ)
    
    # Set up the paths correctly
    apps_path = os.path.join(openssl_path, "apps")
    lib_path = openssl_path
    
    # Modify PATH to ensure the new openssl is found first
    env["PATH"] = f"{apps_path}{os.pathsep}{env.get('PATH', '')}"
    
    # Update library path
    current_ld_path = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = f"{lib_path}{os.pathsep}{current_ld_path}" if current_ld_path else lib_path
    
    print(f"LD_LIBRARY_PATH: {env.get('LD_LIBRARY_PATH')}")
    print(f"PATH: {env.get('PATH')}")
    
    return env

def setup_gnutls_env(gnutls_path: str):
    # Create a new environment dict instead of modifying the existing one
    env = dict(os.environ)
    
    # Set up the paths correctly
    apps_path = gnutls_path
    # Modify PATH to ensure the new openssl is found first
    env["PATH"] = f"{apps_path}{os.pathsep}{env.get('PATH', '')}"
    
    print(f"PATH: {env.get('PATH')}")
    
    return env

def setup_botan_env(botan_path: str):
    # Create a new environment dict instead of modifying the existing one
    env = dict(os.environ)
    
    # Set up the paths correctly
    apps_path = botan_path
    lib_path = botan_path
    
    # Modify PATH to ensure the new openssl is found first
    env["PATH"] = f"{apps_path}{os.pathsep}{env.get('PATH', '')}"
    
    # Update library path
    current_ld_path = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = f"{lib_path}{os.pathsep}{current_ld_path}" if current_ld_path else lib_path
    
    print(f"LD_LIBRARY_PATH: {env.get('LD_LIBRARY_PATH')}")
    print(f"PATH: {env.get('PATH')}")
    
    return env


def setup_envoy_env(envoy_path: str):
    # Create a new environment dict instead of modifying the existing one
    env = dict(os.environ)
    
    # Set up the paths correctly
    apps_path = envoy_path
    # Modify PATH to ensure the new openssl is found first
    env["PATH"] = f"{apps_path}{os.pathsep}{env.get('PATH', '')}"
    
    print(f"PATH: {env.get('PATH')}")
    
    return env

def timing_analysis_bettertls(bettertls_path: str, library_name: str, library_path: str):
    import time
    import re

    print(f"Running bettertls analysis on {library_path}")
    
    # Setup paths and environment
    bettertls_bin = os.path.join(bettertls_path, "test-suites/cmd/bettertls/bettertls")
    bettertls_cmd = [bettertls_bin, "run-tests", "--implementation", library_name]
    
    version_str = "--version"
    if library_name == "openssl":
        version_str = "version"
    elif library_name == "gnutls-cli":
        bettertls_cmd = [bettertls_bin, "run-tests", "--implementation", "gnutls"]
    
    env = None
    if library_name == "openssl" and library_path != "/usr/bin/openssl":
        env = setup_openssl_env(library_path)
    
    elif library_name == "gnutls-cli" and library_path != "/usr/bin/gnutls-cli":
        env = setup_gnutls_env(library_path)
    
    elif library_name == "botan" and library_path != "/usr/bin/botan":
        env = setup_botan_env(library_path)
        
    elif library_name == "envoy" and library_path != "/usr/bin/envoy":
        env = setup_envoy_env(library_path)
        
    # Check library version
    process = subprocess.Popen(
        [library_name, version_str],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    stdout, stderr = process.communicate()
    # Get the first non-empty line from the output
    version = None
    for line in stdout.splitlines():
        if line.strip():
            version = line.strip()
            break
        
    if version is None:
        print(f"Failed to get {library_name} version")
        os._exit(1)
    print(f"{library_name} version: {version}")

    try:
        process = subprocess.Popen(
            bettertls_cmd,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
    except subprocess.SubprocessError as e:
        print(f"Failed to start process: {e}")
        return -1, {"error": str(e)}

    timing_data = None
    start_time = time.time()
    last_progress_update = start_time
    total_tests = 0
    completed_tests = 0

    # Use select to read from both stdout and stderr simultaneously
    while process.poll() is None:
        reads = [process.stdout, process.stderr]
        readable, _, _ = select.select(reads, [], [], 0.1)

        current_time = time.time()
        
        for pipe in readable:
            line = pipe.readline()
            if not line:
                continue

            # Look for progress updates
            progress_match = re.search(r'(\d+)%\s*\|', line)
            if progress_match:
                current_progress = int(progress_match.group(1))
                
                # Extract total number of tests if available
                tests_match = re.search(r'\((\d+)/(\d+)', line)
                if tests_match:
                    completed_tests = int(tests_match.group(1))
                    total_tests = int(tests_match.group(2))
                
                # Update progress estimate every 3 seconds
                if current_time - last_progress_update > 3:
                    elapsed_time = current_time - start_time
                    
                    # Estimate remaining time
                    if current_progress > 0:
                        estimated_total_time = (elapsed_time / current_progress) * 100
                        remaining_time = estimated_total_time - elapsed_time
                        
                        print(f"\rProgress: {current_progress}% | "
                              f"Elapsed: {elapsed_time:.2f}s | "
                              f"Est. Remaining: {remaining_time:.2f}s | "
                              f"Completed Tests: {completed_tests}/{total_tests}", 
                              end='', flush=True)
                    
                    last_progress_update = current_time

            # Check for timing data
            if "Timing Report" in line:
                timing_lines = [line]
                # Continue reading timing data
                for timing_line in iter(process.stdout.readline, ''):
                    timing_lines.append(timing_line)
                    
                    if not timing_line.strip():
                        break
                
                # Parse and sort the timing data
                test_timings = {}
                total_time = None
                for timing_line in timing_lines:
                    if "Total Runner Execution Time" in timing_line:
                        total_time = timing_line.strip()
                    elif "/test-" in timing_line:
                        test, timing = timing_line.split(':')
                        test_timings[test.strip()] = float(timing.strip().replace('ms', ''))
                
                # Sort timing data
                sorted_timings = dict(sorted(test_timings.items(), key=lambda x: float(x[1])))
                
                # Prepare full timing report
                timing_report = f"Timing Report for {library_name}\n"
                timing_report += f"{total_time}\n"
                timing_report += "Individual Test Timings:\n"
                for test, timing in sorted_timings.items():
                    timing_report += f"  {test}: {timing}ms\n"
                
                timing_data = timing_report
                break

    # Print final newline after progress updates
    print()

    # Terminate the process if it's still running
    if process.poll() is None:
        process.terminate()
        process.wait()

    # Close pipes
    if process.stdout:
        process.stdout.close()
    if process.stderr:
        process.stderr.close()
        
    # Print timing data
    print('-'*40)
    print(f"\nTiming data for {library_name}:")
    print(timing_data)
    print('-'*40)


def reset_env():
    current_path = os.environ.get("PATH", "")

    # Split the PATH into components
    path_components = current_path.split(os.pathsep)

    # Remove the first component (if it exists)
    if path_components:
        # Check if "Library_Fingerprinting" is present in any of the path components
        if "Library_Fingerprinting" or ".cache" in path_components[0]:
            path_components.pop(0)

    # Rejoin the remaining components
    updated_path = os.pathsep.join(path_components)

    # Update the PATH environment variable
    os.environ["PATH"] = updated_path
    
    # Reset LD_LIBRARY_PATH
    os.environ["LD_LIBRARY_PATH"] = ""
    
    
if __name__ == "__main__":
    bettertls_path = "/home/ritvik/Crypto/Library_Fingerprinting/bettertls"
    openssl_3_0_2 = "/usr/bin/openssl"
    openssl_3_5_0 = "/home/ritvik/Crypto/Library_Fingerprinting/openssl"
    gnutls_3_7_3 = "/usr/bin/gnutls-cli"
    gnutls_3_8_8 = "/home/ritvik/Crypto/Library_Fingerprinting/gnutls/src"
    botan_2_19_1 = "/usr/bin/botan"
    botan_3_7_0 = "/home/ritvik/Crypto/Library_Fingerprinting/botan"
    envoy_1_32_1 = "/usr/bin/envoy"
    envoy_1_33_0 = "/home/ritvik/.cache/bazel/_bazel_ritvik/f5eed17828cbd18aa53063fc17424c84/execroot/envoy/bazel-out/k8-fastbuild/bin/source/exe"
    
    reset_env()
    # Run bettertls tests on each version of openssl
    timing_analysis_bettertls(bettertls_path, "openssl", openssl_3_0_2)
    timing_analysis_bettertls(bettertls_path, "openssl", openssl_3_5_0)
    # Reset the environment variables
    reset_env()
    # Run bettertls tests on each version of gnutls
    timing_analysis_bettertls(bettertls_path, "gnutls-cli", gnutls_3_7_3)
    timing_analysis_bettertls(bettertls_path, "gnutls-cli", gnutls_3_8_8)
    # Reset the environment variables
    reset_env()
    timing_analysis_bettertls(bettertls_path, "botan", botan_2_19_1)
    timing_analysis_bettertls(bettertls_path, "botan", botan_3_7_0)
    # Reset the environment variables
    reset_env()
    timing_analysis_bettertls(bettertls_path, "envoy", envoy_1_32_1)
    # timing_analysis_bettertls(bettertls_path, "envoy", envoy_1_33_0)