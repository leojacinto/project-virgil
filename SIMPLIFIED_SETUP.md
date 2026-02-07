# Simplified Setup Guide

No more config file drama! Everything is configured through the web interface.

## What You Need

1. **Java 17+** - Required for ServiceNow JDBC connection
   ```bash
   brew install openjdk@17
   ```

2. **An LLM API Key** - From OpenAI, Anthropic, Google, or Azure

That's it! The ServiceNow JDBC driver is already included.

## Setup Steps

### 1. Start the Application

**Option A: Single Command (Recommended)**
```bash
./start.sh
```

This starts both backend and frontend in one terminal!

**Option B: Separate Terminals**

Terminal 1 - Backend:
```bash
./start_backend.sh
```

Terminal 2 - Frontend:
```bash
./start_frontend.sh
```

### 3. Open Browser

Go to: **http://localhost:3000**

The startup scripts automatically:
- ✅ Upgrade pip
- ✅ Install all dependencies
- ✅ Handle slow connections with retries
- ✅ Check for JDBC driver
- ✅ Start both servers

You'll see a setup wizard with 2 steps:

#### Step 1: Configure AI Model
- Choose your LLM provider (OpenAI, Anthropic, Google Gemini, or Azure)
- Enter your API key
- Optionally select a specific model
- Click Continue

#### Step 2: Connect to ServiceNow
- Enter your instance name (e.g., "dev12345")
- Enter your username
- Enter your password
- Optionally specify JDBC path
- Click Connect

Done! The app will load and you're ready to generate architectures.

## Supported LLM Providers

### OpenAI
- **Models**: GPT-4 Turbo, GPT-4, GPT-3.5 Turbo
- **API Key**: Get from https://platform.openai.com/api-keys

### Anthropic Claude
- **Models**: Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Sonnet
- **API Key**: Get from https://console.anthropic.com/

### Google Gemini
- **Models**: Gemini Pro, Gemini 1.5 Pro
- **API Key**: Get from https://makersuite.google.com/app/apikey

### Azure OpenAI
- **Models**: GPT-4, GPT-3.5 Turbo
- **API Key**: From your Azure OpenAI resource

## No Config Files Needed!

Everything is entered through the UI:
- ✅ LLM credentials
- ✅ ServiceNow credentials
- ✅ All configuration

The only file you need is the JDBC driver JAR.

## Switching Providers

Want to try a different LLM? Just refresh the page and go through the wizard again with different credentials.

## That's It!

Two terminals, one browser, zero config files to edit.
