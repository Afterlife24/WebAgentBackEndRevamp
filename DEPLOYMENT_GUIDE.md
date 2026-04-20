# Web Agent Backend Deployment Guide - Complete Step-by-Step

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Part 1: AWS EC2 Instance Setup](#part-1-aws-ec2-instance-setup)
4. [Part 2: Application Deployment](#part-2-application-deployment)
5. [Part 3: Nginx and SSL Configuration](#part-3-nginx-and-ssl-configuration)
6. [Part 4: DNS and Domain Setup](#part-4-dns-and-domain-setup)
7. [Part 5: Frontend Configuration](#part-5-frontend-configuration)
8. [Troubleshooting](#troubleshooting)
9. [Maintenance](#maintenance)

---

## Prerequisites

Before starting, ensure you have:

- AWS Account with billing enabled
- Domain name (e.g., afterlife.org.in) managed by AWS Route 53
- LiveKit Cloud account with a project created
- Groq API Key (for LLM - llama-3.3-70b-versatile)
- Cartesia API Key (for STT/TTS - ink-whisper + sonic-3)
- Basic understanding of terminal/command line

---

## Architecture Overview

### Technology Stack
- **Server:** AWS EC2 (t3.medium, Ubuntu 22.04)
- **AI Agent Framework:** LiveKit Agents SDK (Python)
- **LLM:** Groq (llama-3.3-70b-versatile)
- **STT:** Cartesia (ink-whisper, multilingual)
- **TTS:** Cartesia (sonic-3, multilingual)
- **VAD:** Silero VAD
- **Token Server:** Flask (Python)
- **Web Server:** Nginx (Reverse Proxy)
- **SSL Certificate:** Let's Encrypt (Certbot)
- **Process Manager:** Systemd

### Traffic Flow
```
Frontend (React) → HTTPS (Port 443) → Nginx → Flask Token Server (Port 5001) → LiveKit Cloud
                                                                                      ↕
User Browser ← WebSocket (LiveKit Cloud) ← LiveKit Agent (Port 8081) → Groq/Cartesia APIs
```

### How It Works
1. Frontend requests a LiveKit token from Flask server (`/getToken`)
2. Frontend connects to LiveKit Cloud room using the token
3. LiveKit Cloud dispatches the agent (running on EC2) to join the room
4. Agent uses Groq for LLM reasoning, Cartesia for speech-to-text and text-to-speech
5. Agent can send RPC navigation commands back to the frontend

### Security
- SSL/TLS encryption for all external traffic
- Port 5001 only accessible internally via Nginx
- Environment variables for sensitive API keys
- Systemd service for automatic restart and process management

---

## Part 1: AWS EC2 Instance Setup

### Step 1.1: Launch EC2 Instance

1. **Navigate to EC2 Console**
   - Go to AWS Console: https://console.aws.amazon.com/
   - Search for "EC2" in the top search bar
   - Click on "EC2"

2. **Click "Launch Instance"**

3. **Configure Instance Details**

   **Name and Tags:**
   - Name: `web-agent`

   **Application and OS Images (AMI):**
   - Select: **Ubuntu Server 22.04 LTS (HVM), SSD Volume Type**
   - Architecture: **64-bit (x86)**

   **Instance Type:**
   - Select: **t3.medium**
   - vCPUs: 2
   - Memory: 4 GiB
   - Why: LiveKit agent + multiprocessing forkserver needs more RAM than a simple API server

   **Key Pair (login):**
   - Select existing or create new key pair
   - Or: **Proceed without a key pair** (use EC2 Instance Connect)

   **Network Settings:**
   - VPC: Default VPC
   - Auto-assign public IP: **Enable**
   - Firewall (Security Group): **Create new**
   - Security group name: `web-agent-sg`
   
   **Security Group Rules:**
   - ☑ Allow SSH traffic from Anywhere (0.0.0.0/0)
   - ☑ Allow HTTPS traffic from the internet
   - ☑ Allow HTTP traffic from the internet

   **Configure Storage:**
   - Size: **15 GB**
   - Volume Type: **gp3**
   - Delete on termination: **Yes**

4. **Launch Instance**
   - Review all settings
   - Click **"Launch Instance"**
   - Wait 2-3 minutes for instance to start

5. **Note Your Instance Details**
   - Go to EC2 → Instances
   - Note the **Public IPv4 address**

---

### Step 1.2: Allocate Elastic IP (Static IP)

1. **Navigate to Elastic IPs**
   - EC2 Console → Elastic IPs (left sidebar)

2. **Allocate New Elastic IP**
   - Click **"Allocate Elastic IP address"**
   - Click **"Allocate"**

3. **Associate Elastic IP with Instance**
   - Select the newly allocated Elastic IP
   - Click **Actions** → **Associate Elastic IP address**
   - Instance: Select your `web-agent` instance
   - Click **"Associate"**

4. **Note Your Elastic IP** — this IP will never change

---

### Step 1.3: Connect to EC2 Instance

1. Select your instance → Click **"Connect"**
2. Use **EC2 Instance Connect** tab
3. Username: `ubuntu`
4. Click **"Connect"**

---

## Part 2: Application Deployment

### Step 2.1: Update System Packages

```bash
sudo apt update -y
sudo apt upgrade -y
```

---

### Step 2.2: Install Required System Packages

```bash
sudo apt install -y python3 python3-pip python3-venv git
```

---

### Step 2.3: Create Project Directory

```bash
cd /opt
sudo mkdir web-agent
sudo chown -R ubuntu:ubuntu web-agent
cd web-agent
```

---

### Step 2.4: Clone or Copy Application Files

**Option A: Git Clone**
```bash
git clone https://github.com/YOUR_ORG/WebAgentBackEndRevamp.git .
```

**Option B: Manual Copy (SCP)**
```bash
# From your local machine:
scp -r WebAgentBackEndRevamp/* ubuntu@YOUR_ELASTIC_IP:/opt/web-agent/
```

Your project directory should contain:
```
/opt/web-agent/
├── agent.py              # LiveKit agent (main process)
├── web_agnet_server.py   # Flask token server
├── tools.py              # Agent tools (navigation, product info)
├── prompts.py            # Agent system prompt and session instructions
├── start.sh             # Startup script (runs both processes)
├── shutdown_agent.py     # Graceful shutdown helper
├── requirements.txt      # Python dependencies
├── mcp_client/          # MCP client module
│   ├── __init__.py
│   ├── agent_tools.py
│   ├── server.py
│   └── util.py
└── .env                 # Environment variables (create manually)
```

---

### Step 2.5: Create .env File

```bash
nano /opt/web-agent/.env
```

**Paste your credentials:**

```env
LIVEKIT_URL=wss://webagent-revamp-brx4ajqj.livekit.cloud
LIVEKIT_API_KEY=your-livekit-api-key
LIVEKIT_API_SECRET=your-livekit-api-secret

GROQ_API_KEY=your-groq-api-key
CARTESIA_API_KEY=your-cartesia-api-key
```

**Replace with your actual values!**

**Save:** `CTRL + O` → `ENTER` → `CTRL + X`

**Secure the file:**
```bash
chmod 600 /opt/web-agent/.env
```

---

### Step 2.6: Create Python Virtual Environment

```bash
cd /opt/web-agent
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

---

### Step 2.7: Install Python Dependencies

```bash
pip install -r requirements.txt
```

**This installs:**
- `livekit-agents` — LiveKit agent framework
- `livekit-plugins-groq` — Groq LLM plugin
- `livekit-plugins-cartesia` — Cartesia STT/TTS plugin
- `livekit-plugins-silero` — Silero VAD plugin
- `livekit-plugins-noise-cancellation` — BVC noise cancellation
- `livekit-plugins-turn-detector` — Multilingual turn detection
- `flask[async]` + `flask-cors` — Token server
- `huggingface_hub` — Model downloads for Silero/turn-detector

**Wait:** This takes 2-5 minutes (downloads ML models).

---

### Step 2.8: Make start.sh Executable

```bash
chmod +x /opt/web-agent/start.sh
```

**Verify start.sh content:**
```bash
cat /opt/web-agent/start.sh
```

Should show:
```bash
#!/bin/bash

# Trap SIGTERM and SIGINT, forward to child processes
trap 'kill $PID1 $PID2 2>/dev/null; wait $PID1 $PID2 2>/dev/null; exit 0' SIGTERM SIGINT

/opt/web-agent/venv/bin/python agent.py start &
PID1=$!

/opt/web-agent/venv/bin/python web_agnet_server.py &
PID2=$!

wait -n
kill $PID1 $PID2 2>/dev/null
wait $PID1 $PID2 2>/dev/null
exit 1
```

**If empty or has Windows line endings:**
```bash
sed -i 's/\r$//' /opt/web-agent/start.sh
```

---

### Step 2.9: Test the Application (Manual Run)

```bash
source /opt/web-agent/venv/bin/activate
cd /opt/web-agent

# Test Flask token server
python web_agnet_server.py &
curl http://localhost:5001/health
# Should return: {"status":"healthy","service":"avatar-backend"}
kill %1

# Test agent starts without errors
python agent.py start &
# Wait 5-10 seconds, check for errors in output
kill %1
```

---

### Step 2.10: Create Systemd Service

```bash
sudo nano /etc/systemd/system/web-agent.service
```

**Paste:**

```ini
[Unit]
Description=Web Agent
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/web-agent
EnvironmentFile=/opt/web-agent/.env
ExecStart=/opt/web-agent/start.sh
ExecStop=/bin/kill -TERM $MAINPID
KillMode=control-group
KillSignal=SIGTERM
TimeoutStopSec=15
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Save:** `CTRL + O` → `ENTER` → `CTRL + X`

**Key settings explained:**
- `KillMode=control-group` — Sends SIGTERM to ALL child processes (both Python scripts)
- `TimeoutStopSec=15` — Waits max 15s for graceful shutdown before SIGKILL
- `Restart=always` — Auto-restarts on crash
- `RestartSec=5` — Waits 5s between restart attempts

---

### Step 2.11: Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable web-agent
sudo systemctl start web-agent
```

---

### Step 2.12: Check Service Status

```bash
sudo systemctl status web-agent
```

**Expected output:**
```
● web-agent.service - Web Agent
   Loaded: loaded (/etc/systemd/system/web-agent.service; enabled)
   Active: active (running) since ...
   CGroup: /system.slice/web-agent.service
           ├─ ... /bin/bash /opt/web-agent/start.sh
           ├─ ... /opt/web-agent/venv/bin/python agent.py start
           └─ ... /opt/web-agent/venv/bin/python web_agnet_server.py
```

You should see both `agent.py` and `web_agnet_server.py` as child processes.

---

## Part 3: Nginx and SSL Configuration

### Step 3.1: Install Nginx and Certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

---

### Step 3.2: Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/web-agent
```

**Paste (replace domain with yours):**

```nginx
server {
    listen 80;
    server_name web.afterlife.org.in;

    location / {
        proxy_pass http://localhost:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Save:** `CTRL + O` → `ENTER` → `CTRL + X`

---

### Step 3.3: Enable Configuration

```bash
sudo ln -s /etc/nginx/sites-available/web-agent /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

---

### Step 3.4: Test HTTP

Open browser: `http://YOUR_ELASTIC_IP/health`

Should return: `{"status":"healthy","service":"avatar-backend"}`

---

## Part 4: DNS and Domain Setup

### Step 4.1: Create DNS A Record in Route 53

1. Go to **Route 53** → **Hosted zones** → Select your domain
2. Click **"Create record"**
3. Configure:
   - **Record name:** `web`
   - **Record type:** `A`
   - **Value:** Your Elastic IP
   - **TTL:** `300`
4. Click **"Create records"**
5. Wait 2-5 minutes for DNS propagation

---

### Step 4.2: Test Domain

```bash
curl http://web.afterlife.org.in/health
```

---

### Step 4.3: Get SSL Certificate

```bash
sudo certbot --nginx -d web.afterlife.org.in
```

Follow prompts:
1. Enter email address
2. Agree to terms: `Y`
3. Share email: `N`

---

### Step 4.4: Test HTTPS

Open browser: `https://web.afterlife.org.in/health`

Should work with 🔒 secure padlock.

---

## Part 5: Frontend Configuration

The frontend React app (`3AgentsWebsiteRevamp_React`) connects to this backend.

### Environment Variables (Frontend)

In your frontend `.env` or GitHub Secrets:

```env
VITE_BACKEND_URL=https://web.afterlife.org.in
VITE_LIVEKIT_URL=wss://webagent-revamp-brx4ajqj.livekit.cloud
```

### How Frontend Connects

1. `LiveKitWidget.tsx` fetches token from `${VITE_BACKEND_URL}/getToken?name=admin&language=en`
2. Connects to LiveKit room using the token
3. `NavigationHandler` registers RPC method `"navigate"` to receive navigation commands from the agent
4. Agent calls `navigate_to_section()` or `open_url()` → sends RPC to frontend → frontend navigates

### Triggering Frontend Rebuild

If you update environment variables in GitHub Secrets (for Vercel/Netlify):
```bash
cd 3AgentsWebsiteRevamp_React
git commit --allow-empty -m "trigger rebuild with updated env vars"
git push
```

---

## Troubleshooting

### Issue: Service won't start (exit code 203/EXEC)

**Cause:** Bad shebang or Windows line endings in `start.sh`

**Fix:**
```bash
sed -i 's/\r$//' /opt/web-agent/start.sh
chmod +x /opt/web-agent/start.sh
sudo systemctl restart web-agent
```

---

### Issue: Service stops with timeout (SIGKILL)

**Cause:** Missing `KillMode=control-group` in service file

**Fix:** Ensure your service file has:
```ini
KillMode=control-group
KillSignal=SIGTERM
TimeoutStopSec=15
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl restart web-agent
```

---

### Issue: Agent crashes with API key errors

**Check env vars are loaded:**
```bash
sudo journalctl -u web-agent -n 50
```

**Verify .env file:**
```bash
cat /opt/web-agent/.env
```

Ensure `GROQ_API_KEY`, `CARTESIA_API_KEY`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` are all set.

---

### Issue: Frontend can't get token (CORS or connection error)

**Check Flask server is running:**
```bash
curl http://localhost:5001/health
```

**Check Nginx is proxying correctly:**
```bash
curl https://web.afterlife.org.in/health
```

**Check Nginx logs:**
```bash
sudo tail -f /var/log/nginx/error.log
```

---

### Issue: Agent connects but no audio/voice

**Check LiveKit Cloud dashboard:**
- Go to https://cloud.livekit.io/
- Verify the project URL matches your `.env` `LIVEKIT_URL`
- Check that rooms are being created when frontend connects

**Check agent logs:**
```bash
sudo journalctl -u web-agent -f
```

Look for:
- "Session started successfully"
- "Initial reply generated successfully"
- Any Cartesia/Groq errors

---

### Issue: Navigation not working (RPC fails)

**Check agent logs for:**
```
[TOOL] No room or remote participant found
```

This means the agent can't find the frontend participant. Ensure:
- Frontend is connected to the same LiveKit room
- The `NavigationHandler` component is mounted inside `LiveKitRoom`

---

### Issue: "process exited with non-zero exit code 255" on stop

**This is normal.** LiveKit child processes exit with 255 when receiving SIGTERM during shutdown. The service still stops cleanly (exit code 0).

---

## Maintenance

### Viewing Logs

```bash
# Real-time logs
sudo journalctl -u web-agent -f

# Last 100 lines
sudo journalctl -u web-agent -n 100

# Logs from today
sudo journalctl -u web-agent --since today

# Filter for errors only
sudo journalctl -u web-agent -p err
```

---

### Updating Application Code

```bash
cd /opt/web-agent
sudo systemctl stop web-agent

# Pull latest code (if using git)
git pull origin main

# Or manually copy files from local machine

# Install any new dependencies
source venv/bin/activate
pip install -r requirements.txt

# Fix line endings if pulled from Windows
sed -i 's/\r$//' start.sh
chmod +x start.sh

# Restart
sudo systemctl start web-agent
sudo systemctl status web-agent
```

---

### Updating Environment Variables

```bash
nano /opt/web-agent/.env
# Make changes and save
sudo systemctl restart web-agent
```

---

### SSL Certificate Renewal

Certificates auto-renew via certbot timer. To check:

```bash
sudo certbot renew --dry-run
sudo certbot certificates
```

---

### Monitoring Server Resources

```bash
# Check memory (agent uses ~600-700MB)
free -h

# Check disk space
df -h

# Check CPU
top
```

---

## Quick Reference Commands

### Service Management
```bash
sudo systemctl start web-agent
sudo systemctl stop web-agent
sudo systemctl restart web-agent
sudo systemctl status web-agent
sudo journalctl -u web-agent -f
```

### Nginx Management
```bash
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl reload nginx
sudo tail -f /var/log/nginx/error.log
```

### SSL Management
```bash
sudo certbot certificates
sudo certbot renew
sudo certbot renew --dry-run
```

---

## Ports Reference

| Port | Service | Access |
|------|---------|--------|
| 22 | SSH | Public (EC2 Instance Connect) |
| 80 | HTTP (Nginx) | Public (redirects to 443) |
| 443 | HTTPS (Nginx) | Public |
| 5001 | Flask Token Server | Internal only (via Nginx) |
| 8081 | LiveKit Agent Worker | Internal only (LiveKit Cloud connects outbound) |

---

## Cost Estimation (Monthly)

### AWS Costs
- **EC2 (t3.medium):** ~$30-35/month on-demand
- **Elastic IP:** Free while instance is running
- **Data Transfer:** ~$1-5/month
- **Route 53:** ~$1-2/month
- **Total AWS:** ~$32-42/month

### Third-Party Costs
- **LiveKit Cloud:** Free tier covers development; production pricing varies
- **Groq API:** Free tier available; paid plans for higher throughput
- **Cartesia API:** Usage-based pricing for STT/TTS
- **Total Third-Party:** Varies by usage

---

## Deployment Checklist

### Pre-Deployment
- [ ] AWS account configured
- [ ] Domain managed by Route 53
- [ ] LiveKit Cloud project created (note URL, API key, API secret)
- [ ] Groq API key obtained
- [ ] Cartesia API key obtained

### EC2 Setup
- [ ] EC2 instance launched (t3.medium, Ubuntu 22.04)
- [ ] Elastic IP allocated and associated
- [ ] Security group configured (ports 22, 80, 443)
- [ ] Connected to instance

### Application Deployment
- [ ] System packages installed
- [ ] Project directory created at `/opt/web-agent`
- [ ] Application files copied/cloned
- [ ] `.env` file created with all API keys
- [ ] Virtual environment created and dependencies installed
- [ ] `start.sh` is executable and has correct line endings
- [ ] Systemd service created and enabled
- [ ] Service running with both processes visible

### Networking
- [ ] Nginx installed and configured
- [ ] DNS A record created pointing to Elastic IP
- [ ] SSL certificate obtained via Certbot
- [ ] `https://web.afterlife.org.in/health` returns healthy

### Frontend
- [ ] `VITE_BACKEND_URL` set to `https://web.afterlife.org.in`
- [ ] `VITE_LIVEKIT_URL` set to correct LiveKit Cloud WebSocket URL
- [ ] Frontend deployed and connecting successfully
