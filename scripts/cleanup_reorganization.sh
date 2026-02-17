#!/bin/bash
# Cleanup script: Delete old files after reorganization is complete
# Run this after verifying all new files are in place

set -e

echo "🧹 Cleaning up old agent/governance files..."
echo ""

# Agent files moved to .agent/
echo "Removing old agent files..."
rm -f agents/builder_agent.md
rm -f agents/refactor_agent.md
rm -f agents/migration_agent.md
rm -f agents/analytics_agent.md

# Agent protocol moved to .agent/
echo "Removing old AGENT_PROTOCOL.md..."
rm -f AGENT_PROTOCOL.md

# Governance files moved to .agent/ and docs/development/
echo "Removing old CODEBASE_RULES.md..."
rm -f CODEBASE_RULES.md

echo "Removing old MIGRATIONS.md..."
rm -f MIGRATIONS.md

# Task specs moved to .agent/workflows/
echo "Removing old TASKS/ folder..."
rm -rf TASKS/

# Old agent script moved to .agent/scripts/
echo "Removing old scripts/verify_agent_changes.py..."
rm -f scripts/verify_agent_changes.py

# Remove old empty agents folder if it's empty
if [ -d "agents" ] && [ ! "$(ls -A agents)" ]; then
    rmdir agents
    echo "Removed empty agents/ folder"
fi

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "New structure is ready:"
echo "  .agent/                     — Agent governance (PROTOCOL, roles, workflows, scripts)"
echo "  docs/development/           — Development standards (CODEBASE_RULES, MIGRATIONS)"
echo "  docs/                       — Technical docs (architecture, database, session flow)"
echo "  src/                        — Application source code (coming in next phase)"
echo "  scripts/                    — Application tools (init_db.py, analytics.py)"
echo "  tests/                      — Test suite (placeholder for now)"
echo "  root/                       — README, CONTRIBUTING, LICENSE, pyproject.toml, etc."
echo ""
