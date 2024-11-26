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

def timing_analysis_bettertls(bettertls_path: str, library_name: str, library_path: str):
    print(f"Running bettertls analysis on {library_path}")
    
    # Setup paths and environment
    bettertls_bin = os.path.join(bettertls_path, "test-suites/bettertls")
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
        
    # Check OpenSSL version using the modified environment
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
        
    if version is None:
        print(f"Failed to get {library_name} version")
        os._exit(1)
    # version = stdout.splitlines()[0].strip()
    print(f"{library_name} version: {version}")

    start_time = time.time()
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

    results = {"stdout": [], "stderr": []}
    line_buffers = {
        "stdout": deque(maxlen=100),
        "stderr": deque(maxlen=100)
    }
    line_counts = {"stdout": 0, "stderr": 0}
    
    def process_buffer(pipe_name: str) -> None:
        """Process and print buffered lines when buffer is full."""
        if len(line_buffers[pipe_name]) == 100:
            batch = list(line_buffers[pipe_name])
            results[pipe_name].extend(batch)
            # Print the last line of the batch
            print(f"{batch[-1]}")
            line_buffers[pipe_name].clear()
    
    def read_output(pipe, pipe_name: str) -> bool:
        """Read from a pipe and buffer the output."""
        if pipe.closed:
            return False
        
        line = pipe.readline()
        if line:
            line = line.strip()
            line_counts[pipe_name] += 1
            line_buffers[pipe_name].append(line)
            
            # Process buffer when it reaches 100 lines
            if line_counts[pipe_name] % 100 == 0:
                process_buffer(pipe_name)
            return True
        return False

    while True:
        reads = []
        if process.stdout and not process.stdout.closed:
            reads.append(process.stdout)
        if process.stderr and not process.stderr.closed:
            reads.append(process.stderr)
            
        if not reads or process.poll() is not None:
            break
            
        ready_reads, _, _ = select.select(reads, [], [], 0.1)
        
        for pipe in ready_reads:
            if pipe == process.stdout:
                read_output(pipe, "stdout")
            elif pipe == process.stderr:
                read_output(pipe, "stderr")

    # Process any remaining lines in buffers
    for pipe_name in ["stdout", "stderr"]:
        if line_buffers[pipe_name]:
            remaining = list(line_buffers[pipe_name])
            results[pipe_name].extend(remaining)
            print(f"[{pipe_name}] Remaining lines ({len(remaining)}):")
            for line in remaining:
                print(f"  {line}")

    # Cleanup
    if process.stdout:
        process.stdout.close()
    if process.stderr:
        process.stderr.close()
        
    return_code = process.wait()
    execution_time = time.time() - start_time
    
    results["return_code"] = return_code
    results["execution_time"] = execution_time
    
    print(f"{library_name} : Time taken to run bettertls tests on {version}: {execution_time:.2f} seconds")
    
    if return_code != 0:
        print(f"Process exited with code {return_code}")
        
    return execution_time, results


def reset_env():
    current_path = os.environ.get("PATH", "")

    # Split the PATH into components
    path_components = current_path.split(os.pathsep)

    # Remove the first component (if it exists)
    if path_components:
        # Check if "Library_Fingerprinting" is present in any of the path components
        if "Library_Fingerprinting" in path_components[0]:
            path_components.pop(0)

    # Rejoin the remaining components
    updated_path = os.pathsep.join(path_components)

    # Update the PATH environment variable
    os.environ["PATH"] = updated_path
    
    # Reset LD_LIBRARY_PATH
    os.environ["LD_LIBRARY_PATH"] = ""
    
    
if __name__ == "__main__":
    openssl_3_0_2 = "/usr/bin/openssl"
    openssl_3_5_0 = "/home/ritvik/Crypto/Library_Fingerprinting/openssl"
    gnutls_3_7_3 = "/usr/bin/gnutls-cli"
    gnutls_3_8_8 = "/home/ritvik/Crypto/Library_Fingerprinting/gnutls/src"
    bettertls_path = "/home/ritvik/Crypto/Library_Fingerprinting/bettertls"
    botan_2_19_1 = "/usr/bin/botan"
    botan_3_7_0 = "/home/ritvik/Crypto/Library_Fingerprinting/botan"
    envoy_1_32_1 = "/usr/bin/envoy"
    
    
    # reset_env()
    # # Run bettertls tests on each version of openssl
    # timing_analysis_bettertls(bettertls_path, "openssl", openssl_3_0_2)
    # timing_analysis_bettertls(bettertls_path, "openssl", openssl_3_5_0)
    # # Reset the environment variables
    # reset_env()
    # # Run bettertls tests on each version of gnutls
    # timing_analysis_bettertls(bettertls_path, "gnutls-cli", gnutls_3_7_3)
    # timing_analysis_bettertls(bettertls_path, "gnutls-cli", gnutls_3_8_8)
    # Reset the environment variables
    # reset_env()
    # timing_analysis_bettertls(bettertls_path, "botan", botan_2_19_1)
    # timing_analysis_bettertls(bettertls_path, "botan", botan_3_7_0)
    reset_env()
    timing_analysis_bettertls(bettertls_path, "envoy", envoy_1_32_1)