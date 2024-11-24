#!/usr/bin/env python3
import re
import sys
from datetime import datetime
from collections import defaultdict

class TLS13TestParser:
    def __init__(self):
        self.test_stats = defaultdict(list)
        self.current_test = None
        
    def parse_output(self, output):
        """Parse OpenSSL verbose test output."""
        test_patterns = {
            'test_start': r'(\d+)-test_tls13(\w+)\.t \.\.\.',
            'subtest': r'ok\s+(\d+)\s*-?\s*(.*)',
            'handshake': r'SSL handshake has read (\d+) bytes and written (\d+) bytes',
            'cipher': r'New,\s*(TLSv[\d.]+),\s*Cipher is\s*([\w-]+)',
            'protocol': r'Protocol\s*:\s*(TLSv[\d.]+)',
            'verify': r'Verify return code:\s*(\d+)\s*\((.*?)\)'
        }
        
        current_test = None
        current_stats = {}
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Test suite start
            if match := re.match(test_patterns['test_start'], line):
                if current_stats:
                    self.test_stats[current_test].append(current_stats)
                current_test = f"test_tls13{match.group(2)}"
                current_stats = {
                    'start_time': datetime.now(),
                    'description': '',
                    'status': 'unknown'
                }
                continue
                
            # Test result
            if match := re.match(test_patterns['subtest'], line):
                if current_stats:
                    current_stats.update({
                        'test_number': match.group(1),
                        'description': match.group(2),
                        'end_time': datetime.now(),
                        'status': 'ok',
                        'duration': (datetime.now() - current_stats['start_time']).total_seconds()
                    })
                    self.test_stats[current_test].append(current_stats)
                    current_stats = {
                        'start_time': datetime.now(),
                        'description': '',
                        'status': 'unknown'
                    }
                
            # Handshake stats
            if match := re.match(test_patterns['handshake'], line):
                if current_stats:
                    current_stats.update({
                        'bytes_read': int(match.group(1)),
                        'bytes_written': int(match.group(2))
                    })
                
            # Cipher information
            if match := re.match(test_patterns['cipher'], line):
                if current_stats:
                    current_stats.update({
                        'tls_version': match.group(1),
                        'cipher_suite': match.group(2)
                    })
                    
            # Verification result
            if match := re.match(test_patterns['verify'], line):
                if current_stats:
                    current_stats.update({
                        'verify_code': match.group(1),
                        'verify_message': match.group(2)
                    })

    def print_analysis(self):
        """Print analysis of test execution times."""
        print("\nTLS 1.3 Test Analysis")
        print("-" * 100)
        headers = ['Test', 'Description', 'Status', 'Duration(s)', 'Bytes Read', 'Bytes Written']
        print(f"{headers[0]:<30} {headers[1]:<30} {headers[2]:<8} {headers[3]:<12} {headers[4]:<10} {headers[5]}")
        print("-" * 100)
        
        total_duration = 0
        passed_tests = failed_tests = 0
        
        for test_name, subtests in sorted(self.test_stats.items()):
            for subtest in subtests:
                duration = subtest.get('duration', 0)
                total_duration += duration
                
                if subtest.get('status') == 'ok':
                    passed_tests += 1
                else:
                    failed_tests += 1
                    
                print(f"{test_name[:30]:<30} "
                      f"{subtest.get('description', '')[:30]:<30} "
                      f"{subtest.get('status', '-'):<8} "
                      f"{duration:<12.5f} "
                      f"{subtest.get('bytes_read', '-'):<10} "
                      f"{subtest.get('bytes_written', '-')}")
        
        print("-" * 100)
        print(f"\nSummary:")
        print(f"Total Tests: {passed_tests + failed_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Total Duration: {total_duration:.5f} seconds")

def main():
    if len(sys.argv) != 2:
        print("Usage: ./output_analysis.py <test_output_file>")
        sys.exit(1)
        
    try:
        with open(sys.argv[1], 'r') as f:
            output = f.read()
    except FileNotFoundError:
        print(f"Error: File {sys.argv[1]} not found")
        sys.exit(1)
        
    parser = TLS13TestParser()
    parser.parse_output(output)
    parser.print_analysis()

if __name__ == "__main__":
    main()