"""
Unit tests for data models module.
"""
import pytest
from datetime import datetime
from dataclasses import asdict

from src.models import VLANInfo, DeviceInfo, ProcessingResult, BusinessMetrics


class TestVLANInfo:
    """Test cases for VLANInfo model."""
    
    def test_vlan_info_creation(self):
        """Test VLANInfo object creation."""
        vlan = VLANInfo(
            vlan_id=100,
            name='test-vlan',
            status='active',
            ports=['Gi1/0/1', 'Gi1/0/2']
        )
        
        assert vlan.vlan_id == 100
        assert vlan.name == 'test-vlan'
        assert vlan.status == 'active'
        assert vlan.ports == ['Gi1/0/1', 'Gi1/0/2']
        assert vlan.is_unused is False  # default value
        assert vlan.removal_command == ""  # default value
        assert vlan.risk_level == "low"  # default value
    
    def test_vlan_info_with_optional_fields(self):
        """Test VLANInfo with all optional fields."""
        last_seen = datetime.now()
        vlan = VLANInfo(
            vlan_id=200,
            name='unused-vlan',
            status='active',
            ports=[],
            is_unused=True,
            removal_command='no vlan 200',
            risk_level='medium',
            last_seen=last_seen
        )
        
        assert vlan.is_unused is True
        assert vlan.removal_command == 'no vlan 200'
        assert vlan.risk_level == 'medium'
        assert vlan.last_seen == last_seen
    
    def test_vlan_info_to_dict(self):
        """Test VLANInfo to_dict method."""
        vlan = VLANInfo(
            vlan_id=100,
            name='test-vlan',
            status='active',
            ports=['Gi1/0/1']
        )
        
        result = vlan.to_dict()
        expected = {
            'vlan_id': 100,
            'name': 'test-vlan',
            'status': 'active',
            'ports': ['Gi1/0/1'],
            'is_unused': False,
            'removal_command': '',
            'risk_level': 'low',
            'last_seen': None
        }
        
        assert result == expected


class TestDeviceInfo:
    """Test cases for DeviceInfo model."""
    
    def test_device_info_creation(self):
        """Test DeviceInfo object creation."""
        device = DeviceInfo(
            hostname='test-switch',
            ip_address='192.168.1.10',
            device_type='cisco_ios',
            vendor='cisco'
        )
        
        assert device.hostname == 'test-switch'
        assert device.ip_address == '192.168.1.10'
        assert device.device_type == 'cisco_ios'
        assert device.vendor == 'cisco'
        assert device.model == ""  # default value
        assert device.version == ""  # default value
    
    def test_device_info_with_optional_fields(self):
        """Test DeviceInfo with all optional fields."""
        device = DeviceInfo(
            hostname='core-switch',
            ip_address='10.0.0.1',
            device_type='cisco_nxos',
            vendor='cisco',
            model='Nexus 9000',
            version='9.3.8',
            management_ip='192.168.100.1',
            ssh_key_file='/path/to/key'
        )
        
        assert device.model == 'Nexus 9000'
        assert device.version == '9.3.8'
        assert device.management_ip == '192.168.100.1'
        assert device.ssh_key_file == '/path/to/key'
    
    def test_device_info_to_dict(self):
        """Test DeviceInfo to_dict method."""
        device = DeviceInfo(
            hostname='test-switch',
            ip_address='192.168.1.10',
            device_type='cisco_ios',
            vendor='cisco'
        )
        
        result = device.to_dict()
        expected = {
            'hostname': 'test-switch',
            'ip_address': '192.168.1.10',
            'device_type': 'cisco_ios',
            'vendor': 'cisco',
            'model': '',
            'version': '',
            'management_ip': '',
            'ssh_key_file': ''
        }
        
        assert result == expected


class TestProcessingResult:
    """Test cases for ProcessingResult model."""
    
    def test_processing_result_creation(self, sample_device, sample_vlan_info):
        """Test ProcessingResult object creation."""
        result = ProcessingResult(
            device=sample_device,
            total_vlans=10,
            unused_vlans=[sample_vlan_info],
            removal_commands=['no vlan 100'],
            rollback_commands=['vlan 100'],
            processing_time=5.5,
            status='success'
        )
        
        assert result.device == sample_device
        assert result.total_vlans == 10
        assert len(result.unused_vlans) == 1
        assert result.unused_vlans[0] == sample_vlan_info
        assert result.removal_commands == ['no vlan 100']
        assert result.rollback_commands == ['vlan 100']
        assert result.processing_time == 5.5
        assert result.status == 'success'
        assert result.error_message == ""  # default value
        assert result.warnings == []  # default value from __post_init__
    
    def test_processing_result_with_error(self, sample_device):
        """Test ProcessingResult with error conditions."""
        result = ProcessingResult(
            device=sample_device,
            total_vlans=0,
            unused_vlans=[],
            removal_commands=[],
            rollback_commands=[],
            processing_time=2.0,
            status='failed',
            error_message='Connection timeout'
        )
        
        assert result.status == 'failed'
        assert result.error_message == 'Connection timeout'
        assert result.total_vlans == 0
        assert len(result.unused_vlans) == 0
    
    def test_processing_result_warnings_initialization(self, sample_device):
        """Test that warnings list is properly initialized."""
        result = ProcessingResult(
            device=sample_device,
            total_vlans=5,
            unused_vlans=[],
            removal_commands=[],
            rollback_commands=[],
            processing_time=1.0,
            status='success'
        )
        
        # Warnings should be initialized as empty list
        assert result.warnings == []
        assert isinstance(result.warnings, list)
        
        # Should be able to append to warnings
        result.warnings.append('Test warning')
        assert len(result.warnings) == 1
        assert result.warnings[0] == 'Test warning'
    
    def test_processing_result_to_dict(self, sample_device, sample_vlan_info):
        """Test ProcessingResult to_dict method."""
        result = ProcessingResult(
            device=sample_device,
            total_vlans=1,
            unused_vlans=[sample_vlan_info],
            removal_commands=['no vlan 100'],
            rollback_commands=['vlan 100'],
            processing_time=3.0,
            status='success'
        )
        
        result_dict = result.to_dict()
        
        # Check that device is converted to dict
        assert isinstance(result_dict['device'], dict)
        assert result_dict['device']['hostname'] == 'test-switch-01'
        
        # Check that unused_vlans are converted to dicts
        assert isinstance(result_dict['unused_vlans'], list)
        assert len(result_dict['unused_vlans']) == 1
        assert isinstance(result_dict['unused_vlans'][0], dict)
        assert result_dict['unused_vlans'][0]['vlan_id'] == 100


class TestBusinessMetrics:
    """Test cases for BusinessMetrics model."""
    
    def test_business_metrics_creation(self):
        """Test BusinessMetrics object creation."""
        metrics = BusinessMetrics(
            time_saved_minutes=120.0,
            time_saved_hours=2.0,
            estimated_cost_savings_usd=240.0,
            devices_processed=10,
            vlans_cleaned=25,
            operational_benefits=['Improved security', 'Better performance']
        )
        
        assert metrics.time_saved_minutes == 120.0
        assert metrics.time_saved_hours == 2.0
        assert metrics.estimated_cost_savings_usd == 240.0
        assert metrics.devices_processed == 10
        assert metrics.vlans_cleaned == 25
        assert len(metrics.operational_benefits) == 2
        assert 'Improved security' in metrics.operational_benefits
    
    def test_business_metrics_to_dict(self):
        """Test BusinessMetrics to_dict method."""
        metrics = BusinessMetrics(
            time_saved_minutes=60.0,
            time_saved_hours=1.0,
            estimated_cost_savings_usd=120.0,
            devices_processed=5,
            vlans_cleaned=15,
            operational_benefits=['Test benefit']
        )
        
        result = metrics.to_dict()
        expected = {
            'time_saved_minutes': 60.0,
            'time_saved_hours': 1.0,
            'estimated_cost_savings_usd': 120.0,
            'devices_processed': 5,
            'vlans_cleaned': 15,
            'operational_benefits': ['Test benefit']
        }
        
        assert result == expected
