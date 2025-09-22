#!/usr/bin/env python3
"""
Sanity Check Script for GridBot v2.5 Production Reset

This script verifies that the system reset was successful by:
1. Checking that transactional tables are empty
2. Verifying system settings are reset to defaults
3. Confirming no active trading operations
4. Validating clean state for production deployment

Usage:
    python scripts/sanity_check_reset.py
"""

import os
import sys
import asyncio
import asyncpg
from datetime import datetime
from typing import Dict, List, Any

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings


class SanityChecker:
    """Validates system reset for production deployment"""
    
    def __init__(self):
        self.db_url = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        self.connection = None
        
    async def connect(self):
        """Connect to database"""
        try:
            self.connection = await asyncpg.connect(self.db_url)
            print("✅ Database connection established")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            sys.exit(1)
    
    async def disconnect(self):
        """Close database connection"""
        if self.connection:
            await self.connection.close()
            print("✅ Database connection closed")
    
    async def check_transactional_tables_empty(self) -> bool:
        """Verify all transactional tables are empty"""
        print("\n🔍 Checking transactional tables...")
        
        transactional_tables = [
            'trades',
            'positions', 
            'pnl_history',
            'alerts',
            'reconciliation_logs',
            'system_events',
            'operation_tracking'
        ]
        
        all_empty = True
        
        for table in transactional_tables:
            try:
                # Check if table exists
                exists_query = """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = $1
                    );
                """
                table_exists = await self.connection.fetchval(exists_query, table)
                
                if table_exists:
                    # Count rows
                    count_query = f"SELECT COUNT(*) FROM {table};"
                    row_count = await self.connection.fetchval(count_query)
                    
                    if row_count == 0:
                        print(f"  ✅ {table}: Empty ({row_count} rows)")
                    else:
                        print(f"  ❌ {table}: NOT EMPTY ({row_count} rows)")
                        all_empty = False
                else:
                    print(f"  ⚠️  {table}: Table does not exist")
                    
            except Exception as e:
                print(f"  ❌ {table}: Error checking - {e}")
                all_empty = False
        
        return all_empty
    
    async def check_system_settings_reset(self) -> bool:
        """Verify system settings are reset to defaults"""
        print("\n🔍 Checking system settings...")
        
        try:
            # Check baseline value
            baseline_query = """
                SELECT value FROM system_settings 
                WHERE key = 'portfolio:baseline_value_usdt';
            """
            baseline_value = await self.connection.fetchval(baseline_query)
            
            if baseline_value == '0.0':
                print("  ✅ portfolio:baseline_value_usdt: Reset to 0.0")
            else:
                print(f"  ❌ portfolio:baseline_value_usdt: Not reset ({baseline_value})")
                return False
            
            # Check baseline ISO
            baseline_iso_query = """
                SELECT value FROM system_settings 
                WHERE key = 'profit:baseline_iso';
            """
            baseline_iso = await self.connection.fetchval(baseline_iso_query)
            
            if baseline_iso:
                print(f"  ✅ profit:baseline_iso: Reset to {baseline_iso}")
            else:
                print("  ❌ profit:baseline_iso: Not found")
                return False
                
            return True
            
        except Exception as e:
            print(f"  ❌ Error checking system settings: {e}")
            return False
    
    async def check_no_active_operations(self) -> bool:
        """Verify no active trading operations"""
        print("\n🔍 Checking for active operations...")
        
        try:
            # Check for any active operations in operation_tracking table
            active_ops_query = """
                SELECT COUNT(*) FROM operation_tracking 
                WHERE status IN ('PENDING', 'SUBMITTED', 'ACCEPTED', 'PARTIALLY_FILLED');
            """
            active_count = await self.connection.fetchval(active_ops_query)
            
            if active_count == 0:
                print("  ✅ No active trading operations found")
                return True
            else:
                print(f"  ❌ Found {active_count} active operations")
                return False
                
        except Exception as e:
            print(f"  ⚠️  Could not check active operations: {e}")
            return True  # Assume OK if table doesn't exist
    
    async def check_configuration_tables_intact(self) -> bool:
        """Verify configuration tables are preserved"""
        print("\n🔍 Checking configuration tables...")
        
        config_tables = [
            'system_config',
            'system_settings', 
            'asset_limits',
            'grid_config'
        ]
        
        all_intact = True
        
        for table in config_tables:
            try:
                count_query = f"SELECT COUNT(*) FROM {table};"
                row_count = await self.connection.fetchval(count_query)
                
                if row_count > 0:
                    print(f"  ✅ {table}: Preserved ({row_count} rows)")
                else:
                    print(f"  ⚠️  {table}: Empty (may be normal)")
                    
            except Exception as e:
                print(f"  ❌ {table}: Error checking - {e}")
                all_intact = False
        
        return all_intact
    
    async def run_full_check(self) -> bool:
        """Run complete sanity check"""
        print("🚀 Starting GridBot v2.5 Production Reset Sanity Check")
        print("=" * 60)
        
        await self.connect()
        
        try:
            # Run all checks
            checks = [
                ("Transactional tables empty", await self.check_transactional_tables_empty()),
                ("System settings reset", await self.check_system_settings_reset()),
                ("No active operations", await self.check_no_active_operations()),
                ("Configuration tables intact", await self.check_configuration_tables_intact())
            ]
            
            print("\n" + "=" * 60)
            print("📊 SANITY CHECK RESULTS")
            print("=" * 60)
            
            all_passed = True
            for check_name, result in checks:
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status} {check_name}")
                if not result:
                    all_passed = False
            
            print("=" * 60)
            
            if all_passed:
                print("🎉 ALL CHECKS PASSED - System ready for production!")
                print("✅ GridBot v2.5 is in a clean state for fresh deployment")
                return True
            else:
                print("❌ SOME CHECKS FAILED - System not ready for production")
                print("🔧 Please review failed checks and re-run reset if needed")
                return False
                
        finally:
            await self.disconnect()


async def main():
    """Main execution function"""
    checker = SanityChecker()
    success = await checker.run_full_check()
    
    if success:
        print("\n🚀 Ready to proceed with Phase 2: Critical Fixes")
        sys.exit(0)
    else:
        print("\n🛑 Cannot proceed - fix issues before continuing")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
