#!/bin/bash
# Deployment script for VLAN Cleanup Automation service
# This script deploys the service to a VM with Itential Gateway

set -euo pipefail

# Configuration
SERVICE_NAME="vlan-cleanup-automation"
SERVICE_DIR="/opt/${SERVICE_NAME}"
BACKUP_DIR="/opt/backups/${SERVICE_NAME}"
SERVICE_USER="itential"
GITHUB_REPO="https://github.com/keepithuman/vlan-cleanup-automation.git"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

log_success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

log_error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

# Function to check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root or with sudo"
        exit 1
    fi
}

# Function to check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if Python 3 is installed
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi
    
    # Check Python version
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 8) else 1)'; then
        log_error "Python 3.8 or higher is required, found version $PYTHON_VERSION"
        exit 1
    fi
    
    # Check if pip is installed
    if ! command -v pip3 &> /dev/null; then
        log_error "pip3 is not installed"
        exit 1
    fi
    
    # Check if git is installed
    if ! command -v git &> /dev/null; then
        log_error "git is not installed"
        exit 1
    fi
    
    # Check if service user exists
    if ! id "$SERVICE_USER" &>/dev/null; then
        log_warning "Service user '$SERVICE_USER' does not exist, creating..."
        useradd -r -s /bin/bash -d /home/$SERVICE_USER -m $SERVICE_USER
        log_success "Service user '$SERVICE_USER' created"
    fi
    
    log_success "Prerequisites check completed"
}

# Function to create backup
create_backup() {
    if [ -d "$SERVICE_DIR" ]; then
        log "Creating backup of existing deployment..."
        mkdir -p "$BACKUP_DIR"
        BACKUP_NAME="backup-$(date +%Y%m%d-%H%M%S)"
        cp -r "$SERVICE_DIR" "$BACKUP_DIR/$BACKUP_NAME"
        log_success "Backup created: $BACKUP_DIR/$BACKUP_NAME"
        echo "$BACKUP_DIR/$BACKUP_NAME" > /tmp/vlan_cleanup_backup_path
    fi
}

# Function to deploy from Git
deploy_from_git() {
    log "Deploying from Git repository..."
    
    # Create service directory
    mkdir -p "$SERVICE_DIR"
    
    # Clone or update repository
    if [ -d "$SERVICE_DIR/.git" ]; then
        log "Updating existing repository..."
        cd "$SERVICE_DIR"
        sudo -u "$SERVICE_USER" git pull origin main
    else
        log "Cloning repository..."
        rm -rf "$SERVICE_DIR"/*
        sudo -u "$SERVICE_USER" git clone "$GITHUB_REPO" "$SERVICE_DIR"
        cd "$SERVICE_DIR"
    fi
    
    # Set ownership
    chown -R "$SERVICE_USER:$SERVICE_USER" "$SERVICE_DIR"
    
    log_success "Repository deployment completed"
}

# Function to deploy from package
deploy_from_package() {
    local package_file="$1"
    
    log "Deploying from package: $package_file"
    
    if [ ! -f "$package_file" ]; then
        log_error "Package file not found: $package_file"
        exit 1
    fi
    
    # Create service directory
    mkdir -p "$SERVICE_DIR"
    
    # Extract package
    cd "$SERVICE_DIR"
    tar -xzf "$package_file"
    
    # Set ownership and permissions
    chown -R "$SERVICE_USER:$SERVICE_USER" "$SERVICE_DIR"
    chmod +x "$SERVICE_DIR/main.py"
    chmod +x "$SERVICE_DIR/run_tests.py"
    
    log_success "Package deployment completed"
}

# Function to install dependencies
install_dependencies() {
    log "Installing Python dependencies..."
    
    cd "$SERVICE_DIR"
    
    # Install main dependencies
    sudo -u "$SERVICE_USER" python3 -m pip install --user -r requirements.txt
    
    # Install test dependencies (optional)
    if [ -f "requirements-test.txt" ]; then
        sudo -u "$SERVICE_USER" python3 -m pip install --user -r requirements-test.txt
    fi
    
    log_success "Dependencies installed successfully"
}

# Function to run health checks
run_health_checks() {
    log "Running health checks..."
    
    cd "$SERVICE_DIR"
    
    # Test main script
    if sudo -u "$SERVICE_USER" python3 main.py --help > /dev/null; then
        log_success "Main script health check passed"
    else
        log_error "Main script health check failed"
        return 1
    fi
    
    # Run unit tests if available
    if [ -f "run_tests.py" ]; then
        log "Running unit tests..."
        if sudo -u "$SERVICE_USER" python3 run_tests.py --unit --verbose; then
            log_success "Unit tests passed"
        else
            log_warning "Unit tests failed, but continuing deployment"
        fi
    fi
    
    log_success "Health checks completed"
}

# Function to update IAG service
update_iag_service() {
    log "Updating IAG service..."
    
    # Check if IAG CLI is available
    if ! command -v itential-iag &> /dev/null; then
        log_warning "IAG CLI not found, skipping service update"
        return 0
    fi
    
    cd "$SERVICE_DIR"
    
    # Update repository in IAG
    if sudo -u "$SERVICE_USER" itential-iag repository get vlan-cleanup-automation &> /dev/null; then
        log "Updating existing IAG repository..."
        sudo -u "$SERVICE_USER" itential-iag repository update vlan-cleanup-automation
        log_success "IAG repository updated"
    else
        log "Creating IAG repository..."
        sudo -u "$SERVICE_USER" itential-iag repository create \
            --name "vlan-cleanup-automation" \
            --description "Enterprise VLAN cleanup automation for multi-vendor networks" \
            --url "$GITHUB_REPO" \
            --reference "main"
        log_success "IAG repository created"
    fi
    
    # Update or create service in IAG
    if sudo -u "$SERVICE_USER" itential-iag service get vlan-cleanup-automation &> /dev/null; then
        log "IAG service already exists"
    else
        log "Creating IAG service..."
        sudo -u "$SERVICE_USER" itential-iag service create python-script \
            --name "vlan-cleanup-automation" \
            --repository "vlan-cleanup-automation" \
            --description "Automated VLAN cleanup and analysis service" \
            --filename "main.py" \
            --working-dir "."
        log_success "IAG service created"
    fi
}

# Function to create deployment info
create_deployment_info() {
    log "Creating deployment information..."
    
    cat > "$SERVICE_DIR/deployment.info" << EOF
DEPLOYED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DEPLOYED_BY=$(whoami)
DEPLOYMENT_METHOD=$1
SERVICE_VERSION=$(cd "$SERVICE_DIR" && git rev-parse HEAD 2>/dev/null || echo "unknown")
PYTHON_VERSION=$(python3 --version)
SYSTEM_INFO=$(uname -a)
EOF
    
    chown "$SERVICE_USER:$SERVICE_USER" "$SERVICE_DIR/deployment.info"
    log_success "Deployment information created"
}

# Function to rollback deployment
rollback_deployment() {
    log_error "Deployment failed, initiating rollback..."
    
    if [ -f "/tmp/vlan_cleanup_backup_path" ]; then
        BACKUP_PATH=$(cat /tmp/vlan_cleanup_backup_path)
        if [ -d "$BACKUP_PATH" ]; then
            log "Rolling back to: $BACKUP_PATH"
            rm -rf "$SERVICE_DIR"
            cp -r "$BACKUP_PATH" "$SERVICE_DIR"
            chown -R "$SERVICE_USER:$SERVICE_USER" "$SERVICE_DIR"
            log_success "Rollback completed"
        else
            log_error "Backup directory not found: $BACKUP_PATH"
        fi
    else
        log_error "No backup found for rollback"
    fi
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy VLAN Cleanup Automation service to Itential Gateway VM

OPTIONS:
    -h, --help              Show this help message
    -p, --package FILE      Deploy from package file instead of Git
    -b, --branch BRANCH     Git branch to deploy (default: main)
    -s, --skip-tests        Skip running tests during deployment
    -n, --no-iag            Skip IAG service registration
    -d, --dry-run          Show what would be done without executing

EXAMPLES:
    $0                              # Deploy from Git (main branch)
    $0 --package service.tar.gz     # Deploy from package file
    $0 --branch develop             # Deploy from develop branch
    $0 --skip-tests --no-iag        # Quick deployment without tests or IAG

EOF
}

# Main deployment function
main() {
    local package_file=""
    local git_branch="main"
    local skip_tests=false
    local no_iag=false
    local dry_run=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -p|--package)
                package_file="$2"
                shift 2
                ;;
            -b|--branch)
                git_branch="$2"
                shift 2
                ;;
            -s|--skip-tests)
                skip_tests=true
                shift
                ;;
            -n|--no-iag)
                no_iag=true
                shift
                ;;
            -d|--dry-run)
                dry_run=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    if [ "$dry_run" = true ]; then
        log "DRY RUN MODE - No changes will be made"
        log "Would deploy to: $SERVICE_DIR"
        log "Service user: $SERVICE_USER"
        if [ -n "$package_file" ]; then
            log "Would deploy from package: $package_file"
        else
            log "Would deploy from Git branch: $git_branch"
        fi
        exit 0
    fi
    
    log "Starting VLAN Cleanup Automation deployment..."
    log "Target directory: $SERVICE_DIR"
    log "Service user: $SERVICE_USER"
    
    # Trap for cleanup on failure
    trap 'rollback_deployment' ERR
    
    # Run deployment steps
    check_root
    check_prerequisites
    create_backup
    
    if [ -n "$package_file" ]; then
        deploy_from_package "$package_file"
        create_deployment_info "package"
    else
        deploy_from_git
        create_deployment_info "git"
    fi
    
    install_dependencies
    
    if [ "$skip_tests" = false ]; then
        run_health_checks
    fi
    
    if [ "$no_iag" = false ]; then
        update_iag_service
    fi
    
    # Clean up
    rm -f /tmp/vlan_cleanup_backup_path
    
    log_success "VLAN Cleanup Automation deployment completed successfully!"
    log "Service location: $SERVICE_DIR"
    log "Service user: $SERVICE_USER"
    log "To test the service: sudo -u $SERVICE_USER python3 $SERVICE_DIR/main.py --help"
}

# Run main function with all arguments
main "$@"
