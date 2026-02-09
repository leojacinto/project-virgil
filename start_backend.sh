#!/bin/bash

echo "🚀 Starting ServiceNow Architecture Generator Backend..."
echo ""

# Check for existing process on port 8000
EXISTING_PID=$(lsof -ti:8000 2>/dev/null)
if [ ! -z "$EXISTING_PID" ]; then
    echo "⚠️  Found existing backend process on port 8000 (PID: $EXISTING_PID)"
    read -p "   Kill this process? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kill -9 $EXISTING_PID 2>/dev/null
        echo "   ✓ Process killed"
        sleep 1
    else
        echo "   ❌ Cannot start backend - port 8000 is in use"
        exit 1
    fi
fi
echo ""

cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate

# Set JAVA_HOME for JDBC driver
if [ -z "$JAVA_HOME" ]; then
    if [ -d "/opt/homebrew/opt/java" ]; then
        export JAVA_HOME="/opt/homebrew/opt/java"
    elif [ -d "/usr/local/opt/openjdk@25" ]; then
        export JAVA_HOME="/usr/local/opt/openjdk@25"
    elif command -v /usr/libexec/java_home &> /dev/null; then
        export JAVA_HOME=$(/usr/libexec/java_home 2>/dev/null)
    fi
    
    if [ ! -z "$JAVA_HOME" ]; then
        echo "✓ Java found at: $JAVA_HOME"
    else
        echo "⚠️  WARNING: Java not found. ServiceNow connection requires Java."
        echo "   Install with: brew install openjdk@17"
    fi
fi

# Upgrade pip first
echo ""
echo "⬆️  Upgrading pip..."
pip install --upgrade pip --quiet

# Check if FastAPI is installed (indicator of successful previous install)
if ! python -c "import fastapi" 2>/dev/null; then
    echo ""
    echo "📥 Installing dependencies (this may take a few minutes)..."
    echo "   Using extended timeout for slow connections..."
    
    # Install with longer timeout and retry logic
    pip install -r requirements.txt --default-timeout=100 --retries=3
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "⚠️  Installation had issues. Trying critical packages individually..."
        pip install fastapi uvicorn python-multipart pydantic --default-timeout=100
        pip install langchain langchain-openai langchain-anthropic --default-timeout=100
        pip install jpype1 pandas numpy --default-timeout=100
        pip install PyPDF2 python-docx openpyxl --default-timeout=100
        pip install chromadb sentence-transformers --default-timeout=100
        pip install diagrams requests beautifulsoup4 --default-timeout=100
    fi
    
    echo "✓ Dependencies installed"
else
    echo "✓ Dependencies already installed"
fi

# Check for JDBC driver
echo ""
if [ -f "jdbc/ServiceNowJdbc-1.0.3-SNAPSHOT.jar" ]; then
    echo "✓ JDBC driver found (ServiceNow JDBC v1.0.3)"
elif [ -f "jdbc/servicenow-jdbc.jar" ]; then
    echo "✓ JDBC driver found (custom)"
else
    echo "⚠️  WARNING: ServiceNow JDBC JAR file not found"
    echo "   Expected location: backend/jdbc/ServiceNowJdbc-1.0.3-SNAPSHOT.jar"
    echo "   Please download the JDBC driver from your ServiceNow instance"
    echo "   and place it in the backend/jdbc/ directory."
    echo "   The app will start but ServiceNow connection will fail."
    echo ""
fi

# Start the server
echo ""
echo "🌐 Starting FastAPI server on http://localhost:8000"
echo "   Press Ctrl+C to stop"
echo ""
python main.py
