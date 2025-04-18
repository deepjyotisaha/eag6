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
from memory.working_memory import ExecutionHistory
from desicion.desicion import DecisionMaker
from memory.user_memory import UserMemory
from planner.intent import IntentAnalyzer


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
    

async def _get_tools(math_session: ClientSession, gmail_session: ClientSession) -> List:
    """
    Retrieve and combine tools from math and gmail sessions.
        
    Args:
        math_session: Math server client session
        gmail_session: Gmail server client session
            
    Returns:
        List: Combined list of tools from both servers
    """
    try:
        # Get math tools
        logging.info("Requesting tool list...")
        tools_result = await math_session.list_tools()
        math_tools = tools_result.tools
        logging.info(f"Math server tools: {len(math_tools)}")
        for tool in math_tools:
            tool.server_session = math_session
        logging.info(f"Successfully retrieved {len(math_tools)} math tools")
        
        # Get gmail tools
        tools_result = await gmail_session.list_tools()
        gmail_tools = tools_result.tools
        logging.info(f"Gmail server tools: {len(gmail_tools)}")
        for tool in gmail_tools:
            tool.server_session = gmail_session
        logging.info(f"Successfully retrieved {len(gmail_tools)} gmail tools")

        # Combine tools
        tools = math_tools + gmail_tools
        logging.info(f"Combined tools: {len(tools)}")
        
        return tools
        
    except Exception as e:
        logging.error(f"Error getting tools: {e}")
        raise

# In your agent or main code:
async def setup_user_memory(user_memory: UserMemory, general_instructions: str, user_query: str):
    
    # Gather initial facts
    await user_memory.gather_initial_facts_for_query(user_query, general_instructions)
        
    # Recall information
    result = await user_memory.recall_query_specific_facts(
        "What does the user want to do? Include their preferences and requirements for the task, and any pontential ambiguities that were clarified."
    )
    if result:
        UserInteraction.show_information(f"Recall result: {json.dumps(result, indent=2)}")
    
    # Display current memory contents
    user_memory.print_facts(detailed=True)
    
    # Save memory for later
    #user_memory.save_to_file("user_memory.json")


async def agent_main():
    reset_state()  # Reset at the start of main
    logging.info("Starting main execution...")
    try:
                # Show startup information
        UserInteraction.show_information(
            "Initializing math agent...",
            "Startup"
        )

        # Initialize LLM
        llm_manager = LLMManager()
        llm_manager.initialize()

        # Initialize execution history
        execution_history = ExecutionHistory()
        user_memory = UserMemory(llm_manager)

        # Initialize planner with generate_with_timeout function
        planner = Planner(llm_manager)

        # Initialize action executor
        action_executor = ActionExecutor()
        
        # Initialize decision maker
        decision_maker = DecisionMaker()

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

        # Create MCP server connection
        async with stdio_client(math_server_params) as (math_read, math_write), \
            stdio_client(gmail_server_params) as (gmail_read, gmail_write):
            logging.info("Connection established, creating session...")
            async with ClientSession(math_read, math_write) as math_session, \
                ClientSession(gmail_read, gmail_write) as gmail_session:
                logging.info("Session created, initializing...")
                await math_session.initialize()
                await gmail_session.initialize()
                time.sleep(0.5)
            
                # Get tools using the new helper function
                try:
                    tools = await _get_tools(math_session, gmail_session)
                except Exception as e:
                    logging.error(f"Error getting tools: {e}")
                    raise
                
                # Create system prompt with available tools
                logging.info("Creating system prompt...")
                logging.info(f"Number of tools: {len(tools)}")
                
                try:
                    if tools:
                        tools_description = _create_tools_description(tools)
                except Exception as e:
                    logging.error(f"Error creating tools description: {e}")
                    tools_description = "Error loading tools"
                
                # Create system prompt
                logging.info("Created system prompt...")
                
                user_query = Config.DEFAULT_QUERIES["ascii_sum"]
                execution_history.user_query = user_query

                general_instructions = Config.GENERAL_INSTRUCTIONS.format(tools_description=tools_description)

                # Show startup information
                UserInteraction.show_information(
                    "Gathering initial facts...",
                )

                await setup_user_memory(
                    user_memory,
                    general_instructions,
                    user_query
                )

                user_memory.print_status()

                # Show startup information
                UserInteraction.show_information(
                    "Initial facts gathered, now analyzing intent...",
                )

                # In your main execution flow or planner
                intent_analyzer = IntentAnalyzer(llm_manager, user_memory)
                intent_analysis = await intent_analyzer.analyze_intent(
                    query=user_query
                )

                intent_analyzer.print_status(intent_analysis)

                # Use the analysis for planning
                UserInteraction.show_information(f"Primary Intent: {intent_analysis['primary_intent']}")
                UserInteraction.show_information(f"Required Knowledge: {intent_analysis['required_knowledge']}")
                UserInteraction.show_information(f"Execution Hints: {intent_analysis['execution_hints']}")
                UserInteraction.show_information(f"Complete Intent Analysis: {intent_analysis}")

                # Show startup information
                UserInteraction.show_information(
                    "Intent analysis complete, now generating plan...",
                )

                # Get the initial plan and confirmation using the planner
                plan = await planner.get_plan(
                    llm_manager,
                    tools,
                    general_instructions,
                    intent_analysis,
                    user_memory,
                    execution_history)
                
                if plan is None:
                    logging.info("Exiting due to plan abortion or error")
                    return
                
                logging.info("Starting execution with confirmed plan...")
 
                global iteration, last_response
                
                while iteration < max_iterations:
                    logging.info(f"\n--- Iteration {iteration + 1} ---")

                    # Print summary view
                    #execution_history.print_status()

                    # Print detailed view
                    #execution_history.print_status(detailed=True)

                    # Print JSON view
                    #execution_history.print_json()
                    
                    decision = await decision_maker.make_next_step_decision(
                        llm_manager, 
                        tools,
                        general_instructions, 
                        intent_analysis,
                        user_memory,
                        execution_history
                    )
                    if not decision:
                        break

                    logging.info(f"Decision: {decision}")
                        
                    if decision["step_type"] == "function_call":
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

                    elif decision["step_type"] == "user_interaction":   
                        # Execute tool
                        #Do nothing as the user interaction is handled by the desicion maker
                        #In future we can add a tool to handle the user interaction
                        result = decision
                        if result is None:
                            break
                        iteration_response.append(result)

                    elif decision["step_type"] == "final_answer":
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
    
    
