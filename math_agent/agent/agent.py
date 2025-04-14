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

# Get logger for this module
logging = setup_logging(__name__)

# Use logger in your code
#logging.debug("Debug message")
#logging.info("Info message")
#logging.error("Error message")

# Load environment variables from .env file
load_dotenv()

# Access your API key and initialize Gemini client correctly
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")

logging.info("Configuring Gemini API...")
try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(Config.MODEL_NAME)
    logging.info("Gemini API configured successfully")
except Exception as e:
    logging.error(f"Error configuring Gemini API: {str(e)}")
    raise

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

async def get_agent_plan(system_prompt: str, execution_history) -> Optional[Dict]:
    """
    Get the initial plan from LLM and seek user confirmation
    
    Args:
        system_prompt: The system prompt to use
        execution_history: Current execution history
        
    Returns:
        Optional[Dict]: The confirmed plan or None if aborted
    """
    logging.info("Generating initial plan...")
    
    try:
        # Generate plan from LLM
        plan_prompt = f"{system_prompt}\n\nPlease generate a plan for the following query: {execution_history.user_query}"
        response = await generate_with_timeout(plan_prompt)
        response_text = response.text

        logging.info(f"Plan prompt: {plan_prompt}")
        logging.info(f"Plan response: {response_text}")

        response_text = response_text.replace('```json', '').replace('```', '').strip()

        # Clean up the response text
        #cleaned_response = response_text
        #if cleaned_response.startswith("```json"):
        #    cleaned_response = cleaned_response[7:]  # Remove ```json prefix
        #if cleaned_response.endswith("```"):
        #    cleaned_response = cleaned_response[:-3]  # Remove ``` suffix
        #cleaned_response = cleaned_response.strip()
        
        try:
            # Parse the response to get the plan
            plan_data = json.loads(response_text)
            if plan_data.get("response_type") != "plan":
                raise ValueError("Expected plan response type")
            
            plan_steps = plan_data.get("steps", [])
            
            # Format plan for user display
            plan_display = "Proposed Plan:\n"
            for step in plan_steps:
                plan_display += f"\nStep {step['step_number']}:"
                plan_display += f"\n- Action: {step['description']}"
                plan_display += f"\n- Reasoning: {step['reasoning']}"
                plan_display += f"\n- Tool: {step.get('expected_tool', 'No tool specified')}"
            
            # Show plan to user and get confirmation
            choice, feedback = UserInteraction.get_confirmation(
                plan_display,
                "Please review the proposed plan. You can confirm to proceed, provide feedback to revise, or abort."
            )
            
            if choice == "confirm":
                logging.info("Plan confirmed by user")
                execution_history.plan = plan_data
                return plan_data
            elif choice == "redo":
                logging.info(f"User requested plan revision with feedback: {feedback}")
                # Add feedback to prompt and try again
                revised_prompt = f"{plan_prompt}\n\nRevision Request Feedback: {feedback}\n\nPlease generate a new plan based on the feedback."
                return await get_agent_plan(revised_prompt, execution_history)
            else:  # abort
                logging.info("Plan aborted by user")
                UserInteraction.show_information("Operation aborted by user", "Abort")
                return None
                
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse LLM response as JSON: {e}")
            UserInteraction.report_error(
                "Failed to generate a valid plan",
                "Plan Generation Error",
                f"The model response was not in the expected format: {str(e)}"
            )
            return None
            
    except Exception as e:
        logging.error(f"Error generating plan: {str(e)}")
        UserInteraction.report_error(
            "Failed to generate plan",
            "Plan Generation Error",
            str(e)
        )
        return None

async def generate_with_timeout(prompt, timeout=Config.TIMEOUT_SECONDS):
    """Generate content with a timeout"""
    logging.info("Starting LLM generation...")
    try:
        # Convert the synchronous generate_content call to run in a thread
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None, 
                lambda: model.generate_content(
                    contents=prompt
                )
            ),
            timeout=timeout
        )
        logging.info("LLM generation completed")
        return response
    except TimeoutError:
        logging.error("LLM generation timed out!")
        raise
    except Exception as e:
        logging.error(f"Error in LLM generation: {e}")
        raise

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

                plan = await get_agent_plan(system_prompt, execution_history)
                
                if plan is None:
                    logging.info("Exiting due to plan abortion or error")
                    return

                logging.info("Starting iteration loop...")
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
                        response = await generate_with_timeout(prompt)
                        response_text = response.text.strip()
                        logging.info(f"LLM Response: {response_text}")
                        #logging.info(f"############# Going to parse JSON ##############")
                        
                        # Parse JSON response
                        try:
                            logging.info("######################### Received execution plan: #########################")
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
                            
                            #if response_type == "plan":
                                # Log the plan
                            #    logging.info("######################### Received execution plan: #########################")
                            #    for step in response_json.get("steps", []):
                            #        logging.info(f"Step {step['step_number']}: {step['description']}")
                            #        logging.info(f"Reasoning: {step['reasoning']}")
                            #        logging.info(f"Expected tool: {step['expected_tool']}")
                            #    execution_history.plan = response_json
                            #    #logging.info(f"######################### Plan stored in execution history: {json.dumps(execution_history.plan, indent=2)} #########################")
                            #    logging.info("######################### End of execution plan: #########################")
                            #    #continue  # Move to next iteration for actual execution
                                
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
    
    
