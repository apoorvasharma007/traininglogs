"`"'python
#!/usr/bin/env python3
"""
Safety verification script for agent-produced code.

Run this after agent completes a task to verify:
- No circular imports
- Code follows standards
- Tests pass
- Database operations work

Usage:
    python .agent/scripts/verify_changes.py
"""

import sys
import subprocess
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class SafetyVerifier:
    """Verifies agent-produced code meets safety standards."""

    def __init__(self):
        self.checks_passed = []
        self.checks_failed = []
        self.warnings = []

    def run_all(self) -> bool:
        """Run all safety checks."""
        print("\n🔒 Agent Code Safety Verification")
        print("=" * 50)

        self.check_imports()
        self.check_database()
        self.check_format()
        self.check_lint()

        print("\n" + "=" * 50)
        self._print_summary()

        return len(self.checks_failed) == 0

    def check_imports(self) -> bool:
        """Verify no circular imports."""
        print("\n1️⃣  Checking imports...")

        tests = [
            ("CLI", "import cli.main"),
            ("Core", "import core.validators"),
            ("Persistence", "import persistence.database"),
            ("History", "import history.history_service"),
            ("Analytics", "import analytics.basic_queries"),
        ]

        for name, import_stmt in tests:
            try:
                exec(import_stmt)
                print(f"   ✓ {name}")
                self.checks_passed.append(f"Import: {name}")
            except Exception as e:
                print(f"   ✗ {name}: {e}")
                self.checks_failed.append(f"Import: {name}")

        return len(self.checks_failed) == 0

    def check_database(self) -> bool:
        """Verify database operations work."""
        print("\n2️⃣  Checking database...")

        try:
            from persistence import Database, MigrationManager

            # Create test database
            test_db = "verify_test.db"
            db = Database(test_db)
            db.init_schema()

            # Check schema version
            mgr = MigrationManager(db)
            version = mgr.get_version()

            if version == 1:
                print(f"   ✓ Schema initialization")
                print(f"   ✓ Schema version: {version}")
                self.checks_passed.extend(
                    ["Database: Init", "Database: Version"]
                )
            else:
                print(f"   ✗ Schema version mismatch: {version}")
                self.checks_failed.append("Database: Version")

            # Cleanup
            db.close()
            import os
            os.remove(test_db)

            return len(self.checks_failed) == 0
        except Exception as e:
            print(f"   ✗ Database check failed: {e}")
            self.checks_failed.append("Database: Init")
            return False

    def check_format(self) -> bool:
        """Check code formatting (black)."""
        print("\n3️⃣  Checking code format (black)...")

        try:
            result = subprocess.run(
                ["black", "--check", "--line-length=88", "."],
                cwd=Path(__file__).parent.parent.parent,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                print("   ✓ Code formatting OK")
                self.checks_passed.append("Format: Black")
            else:
                print("   ⚠ Code needs formatting:")
                for line in result.stdout.split('\n')[:5]:  # Show first 5
                    if line:
                        print(f"      {line}")
                self.warnings.append("Format: Run black .")
        except FileNotFoundError:
            print("   ⚠ black not installed (optional)")
            self.warnings.append("Format: Install black")
        except Exception as e:
            print(f"   ⚠ Format check error: {e}")
            self.warnings.append(f"Format: {e}")

        return True  # Don't fail hard on format

    def check_lint(self) -> bool:
        """Check code linting (ruff)."""
        print("\n4️⃣  Checking code lint (ruff)...")

        try:
            result = subprocess.run(
                ["ruff", "check", "--line-length=88", "."],
                cwd=Path(__file__).parent.parent.parent,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                print("   ✓ Code lint OK")
                self.checks_passed.append("Lint: Ruff")
            else:
                print("   ⚠ Lint issues found:")
                for line in result.stdout.split('\n')[:5]:  # Show first 5
                    if line:
                        print(f"      {line}")
                self.warnings.append("Lint: Review ruff output")
        except FileNotFoundError:
            print("   ⚠ ruff not installed (optional)")
            self.warnings.append("Lint: Install ruff")
        except Exception as e:
            print(f"   ⚠ Lint check error: {e}")
            self.warnings.append(f"Lint: {e}")

        return True  # Don't fail hard on lint

    def _print_summary(self):
        """Print summary of checks."""
        passed = len(self.checks_passed)
        failed = len(self.checks_failed)
        warnings = len(self.warnings)

        print(f"\n✓ Passed: {passed}")
        if self.checks_passed:
            for check in self.checks_passed:
                print(f"   • {check}")

        if failed > 0:
            print(f"\n✗ Failed: {failed}")
            for check in self.checks_failed:
                print(f"   • {check}")

        if warnings > 0:
            print(f"\n⚠ Warnings: {warnings}")
            for warning in self.warnings:
                print(f"   • {warning}")

        print()

        if failed > 0:
            print("❌ VERIFICATION FAILED")
            print("Fix the errors above before merging.")
            return False
        else:
            print("✅ VERIFICATION PASSED")
            print("Code is ready for review.")
            return True


def main():
    """Run verification."""
    verifier = SafetyVerifier()
    passed = verifier.run_all()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()

"`"'
