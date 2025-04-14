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

class ExecutionHistory:
    def __init__(self):
        self.plan = None
        self.steps = []
        self.final_answer = None
        self.user_query = None

execution_history = ExecutionHistory()

def reset_state():
    """Reset all global variables to their initial state"""
    global last_response, iteration, iteration_response
    last_response = None
    iteration = 0
    iteration_response = []
    
    # Reset execution history
    execution_history = ExecutionHistory()


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

        # Initialize planner with generate_with_timeout function
        planner = Planner(llm_manager)

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
                    # if tools:
                    #     print(f"First tool properties: {dir(tools[0])}")
                    #     print(f"First tool example: {tools[0]}")
                    
                    tools_description = []
                    for i, tool in enumerate(tools):
                        try:
                            # Get tool properties
                            params = tool.inputSchema
                            desc = getattr(tool, 'description', 'No description available')
                            name = getattr(tool, 'name', f'tool_{i}')
                            
                            # Format the input schema in a more readable way
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
                    
                    tools_description = "\n".join(tools_description)
                    logging.info("Successfully created tools description")
                except Exception as e:
                    logging.error(f"Error creating tools description: {e}")
                    tools_description = "Error loading tools"
                
                logging.info("Created system prompt...")
                
                execution_history.user_query = Config.DEFAULT_QUERIES["ascii_sum"]
                #system_prompt = Config.SYSTEM_PROMPT.format(tools_description=tools_description, execution_history=execution_history)

                #logging.info("Generating Plan...")
                #plan_query = Config.PLAN_QUERY
                #plan_prompt = f"{system_prompt}\n\nQuery: {plan_query}"
                #logging.debug(f"Plan prompt: {plan_prompt}")

                #response = await generate_with_timeout(prompt)
                #response_text = response.text.strip()
                #logging.info(f"LLM Response for Plan: {response_text}")
                system_prompt = Config.SYSTEM_PROMPT.format(tools_description=tools_description, execution_history=execution_history)

                # Get the initial plan and confirmation using the planner
                plan = await planner.get_plan(system_prompt, execution_history)
                
                if plan is None:
                    logging.info("Exiting due to plan abortion or error")
                    return
                

                logging.info("Starting execution with confirmed plan...")
                #logging.debug(f"Query: {query}")
                #logging.debug(f"System prompt: {system_prompt}")
                
                # Use global iteration variables
                global iteration, last_response
                
                while iteration < max_iterations:
                    logging.info(f"\n--- Iteration {iteration + 1} ---")
                    
                    #if last_response is None:
                    #    current_query = query
                    #else:
                        #current_query = current_query + "\n\n" + " ".join(iteration_response)
                        #current_query = current_query + "  What should I do next?"

                    # Get model's response with timeout
                    logging.info("Preparing to generate LLM response...")
                    #prompt = f"{system_prompt}\n\nQuery: {current_query}"
                    #prompt = f"{system_prompt}\n\nQuery: {execution_history.user_query}"
                    system_prompt = Config.SYSTEM_PROMPT.format(tools_description=tools_description, execution_history=execution_history)
                    prompt = system_prompt
                    #logging.debug(f"Prompt: {prompt}")
                    try:
                        response = await llm_manager.generate_with_timeout(prompt)
                        response_text = response.text.strip()
                        logging.info(f"LLM Response: {response_text}")
                        #logging.info(f"############# Going to parse JSON ##############")
                        
                        # Parse JSON response
                        try:

                            # Clean up the response text
                            cleaned_response = response_text
                            if cleaned_response.startswith("```json"):
                                cleaned_response = cleaned_response[7:]  # Remove ```json prefix
                            if cleaned_response.endswith("```"):
                                cleaned_response = cleaned_response[:-3]  # Remove ``` suffix
                            cleaned_response = cleaned_response.strip()
                            
                            #logging.info(f"Cleaned response for parsing: {cleaned_response}")
                            response_json = json.loads(cleaned_response)
                            response_type = response_json.get("response_type")
                                
                            if response_type == "function_call":
                                # Extract function call details
                                function_info = response_json.get("function", {})
                                func_name = function_info.get("name")
                                parameters = function_info.get("parameters", {})
                                reasoning_tag = function_info.get("reasoning_tag")
                                reasoning = function_info.get("reasoning")
                                
                                logging.info(f"\nDEBUG: Function call: {func_name}")
                                logging.info(f"DEBUG: Parameters: {parameters}")
                                logging.info(f"DEBUG: Reasoning tag: {reasoning_tag}")
                                logging.info(f"DEBUG: Reasoning: {reasoning}")

                                try:
                                    # Find the matching tool to get its input schema
                                    tool = next((t for t in tools if t.name == func_name), None)
                                    if not tool:
                                        logging.info(f"DEBUG: Available tools: {[t.name for t in tools]}")
                                        raise ValueError(f"Unknown tool: {func_name}")

                                    logging.info(f"DEBUG: Found tool: {tool.name}")
                                    logging.info(f"DEBUG: Tool schema: {tool.inputSchema}")

                                    # Get the correct session from the tool
                                    session = tool.server_session
                                    if not session:
                                        raise ValueError(f"No session found for tool: {func_name}")

                                    # Prepare arguments according to the tool's input schema
                                    arguments = {}
                                    schema_properties = tool.inputSchema.get('properties', {})
                                    logging.info(f"DEBUG: Schema properties: {schema_properties}")

                                    # Convert parameters dictionary to a list of values
                                    params = list(parameters.values())
                                    logging.info(f"DEBUG: Parameters list: {params}")

                                    for param_name, param_info in schema_properties.items():
                                        if not params:  # Check if we have enough parameters
                                            raise ValueError(f"Not enough parameters provided for {func_name}")
                                        
                                        value = params.pop(0)  # Get and remove the first parameter
                                        param_type = param_info.get('type', 'string')

                                        logging.info(f"DEBUG: Converting parameter {param_name} with value {value} to type {param_type}")
                                        # Convert the value to the correct type based on the schema
                                        if param_type == 'integer':
                                            arguments[param_name] = int(value)
                                        elif param_type == 'number':
                                            arguments[param_name] = float(value)
                                        elif param_type == 'array':
                                            # Handle array input
                                            if isinstance(value, str):
                                                # If it's a string, parse it
                                                value = value.strip('[]').split(',')
                                                arguments[param_name] = [int(x.strip()) for x in value]
                                            elif isinstance(value, list):
                                                # If it's a list, check if it's nested
                                                if len(value) > 0 and isinstance(value[0], list):
                                                    # If nested, use the first list
                                                    arguments[param_name] = value[0]
                                                else:
                                                    # If not nested, use as is
                                                    arguments[param_name] = value
                                            else:
                                                # If it's neither string nor list, raise error
                                                raise ValueError(f"Invalid array parameter: {value}")

                                            logging.info(f"DEBUG: Final array value: {arguments[param_name]}")
                                        else:
                                            arguments[param_name] = str(value)

                                    logging.info(f"DEBUG: Final arguments: {arguments}")
                                    logging.info(f"DEBUG: Calling tool {func_name}")

                                    # Execute the tool with our converted arguments
                                    result = await session.call_tool(func_name, arguments=arguments)
                                    logging.info(f"DEBUG: Raw result: {result}")
                                    
                                    # Process result
                                    if hasattr(result, 'content'):
                                        if isinstance(result.content, list):
                                            iteration_result = [
                                                item.text if hasattr(item, 'text') else str(item)
                                                for item in result.content
                                            ]
                                        else:
                                            iteration_result = str(result.content)
                                    else:
                                        iteration_result = str(result)
                                        
                                    # Store execution details
                                    execution_history.steps.append({
                                        "step_number": len(execution_history.steps) + 1,
                                        "function": func_name,
                                        "parameters": parameters,
                                        "reasoning_tag": reasoning_tag,
                                        "reasoning": reasoning,
                                        "result": iteration_result
                                    })

                                except Exception as e:
                                    logging.error(f"DEBUG: Error details: {str(e)}")
                                    logging.error(f"DEBUG: Error type: {type(e)}")
                                    import traceback
                                    traceback.print_exc()
                                    iteration_response.append(f"Error in iteration {iteration + 1}: {str(e)}")
                                    break

                            elif response_type == "final_answer":
                                logging.info("\n=== Agent Execution Complete ===")
                                logging.info(f"Final Result: {response_json.get('result')}")
                                logging.info(f"Summary: {response_json.get('summary')}")
                                execution_history.final_answer = response_json
                                break
                                
                        except json.JSONDecodeError:
                            logging.error("Failed to parse JSON response")
                            break

                    except Exception as e:
                        logging.error(f"Failed to get LLM response: {e}")
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
    
    
