# Deployment Guide - GitHub Actions CI/CD Pipeline

This guide provides comprehensive instructions for setting up and using the GitHub Actions CI/CD pipeline to deploy the VLAN Cleanup Automation service to VMs running Itential Gateway.

## 🚀 Pipeline Overview

The CI/CD pipeline provides automated testing, building, and deployment with the following stages:

1. **Testing & Quality Assurance** - Unit tests, integration tests, security scanning
2. **Build & Package** - Create deployment packages 
3. **Deploy to Development** - Automatic deployment to dev environment
4. **Deploy to Production** - Deployment to production on releases
5. **IAG Service Registration** - Automatic service registration in Itential Gateway

## 📁 Pipeline Files

### **Required Files:**
- **`.github/workflows/ci-cd.yml`** - Main pipeline configuration
- **`deployment/deploy.sh`** - Deployment script for VM deployment
- **`deployment/github-actions-pipeline.yml`** - Template pipeline file

### **Setup Instructions:**

1. **Copy the pipeline file to your repository:**
   ```bash
   # Create .github/workflows directory
   mkdir -p .github/workflows
   
   # Copy the pipeline configuration
   cp deployment/github-actions-pipeline.yml .github/workflows/ci-cd.yml
   ```

2. **Make deployment script executable:**
   ```bash
   chmod +x deployment/deploy.sh
   ```

## ⚙️ Configuration Requirements

### **GitHub Secrets Setup**

Configure the following secrets in your GitHub repository (**Settings > Secrets and variables > Actions**):

#### **Development Environment Secrets:**
- `DEV_SSH_PRIVATE_KEY` - SSH private key for development VM access
- `DEV_HOST` - Development VM hostname/IP address
- `DEV_USER` - SSH username for development VM

#### **Production Environment Secrets:**
- `PROD_SSH_PRIVATE_KEY` - SSH private key for production VM access
- `PROD_HOST` - Production VM hostname/IP address  
- `PROD_USER` - SSH username for production VM

#### **Optional Notification Secrets:**
- `SLACK_WEBHOOK_URL` - Slack webhook for deployment notifications

### **SSH Key Setup**

1. **Generate SSH key pair:**
   ```bash
   ssh-keygen -t rsa -b 4096 -C "github-actions@yourcompany.com" -f github-actions-key
   ```

2. **Add public key to VM:**
   ```bash
   # Copy public key to the VM
   ssh-copy-id -i github-actions-key.pub user@vm-hostname
   
   # Or manually add to ~/.ssh/authorized_keys
   cat github-actions-key.pub >> ~/.ssh/authorized_keys
   ```

3. **Add private key to GitHub secrets:**
   ```bash
   # Copy private key content to GitHub secret
   cat github-actions-key
   ```

## 🖥️ VM Prerequisites

### **VM Requirements:**
- Ubuntu 18.04+ or RHEL/CentOS 7+
- Python 3.8 or higher
- Git installed
- Sudo access for deployment user
- Itential Gateway installed and configured

### **VM Setup Script:**

```bash
#!/bin/bash
# VM preparation script

# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip git curl

# Create itential user if not exists
sudo useradd -r -s /bin/bash -d /home/itential -m itential

# Create service directories
sudo mkdir -p /opt/vlan-cleanup-automation
sudo mkdir -p /opt/backups/vlan-cleanup-automation

# Set permissions
sudo chown -R itential:itential /opt/vlan-cleanup-automation
sudo chown -R itential:itential /opt/backups/vlan-cleanup-automation

# Install IAG CLI (if not already installed)
# Follow Itential documentation for IAG CLI installation
```

## 🔄 Pipeline Triggers

### **Automatic Triggers:**

1. **Push to `main` branch** → Runs tests and deploys to production (if release)
2. **Push to `develop` branch** → Runs tests and deploys to development
3. **Pull Request to `main`** → Runs tests only
4. **Release published** → Full production deployment

### **Manual Triggers:**

```bash
# Trigger deployment manually via GitHub CLI
gh workflow run ci-cd.yml --ref main

# Or use GitHub web interface: Actions > CI/CD Pipeline > Run workflow
```

## 🏗️ Deployment Process

### **Development Deployment (Automatic)**

Triggered on push to `develop` branch:

1. **Testing Phase:**
   - Unit tests across Python versions (3.8, 3.9, 3.10, 3.11)
   - Integration tests
   - Security scanning (safety, bandit)
   - Code quality checks (flake8, pylint)

2. **Build Phase:**
   - Create deployment package
   - Generate version information
   - Upload build artifacts

3. **Deploy Phase:**
   - SSH to development VM
   - Backup existing deployment
   - Extract new deployment package
   - Install dependencies
   - Run health checks
   - Update IAG service

### **Production Deployment (Release)**

Triggered on GitHub release:

1. **All testing and build phases** (same as development)

2. **Production Deploy Phase:**
   - SSH to production VM
   - Create backup of current deployment
   - Deploy new version
   - Run comprehensive health checks
   - Update IAG service registration
   - Create deployment information file
   - Run production validation tests

3. **Rollback on Failure:**
   - Automatic rollback to previous version if deployment fails
   - Restore from backup
   - Notification of rollback

## 📊 Pipeline Outputs

### **Artifacts Generated:**
- **Test Reports** - HTML coverage reports, JUnit XML
- **Security Reports** - Safety and Bandit scan results
- **Deployment Package** - Compressed application package
- **Build Information** - Version, build date, branch information

### **Deployment Information File:**
```bash
# Created at: /opt/vlan-cleanup-automation/deployment.info
SERVICE_VERSION=abc123def456
DEPLOYED_AT=2025-01-15T10:30:00Z
DEPLOYED_BY=GitHub Actions
```

## 🔍 Monitoring & Troubleshooting

### **Pipeline Monitoring:**

1. **GitHub Actions Dashboard:**
   - Go to **Actions** tab in your repository
   - View workflow runs, logs, and artifacts
   - Monitor test results and deployment status

2. **Slack Notifications:**
   - Configure `SLACK_WEBHOOK_URL` for deployment notifications
   - Receive alerts for successful/failed deployments

### **Common Issues:**

1. **SSH Connection Failed:**
   ```bash
   # Check SSH key permissions
   chmod 600 ~/.ssh/github-actions-key
   
   # Test SSH connection
   ssh -i github-actions-key user@vm-hostname
   
   # Verify VM firewall allows SSH
   sudo ufw status
   ```

2. **Python Dependencies Failed:**
   ```bash
   # Check Python version on VM
   python3 --version
   
   # Verify pip installation
   python3 -m pip --version
   
   # Check disk space
   df -h
   ```

3. **IAG Service Registration Failed:**
   ```bash
   # Check if IAG CLI is installed
   itential-iag --version
   
   # Verify IAG CLI authentication
   sudo -u itential itential-iag service list
   
   # Check IAG service status
   systemctl status itential-gateway
   ```

### **Manual Deployment:**

If pipeline fails, you can deploy manually:

```bash
# SSH to the VM
ssh user@vm-hostname

# Download and run deployment script
curl -O https://raw.githubusercontent.com/keepithuman/vlan-cleanup-automation/main/deployment/deploy.sh
chmod +x deploy.sh
sudo ./deploy.sh
```

## 🔧 Customization

### **Environment-Specific Configuration:**

1. **Different Python versions:**
   ```yaml
   # Modify in .github/workflows/ci-cd.yml
   strategy:
     matrix:
       python-version: ['3.8', '3.9', '3.10', '3.11', '3.12']
   ```

2. **Additional test environments:**
   ```yaml
   # Add new deployment job
   deploy-staging:
     name: Deploy to Staging
     runs-on: ubuntu-latest
     needs: build
     if: github.ref == 'refs/heads/staging'
     environment: staging
   ```

3. **Custom deployment paths:**
   ```bash
   # Modify in deploy.sh
   SERVICE_DIR="/custom/path/vlan-cleanup-automation"
   SERVICE_USER="custom-user"
   ```

### **Advanced Pipeline Features:**

1. **Multi-region deployment:**
   ```yaml
   strategy:
     matrix:
       region: [us-east, us-west, eu-central]
   ```

2. **Blue-green deployment:**
   ```bash
   # Implement in deploy.sh
   deploy_blue_green() {
     # Deploy to inactive slot
     # Run health checks
     # Switch traffic to new deployment
   }
   ```

3. **Canary deployments:**
   ```yaml
   # Deploy to subset of instances first
   - name: Canary Deployment
     run: |
       deploy_to_percentage 10
       run_canary_tests
       deploy_to_percentage 100
   ```

## 📋 Checklist for Production Setup

### **Pre-deployment Checklist:**
- [ ] SSH keys generated and configured
- [ ] GitHub secrets properly set
- [ ] VM prerequisites installed
- [ ] IAG service user created
- [ ] Service directories created with proper permissions
- [ ] IAG CLI installed and configured
- [ ] Network connectivity verified
- [ ] Backup strategy implemented

### **Post-deployment Verification:**
- [ ] Service health checks pass
- [ ] IAG service registered successfully
- [ ] Tests execute successfully
- [ ] Deployment info file created
- [ ] Service accessible via IAG
- [ ] Monitoring and alerts configured
- [ ] Rollback procedure tested

## 🆘 Emergency Procedures

### **Rollback Commands:**
```bash
# SSH to VM
ssh user@vm-hostname

# List available backups
ls -la /opt/backups/vlan-cleanup-automation/

# Restore from backup
sudo rm -rf /opt/vlan-cleanup-automation
sudo cp -r /opt/backups/vlan-cleanup-automation/backup-YYYYMMDD-HHMMSS /opt/vlan-cleanup-automation
sudo chown -R itential:itential /opt/vlan-cleanup-automation

# Restart IAG service if needed
sudo systemctl restart itential-gateway
```

### **Manual IAG Service Registration:**
```bash
# SSH to VM as itential user
sudo -u itential bash

# Register repository
itential-iag repository create \
  --name "vlan-cleanup-automation" \
  --description "Enterprise VLAN cleanup automation" \
  --url "https://github.com/keepithuman/vlan-cleanup-automation.git" \
  --reference "main"

# Register service
itential-iag service create python-script \
  --name "vlan-cleanup-automation" \
  --repository "vlan-cleanup-automation" \
  --description "Automated VLAN cleanup service" \
  --filename "main.py" \
  --working-dir "."
```

## 📞 Support

- **Pipeline Issues**: Check GitHub Actions logs and artifacts
- **VM Issues**: Review deployment script logs and system status
- **IAG Issues**: Consult Itential Gateway documentation
- **Service Issues**: Check service health and test results

---

**🎯 This CI/CD pipeline provides production-ready automation for deploying the VLAN Cleanup service to Itential Gateway environments with comprehensive testing, security scanning, and rollback capabilities.**
