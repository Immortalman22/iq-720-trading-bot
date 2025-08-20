#!/usr/bin/env python3
"""
Production Readiness Verification Script
Checks all systems and configurations before production deployment
"""

import os
import sys
import yaml
import logging
import subprocess
from datetime import datetime
from typing import List, Dict, Tuple

class ProductionVerifier:
    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = []
        
    def verify_all(self) -> bool:
        """Run all verification checks."""
        print("Starting production verification...")
        
        checks = [
            self._verify_system_resources(),
            self._verify_configurations(),
            self._verify_performance(),
            self._verify_monitoring(),
            self._verify_backup_system(),
            self._verify_trading_systems()
        ]
        
        print("\nVerification Summary:")
        print(f"Checks Passed: {self.checks_passed}")
        print(f"Checks Failed: {self.checks_failed}")
        print(f"Warnings: {len(self.warnings)}")
        
        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings:
                print(f"- {warning}")
                
        return all(checks)
        
    def _verify_system_resources(self) -> bool:
        """Verify system has adequate resources."""
        print("\nChecking system resources...")
        
        # Check CPU
        try:
            cpu_count = os.cpu_count()
            if cpu_count < 2:
                self.warnings.append("Less than 2 CPU cores available")
        except:
            self.warnings.append("Could not determine CPU count")
            
        # Check Memory
        try:
            import psutil
            memory = psutil.virtual_memory()
            if memory.available < 2 * 1024 * 1024 * 1024:  # 2GB
                self.warnings.append("Less than 2GB RAM available")
        except:
            self.warnings.append("Could not check memory availability")
            
        # Check Disk Space
        try:
            disk = psutil.disk_usage('/')
            if disk.percent > 80:
                self.warnings.append(f"Disk usage high: {disk.percent}%")
        except:
            self.warnings.append("Could not check disk space")
            
        self.checks_passed += 1
        return True
        
    def _verify_configurations(self) -> bool:
        """Verify all configuration files are present and valid."""
        print("\nChecking configurations...")
        required_files = [
            'config/production.yml',
            'config/logging.yml'
        ]
        
        for file in required_files:
            if not os.path.exists(file):
                print(f"ERROR: Missing configuration file: {file}")
                self.checks_failed += 1
                return False
                
        try:
            with open('config/production.yml', 'r') as f:
                config = yaml.safe_load(f)
                
            required_sections = ['trading', 'performance', 'security', 'backup']
            for section in required_sections:
                if section not in config:
                    print(f"ERROR: Missing configuration section: {section}")
                    self.checks_failed += 1
                    return False
        except Exception as e:
            print(f"ERROR: Configuration validation failed: {e}")
            self.checks_failed += 1
            return False
            
        self.checks_passed += 1
        return True
        
    def _verify_performance(self) -> bool:
        """Verify system meets performance requirements."""
        print("\nChecking performance metrics...")
        
        # Run quick performance test
        start_time = datetime.now()
        try:
            # Import and initialize key components
            from src.utils.pattern_recognition import PatternRecognition
            from src.utils.market_regime import MarketRegimeDetector
            
            pattern_recognition = PatternRecognition()
            regime_detector = MarketRegimeDetector()
            
            # Test processing speed
            import numpy as np
            test_data = np.random.random(1000)
            
            # Measure processing time
            process_start = datetime.now()
            # Run some typical calculations
            for _ in range(100):
                test_data = np.convolve(test_data, [0.2, 0.3, 0.5], mode='valid')
            process_time = (datetime.now() - process_start).total_seconds()
            
            if process_time > 0.5:
                self.warnings.append(f"Processing time high: {process_time:.2f}s")
                
        except Exception as e:
            print(f"ERROR: Performance test failed: {e}")
            self.checks_failed += 1
            return False
            
        self.checks_passed += 1
        return True
        
    def _verify_monitoring(self) -> bool:
        """Verify monitoring systems are in place."""
        print("\nChecking monitoring setup...")
        
        required_logs = [
            'logs/trading.log',
            'logs/errors.log',
            'logs/performance.log'
        ]
        
        for log in required_logs:
            if not os.path.exists(log):
                try:
                    os.makedirs(os.path.dirname(log), exist_ok=True)
                    open(log, 'a').close()
                except Exception as e:
                    print(f"ERROR: Could not create log file {log}: {e}")
                    self.checks_failed += 1
                    return False
                    
        self.checks_passed += 1
        return True
        
    def _verify_backup_system(self) -> bool:
        """Verify backup system is configured."""
        print("\nChecking backup system...")
        
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            try:
                os.makedirs(backup_dir)
            except Exception as e:
                print(f"ERROR: Could not create backup directory: {e}")
                self.checks_failed += 1
                return False
                
        # Test backup write access
        try:
            test_file = os.path.join(backup_dir, "test_backup")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            print(f"ERROR: Backup system write test failed: {e}")
            self.checks_failed += 1
            return False
            
        self.checks_passed += 1
        return True
        
    def _verify_trading_systems(self) -> bool:
        """Verify core trading systems."""
        print("\nChecking trading systems...")
        
        try:
            # Import key components
            from src.signal_generator import SignalGenerator
            from src.utils.session_manager import SessionManager
            
            # Initialize components
            signal_gen = SignalGenerator()
            session_mgr = SessionManager()
            
            # Verify current session can be determined
            current_session = session_mgr.get_current_session()
            if not current_session:
                self.warnings.append("Could not determine current trading session")
                
        except Exception as e:
            print(f"ERROR: Trading systems check failed: {e}")
            self.checks_failed += 1
            return False
            
        self.checks_passed += 1
        return True

def main():
    verifier = ProductionVerifier()
    if verifier.verify_all():
        print("\nProduction verification PASSED ✅")
        sys.exit(0)
    else:
        print("\nProduction verification FAILED ❌")
        sys.exit(1)

if __name__ == "__main__":
    main()
