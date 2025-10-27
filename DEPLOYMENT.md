# PrivAgent Deployment Guide

## 🚀 REAL Implementation Deployment

This guide shows how to deploy the **REAL** PrivAgent system with authentic Solana transactions, Jupiter integration, and Light Protocol compression - **NO SIMULATIONS**.

## 📋 Prerequisites

### 1. Install Dependencies

```bash
# Core Python dependencies
pip install -r requirements.txt

# Solana CLI
sh <(curl -sSfL https://release.solana.com/v1.18.4/install)

# Light Protocol CLI
npm install -g @lightprotocol/zk-compression-cli

# Optional: Jupiter Python SDK
pip install jupiter-python-sdk-public
```

### 2. Generate KeyPairs

```bash
# Generate a new keypair for transactions
solana-keygen new --no-bip39 --silent

# Copy the base58 private key
# IMPORTANT: Keep this secure!
```

### 3. Get RPC Access

**Helius (Recommended):**
- Sign up at https://www.helius.dev/
- Get free API key
- Supports high-rate requests

**Alternative:**
- Public RPC (rate limited)
- Alchemy, QuickNode, etc.

## ⚙️ Configuration

### 1. Environment Setup

```bash
# Copy the example configuration
cp .env.example .env

# Edit with your real values
nano .env
```

### 2. Critical Settings

```bash
# REQUIRED FOR REAL TRANSACTIONS
PAYER_PRIVATE_KEY=your_base58_encoded_private_key_here
HELIUS_RPC_URL=https://rpc.helius.xyz/?api-key=YOUR_API_KEY

# REQUIRED FOR AGENT COMMUNICATION
PRIVACY_AGENT_ADDRESS=agent1_generated_address_here
EXECUTION_AGENT_ADDRESS=agent2_generated_address_here
MONITORING_AGENT_ADDRESS=agent3_generated_address_here
```

## 🚀 Deployment Methods

### Method 1: Development (All agents on single machine)

```bash
# Terminal 1 - Coordinator
cd agent
python -m agents.coordinator

# Terminal 2 - Privacy Agent
cd agent
python -m agents.privacy_agent

# Terminal 3 - Execution Agent
cd agent
python -m agents.execution_agent

# Terminal 4 - Monitoring Agent
cd agent
python -m agents.monitoring_agent
```

### Method 2: Production (Docker Compose)

```bash
# Build Docker images
docker build -t privagent-coordinator -f Dockerfile.coordinator .
docker build -t privagent-privacy -f Dockerfile.privacy .
docker build -t privagent-execution -f Dockerfile.execution .
docker build -t privagent-monitoring -f Dockerfile.monitoring .

# Deploy with docker-compose
docker-compose up -d
```

### Method 3: Bureau (Production Multi-Agent)

```bash
# Create deployment script
cat > deploy.py << 'EOF'
from agents.coordinator import coordinator
from agents.privacy_agent import privacy_agent
from agents.execution_agent import execution_agent
from agents.monitoring_agent import monitoring_agent
from uagents import Bureau

# Create bureau
bureau = Bureau()
bureau.add(coordinator)
bureau.add(privacy_agent)
bureau.add(execution_agent)
bureau.add(monitoring_agent)

if __name__ == "__main__":
    bureau.run()
EOF

# Deploy bureau
python deploy.py
```

## 🔧 Configuration Files

### Docker Compose

```yaml
version: '3.8'
services:
  coordinator:
    build:
      context: .
      dockerfile: Dockerfile.coordinator
    ports:
      - "8000:8000"
    environment:
      - AGENT_PORT_COORDINATOR=8000
      - PRIVACY_AGENT_ADDRESS=${PRIVACY_AGENT_ADDRESS}
      - EXECUTION_AGENT_ADDRESS=${EXECUTION_AGENT_ADDRESS}
      - MONITORING_AGENT_ADDRESS=${MONITORING_AGENT_ADDRESS}
      - HELIUS_RPC_URL=${HELIUS_RPC_URL}
      - PAYER_PRIVATE_KEY=${PAYER_PRIVATE_KEY}

  privacy-agent:
    build:
      context: .
      dockerfile: Dockerfile.privacy
    ports:
      - "8001:8001"
    environment:
      - AGENT_PORT_PRIVACY=8001
      - HELIUS_RPC_URL=${HELIUS_RPC_URL}
      - LIGHT_CLI_PATH=light

  execution-agent:
    build:
      context: .
      dockerfile: Dockerfile.execution
    ports:
      - "8002:8002"
    environment:
      - AGENT_PORT_EXECUTION=8002
      - HELIUS_RPC_URL=${HELIUS_RPC_URL}
      - PAYER_PRIVATE_KEY=${PAYER_PRIVATE_KEY}

  monitoring-agent:
    build:
      context: .
      dockerfile: Dockerfile.monitoring
    ports:
      - "8003:8003"
    environment:
      - AGENT_PORT_MONITORING=8003
      - HELIUS_RPC_URL=${HELIUS_RPC_URL}
```

### Systemd Services (Linux)

```bash
# Create service files
sudo tee /etc/systemd/system/privagent-coordinator.service > /dev/null <<EOF
[Unit]
Description=PrivAgent Coordinator
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/path/to/privagent/agent
Environment=PATH=/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/python -m agents.coordinator
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start services
sudo systemctl enable privagent-coordinator
sudo systemctl start privagent-coordinator
```

## 🔍 Verification

### 1. Check Agent Status

```bash
# Test coordinator
curl http://localhost:8000/health

# Test privacy agent
curl http://localhost:8001/health

# Test execution agent
curl http://localhost:8002/health

# Test monitoring agent
curl http://localhost:8003/health
```

### 2. Run Integration Tests

```bash
# Run comprehensive tests
cd agent
python tests/test_real_integration.py

# Run basic tests
python tests/test_agents.py
```

### 3. Test Real Operations

```bash
# Test Jupiter integration (will make REAL API call)
curl -X POST http://localhost:8002/api/test-jupiter

# Test Light Protocol (requires CLI)
curl -X POST http://localhost:8001/api/test-compression

# Test MEV detection
curl -X POST http://localhost:8003/api/test-mev-detection
```

## 📊 Monitoring

### 1. Health Checks

```bash
# All agents health
curl http://localhost:8000/api/health/all

# Agent communication test
curl -X POST http://localhost:8000/api/test-communication
```

### 2. Logs

```bash
# View coordinator logs
tail -f logs/coordinator.log

# View all agent logs
tail -f logs/*.log
```

### 3. Metrics

```bash
# Agent performance metrics
curl http://localhost:8000/api/metrics

# Privacy statistics
curl http://localhost:8001/api/stats

# Transaction statistics
curl http://localhost:8002/api/stats
```

## 🚨 Production Considerations

### Security

1. **Private Keys**: Never commit `.env` with real keys
2. **Network**: Use HTTPS in production
3. **Rate Limiting**: Configure appropriate limits
4. **Monitoring**: Set up alerts for failures

### Scalability

1. **Load Balancing**: Deploy multiple instances
2. **Caching**: Redis for session storage
3. **Database**: PostgreSQL for persistent data
4. **Monitoring**: Prometheus + Grafana

### Reliability

1. **Health Checks**: Kubernetes liveness/readiness
2. **Circuit Breakers**: Handle RPC failures
3. **Retries**: Exponential backoff
4. **Failover**: Multiple RPC endpoints

## 🔧 Troubleshooting

### Common Issues

1. **"Agent not responding"**
   - Check ports are not blocked
   - Verify `.env` configuration
   - Check logs for errors

2. **"Transaction failed"**
   - Verify `PAYER_PRIVATE_KEY` is correct
   - Check wallet has SOL for fees
   - Verify RPC endpoint is working

3. **"Light CLI not found"**
   - Install: `npm install -g @lightprotocol/zk-compression-cli`
   - Add to PATH or set `LIGHT_CLI_PATH`

4. **"Jupiter API timeout"**
   - Check network connectivity
   - Verify API endpoint
   - Consider rate limiting

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Enable test mode
export TEST_MODE=true

# Run with debug
python -m agents.coordinator
```

## 📈 Performance Optimization

### RPC Optimization

1. **Use Helius**: Higher rate limits
2. **Connection Pooling**: Reuse connections
3. **Batch Requests**: Combine multiple calls
4. **Caching**: Cache account info

### Agent Optimization

1. **Async Operations**: Non-blocking I/O
2. **Memory Management**: Clear old data
3. **Error Handling**: Graceful degradation
4. **Resource Limits**: Set appropriate limits

## 🌍 Network Configuration

### Mainnet Deployment

```bash
# Use mainnet RPC
HELIUS_RPC_URL=https://rpc.helius.xyz/?api-key=MAINNET_KEY
SOLANA_NETWORK=mainnet-beta
```

### Devnet Testing

```bash
# Use devnet for testing
HELIUS_RPC_URL=https://rpc.devnet.helius.xyz/?api-key=DEVNET_KEY
SOLANA_RPC_URL=https://api.devnet.solana.com
TEST_MODE=true
```

### Local Development

```bash
# Use local validator
SOLANA_RPC_URL=http://localhost:8899
TEST_MODE=true
LOG_LEVEL=DEBUG
```

## 📞 Support

### Issues and Help

1. **Check Logs**: Always check agent logs first
2. **Run Tests**: Verify integrations work
3. **Network**: Check RPC connectivity
4. **Configuration**: Verify `.env` settings

### Community

- **GitHub Issues**: Report bugs and feature requests
- **Discord**: Real-time support
- **Documentation**: Check latest guides

---

## 🎉 Success Metrics

When deployment is successful, you should see:

✅ All 4 agents running with unique addresses
✅ Real Jupiter API quotes working
✅ Real Light Protocol CLI integration
✅ Real MEV detection algorithms running
✅ Real inter-agent communication working
✅ Real Solana transactions executing

**No more simulations - everything is REAL!** 🚀

---

*Last Updated: October 2025*
*Version: 2.0 - REAL Implementation*