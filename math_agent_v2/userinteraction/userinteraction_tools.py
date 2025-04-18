import inspect
from typing import List, Dict, Optional
import ast
import docstring_parser
import logging
import inspect
from typing import List, Dict, Optional
import ast
import docstring_parser
from userinteraction.console_ui import UserInteraction


def format_tools_for_llm_prompt(tools: List[Dict]) -> str:
    """
    Format tool descriptions into a clear, structured prompt for LLM consumption.
    """
    prompt_parts = [
        "# Available User Interaction Tools\n",
        "You can use the following tools to interact with the user:\n"
    ]

    for tool in tools:
        # Tool header with name and description
        tool_section = [
            f"## {tool['name']}\n",
            f"{tool['description']}\n"
        ]

        # Parameters section
        if tool['parameters']:
            tool_section.append("\nParameters:")
            for param_name, param_info in tool['parameters'].items():
                required_str = "Required" if param_info['required'] else "Optional"
                param_type = param_info['type'].replace("typing.", "")  # Clean up typing prefixes
                
                param_desc = f"\n- {param_name} ({param_type}): {param_info['description']}"
                if not param_info['required'] and 'default' in param_info:
                    default_val = f'"{param_info["default"]}"' if isinstance(param_info["default"], str) else param_info["default"]
                    param_desc += f" (Default: {default_val})"
                param_desc += f" [{required_str}]"
                tool_section.append(param_desc)

        # Returns section
        tool_section.append("\nReturns:")
        if tool['returns']:
            return_type = tool['returns']['type'].replace("typing.", "")
            tool_section.append(f"- Type: {return_type}")
            tool_section.append(f"- Description: {tool['returns']['description']}")
        else:
            tool_section.append("- None (displays information only)")

        # Example usage section
        tool_section.extend([
            "\nExample usage:",
            "```json",
            "{",
            '  "llm_response_type": "user_interaction",',
            '  "function": {',
            f'    "name": "{tool["name"]}",',
            '    "parameters": {',
        ])

        # Add example parameters
        example_params = {}
        for param_name, param_info in tool['parameters'].items():
            if param_info['required']:
                if param_info['type'] == 'str':
                    example_params[param_name] = f"your {param_name} here"
                else:
                    example_params[param_name] = f"<{param_info['type']}>"

        # Format example parameters as JSON
        param_lines = [f'      "{k}": "{v}"' for k, v in example_params.items()]
        tool_section.append("      " + ",\n      ".join(param_lines))
        
        tool_section.extend([
            "    },",
            '    "reasoning_tag": "<REASONING_TAG>",',
            '    "reasoning": "<explanation of why this interaction is needed>",',
            '    "confidence": "<confidence level>"',
            "  }",
            "}",
            "```\n"
        ])

        # Add usage notes if there are special considerations
        if tool['name'] == 'get_confirmation':
            tool_section.extend([
                "Note: This tool returns one of:",
                "- ('confirm', '') - User confirmed the action",
                "- ('redo', 'feedback') - User wants to redo with feedback",
                "- ('abort', '') - User wants to abort the operation\n"
            ])
        
        prompt_parts.append("\n".join(tool_section))
        prompt_parts.append("\n" + "-"*50 + "\n")  # Separator between tools

    # Add final usage instructions
    prompt_parts.extend([
        "\n## How to Use These Tools",
        "1. Choose the appropriate tool based on the type of interaction needed",
        "2. Provide all required parameters",
        "3. Format your response as a JSON object with 'function' and 'parameters' fields",
        "4. Always handle the return value appropriately, especially for get_confirmation()",
        "\nImportant:",
        "- Always provide required parameters",
        "- Use clear, user-friendly messages",
        "- Handle errors and responses appropriately",
        "- Consider the context when choosing between tools\n"
    ])

    return "\n".join(prompt_parts)



def create_user_interaction_tools() -> List[Dict]:
    """
    Create tool descriptions by parsing docstrings from UserInteraction class methods
    """
    def parse_docstring(func) -> Dict:
        # Get the docstring and parse it
        doc = docstring_parser.parse(inspect.getdoc(func))
        
        # Get function signature
        sig = inspect.signature(func)
        
        # Create tool description
        tool = {
            "name": func.__name__,
            "description": doc.short_description,
            "parameters": {},
            "returns": None
        }
        
        # Parse parameters from docstring
        for param in doc.params:
            param_info = {
                "description": param.description,
                "type": str(sig.parameters[param.arg_name].annotation),
                "required": sig.parameters[param.arg_name].default == inspect.Parameter.empty
            }
            if not param_info["required"]:
                param_info["default"] = sig.parameters[param.arg_name].default
            
            tool["parameters"][param.arg_name] = param_info
        
        # Parse return info
        if doc.returns:
            tool["returns"] = {
                "type": str(sig.return_annotation),
                "description": doc.returns.description
            }
        
        return tool
    
    # Get all methods from UserInteraction class
    tools = []
    for name, func in inspect.getmembers(UserInteraction, predicate=inspect.isfunction):
        if not name.startswith('_'):  # Skip private methods
            tools.append(parse_docstring(func))

    # Format the tools for the LLM prompt
    formatted_tools = format_tools_for_llm_prompt(tools)
    
    return formatted_tools  # Return the formatted string
