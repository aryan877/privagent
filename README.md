![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
![Python](https://img.shields.io/badge/python-3.13-blue)
![uAgents](https://img.shields.io/badge/uAgents-0.22+-purple)
![Solana](https://img.shields.io/badge/Solana-mainnet-green)

# PrivAgent 🔐

> **Multi-Agent Privacy System for Solana**
> Built for ASI Alliance Cypherpunk Hackathon

Privacy-preserving AI agents that enable confidential transactions, MEV protection, and ZK compression on Solana - making blockchain truly usable for institutions and privacy-conscious users.

---

## 🎯 The Problem

Every Solana transaction is public:
- ❌ Wallet balances visible to everyone
- ❌ Trading strategies easily copied
- ❌ MEV bots extract billions in value
- ❌ Institutions won't adopt public blockchains

## ✨ The Solution

PrivAgent is a multi-agent AI system powered by Fetch.ai that brings privacy to Solana through **4 Specialized Agents**.

---

## ⚡ Quick Start (5 Minutes)

### Prerequisites

\`\`\`bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Light Protocol CLI
bun install -g @lightprotocol/zk-compression-cli

# Verify
uv --version
light --version
\`\`\`

### Run Coordinator Agent

\`\`\`bash
# Install dependencies
export PATH="$HOME/.local/bin:$PATH"
uv sync

# Start coordinator
uv run python run_coordinator.py
\`\`\`

**Test via ASI:One:**
1. Copy agent address from terminal
2. Go to https://asi1.ai
3. Search for agent and send "hello"

---

## 🏗️ Architecture

\`\`\`
User (ASI:One) → Coordinator Agent
                       ↓
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
  Privacy Agent  Execution Agent  Monitoring Agent
        ↓              ↓              ↓
    ┌───────────────────────────────────┐
    │       Solana Blockchain           │
    │  Light Protocol | Token 2022      │
    └───────────────────────────────────┘
\`\`\`

---

## 💡 Features

- 🔐 **ZK Compression** - 99.9% storage cost savings
- 📊 **Privacy Scoring** - Actionable privacy recommendations
- 🛡️ **MEV Protection** - Multi-layer swap protection
- 👁️ **Monitoring** - Real-time privacy alerts

---

## 📋 Commands (via ASI:One)

\`\`\`
• "check my privacy score"
• "compress my tokens"
• "protect my swap from MEV"
• "monitor my wallet"
• "help"
\`\`\`

---

## 🛠️ Tech Stack

- ✅ Fetch.ai uAgents 0.22+
- ✅ Light Protocol ZK Compression
- ✅ Solana SDK (solana-py)
- ✅ Python 3.13 + uv
- ✅ ASI:One Chat Protocol

---

## 🚀 Full Documentation

See [guide.md](../guide.md) for complete implementation details.

**Privacy isn't a feature. It's a right.** 🔐
