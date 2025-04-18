from typing import Optional, Dict, List
import logging
import traceback
from userinteraction.console_ui import UserInteraction
from memory.working_memory import ExecutionHistory  
import ast

class ActionExecutor:
    """
    Handles the execution of tools and actions in the math agent system.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def parse_function_call_params(param_parts: list[str]) -> dict:
        """
        Parses key=value parts from the FUNCTION_CALL format.
        Supports nested keys like input.string=foo and list values like input.int_list=[1,2,3]
        Returns a nested dictionary.
        """
        result = {}

        logging.info(f"Parsing function call parameters: {param_parts}")

        for part in param_parts:
            if "=" not in part:
                raise ValueError(f"Invalid parameter format (expected key=value): {part}")

            key, value = part.split("=", 1)

            # Try to parse as Python literal (int, float, list, etc.)
            try:
                parsed_value = ast.literal_eval(value)
            except Exception:
                parsed_value = value.strip()

            # Support nested keys like input.string
            keys = key.split(".")
            current = result
            for k in keys[:-1]:
                current = current.setdefault(k, {})
            current[keys[-1]] = parsed_value

        return result

    @staticmethod
    def _convert_parameter(param_name: str, value: any, param_type: str) -> any:
        """
        Convert a parameter value to the specified type.
        """
        try:
            if param_type == 'integer':
                return int(value)
            elif param_type == 'number':
                return float(value)
            elif param_type == 'array':
                if isinstance(value, str):
                    value = value.strip('[]').split(',')
                    return [int(x.strip()) for x in value]
                elif isinstance(value, list):
                    return value[0] if len(value) > 0 and isinstance(value[0], list) else value
                else:
                    raise ValueError(f"Invalid array parameter: {value}")
            else:
                return str(value)
        except (ValueError, TypeError) as e:
            UserInteraction.report_error(
                f"Parameter conversion error for {param_name}",
                "Type Error",
                f"Failed to convert value '{value}' to type {param_type}: {str(e)}"
            )
            raise

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
            logging.info(f"Executing tool: {tool.name}")
            logging.info(f"Function info: {function_info}")

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


            logging.info(f"Found tool: {tool.name}")
            logging.info(f"Tool schema: {tool.inputSchema}")
            logging.info(f"Parameters: {parameters}")

            
            #arguments = ActionExecutor.parse_function_call_params(parameters)
            arguments = parameters

            logging.info(f"Final arguments: {arguments}")
            logging.info(f"Calling tool {func_name}")
            
            logging.info(f"Arguments: {arguments}")

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