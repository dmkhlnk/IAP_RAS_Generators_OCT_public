# Setup Instructions

## Quick Setup Guide

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Choose one of the following methods:

**Method 1: Interactive Setup Script (Recommended)**

```bash
./setup_api_key.sh
```

**Method 2: Manual Configuration**

```bash
cp env.example .env
# Edit .env file and replace 'your_gemini_api_key_here' with your actual API key
```

**Method 3: Environment Variable**

```bash
export GEMINI_API_KEY='your_api_key_here'
```

### 3. Verify Configuration

Test that your API key is configured correctly:

```bash
python3 load_api_key.py
```

If successful, you should see:
```
API key loaded successfully
Key preview: AIzaSy...XXXX
```

### 4. Run Your First Generation

```bash
python3 alpha_evolve_final.py --generation 1
```

## Getting Your API Key

1. Visit https://aistudio.google.com/app/apikey
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the generated key
5. Use it in one of the configuration methods above

## Troubleshooting

### API Key Not Found

If you see "API key not found" error:

1. Verify .env file exists: `ls -la .env`
2. Check .env file contains valid key (not 'your_gemini_api_key_here')
3. Try setting environment variable directly: `export GEMINI_API_KEY='your_key'`
4. Run verification: `python3 load_api_key.py`

### Import Errors

If you see import errors:

1. Verify dependencies: `pip list | grep google-generativeai`
2. Reinstall: `pip install -r requirements.txt --upgrade`
3. Check Python version: `python3 --version` (should be 3.9+)

### Permission Denied

If setup script fails:

```bash
chmod +x setup_api_key.sh
./setup_api_key.sh
```

## Security Notes

- Never commit your .env file to git
- The .env file is automatically ignored by .gitignore
- Never share your API key publicly
- Regenerate your API key if it's accidentally exposed



