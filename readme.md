# Math Agent with Visual and Email Support

This project implements a math agent that can solve mathematical problems, display results visually on a canvas, and send the results via email. It uses the Model Context Protocol (MCP) to communicate with both a math server and a Gmail server.

## Features

- Mathematical problem solving using specialized tools
- Visual display of results on a canvas
- Email notifications of results
- Support for visually impaired users
- Integration with Gmail MCP server for email functionality

## Prerequisites

- Python 3.x
- Gmail API credentials
- Gemini API key
- Required Python packages:
  ```bash
  pip install pyautogui
  pip install pillow
  pip install mouseinfo
  ```

## Setup

1. Create a `.env` file in the project root with your Gemini API key:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```

2. Set up Gmail API credentials:
   - Place your Gmail API credentials in `.google/client_creds.json`
   - Place your app tokens in `.google/app_tokens.json`

## Running the Application

1. Start the Gmail MCP server:
   ```bash
   python .\gmail-mcp-server\src\gmail\server.py
   ```

2. Run the main application:
   ```bash
   python mcp_client.py
   ```

## Development Tools

### Inspector Mode
To run the Gmail server in inspector mode:
```bash
npx @modelcontextprotocol/inspector python gmail-mcp-server\\src\\gmail\\server.py --creds-file-path .google\\client_creds.json --token-path .google\\app_tokens.json
```

## Known Issues

1. Calling the int_list_to_exponential_sum twice
2. Rectangle size is small
3. Need to check pass the screen size and inform about the canvas size with drawing instructions
4. Need to increase the font size and formatting

## Configuration

The application can be configured through `config.py`:
- `MAX_ITERATIONS`: Maximum number of iterations for problem solving
- `TIMEOUT_SECONDS`: Timeout for operations
- `MODEL_NAME`: Name of the Gemini model to use
- `LOG_LEVEL`: Logging level
- `EMAIL`: Email address for notifications
- `LAPTOP_MONITOR`: Monitor configuration settings

## Dependencies

- [Gmail MCP Server](https://github.com/jasonsum/gmail-mcp-server/tree/main)
- PyAutoGUI for GUI automation
- Pillow for image processing
- Gemini API for language model capabilities

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License - see the LICENSE file for details.
