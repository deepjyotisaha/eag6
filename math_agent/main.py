import asyncio
from agent.agent import agent_main
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config.mcp_server_config import MCP_SERVER_CONFIG
from config.log_config import setup_logging

# Get logger for this module
logging = setup_logging(__name__)

# Use logger in your code
#logging.debug("Debug message")
#logging.info("Info message")
#logging.error("Error message")

if __name__ == "__main__":
    try:
        asyncio.run(agent_main())
    except KeyboardInterrupt:
        logging.info("\nAgent execution stopped by user")
    except Exception as e:
        logging.error(f"Error during agent execution: {str(e)}")