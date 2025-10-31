#!/bin/bash

# PrivAgent - Run All Agents Script
# This script starts all 4 agents in separate terminal windows/tabs

echo "🚀 Starting PrivAgent Multi-Agent System..."
echo "================================================"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv not found. Please install uv first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check if Light Protocol CLI is installed
if ! command -v light &> /dev/null; then
    echo "❌ Error: Light Protocol CLI not found. Please install:"
    echo "   bun install -g @lightprotocol/zk-compression-cli"
    exit 1
fi

# Export PATH for uv
export PATH="$HOME/.local/bin:$PATH"

echo "✅ Prerequisites checked"
echo ""
echo "Starting agents..."
echo "Each agent will run in a separate process"
echo "Press Ctrl+C in this terminal to stop all agents"
echo ""

# Function to run agent in background
run_agent() {
    local agent_name=$1
    local agent_module=$2
    echo "  📡 Starting $agent_name..."
    uv run python -m "$agent_module" &
    pids+=($!)
}

# Array to store process IDs
pids=()

# Start all agents
run_agent "Privacy Agent" "agents.privacy_agent"
sleep 2

run_agent "Execution Agent" "agents.execution_agent"
sleep 2

run_agent "Monitoring Agent" "agents.monitoring_agent"
sleep 2

run_agent "Coordinator Agent" "agents.coordinator"
sleep 2

echo ""
echo "================================================"
echo "✅ All agents started successfully!"
echo "================================================"
echo ""
echo "Agent Status:"
echo "  • Privacy Agent    - PID ${pids[0]}"
echo "  • Execution Agent  - PID ${pids[1]}"
echo "  • Monitoring Agent - PID ${pids[2]}"
echo "  • Coordinator Agent - PID ${pids[3]}"
echo ""
echo "⏳ Agents will display their addresses immediately when starting..."
echo "📝 Watch for the addresses above! They will appear instantly!"
echo ""
echo "================================================"
echo "🎯 HOW TO USE YOUR AGENT ADDRESSES:"
echo "================================================"
echo ""
echo "🤖 **COORDINATOR AGENT** (Main entry point):"
echo "    Search this address on https://asi1.ai"
echo "    Send messages like: 'hello', 'check privacy score for wallet...'"
echo ""
echo "🔒 **PRIVACY AGENT** (Privacy analysis):"
echo "    Accessed via coordinator automatically"
echo ""
echo "⚡ **EXECUTION AGENT** (Transaction execution):"
echo "    Accessed via coordinator automatically"
echo ""
echo "📡 **MONITORING AGENT** (Threat monitoring):"
echo "    Accessed via coordinator automatically"
echo ""
echo "📋 TESTING STEPS:"
echo "   1. Copy the COORDINATOR agent address from above"
echo "   2. Go to https://asi1.ai"
echo "   3. Search for the coordinator address"
echo "   4. Send: 'hello'"
echo ""
echo "🔄 **AGENT STATUS:**"
echo "   ✅ Addresses show IMMEDIATELY when agents start"
echo "   ✅ Agents keep running as long as this script runs"
echo "   ❌ Agents STOP when you press Ctrl+C or close this terminal"
echo ""
echo "Press Ctrl+C to stop all agents"
echo "================================================"

# Trap Ctrl+C and kill all agents
trap 'echo ""; echo "Stopping all agents..."; for pid in ${pids[@]}; do kill $pid 2>/dev/null; done; echo "✅ All agents stopped"; exit 0' INT

# Wait for all background processes
wait
