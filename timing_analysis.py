import subprocess
import os
import time
import select
from typing import Optional, Tuple, Dict
from collections import deque

def timing_analysis_bettertls(bettertls_path: str, openssl_path: str) -> Tuple[float, Dict[str, str]]:
    print(f"Running bettertls analysis on {openssl_path}")
    
    # Setup paths and environment
    bettertls_bin = os.path.join(bettertls_path, "test-suites/bettertls")
    bettertls_cmd = [bettertls_bin, "run-tests", "--implementation", "openssl"]
    
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
    
    # Check OpenSSL version using the modified environment
    process = subprocess.Popen(
        ["openssl", "version"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    stdout, stderr = process.communicate()
    print(f"OpenSSL version: {stdout.strip()}")

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
            # print(f"[{pipe_name}] Batch of 100 lines:")
            # Print the last line of the batch
            print(f"{batch[-1]}")
            # for line in batch:
            #     print(f"{line}")
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
    
    print(f"Time taken to run bettertls tests: {execution_time:.2f} seconds")
    
    if return_code != 0:
        print(f"Process exited with code {return_code}")
        
    return execution_time, results
    
    
if __name__ == "__main__":
    openssl_3_0_2 = "/usr/bin/openssl"
    openssl_3_5_0 = "/home/ritvik/Crypto/openssl"
    bettertls_path = "/home/ritvik/Crypto/bettertls"
    # Run bettertls tests on each version of openssl
    # timing_analysis_bettertls(bettertls_path, openssl_3_0_2)
    timing_analysis_bettertls(bettertls_path, openssl_3_5_0)