#!/bin/bash
set -e

# Setup variables
OPENSSL_DIR="./custom-openssl"
BETTERTLS_DIR="./bettertls"
TEST_OUTPUT="tls_test_results.txt"

# Function to check required tools
check_requirements() {
    command -v git >/dev/null 2>&1 || { echo "git is required but not installed. Aborting." >&2; exit 1; }
    command -v make >/dev/null 2>&1 || { echo "make is required but not installed. Aborting." >&2; exit 1; }
    command -v go >/dev/null 2>&1 || { echo "golang is required but not installed. Aborting." >&2; exit 1; }
}

# Build the bettertls command line tool
build_bettertls() {
    echo "Building bettertls tool..."
    cd "$BETTERTLS_DIR/test-suites/cmd/bettertls"
    go build -o ../../bettertls
    cd ../../..
}

# Generate test manifests
generate_manifests() {
    echo "Generating test manifests..."
    cd "./test-suites"
    ./bettertls generate-manifests
    cd ../..
}

# Run the tests
run_tests() {
    echo "Running TLS implementation tests..."
    cd "$BETTERTLS_DIR/test-suites"
    
    # Configure test environment for OpenSSL
    export OPENSSL_PATH="$OPENSSL_DIR/apps/openssl"
    export LD_LIBRARY_PATH="$OPENSSL_DIR"
    
    # Run the test suite
    ./bettertls run-tests \
        --openssl="$OPENSSL_PATH" \
        > "../../$TEST_OUTPUT" 2>&1
    
    # Show results
    ./bettertls show-results >> "../../$TEST_OUTPUT" 2>&1
    
    cd ../..
    echo "Tests completed. Results saved to $TEST_OUTPUT"
}

# Main execution
main() {
    echo "Starting TLS test suite execution..."
    
    # Check requirements
    check_requirements
    
    if [ ! -d "$BETTERTLS_DIR" ]; then
        echo "Setting up BetterTLS..."
        git clone https://github.com/Netflix/bettertls.git "$BETTERTLS_DIR"
    fi
    
    # Build the tool
    build_bettertls
    
    # Generate manifests
    generate_manifests
    
    # Run tests
    run_tests
    
    echo "Test suite execution completed"
    echo "Please check $TEST_OUTPUT for detailed results"
}

# Execute main function
main