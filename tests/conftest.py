"""
Test fixtures and common utilities for VLAN cleanup automation tests.
"""
import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch
from pathlib import Path
import yaml

from src.models import DeviceInfo, VLANInfo, ProcessingResult
from src.config import ConfigManager


@pytest.fixture
def temp_config_file():
    """Create a temporary configuration file for testing."""
    config_data = {
        'devices': [
            {
                'hostname': 'test-switch-01',
                'ip_address': '192.168.1.10',
                'vendor': 'cisco',
                'device_type': 'cisco_ios'
            }
        ],
        'authentication': {
            'username': 'testuser',
            'password': 'testpass',
            'enable_password': 'enablepass'
        },
        'vlan_analysis': {
            'exclude_vlans': [1, 1002, 1003, 1004, 1005],
            'minimum_age_days': 30,
            'require_manual_approval': True,
            'critical_vlan_names': ['management', 'voice']
        },
        'processing': {
            'max_concurrent_devices': 2,
            'device_timeout': 30,
            'connection_retries': 2
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.unlink(temp_file)


@pytest.fixture
def sample_device_info():
    """Sample device info for testing."""
    return {
        'hostname': 'test-switch-01',
        'ip_address': '192.168.1.10',
        'vendor': 'cisco',
        'device_type': 'cisco_ios',
        'model': 'Catalyst 3850'
    }


@pytest.fixture
def sample_vlan_info():
    """Sample VLAN info for testing."""
    return VLANInfo(
        vlan_id=100,
        name='test-vlan',
        status='active',
        ports=[],
        is_unused=True,
        removal_command='no vlan 100',
        risk_level='low'
    )


@pytest.fixture
def sample_device():
    """Sample device object for testing."""
    return DeviceInfo(
        hostname='test-switch-01',
        ip_address='192.168.1.10',
        vendor='cisco',
        device_type='cisco_ios'
    )


@pytest.fixture
def sample_processing_result(sample_device, sample_vlan_info):
    """Sample processing result for testing."""
    return ProcessingResult(
        device=sample_device,
        total_vlans=10,
        unused_vlans=[sample_vlan_info],
        removal_commands=['no vlan 100'],
        rollback_commands=['vlan 100', ' name test-vlan'],
        processing_time=5.0,
        status='success'
    )


@pytest.fixture
def mock_netmiko_connection():
    """Mock netmiko connection for testing."""
    mock_conn = MagicMock()
    mock_conn.send_command.return_value = "Sample output"
    mock_conn.send_config_set.return_value = "Config applied"
    mock_conn.enable.return_value = None
    mock_conn.disconnect.return_value = None
    return mock_conn


@pytest.fixture
def config_manager(temp_config_file):
    """ConfigManager instance for testing."""
    return ConfigManager(temp_config_file)


@pytest.fixture
def cisco_vlan_output():
    """Sample Cisco VLAN output for testing."""
    return """VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
1    default                          active    
10   management                       active    Gi1/0/1, Gi1/0/2
20   voice                           active    
100  unused-vlan                     active    
200  test-vlan                       active    
1002 fddi-default                    act/unsup 
1003 token-ring-default              act/unsup 
1004 fddinet-default                 act/unsup 
1005 trnet-default                   act/unsup"""


@pytest.fixture
def arista_vlan_output():
    """Sample Arista VLAN output for testing."""
    return """VLAN  Name                Status    Ports
----- ------------------- --------- -------------------------------
1     default             active    
10    management          active    Et1, Et2
20    voice              active    
100   unused-vlan        active    
200   test-vlan          active    """


@pytest.fixture
def juniper_vlan_output():
    """Sample Juniper VLAN output for testing."""
    return """Routing instance        Type           State      Description
default-switch          virtual-switch Up

VLAN    Name               Tag     Interfaces
default                   1       
management               10       ge-0/0/1.0, ge-0/0/2.0
voice                    20       
unused-vlan             100       
test-vlan               200       """


@pytest.fixture
def mock_file_system():
    """Mock file system operations."""
    with patch('builtins.open'), \
         patch('os.path.exists'), \
         patch('pathlib.Path.exists'):
        yield
