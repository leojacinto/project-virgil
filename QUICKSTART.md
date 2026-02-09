# Quick Start Guide

Get the ServiceNow Architecture Generator running in 5 minutes!

## Prerequisites

- Python 3.9.6 (recommended and tested version)
- Node.js 16+ installed
- ServiceNow JDBC driver JAR file
- OpenAI or Anthropic API key

## Quick Setup

### 1. Place JDBC Driver

```bash
mkdir -p backend/jdbc
cp /path/to/servicenow-jdbc.jar backend/jdbc/
```

### 2. Configure Backend

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env` and add:
```env
OPENAI_API_KEY=sk-...
SERVICENOW_INSTANCE=your_instance
SERVICENOW_USERNAME=your_username
SERVICENOW_PASSWORD=your_password
```

### 3. Start Backend

```bash
chmod +x start_backend.sh
./start_backend.sh
```

Or manually:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 4. Start Frontend (New Terminal)

```bash
chmod +x start_frontend.sh
./start_frontend.sh
```

Or manually:
```bash
cd frontend
npm install
npm start
```

### 5. Open Application

Open your browser to: **http://localhost:3000**

## First Use

1. **Connect**: Enter your ServiceNow credentials and click "Connect"
2. **Upload** (Optional): Add pricing/reference documents in the Documents tab
3. **Query**: Enter your architecture requirement
4. **Generate**: Click "Generate Architecture" and wait for results

## Test Connection

Before using the UI, test your ServiceNow connection:

```bash
cd backend
source venv/bin/activate
python test_connection.py
```

This will verify:
- JDBC driver is accessible
- Credentials are correct
- Can query tables and applications

## Example Query

Try this in the Architecture Query tab:

```
Design a customer service management solution that integrates 
with our existing CRM and includes case management, knowledge 
base, and automated routing workflows.
```

## Troubleshooting

**Can't connect to ServiceNow?**
- Verify credentials in `.env`
- Check JDBC JAR file is in `backend/jdbc/`
- Run `python test_connection.py` for detailed diagnostics

**LLM not working?**
- Verify API key in `.env`
- Check you have API credits
- Try switching between OpenAI and Anthropic

**Port conflicts?**
- Backend: Change port in `main.py` (default 8000)
- Frontend: Set `PORT=3001` before `npm start`

## Next Steps

- Read [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed setup
- See [README.md](README.md) for full documentation
- Check [JDBC_INTEGRATION.md](JDBC_INTEGRATION.md) to integrate your existing code

## Support

For issues, check the logs:
- Backend: Terminal running `python main.py`
- Frontend: Browser console (F12)
- API docs: http://localhost:8000/docs
