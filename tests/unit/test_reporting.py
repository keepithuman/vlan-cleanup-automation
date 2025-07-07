"""
Unit tests for reporting module.
"""
import pytest
import json
import tempfile
import os
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime

from src.reporting import ReportGenerator
from src.models import ProcessingResult, BusinessMetrics, DeviceInfo, VLANInfo


class TestReportGenerator:
    """Test cases for ReportGenerator class."""
    
    def test_init(self, config_manager):
        """Test ReportGenerator initialization."""
        generator = ReportGenerator(config_manager)
        
        assert generator.config_manager == config_manager
        assert hasattr(generator, 'output_config')
        assert isinstance(generator.output_config, dict)
    
    def test_generate_comprehensive_report_no_results(self, config_manager):
        """Test report generation with no results."""
        generator = ReportGenerator(config_manager)
        
        report = generator.generate_comprehensive_report([], BusinessMetrics(0, 0, 0, 0, 0, []), [], True)
        
        assert report == {}
    
    def test_generate_comprehensive_report_with_results(self, config_manager, sample_processing_result):
        """Test comprehensive report generation with results."""
        generator = ReportGenerator(config_manager)
        
        business_metrics = BusinessMetrics(
            time_saved_minutes=60.0,
            time_saved_hours=1.0,
            estimated_cost_savings_usd=120.0,
            devices_processed=1,
            vlans_cleaned=1,
            operational_benefits=['Test benefit']
        )
        
        recommendations = ['Test recommendation']
        
        report = generator.generate_comprehensive_report(
            [sample_processing_result], 
            business_metrics, 
            recommendations, 
            dry_run=True
        )
        
        # Check report structure
        assert 'report_metadata' in report
        assert 'executive_summary' in report
        assert 'risk_assessment' in report
        assert 'business_impact' in report
        assert 'device_analysis' in report
        assert 'operational_recommendations' in report
        assert 'detailed_findings' in report
        assert 'next_steps' in report
        assert 'detailed_results' in report
        
        # Check executive summary
        summary = report['executive_summary']
        assert summary['total_devices_analyzed'] == 1
        assert summary['successful_analyses'] == 1
        assert summary['failed_analyses'] == 0
        assert summary['total_vlans_discovered'] == 10
        assert summary['unused_vlans_identified'] == 1
        
        # Check business impact
        assert report['business_impact'] == business_metrics.to_dict()
        
        # Check recommendations
        assert report['operational_recommendations'] == recommendations
    
    def test_get_vendor_breakdown(self, config_manager, sample_device, sample_vlan_info):
        """Test vendor breakdown generation."""
        generator = ReportGenerator(config_manager)
        
        # Create results with different vendors
        cisco_result = ProcessingResult(
            device=sample_device,
            total_vlans=10,
            unused_vlans=[sample_vlan_info],
            removal_commands=[],
            rollback_commands=[],
            processing_time=5.0,
            status='success'
        )
        
        arista_device = DeviceInfo(
            hostname='arista-switch',
            ip_address='192.168.1.20',
            vendor='arista',
            device_type='arista_eos'
        )
        
        arista_result = ProcessingResult(
            device=arista_device,
            total_vlans=15,
            unused_vlans=[sample_vlan_info, sample_vlan_info],
            removal_commands=[],
            rollback_commands=[],
            processing_time=3.0,
            status='success'
        )
        
        results = [cisco_result, arista_result]
        vendor_breakdown = generator._get_vendor_breakdown(results)
        
        # Check Cisco stats
        assert 'cisco' in vendor_breakdown
        cisco_stats = vendor_breakdown['cisco']
        assert cisco_stats['device_count'] == 1
        assert cisco_stats['total_vlans'] == 10
        assert cisco_stats['unused_vlans'] == 1
        assert cisco_stats['success_rate'] == 100.0
        
        # Check Arista stats
        assert 'arista' in vendor_breakdown
        arista_stats = vendor_breakdown['arista']
        assert arista_stats['device_count'] == 1
        assert arista_stats['total_vlans'] == 15
        assert arista_stats['unused_vlans'] == 2
        assert arista_stats['success_rate'] == 100.0
    
    def test_generate_next_steps_with_issues(self, config_manager, sample_processing_result):
        """Test next steps generation with various issues."""
        generator = ReportGenerator(config_manager)
        
        # Create risk analysis with high-risk VLANs
        risk_analysis = {
            'low': 5,
            'medium': 3,
            'high': 2,
            'critical': 1
        }
        
        # Add failed result
        failed_result = ProcessingResult(
            device=DeviceInfo(
                hostname='failed-switch',
                ip_address='192.168.1.50',
                vendor='cisco',
                device_type='cisco_ios'
            ),
            total_vlans=0,
            unused_vlans=[],
            removal_commands=[],
            rollback_commands=[],
            processing_time=1.0,
            status='failed',
            error_message='Connection error'
        )
        
        results = [sample_processing_result, failed_result]
        next_steps = generator._generate_next_steps(results, risk_analysis)
        
        # Should include steps for high-risk VLANs and failed devices
        high_risk_step = next((s for s in next_steps if 'high/critical risk' in s), None)
        assert high_risk_step is not None
        assert '3 high/critical risk VLANs' in high_risk_step
        
        failed_step = next((s for s in next_steps if 'connectivity issues' in s), None)
        assert failed_step is not None
        assert '1 failed devices' in failed_step
        
        safe_step = next((s for s in next_steps if 'can be safely removed' in s), None)
        assert safe_step is not None
        assert '8 VLANs' in safe_step  # low + medium


class TestReportGeneratorFileSaving:
    """Test cases for file saving functionality."""
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_report_success(self, mock_json_dump, mock_file, config_manager):
        """Test successful report saving."""
        generator = ReportGenerator(config_manager)
        
        test_report = {'test': 'report'}
        filename = 'test_report.json'
        
        result = generator.save_report(test_report, filename)
        
        assert result == filename
        mock_file.assert_called_once_with(filename, 'w')
        mock_json_dump.assert_called_once_with(test_report, mock_file(), indent=2, default=str)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    @patch('datetime.datetime')
    def test_save_report_default_filename(self, mock_datetime, mock_json_dump, mock_file, config_manager):
        """Test report saving with default filename."""
        generator = ReportGenerator(config_manager)
        
        # Mock datetime for timestamp
        mock_datetime.now.return_value.strftime.return_value = '20231201_120000'
        
        test_report = {'test': 'report'}
        
        result = generator.save_report(test_report)
        
        assert 'vlan_cleanup_report_20231201_120000.json' in result
    
    @patch('builtins.open', side_effect=IOError("Permission denied"))
    def test_save_report_failure(self, mock_file, config_manager):
        """Test report saving failure."""
        generator = ReportGenerator(config_manager)
        
        test_report = {'test': 'report'}
        
        with pytest.raises(IOError):
            generator.save_report(test_report, 'test.json')
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('csv.writer')
    def test_generate_summary_csv(self, mock_csv_writer, mock_file, config_manager, sample_processing_result):
        """Test CSV summary generation."""
        generator = ReportGenerator(config_manager)
        
        # Mock CSV writer
        mock_writer = MagicMock()
        mock_csv_writer.return_value = mock_writer
        
        results = [sample_processing_result]
        filename = generator.generate_summary_csv(results, 'test.csv')
        
        assert filename == 'test.csv'
        mock_file.assert_called_once_with('test.csv', 'w', newline='')
        
        # Check that header and data rows were written
        assert mock_writer.writerow.call_count >= 2  # Header + at least one data row
        
        # Check header row
        header_call = mock_writer.writerow.call_args_list[0]
        header_row = header_call[0][0]
        assert 'Hostname' in header_row
        assert 'Total_VLANs' in header_row
        assert 'Unused_VLANs' in header_row
    
    @patch('builtins.open', side_effect=IOError("Permission denied"))
    def test_generate_summary_csv_failure(self, mock_file, config_manager, sample_processing_result):
        """Test CSV generation failure."""
        generator = ReportGenerator(config_manager)
        
        results = [sample_processing_result]
        
        with pytest.raises(IOError):
            generator.generate_summary_csv(results, 'test.csv')


class TestReportGeneratorHelperMethods:
    """Test cases for helper methods."""
    
    def test_get_top_cleanup_candidates_limit(self, config_manager, sample_device, sample_vlan_info):
        """Test top cleanup candidates with limit."""
        generator = ReportGenerator(config_manager)
        
        # Create multiple results
        results = []
        for i in range(10):
            device = DeviceInfo(
                hostname=f'switch-{i:02d}',
                ip_address=f'192.168.1.{i+10}',
                vendor='cisco',
                device_type='cisco_ios'
            )
            
            result = ProcessingResult(
                device=device,
                total_vlans=20,
                unused_vlans=[sample_vlan_info] * (i + 1),  # Different VLAN counts
                removal_commands=[],
                rollback_commands=[],
                processing_time=5.0,
                status='success'
            )
            results.append(result)
        
        # Get top 3 candidates
        candidates = generator._get_top_cleanup_candidates(results, limit=3)
        
        assert len(candidates) == 3
        # Should be sorted by unused VLAN count (highest first)
        assert candidates[0]['unused_vlans_count'] == 10  # switch-09
        assert candidates[1]['unused_vlans_count'] == 9   # switch-08
        assert candidates[2]['unused_vlans_count'] == 8   # switch-07
    
    def test_get_top_cleanup_candidates_empty_results(self, config_manager):
        """Test top cleanup candidates with empty results."""
        generator = ReportGenerator(config_manager)
        
        candidates = generator._get_top_cleanup_candidates([])
        
        assert candidates == []
    
    def test_extract_critical_warnings_no_warnings(self, config_manager, sample_processing_result):
        """Test warnings extraction with no warnings."""
        generator = ReportGenerator(config_manager)
        
        # Ensure no warnings
        sample_processing_result.warnings = []
        
        warnings = generator._extract_critical_warnings([sample_processing_result])
        
        assert warnings == []
    
    def test_identify_config_issues_no_issues(self, config_manager, sample_processing_result):
        """Test config issues identification with no issues."""
        generator = ReportGenerator(config_manager)
        
        # Successful result with normal VLAN count
        results = [sample_processing_result]
        issues = generator._identify_config_issues(results)
        
        assert issues == []
    
    def test_identify_config_issues_edge_case_vlan_count(self, config_manager, sample_device):
        """Test config issues with edge case VLAN count."""
        generator = ReportGenerator(config_manager)
        
        # Result with exactly 100 VLANs (edge case)
        edge_case_result = ProcessingResult(
            device=sample_device,
            total_vlans=100,  # Exactly at threshold
            unused_vlans=[],
            removal_commands=[],
            rollback_commands=[],
            processing_time=5.0,
            status='success'
        )
        
        results = [edge_case_result]
        issues = generator._identify_config_issues(results)
        
        # Should not flag 100 VLANs as an issue (threshold is > 100)
        assert len(issues) == 0


class TestReportGeneratorIntegration:
    """Integration tests for report generator."""
    
    def test_full_report_generation_workflow(self, config_manager, sample_device, sample_vlan_info):
        """Test complete report generation workflow."""
        generator = ReportGenerator(config_manager)
        
        # Create comprehensive test data
        high_risk_vlan = VLANInfo(
            vlan_id=5,
            name='management',
            status='active',
            ports=[],
            is_unused=True,
            risk_level='critical'
        )
        
        success_result = ProcessingResult(
            device=sample_device,
            total_vlans=20,
            unused_vlans=[sample_vlan_info, high_risk_vlan],
            removal_commands=['no vlan 100', 'no vlan 5'],
            rollback_commands=['vlan 100', 'vlan 5'],
            processing_time=8.5,
            status='success',
            warnings=['High-risk VLAN detected']
        )
        
        failed_device = DeviceInfo(
            hostname='failed-device',
            ip_address='192.168.1.99',
            vendor='arista',
            device_type='arista_eos'
        )
        
        failed_result = ProcessingResult(
            device=failed_device,
            total_vlans=0,
            unused_vlans=[],
            removal_commands=[],
            rollback_commands=[],
            processing_time=1.0,
            status='failed',
            error_message='Authentication failed'
        )
        
        results = [success_result, failed_result]
        
        business_metrics = BusinessMetrics(
            time_saved_minutes=28.0,
            time_saved_hours=0.47,
            estimated_cost_savings_usd=56.0,
            devices_processed=1,
            vlans_cleaned=2,
            operational_benefits=['Improved security', 'Better performance']
        )
        
        recommendations = [
            'Review high-risk VLANs manually',
            'Investigate failed device connections'
        ]
        
        # Generate comprehensive report
        report = generator.generate_comprehensive_report(
            results, business_metrics, recommendations, dry_run=False
        )
        
        # Verify comprehensive report structure and content
        assert report['report_metadata']['dry_run_mode'] is False
        
        summary = report['executive_summary']
        assert summary['total_devices_analyzed'] == 2
        assert summary['successful_analyses'] == 1
        assert summary['failed_analyses'] == 1
        assert summary['unused_vlans_identified'] == 2
        
        risk_assessment = report['risk_assessment']
        assert risk_assessment['risk_distribution']['low'] == 1
        assert risk_assessment['risk_distribution']['critical'] == 1
        assert risk_assessment['high_risk_vlans_requiring_approval'] == 1
        
        device_analysis = report['device_analysis']
        assert len(device_analysis['device_summaries']) == 2
        assert 'cisco' in device_analysis['vendor_breakdown']
        assert 'arista' in device_analysis['vendor_breakdown']
        
        detailed_findings = report['detailed_findings']
        assert len(detailed_findings['devices_with_most_unused_vlans']) > 0
        assert len(detailed_findings['critical_warnings']) > 0
        assert len(detailed_findings['configuration_issues']) > 0
        
        next_steps = report['next_steps']
        assert len(next_steps) > 0
        assert any('high/critical risk' in step for step in next_steps)
        assert any('failed devices' in step for step in next_steps)
        
        # Verify detailed results include all data
        detailed_results = report['detailed_results']
        assert len(detailed_results) == 2
        assert all(isinstance(result, dict) for result in detailed_results)
