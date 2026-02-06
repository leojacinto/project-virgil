# ServiceNow Architecture Generator - Setup Guide

This guide will walk you through setting up the ServiceNow Architecture Diagram Generator application.

## Step 1: Obtain ServiceNow JDBC Driver

### Download the JDBC Driver

1. Log in to your ServiceNow instance
2. Navigate to **System Applications** > **Studio**
3. Search for "JDBC Driver" in the application repository
4. Download the ServiceNow JDBC driver JAR file

Alternatively, contact your ServiceNow administrator to obtain the JDBC driver.

### Place the JDBC Driver

```bash
cd backend
mkdir -p jdbc
cp /path/to/servicenow-jdbc.jar jdbc/
```

The JAR file should be named something like `servicenow-jdbc-<version>.jar`

## Step 2: Set Up Backend

### Install Python Dependencies

```bash
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your preferred editor
```

Required configuration:

```env
# LLM API Key (choose one)
OPENAI_API_KEY=sk-proj-...
# OR
ANTHROPIC_API_KEY=sk-ant-...

# ServiceNow Connection
SERVICENOW_INSTANCE=dev12345
SERVICENOW_USERNAME=admin
SERVICENOW_PASSWORD=your_password
SERVICENOW_JDBC_PATH=./jdbc/servicenow-jdbc.jar

# Optional: Web Search
SERPAPI_KEY=your_serpapi_key_here
```

### Test Backend Installation

```bash
python main.py
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Visit `http://localhost:8000/api/health` to verify the backend is running.

## Step 3: Set Up Frontend

### Install Node Dependencies

```bash
cd frontend
npm install
```

### Start Development Server

```bash
npm start
```

The application will open in your browser at `http://localhost:3000`

## Step 4: Connect to ServiceNow

1. Open the application in your browser
2. You'll see the connection panel
3. Enter your ServiceNow credentials:
   - **Instance Name**: Just the instance name (e.g., "dev12345", not the full URL)
   - **Username**: Your ServiceNow username
   - **Password**: Your ServiceNow password
   - **JDBC JAR Path**: Leave empty to use default, or specify custom path
4. Click "Connect to ServiceNow"
5. Wait for the connection to establish (may take 10-30 seconds)

## Step 5: Upload Reference Documents (Optional)

1. Navigate to the "Documents" tab
2. Upload any relevant documents:
   - ServiceNow pricing documents
   - Technical specifications
   - Architecture guidelines
   - Best practices documents
3. Documents will be processed and indexed automatically

## Step 6: Generate Your First Architecture

1. Navigate to the "Architecture Query" tab
2. Try an example query:
   ```
   How do I address a customer service workflow requirement?
   ```
3. Configure options:
   - ✅ Web Search (recommended)
   - ✅ Use Documents (if you uploaded any)
   - Format: PNG
4. Click "Generate Architecture"
5. Wait for the analysis (may take 30-60 seconds)
6. Review the results in the "Results" tab

## Verification Checklist

- [ ] Backend server running on port 8000
- [ ] Frontend server running on port 3000
- [ ] ServiceNow JDBC JAR file in place
- [ ] Environment variables configured
- [ ] LLM API key configured (OpenAI or Anthropic)
- [ ] Successfully connected to ServiceNow
- [ ] Can view instance tables and applications
- [ ] Can upload documents
- [ ] Can generate architecture analysis

## Common Issues and Solutions

### Issue: "JDBC JAR file not found"

**Solution**: Verify the JAR file is in `backend/jdbc/` directory and the path in `.env` is correct.

```bash
ls -la backend/jdbc/
# Should show servicenow-jdbc.jar
```

### Issue: "Connection failed"

**Solutions**:
1. Verify ServiceNow credentials are correct
2. Check instance name (without .service-now.com)
3. Ensure your ServiceNow instance allows JDBC connections
4. Check firewall/network settings

### Issue: "No LLM model configured"

**Solution**: Add either `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` to your `.env` file.

### Issue: "Module not found" errors

**Solution**: Ensure all dependencies are installed:

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### Issue: JVM startup errors

**Solution**: Ensure Java is installed:

```bash
java -version
# Should show Java 8 or higher
```

If Java is not installed:
- **macOS**: `brew install openjdk`
- **Ubuntu/Debian**: `sudo apt-get install default-jdk`
- **Windows**: Download from [Oracle](https://www.oracle.com/java/technologies/downloads/)

### Issue: Port already in use

**Solution**: Change the port in the respective configuration:

Backend (`main.py`):
```python
uvicorn.run(app, host="0.0.0.0", port=8001)  # Change 8000 to 8001
```

Frontend (`package.json`):
```json
"start": "PORT=3001 react-scripts start"
```

## Production Deployment

For production deployment, consider:

1. **Use production-grade WSGI server**:
   ```bash
   gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
   ```

2. **Build frontend for production**:
   ```bash
   cd frontend
   npm run build
   ```

3. **Set up reverse proxy** (nginx/Apache)

4. **Enable HTTPS** with SSL certificates

5. **Implement authentication** and authorization

6. **Set up monitoring** and logging

7. **Configure database backups**

8. **Use environment-specific configurations**

## Next Steps

- Explore the "Instance Info" tab to see your ServiceNow data
- Upload pricing and reference documents
- Try different architecture queries
- Customize diagram formats
- Review and refine recommendations

## Getting Help

If you encounter issues not covered in this guide:

1. Check the main README.md for additional documentation
2. Review the API documentation at `http://localhost:8000/docs`
3. Check application logs for error messages
4. Contact the development team

## Updating the Application

To update to the latest version:

```bash
# Backend
cd backend
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Frontend
cd frontend
npm install
```

Restart both servers after updating.
