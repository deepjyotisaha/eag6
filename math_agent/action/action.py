from typing import Optional, Dict, List
import logging
import traceback
from userinteraction.console_ui import UserInteraction
from memory.working_memory import ExecutionHistory  

class ActionExecutor:
    """
    Handles the execution of tools and actions in the math agent system.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @staticmethod
    async def execute_tool(tool, function_info: Dict, tools: List, execution_history: ExecutionHistory) -> Optional[str]:
        """
        Execute a tool and update execution history with the results.
        
        Args:
            tool: The tool object to execute
            function_info: Dictionary containing function call details
            tools: List of available tools
            execution_history: ExecutionHistory object to track execution
            
        Returns:
            Optional[str]: The result of the tool execution, or None if there was an error
        """
        try:
            # Extract function call details
            func_name = function_info.get("name")
            parameters = function_info.get("parameters", {})
            reasoning_tag = function_info.get("reasoning_tag")
            reasoning = function_info.get("reasoning")
            
            # Inform user about the tool being executed
            UserInteraction.show_information(
                f"Executing tool: {func_name}\nParameters: {parameters}\nReasoning: {reasoning}",
                "Tool Execution"
            )
            
            # Verify tool session
            session = tool.server_session
            if not session:
                UserInteraction.report_error(
                    f"No session found for tool: {func_name}",
                    "Session Error"
                )
                raise ValueError(f"No session found for tool: {func_name}")

            # Prepare arguments according to tool's input schema
            arguments = {}
            schema_properties = tool.inputSchema.get('properties', {})
            params = list(parameters.values())

            # Process each parameter according to schema
            for param_name, param_info in schema_properties.items():
                if not params:
                    UserInteraction.report_error(
                        f"Not enough parameters provided for {func_name}",
                        "Parameter Error",
                        f"Required parameter '{param_name}' is missing"
                    )
                    raise ValueError(f"Not enough parameters provided for {func_name}")
                
                value = params.pop(0)
                param_type = param_info.get('type', 'string')

                # Convert parameter to correct type
                try:
                    if param_type == 'integer':
                        arguments[param_name] = int(value)
                    elif param_type == 'number':
                        arguments[param_name] = float(value)
                    elif param_type == 'array':
                        if isinstance(value, str):
                            value = value.strip('[]').split(',')
                            arguments[param_name] = [int(x.strip()) for x in value]
                        elif isinstance(value, list):
                            arguments[param_name] = value[0] if len(value) > 0 and isinstance(value[0], list) else value
                        else:
                            raise ValueError(f"Invalid array parameter: {value}")
                    else:
                        arguments[param_name] = str(value)
                except (ValueError, TypeError) as e:
                    UserInteraction.report_error(
                        f"Parameter conversion error for {param_name}",
                        "Type Error",
                        f"Failed to convert value '{value}' to type {param_type}: {str(e)}"
                    )
                    raise

            # Execute the tool
            result = await session.call_tool(func_name, arguments=arguments)
            
            # Process and format the result
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

            # Update execution history
            step_info = {
                "step_number": execution_history.get_step_count() + 1,
                "function": func_name,
                "parameters": parameters,
                "reasoning_tag": reasoning_tag,
                "reasoning": reasoning,
                "result": iteration_result
            }
            execution_history.add_step(step_info)

            # Show successful execution result to user
            UserInteraction.show_information(
                f"Tool execution successful!\n\n"
                f"Result: {iteration_result}\n\n"
                f"Step Details:\n"
                f"- Function: {func_name}\n"
                f"- Reasoning: {reasoning}\n"
                f"- Step Number: {step_info['step_number']}\n"
                f"- Total Steps: {execution_history.get_step_count()}",
                "Execution Success"
            )

            return iteration_result

        except Exception as e:
            # Log the error
            logging.error(f"Error executing tool {func_name}: {str(e)}")
            logging.error(f"Error type: {type(e)}")
            
            # Get detailed error information
            error_details = traceback.format_exc()
            
            # Report error to user
            UserInteraction.report_error(
                f"Error executing tool: {func_name}",
                "Execution Error",
                f"Error: {str(e)}\n\nDetails:\n{error_details}"
            )
            
            return None