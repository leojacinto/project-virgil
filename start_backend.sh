#!/bin/bash

echo "🚀 Starting ServiceNow Architecture Generator Backend..."
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
if [ ! -f "jdbc/servicenow-jdbc.jar" ]; then
    echo "⚠️  WARNING: ServiceNow JDBC JAR file not found"
    echo "   Expected location: backend/jdbc/servicenow-jdbc.jar"
    echo "   The app will start but ServiceNow connection will fail."
    echo ""
else
    echo "✓ JDBC driver found"
fi

# Start the server
echo ""
echo "🌐 Starting FastAPI server on http://localhost:8000"
echo "   Press Ctrl+C to stop"
echo ""
python main.py
