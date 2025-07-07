"""
Integration tests for VLAN cleanup automation.

These tests verify the interaction between multiple components
and end-to-end functionality.
"""
import pytest
import tempfile
import os
import yaml
from unittest.mock import patch, MagicMock

from src.processor import VLANCleanupProcessor
from src.config import ConfigManager
from src.device_handler import DeviceHandler
from src.reporting import ReportGenerator
from src.models import VLANInfo, ProcessingResult


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Integration tests for complete VLAN cleanup workflow."""
    
    def test_complete_dry_run_workflow(self, temp_config_file):
        """Test complete dry-run workflow from start to finish."""
        # Initialize processor
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        # Mock device connections and VLAN data
        mock_connection = MagicMock()
        
        # Mock Cisco VLAN output with unused VLANs
        cisco_vlan_output = """VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
1    default                          active    
10   management                       active    Gi1/0/1, Gi1/0/2
100  unused-vlan-1                   active    
200  unused-vlan-2                   active    
300  test-vlan                       active    Gi1/0/3
"""
        
        mock_connection.send_command.return_value = cisco_vlan_output
        
        # Mock device handler methods
        with patch.object(processor.device_handler, 'connect_to_device') as mock_connect, \
             patch.object(processor.device_handler, '_is_vlan_unused_cisco') as mock_unused:
            
            mock_connect.return_value = mock_connection
            # Mark VLANs 100 and 200 as unused
            mock_unused.side_effect = lambda conn, vlan_id, ports: vlan_id in [100, 200]
            
            # Process devices
            results = processor.process_devices()
            
            # Verify results
            assert len(results) == 1
            result = results[0]
            assert result.status == 'success'
            assert result.total_vlans > 0
            assert len(result.unused_vlans) == 2  # VLANs 100 and 200
            
            # Check unused VLANs
            unused_vlan_ids = [vlan.vlan_id for vlan in result.unused_vlans]
            assert 100 in unused_vlan_ids
            assert 200 in unused_vlan_ids
            
            # Check removal commands
            assert len(result.removal_commands) == 2
            assert 'no vlan 100' in result.removal_commands
            assert 'no vlan 200' in result.removal_commands
            
            # Check rollback commands
            assert len(result.rollback_commands) > 0
        
        # Calculate business metrics
        business_metrics = processor.calculate_business_metrics()
        assert business_metrics.devices_processed == 1
        assert business_metrics.vlans_cleaned == 2
        assert business_metrics.time_saved_minutes > 0
        
        # Generate recommendations
        recommendations = processor.generate_recommendations()
        assert len(recommendations) > 0
        
        # Generate comprehensive report
        report_generator = ReportGenerator(processor.config_manager)
        report = report_generator.generate_comprehensive_report(
            results, business_metrics, recommendations, dry_run=True
        )
        
        # Verify report structure
        assert 'executive_summary' in report
        assert 'business_impact' in report
        assert 'detailed_results' in report
        assert report['executive_summary']['unused_vlans_identified'] == 2
    
    def test_multi_vendor_integration(self):
        """Test integration with multiple vendor devices."""
        # Create config with multiple vendors
        config_data = {
            'devices': [
                {
                    'hostname': 'cisco-switch',
                    'ip_address': '192.168.1.10',
                    'vendor': 'cisco',
                    'device_type': 'cisco_ios'
                },
                {
                    'hostname': 'arista-switch',
                    'ip_address': '192.168.1.20',
                    'vendor': 'arista',
                    'device_type': 'arista_eos'
                },
                {
                    'hostname': 'juniper-switch',
                    'ip_address': '192.168.1.30',
                    'vendor': 'juniper',
                    'device_type': 'juniper_junos'
                }
            ],
            'authentication': {
                'username': 'testuser',
                'password': 'testpass'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_config = f.name
        
        try:
            processor = VLANCleanupProcessor(temp_config, dry_run=True)
            
            # Mock different outputs for each vendor
            cisco_output = "VLAN Name Status Ports\n100 unused-vlan active"
            arista_output = "VLAN Name Status Ports\n200 unused-vlan active"
            juniper_output = "VLAN Name Tag Interfaces\nunused-vlan 300"
            
            def mock_send_command(command):
                hostname = mock_send_command.current_hostname
                if 'cisco' in hostname:
                    return cisco_output
                elif 'arista' in hostname:
                    return arista_output
                elif 'juniper' in hostname:
                    return juniper_output
                return ""
            
            mock_connection = MagicMock()
            mock_connection.send_command.side_effect = mock_send_command
            
            with patch.object(processor.device_handler, 'connect_to_device') as mock_connect, \
                 patch.object(processor.device_handler, '_is_vlan_unused_cisco') as mock_cisco_unused, \
                 patch.object(processor.device_handler, '_is_vlan_unused_arista') as mock_arista_unused, \
                 patch.object(processor.device_handler, '_is_vlan_unused_juniper') as mock_juniper_unused:
                
                def mock_connect_side_effect(device_info):
                    mock_send_command.current_hostname = device_info['hostname']
                    return mock_connection
                
                mock_connect.side_effect = mock_connect_side_effect
                mock_cisco_unused.return_value = True
                mock_arista_unused.return_value = True
                mock_juniper_unused.return_value = True
                
                # Process all devices
                results = processor.process_devices()
                
                # Verify multi-vendor processing
                assert len(results) == 3
                assert all(result.status == 'success' for result in results)
                
                # Verify vendor-specific device types were detected
                device_types = [processor.device_handler.get_device_type(device) 
                              for device in config_data['devices']]
                assert 'cisco_ios' in device_types
                assert 'arista_eos' in device_types
                assert 'juniper_junos' in device_types
        
        finally:
            os.unlink(temp_config)
    
    def test_error_handling_integration(self, temp_config_file):
        """Test error handling across integrated components."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        # Test connection failure
        with patch.object(processor.device_handler, 'connect_to_device') as mock_connect:
            mock_connect.return_value = None  # Connection failure
            
            results = processor.process_devices()
            
            assert len(results) == 1
            assert results[0].status == 'failed'
            assert 'Failed to connect' in results[0].error_message
        
        # Test exception during processing
        with patch.object(processor.device_handler, 'connect_to_device') as mock_connect:
            mock_connect.side_effect = Exception("Network timeout")
            
            results = processor.process_devices()
            
            assert len(results) == 1
            assert results[0].status == 'failed'
            assert 'Network timeout' in results[0].error_message


@pytest.mark.integration
class TestComponentInteraction:
    """Test interactions between specific components."""
    
    def test_config_manager_device_handler_integration(self, temp_config_file):
        """Test integration between ConfigManager and DeviceHandler."""
        config_manager = ConfigManager(temp_config_file)
        device_handler = DeviceHandler(config_manager)
        
        # Verify device handler uses config manager settings
        assert device_handler.config_manager == config_manager
        assert device_handler.processing_config == config_manager.get_processing_config()
        assert device_handler.auth_config == config_manager.get_authentication()
        
        # Test device type detection
        test_device = {
            'hostname': 'test',
            'vendor': 'cisco',
            'device_type': '',
            'model': ''
        }
        
        device_type = device_handler.get_device_type(test_device)
        assert device_type.startswith('cisco')
    
    def test_processor_reporting_integration(self, temp_config_file, sample_processing_result):
        """Test integration between Processor and ReportGenerator."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        processor.results = [sample_processing_result]
        
        # Calculate business metrics
        business_metrics = processor.calculate_business_metrics()
        recommendations = processor.generate_recommendations()
        
        # Generate report
        report_generator = ReportGenerator(processor.config_manager)
        report = report_generator.generate_comprehensive_report(
            processor.results, business_metrics, recommendations, dry_run=True
        )
        
        # Verify integration
        assert report['business_impact'] == business_metrics.to_dict()
        assert report['operational_recommendations'] == recommendations
        assert len(report['detailed_results']) == len(processor.results)
    
    def test_device_handler_vlan_parsing_integration(self, config_manager):
        """Test integration of VLAN parsing across vendors."""
        device_handler = DeviceHandler(config_manager)
        mock_connection = MagicMock()
        
        # Test Cisco VLAN parsing
        cisco_output = """VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
1    default                          active    
100  test-vlan                       active    
"""
        mock_connection.send_command.return_value = cisco_output
        
        with patch.object(device_handler, '_is_vlan_unused_cisco') as mock_unused:
            mock_unused.return_value = True
            
            vlans = device_handler.get_vlan_info(mock_connection, 'cisco_ios')
            
            # Should have parsed VLANs
            assert len(vlans) > 0
            
            # Find test VLAN
            test_vlan = next((v for v in vlans if v.vlan_id == 100), None)
            assert test_vlan is not None
            assert test_vlan.name == 'test-vlan'


@pytest.mark.integration
@pytest.mark.slow
class TestProductionWorkflow:
    """Integration tests simulating production scenarios."""
    
    def test_large_scale_processing(self):
        """Test processing of many devices (simulated)."""
        # Create config with many devices
        devices = []
        for i in range(50):
            devices.append({
                'hostname': f'switch-{i:03d}',
                'ip_address': f'192.168.{i//255}.{i%255}',
                'vendor': 'cisco' if i % 2 == 0 else 'arista',
                'device_type': 'cisco_ios' if i % 2 == 0 else 'arista_eos'
            })
        
        config_data = {
            'devices': devices,
            'authentication': {
                'username': 'testuser',
                'password': 'testpass'
            },
            'processing': {
                'max_concurrent_devices': 10,
                'device_timeout': 30
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_config = f.name
        
        try:
            processor = VLANCleanupProcessor(temp_config, dry_run=True)
            
            # Mock fast processing for all devices
            mock_connection = MagicMock()
            mock_connection.send_command.return_value = "VLAN Name Status\n100 unused-vlan active"
            
            with patch.object(processor.device_handler, 'connect_to_device') as mock_connect, \
                 patch.object(processor.device_handler, '_is_vlan_unused_cisco') as mock_cisco_unused, \
                 patch.object(processor.device_handler, '_is_vlan_unused_arista') as mock_arista_unused:
                
                mock_connect.return_value = mock_connection
                mock_cisco_unused.return_value = True
                mock_arista_unused.return_value = True
                
                # Process all devices
                results = processor.process_devices()
                
                # Verify large-scale processing
                assert len(results) == 50
                assert all(result.status == 'success' for result in results)
                
                # Verify business metrics scale appropriately
                business_metrics = processor.calculate_business_metrics()
                assert business_metrics.devices_processed == 50
                assert business_metrics.time_saved_minutes > 1000  # Significant savings
        
        finally:
            os.unlink(temp_config)
    
    def test_mixed_success_failure_scenario(self, temp_config_file):
        """Test scenario with mixed success and failure results."""
        # Create config with multiple devices
        config_data = {
            'devices': [
                {
                    'hostname': 'working-switch-01',
                    'ip_address': '192.168.1.10',
                    'vendor': 'cisco',
                    'device_type': 'cisco_ios'
                },
                {
                    'hostname': 'failing-switch-01',
                    'ip_address': '192.168.1.11',
                    'vendor': 'cisco',
                    'device_type': 'cisco_ios'
                },
                {
                    'hostname': 'working-switch-02',
                    'ip_address': '192.168.1.12',
                    'vendor': 'arista',
                    'device_type': 'arista_eos'
                }
            ],
            'authentication': {
                'username': 'testuser',
                'password': 'testpass'
            }
        }
        
        # Update temp config file
        with open(temp_config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        mock_connection = MagicMock()
        mock_connection.send_command.return_value = "VLAN Name Status\n100 unused-vlan active"
        
        def mock_connect_side_effect(device_info):
            # Simulate failure for specific device
            if 'failing' in device_info['hostname']:
                return None  # Connection failure
            return mock_connection
        
        with patch.object(processor.device_handler, 'connect_to_device') as mock_connect, \
             patch.object(processor.device_handler, '_is_vlan_unused_cisco') as mock_cisco_unused, \
             patch.object(processor.device_handler, '_is_vlan_unused_arista') as mock_arista_unused:
            
            mock_connect.side_effect = mock_connect_side_effect
            mock_cisco_unused.return_value = True
            mock_arista_unused.return_value = True
            
            # Process devices
            results = processor.process_devices()
            
            # Verify mixed results
            assert len(results) == 3
            
            successful_results = [r for r in results if r.status == 'success']
            failed_results = [r for r in results if r.status == 'failed']
            
            assert len(successful_results) == 2
            assert len(failed_results) == 1
            
            # Verify failed device
            failed_result = failed_results[0]
            assert 'failing-switch-01' in failed_result.device.hostname
            assert 'Failed to connect' in failed_result.error_message
            
            # Generate report with mixed results
            business_metrics = processor.calculate_business_metrics()
            recommendations = processor.generate_recommendations()
            
            # Should recommend investigating failed devices
            failed_rec = next((r for r in recommendations if 'connection issues' in r), None)
            assert failed_rec is not None
    
    def test_high_risk_vlan_workflow(self, temp_config_file):
        """Test workflow with high-risk VLANs requiring special handling."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        
        # Mock VLAN output with high-risk VLANs
        high_risk_vlan_output = """VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
1    default                          active    
5    management                       active    
100  voice-users                     active    
200  normal-vlan                     active    
"""
        
        mock_connection = MagicMock()
        mock_connection.send_command.return_value = high_risk_vlan_output
        
        with patch.object(processor.device_handler, 'connect_to_device') as mock_connect, \
             patch.object(processor.device_handler, '_is_vlan_unused_cisco') as mock_unused:
            
            mock_connect.return_value = mock_connection
            # Mark management and voice VLANs as unused (high-risk scenario)
            mock_unused.side_effect = lambda conn, vlan_id, ports: vlan_id in [5, 100, 200]
            
            # Process devices
            results = processor.process_devices()
            
            # Verify results
            assert len(results) == 1
            result = results[0]
            assert result.status == 'success'
            
            # Check that high-risk VLANs were identified
            high_risk_vlans = [v for v in result.unused_vlans if v.risk_level in ['high', 'critical']]
            assert len(high_risk_vlans) >= 2  # management and voice VLANs
            
            # Verify warnings were generated
            assert len(result.warnings) >= 2
            
            # Generate recommendations
            recommendations = processor.generate_recommendations()
            
            # Should recommend manual review for high-risk VLANs
            manual_review_rec = next((r for r in recommendations if 'Manual review required' in r), None)
            assert manual_review_rec is not None


@pytest.mark.integration
class TestFileOperationsIntegration:
    """Test file operations and persistence integration."""
    
    def test_report_generation_and_saving(self, temp_config_file, sample_processing_result):
        """Test complete report generation and file saving workflow."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        processor.results = [sample_processing_result]
        
        # Calculate business metrics and recommendations
        business_metrics = processor.calculate_business_metrics()
        recommendations = processor.generate_recommendations()
        
        # Generate and save report
        report_generator = ReportGenerator(processor.config_manager)
        report = report_generator.generate_comprehensive_report(
            processor.results, business_metrics, recommendations, dry_run=True
        )
        
        # Save report to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            report_file = f.name
        
        try:
            saved_file = report_generator.save_report(report, report_file)
            assert saved_file == report_file
            assert os.path.exists(report_file)
            
            # Verify file contents
            with open(report_file, 'r') as f:
                import json
                saved_report = json.load(f)
            
            assert saved_report['executive_summary']['total_devices_analyzed'] == 1
            assert 'business_impact' in saved_report
            assert 'detailed_results' in saved_report
        
        finally:
            if os.path.exists(report_file):
                os.unlink(report_file)
    
    def test_csv_report_generation(self, temp_config_file, sample_processing_result):
        """Test CSV report generation integration."""
        processor = VLANCleanupProcessor(temp_config_file, dry_run=True)
        processor.results = [sample_processing_result]
        
        report_generator = ReportGenerator(processor.config_manager)
        
        # Generate CSV report
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_file = f.name
        
        try:
            saved_csv = report_generator.generate_summary_csv(processor.results, csv_file)
            assert saved_csv == csv_file
            assert os.path.exists(csv_file)
            
            # Verify CSV contents
            with open(csv_file, 'r') as f:
                csv_content = f.read()
            
            assert 'Hostname' in csv_content
            assert 'test-switch-01' in csv_content
            assert 'Total_VLANs' in csv_content
        
        finally:
            if os.path.exists(csv_file):
                os.unlink(csv_file)
    
    def test_configuration_persistence(self):
        """Test configuration loading and saving integration."""
        # Create test configuration
        test_config = {
            'devices': [
                {
                    'hostname': 'persistence-test',
                    'ip_address': '192.168.1.100',
                    'vendor': 'cisco',
                    'device_type': 'cisco_ios'
                }
            ],
            'authentication': {
                'username': 'testuser',
                'password': 'testpass'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            temp_config = f.name
        
        try:
            # Load configuration
            config_manager = ConfigManager(temp_config)
            
            # Verify loaded configuration
            assert len(config_manager.get_devices()) == 1
            assert config_manager.get_devices()[0]['hostname'] == 'persistence-test'
            assert config_manager.validate_config() is True
            
            # Modify and save configuration
            modified_config = config_manager.get_config()
            modified_config['devices'][0]['hostname'] = 'modified-hostname'
            
            success = config_manager.save_config(modified_config)
            assert success is True
            
            # Reload and verify changes
            new_config_manager = ConfigManager(temp_config)
            assert new_config_manager.get_devices()[0]['hostname'] == 'modified-hostname'
        
        finally:
            if os.path.exists(temp_config):
                os.unlink(temp_config)
