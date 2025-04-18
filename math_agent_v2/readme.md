# Math Agent v2 - Intelligent Mathematical Problem Solving Assistant

## Overview
Math Agent v2 is an intelligent agent designed to assist users, particularly those with visual impairments, in solving mathematical problems. The agent combines advanced language models, visual representation capabilities, and email communication to provide a comprehensive problem-solving experience.

## Key Features
- **Intelligent Problem Solving**: Uses Gemini AI to analyze and solve mathematical problems
- **Visual Representation**: Draws solutions on Microsoft Paint with accessibility considerations
- **Email Communication**: Sends detailed solution reports with step-by-step explanations
- **Adaptive Interface**: Adjusts output based on user preferences and accessibility needs
- **Memory Management**: Maintains user preferences and problem-solving history
- **Real-time Feedback**: Interactive confirmation and feedback system

## System Architecture

### Core Components
1. **Agent Module** (`agent/`)
   - Main execution logic
   - Tool coordination
   - State management

2. **LLM Integration** (`llm/`)
   - Gemini AI integration
   - Response parsing and validation
   - Timeout handling

3. **Planning System** (`planner/`)
   - Task decomposition
   - Intent analysis
   - Execution planning

4. **Decision Making** (`desicion/`)
   - Next step determination
   - User feedback processing
   - Execution flow control

5. **Memory Management** (`memory/`)
   - User preferences storage
   - Working memory management
   - Execution history tracking

6. **User Interaction** (`userinteraction/`)
   - Console-based UI
   - Rich text formatting
   - User input handling

7. **MCP Servers** (`mcp_server/`)
   - Math operations server
   - Gmail integration server
   - Display server for visual output

### Configuration System
- **Environment Settings** (`.env`)
- **Display Configuration** (`config/mcp_display_server_config.py`)
- **MCP Server Settings** (`config/mcp_server_config.py`)
- **Logging Configuration** (`config/log_config.py`)

## Installation

### Prerequisites
- Python 3.8+
- Windows OS (for Paint integration)
- Gmail API access
- Gemini API access

### Required Python Packages
```bash
pip install rich
pip install google-generativeai
pip install pyautogui
pip install pillow
pip install mouseinfo
pip install google-auth-oauthlib
pip install google-auth-httplib2
pip install google-api-python-client
pip install beautifulsoup4
```

### Setup Steps

1. **Environment Configuration**
   ```bash
   # Create .env file with:
   GOOGLE_API_KEY=your_gemini_api_key_here
   ```

2. **Gmail API Setup**
   - Create `.google` directory in project root
   - Add Gmail API credentials in `.google/client_creds.json`
   - Configure app tokens in `.google/app_tokens.json`

3. **Display Configuration**
   - Adjust `config/mcp_display_server_config.py` based on your monitor setup
   - Configure canvas dimensions and positions

## Usage

### Starting the System
1. Start the Gmail MCP server:
   ```bash
   python mcp_server/gmail_mcp_server/src/gmail/gmail_mcp_server.py
   ```

2. Launch the main application:
   ```bash
   python main.py
   ```

### User Interaction
- Follow the interactive prompts for problem input
- Confirm or provide feedback on proposed solutions
- View results on Microsoft Paint canvas
- Receive detailed email reports

## Development Tools

### Debugging
- Rich console output for development
- Comprehensive logging system
- Inspector mode for Gmail server:
  ```bash
  npx @modelcontextprotocol/inspector python mcp_server/gmail_mcp_server/src/gmail/gmail_mcp_server.py
  ```

### Configuration Options
Customize behavior in `config/config.py`:
- `MAX_ITERATIONS`: Maximum problem-solving iterations
- `TIMEOUT_SECONDS`: Operation timeout duration
- `MODEL_NAME`: Gemini model selection
- `LOG_LEVEL`: Logging verbosity
- `GENERAL_INSTRUCTIONS`: Agent behavior guidelines

## System Capabilities

### Mathematical Operations
- Basic arithmetic
- Complex calculations
- Step-by-step problem solving
- Result verification

### Visual Representation
- Canvas drawing
- Text formatting
- Color contrast adjustment
- Position optimization

### Email Communication
- HTML formatted reports
- Step-by-step explanations
- Result visualization
- Audit trail

## Error Handling
- Input validation
- Operation timeout management
- API error recovery
- User feedback integration

## Known Limitations
1. Function call repetition issues
2. Canvas size constraints
3. Screen resolution dependencies
4. Font size optimization needed

## Contributing
1. Fork the repository
2. Create a feature branch
3. Submit pull request with detailed description
4. Follow existing code style and documentation patterns

## License
MIT License - See LICENSE file for details

## Support
- Report issues via GitHub
- Contact maintainers for major concerns
- Check documentation for common solutions
