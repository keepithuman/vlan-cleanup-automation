# IAG Service Registration Guide

This document provides step-by-step instructions for registering the VLAN Cleanup Automation service in Itential Automation Gateway (IAG).

## Prerequisites

- IAG instance with appropriate permissions
- Access to IAG CLI or web interface
- Network connectivity to GitHub repository

## Method 1: Using IAG CLI (Recommended)

### Step 1: Create Repository

```bash
# Create the repository in IAG
itential-iag repository create \
  --name "vlan-cleanup-automation" \
  --description "Enterprise-grade automation solution for identifying unused VLANs and generating removal commands for Cisco, Arista, and Juniper network devices" \
  --url "https://github.com/keepithuman/vlan-cleanup-automation.git" \
  --reference "main"
```

### Step 2: Register Python Script Service

```bash
# Register the service
itential-iag service create python-script \
  --name "vlan-cleanup-automation" \
  --repository "vlan-cleanup-automation" \
  --description "Automated VLAN cleanup and analysis service for multi-vendor network environments" \
  --filename "main.py" \
  --working-dir "." \
  --env "PYTHONPATH=." \
  --tag "network" \
  --tag "vlan" \
  --tag "automation" \
  --tag "cisco" \
  --tag "arista" \
  --tag "juniper"
```

## Method 2: Using IAG Web Interface

### Step 1: Access IAG Web Interface

1. Navigate to your IAG instance web interface
2. Login with appropriate credentials
3. Go to **Services** → **Repositories**

### Step 2: Create Repository

1. Click **+ Add Repository**
2. Fill in the details:
   - **Name**: `vlan-cleanup-automation`
   - **Description**: `Enterprise-grade automation solution for identifying unused VLANs and generating removal commands for Cisco, Arista, and Juniper network devices`
   - **URL**: `https://github.com/keepithuman/vlan-cleanup-automation.git`
   - **Reference**: `main`
3. Click **Save**

### Step 3: Register Service

1. Go to **Services** → **Services**
2. Click **+ Add Service**
3. Select **Python Script** as service type
4. Fill in the details:
   - **Name**: `vlan-cleanup-automation`
   - **Repository**: `vlan-cleanup-automation` (select from dropdown)
   - **Description**: `Automated VLAN cleanup and analysis service for multi-vendor network environments`
   - **Script File**: `main.py`
   - **Working Directory**: `.`
   - **Environment Variables**: `PYTHONPATH=.`
   - **Tags**: `network`, `vlan`, `automation`, `cisco`, `arista`, `juniper`
5. Click **Save**

## Method 3: Using Itential MCP (If Available)

If you have access to the Itential MCP tools:

```bash
# Create repository
itential-mcp:create_iag_repository \
  --name "vlan-cleanup-automation" \
  --description "Enterprise-grade automation solution for identifying unused VLANs and generating removal commands for Cisco, Arista, and Juniper network devices" \
  --url "https://github.com/keepithuman/vlan-cleanup-automation.git" \
  --reference "main"

# Register service
itential-mcp:create_iag_service \
  --service-type "python-script" \
  --name "vlan-cleanup-automation" \
  --repository "vlan-cleanup-automation" \
  --description "Automated VLAN cleanup and analysis service for multi-vendor network environments" \
  --filename "main.py" \
  --working-dir "."
```

## Service Configuration Parameters

Once registered, the service will accept the following parameters:

### Required Inputs
- `config_file` (string): Path to configuration file (default: "config.yaml")
- `username` (string, sensitive): Network device username
- `password` (string, sensitive): Network device password

### Optional Inputs
- `dry_run` (boolean): Run in analysis mode only (default: true)
- `execute` (boolean): Execute actual cleanup (default: false)
- `approve_all` (boolean): Auto-approve high-risk VLANs (default: false)
- `output_file` (string): Custom output file path
- `generate_csv` (boolean): Generate CSV summary (default: true)
- `enable_password` (string, sensitive): Enable password for Cisco devices
- `verbose` (boolean): Enable verbose logging (default: false)

### Outputs
- `report_file` (string): Path to comprehensive JSON report
- `csv_file` (string): Path to CSV summary (if generated)
- `summary` (object): Executive summary of results
- `recommendations` (array): List of operational recommendations

## Testing the Service

### Step 1: Verify Service Registration

```bash
# List services to verify registration
itential-iag service list | grep vlan-cleanup

# Get service details
itential-iag service get vlan-cleanup-automation
```

### Step 2: Test Execution

Create a test job with the following parameters:

```json
{
  "service": "vlan-cleanup-automation",
  "inputs": {
    "config_file": "config.yaml",
    "dry_run": true,
    "username": "test_user",
    "password": "test_password",
    "generate_csv": true,
    "verbose": true
  }
}
```

### Step 3: Monitor Execution

1. Check job status in IAG web interface
2. Review logs for any errors
3. Verify output files are generated
4. Validate report content

## Workflow Integration

### Example IAG Workflow Integration

```yaml
# Example workflow step
workflows:
  vlan_cleanup_workflow:
    steps:
      - name: "VLAN Analysis"
        type: "service"
        service: "vlan-cleanup-automation"
        inputs:
          config_file: "{{ .WorkflowInputs.config_file }}"
          dry_run: true
          username: "{{ .Secrets.network_username }}"
          password: "{{ .Secrets.network_password }}"
          generate_csv: true
        outputs:
          analysis_report: "{{ .ServiceOutputs.report_file }}"
          
      - name: "Review Results"
        type: "approval"
        condition: "{{ .StepOutputs.analysis_report.summary.unused_vlans > 0 }}"
        approvers: ["network-team"]
        
      - name: "Execute Cleanup"
        type: "service"
        service: "vlan-cleanup-automation"
        condition: "{{ .ApprovalOutputs.approved }}"
        inputs:
          config_file: "{{ .WorkflowInputs.config_file }}"
          execute: true
          username: "{{ .Secrets.network_username }}"
          password: "{{ .Secrets.network_password }}"
```

## Security Configuration

### Credential Management

1. **Store credentials in IAG Secrets**:
   ```bash
   itential-iag secret create network_credentials \
     --key "username" --value "your_username" \
     --key "password" --value "your_password" \
     --key "enable_password" --value "your_enable_password"
   ```

2. **Reference secrets in service calls**:
   ```json
   {
     "username": "{{ .Secrets.network_credentials.username }}",
     "password": "{{ .Secrets.network_credentials.password }}",
     "enable_password": "{{ .Secrets.network_credentials.enable_password }}"
   }
   ```

### Access Control

1. Configure appropriate RBAC policies
2. Limit service execution to authorized users
3. Implement approval workflows for production execution
4. Enable audit logging for all service executions

## Monitoring and Alerting

### Performance Monitoring

Monitor these key metrics:
- Service execution time
- Success/failure rates
- Number of devices processed
- VLANs cleaned per execution

### Alert Configuration

Set up alerts for:
- Service execution failures
- High processing times (>30 minutes)
- Connectivity issues with devices
- Critical VLAN detection

### Log Management

Configure centralized logging for:
- Service execution logs
- Device connection logs
- Configuration change logs
- Error and warning messages

## Troubleshooting

### Common Issues

1. **Repository Not Found**
   - Verify GitHub repository URL
   - Check IAG connectivity to GitHub
   - Ensure repository is public or IAG has access

2. **Service Registration Fails**
   - Check IAG permissions
   - Verify repository exists in IAG
   - Validate service configuration

3. **Service Execution Errors**
   - Review service logs
   - Check device connectivity
   - Verify credentials
   - Validate configuration file

### Debug Steps

1. **Check Service Status**:
   ```bash
   itential-iag service status vlan-cleanup-automation
   ```

2. **Review Logs**:
   ```bash
   itential-iag logs service vlan-cleanup-automation
   ```

3. **Test Connectivity**:
   ```bash
   # Test from IAG host
   ping <device_ip>
   ssh <username>@<device_ip>
   ```

## Support and Maintenance

### Regular Maintenance

1. **Update Repository**:
   ```bash
   itential-iag repository update vlan-cleanup-automation
   ```

2. **Service Updates**:
   - Monitor for new releases
   - Test updates in development environment
   - Deploy updates during maintenance windows

3. **Performance Optimization**:
   - Review execution metrics
   - Adjust concurrent device limits
   - Optimize device timeout settings

### Getting Help

- **Documentation**: [GitHub Repository](https://github.com/keepithuman/vlan-cleanup-automation)
- **Issues**: [GitHub Issues](https://github.com/keepithuman/vlan-cleanup-automation/issues)
- **Support**: Contact network automation team

---

**Note**: This service has been successfully registered in IAG and is ready for use. Please ensure proper testing in a development environment before production deployment.
