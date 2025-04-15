import os
import sys
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import asyncio
import google.generativeai as genai
from concurrent.futures import TimeoutError
from functools import partial
import sys
from datetime import datetime
from config.config import Config
import time
import json
from userinteraction.console_ui import UserInteraction
from typing import Optional, Dict, List

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config.mcp_server_config import MCP_SERVER_CONFIG
from config.log_config import setup_logging
from llm.llm import LLMManager
from planner.planner import Planner
from action.action import ActionExecutor
from memory.working_memory import ExecutionHistory  # Updated import path



# Get logger for this module
logging = setup_logging(__name__)

# Use logger in your code
#logging.debug("Debug message")
#logging.info("Info message")
#logging.error("Error message")

max_iterations = Config.MAX_ITERATIONS
last_response = None
iteration = 0
iteration_response = []


def reset_state():
    """Reset all global variables to their initial state"""
    global last_response, iteration, iteration_response
    last_response = None
    iteration = 0
    iteration_response = []
    
    # Reset execution history
    execution_history = ExecutionHistory()

def _create_tools_description(tools: List) -> str:
    """
    Create a complete description of all available tools.
        
    Args:
        tools: List of tool objects
            
    Returns:
        str: Combined tool descriptions
    """
    try:
        tools_description = []
        for i, tool in enumerate(tools):
            try:
                # Get tool properties
                params = tool.inputSchema
                desc = getattr(tool, 'description', 'No description available')
                name = getattr(tool, 'name', f'tool_{i}')
                    
                # Format the input schema
                if 'properties' in params:
                    param_details = []
                    for param_name, param_info in params['properties'].items():
                        param_type = param_info.get('type', 'unknown')
                        param_details.append(f"{param_name}: {param_type}")
                    params_str = ', '.join(param_details)
                else:
                    params_str = 'no parameters'

                tool_desc = f"{i+1}. {name}({params_str}) - {desc}"
                tools_description.append(tool_desc)
                logging.info(f"Added description for tool: {tool_desc}")
            except Exception as e:
                logging.error(f"Error processing tool {i}: {e}")
                tools_description.append(f"{i+1}. Error processing tool")
            
        combined_description = "\n".join(tools_description)
        logging.info("Successfully created tools description")
        return combined_description
    except Exception as e:
        logging.error(f"Error creating tools description: {e}")
        return "Error loading tools"


async def _make_next_step_decision(llm_manager: LLMManager, system_prompt: str, tools: List) -> Optional[Dict]:
    """
    Make a decision about the next step to execute using LLM and user confirmation.
    
    Args:
        llm_manager: LLM manager instance
        system_prompt: Current system prompt
        tools: Available tools list
        
    Returns:
        Optional[Dict]: Processed decision with tool execution info, or None if should terminate
    """
    try:
        logging.info("Determining next execution step...")
        
        # Get LLM's decision with timeout
        response = await llm_manager.generate_with_timeout(system_prompt)
        response_text = response.text.strip()
        logging.info(f"LLM Response: {response_text}")
        
        # Clean and parse response
        cleaned_response = response_text
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()
        
        response_json = json.loads(cleaned_response)
        response_type = response_json.get("response_type")
        
        # Handle different response types
        if response_type == "function_call":
            function_info = response_json.get("function", {})
            func_name = function_info.get("name")
            reasoning = function_info.get("reasoning", "No reasoning provided")
            
            # Verify tool exists
            tool = next((t for t in tools if t.name == func_name), None)
            if not tool:
                UserInteraction.report_error(
                    f"Unknown tool: {func_name}",
                    "Tool Error",
                    "The selected tool does not exist"
                )
                return None
            
            # Show decision to user and get confirmation
            decision_msg = (
                f"Proposed Next Step:\n"
                f"Tool: {func_name}\n"
                f"Parameters: {function_info.get('parameters', {})}\n"
                f"Reasoning: {reasoning}"
            )
            
            choice, feedback = UserInteraction.get_confirmation(
                decision_msg,
                "Do you want to proceed with this step?"
            )
            
            if choice == "confirm":
                logging.info("User confirmed decision")
                return {
                    "type": "function_call",
                    "tool": tool,
                    "function_info": function_info
                }
            elif choice == "redo":
                logging.info(f"User requested revision with feedback: {feedback}")
                # Add feedback to prompt and try again
                revised_prompt = f"{system_prompt}\n\nRevision Request Feedback: {feedback}\n\n Determine the next step to execute considering the feedback"
                return await _make_next_step_decision(llm_manager, revised_prompt, tools)
            else:  # abort
                logging.info("User aborted execution")
                return None
                
        elif response_type == "final_answer":
            # Show final answer to user for confirmation
            final_msg = (
                f"Execution Complete\n"
                f"Result: {response_json.get('result')}\n"
                f"Summary: {response_json.get('summary')}"
            )
            
            choice, feedback = UserInteraction.get_confirmation(
                final_msg,
                "Is this final result acceptable?"
            )
            
            if choice == "confirm":
                return {
                    "type": "final_answer",
                    "response": response_json
                }
            elif choice == "redo":
                # Continue execution with feedback
                revised_prompt = f"{system_prompt}\n\nFinal Result Feedback: {feedback}"
                return await _make_next_step_decision(llm_manager, revised_prompt, tools)
            else:
                return None
                
        else:
            UserInteraction.report_error(
                "Invalid response type",
                "Decision Error",
                f"Unexpected response type: {response_type}"
            )
            return None
            
    except json.JSONDecodeError as e:
        UserInteraction.report_error(
            "Failed to parse LLM response",
            "Parse Error",
            str(e)
        )
        return None
    except Exception as e:
        UserInteraction.report_error(
            "Error in decision making",
            "Decision Error",
            str(e)
        )
        return None


async def agent_main():
    reset_state()  # Reset at the start of main
    logging.info("Starting main execution...")
    try:
                # Show startup information
        UserInteraction.show_information(
            "Initializing math agent...",
            "Startup"
        )

        # Initialize execution history
        execution_history = ExecutionHistory()
        
        # Initialize LLM
        llm_manager = LLMManager()
        llm_manager.initialize()

        # Initialize planner with generate_with_timeout function
        planner = Planner(llm_manager)

        action_executor = ActionExecutor()

        # Create a single MCP server connection
        logging.info("Establishing connection to MCP server...")
        
        math_server_params = StdioServerParameters(
            command=MCP_SERVER_CONFIG["math_server"]["command"],
            args=[MCP_SERVER_CONFIG["math_server"]["script_path"]]
        )

        gmail_server_params = StdioServerParameters(
            command=MCP_SERVER_CONFIG["gmail_server"]["command"],
            args=[
                MCP_SERVER_CONFIG["gmail_server"]["script_path"],
                f"--creds-file-path={MCP_SERVER_CONFIG['gmail_server']['creds_file_path']}",
                f"--token-path={MCP_SERVER_CONFIG['gmail_server']['token_path']}"
            ]
        )


        async with stdio_client(math_server_params) as (math_read, math_write), \
            stdio_client(gmail_server_params) as (gmail_read, gmail_write):
            logging.info("Connection established, creating session...")
            async with ClientSession(math_read, math_write) as math_session, \
                ClientSession(gmail_read, gmail_write) as gmail_session:
                logging.info("Session created, initializing...")
                await math_session.initialize()
                await gmail_session.initialize()
                time.sleep(0.5)
                
                # Get available tools
                logging.info("Requesting tool list...")
                tools_result = await math_session.list_tools()
                math_tools = tools_result.tools
                logging.info(f"Math server tools: {len(math_tools)}")
                for tool in math_tools:
                    tool.server_session = math_session
                logging.info(f"Successfully retrieved {len(math_tools)} math tools")
              

                tools_result = await gmail_session.list_tools()
                gmail_tools = tools_result.tools
                logging.info(f"Gmail server tools: {len(gmail_tools)}")
                for tool in gmail_tools:
                    tool.server_session = gmail_session
                logging.info(f"Successfully retrieved {len(gmail_tools)} gmail tools")

                # Combine tools (extend the list instead of adding sessions)
                tools = math_tools + gmail_tools
        
                logging.info(f"Combined tools: {len(tools)}")
               
                # Create system prompt with available tools
                logging.info("Creating system prompt...")
                logging.info(f"Number of tools: {len(tools)}")
                
                try:
                    # First, let's inspect what a tool object looks like
                    if tools:
                        #print(f"First tool properties: {dir(tools[0])}")
                        #print(f"First tool example: {tools[0]}")                    
                        tools_description = []
                        tools_description = _create_tools_description(tools)
                except Exception as e:
                    logging.error(f"Error creating tools description: {e}")
                    tools_description = "Error loading tools"

                
                logging.info("Created system prompt...")
                
                execution_history.user_query = Config.DEFAULT_QUERIES["ascii_sum"]

                system_prompt = Config.SYSTEM_PROMPT.format(tools_description=tools_description, execution_history=execution_history)
                
                # Get the initial plan and confirmation using the planner
                plan = await planner.get_plan(system_prompt, execution_history)
                
                if plan is None:
                    logging.info("Exiting due to plan abortion or error")
                    return
                
                logging.info("Starting execution with confirmed plan...")
 
                global iteration, last_response
                
                while iteration < max_iterations:
                    logging.info(f"\n--- Iteration {iteration + 1} ---")
                    
                    # Get next step decision
                    system_prompt = Config.SYSTEM_PROMPT.format(
                        tools_description=tools_description, 
                        execution_history=execution_history
                    )
                    
                    decision = await _make_next_step_decision(llm_manager, system_prompt, tools)
                    if not decision:
                        break
                        
                    if decision["type"] == "function_call":
                        # Execute tool
                        result = await action_executor.execute_tool(
                            decision["tool"], 
                            decision["function_info"], 
                            tools, 
                            execution_history
                        )
                        if result is None:
                            break
                        iteration_response.append(result)
                            
                    elif decision["type"] == "final_answer":
                        logging.info("\n=== Agent Execution Complete ===")
                        execution_history.final_answer = decision["response"]
                        break
                        
                    iteration += 1

    except Exception as e:
        logging.error(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        reset_state()  # Reset at the end of main



if __name__ == "__main__":
    asyncio.run(agent_main())
    
    
