from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.style import Style
from rich.theme import Theme
from rich.text import Text
from rich.table import Table
from rich.box import ROUNDED
from typing import Tuple, Optional
import json
import logging
from config.config import Config
from llm.llm import LLMManager

# Custom theme for the introduction
theme = Theme({
    "title": "bold cyan",
    "capability": "green",
    "constraint": "yellow",
    "example": "blue italic",
    "prompt": "bold white"
})

console = Console(theme=theme)
logger = logging.getLogger(__name__)

async def _create_agent_introduction(llm_manager: LLMManager, general_instructions: str) -> str:
    """
    Create a crisp introduction of the agent using LLM based on general instructions
    """
    prompt = f"""
    Based on these general instructions about my capabilities:
    
    {general_instructions}
    
    Create a BRIEF and CRISP introduction about me that covers:
    1. Who I am (1 sentence)
    2. My key capabilities (3-4 bullet points)
    3. Important constraints (2-3 bullet points)
    
    Format the response as a JSON:
    {{
        "introduction": "one sentence about who I am",
        "capabilities": ["bullet point 1", "bullet point 2", ...],
        "constraints": ["constraint 1", "constraint 2", ...]
    }}
    
    Keep it concise and user-friendly. Avoid technical jargon.
    """
    
    try:
        response = await llm_manager.generate_with_timeout(prompt)
        intro_data = json.loads(response.text)
        
        # Format the introduction nicely
        formatted_intro = f"{intro_data['introduction']}\n\n"
        formatted_intro += "Key Capabilities:\n"
        for cap in intro_data['capabilities']:
            formatted_intro += f"• {cap}\n"
        formatted_intro += "\nKey Constraints:\n"
        for con in intro_data['constraints']:
            formatted_intro += f"• {con}\n"
            
        return formatted_intro
        
    except Exception as e:
        logger.error(f"Error generating introduction: {e}")
        # Fallback to a basic introduction if LLM fails
        return """I am a Math Agent specialized in solving mathematical problems with visual outputs.

Key Capabilities:
• Solving mathematical problems step-by-step
• Creating visual representations of solutions
• Handling user interactions for clarity
• Maintaining detailed execution records

Key Constraints:
• Require clear mathematical problems
• Follow strict validation steps
• Maintain audit trails"""

async def _get_example_prompts(llm_manager: LLMManager, general_instructions: str) -> list[str]:
    """
    Generate example prompts using LLM based on general instructions
    """
    prompt = f"""
    Based on these general instructions about my capabilities:
    
    {general_instructions}
    
    Generate 2 example prompts that:
    1. Showcase different aspects of my capabilities
    2. Are clear and easy to understand
    3. Demonstrate practical use cases
    
    Format the response as a JSON array:
    {{
        "examples": [
            {{
                "prompt": "example prompt 1",
                "showcases": ["capability 1", "capability 2"]
            }},
            {{
                "prompt": "example prompt 2",
                "showcases": ["capability 3", "capability 4"]
            }}
        ]
    }}
    
    Make the examples concrete and practical.
    """
    
    try:
        response = await llm_manager.generate_with_timeout(prompt)
        examples_data = json.loads(response.text)
        return [ex["prompt"] for ex in examples_data["examples"]]
        
    except Exception as e:
        logger.error(f"Error generating example prompts: {e}")
        # Fallback examples if LLM fails
        return [
            "Calculate the sum of ASCII values for the word 'INDIA' and display it on canvas",
            "Find the factorial of 5 and show the calculation steps visually"
        ]

async def get_user_prompt(llm_manager: LLMManager, general_instructions: str) -> Optional[str]:
    """
    Display agent introduction and get user prompt
    
    Args:
        llm_manager: LLM manager instance for generating content
    
    Returns:
        Optional[str]: User's prompt or None if they choose to exit
    """
    # Clear the screen for a fresh start
    console.clear()
    
    # Show welcome banner
    console.print(Panel(
        "[title]Welcome to Math Agent[/title]",
        border_style="cyan",
        box=ROUNDED
    ))
    
    # Get and show agent introduction
    intro_text = await _create_agent_introduction(llm_manager, general_instructions)
    intro_panel = Panel(
        Text(intro_text),
        title="About Me",
        border_style="blue",
        box=ROUNDED
    )
    console.print(intro_panel)
    
    # Get and show example prompts
    examples = await _get_example_prompts(llm_manager, general_instructions)
    example_table = Table(
        show_header=True,
        header_style="bold magenta",
        box=ROUNDED,
        title="Example Prompts"
    )
    example_table.add_column("Examples", style="blue")
    for example in examples:
        example_table.add_row(f"• {example}")
    console.print(example_table)
    
    # Get user input
    console.print("\n[prompt]What would you like me to help you with?[/prompt]")
    console.print("[yellow](Type 'exit' to quit)[/yellow]\n")
    
    user_input = Prompt.ask("[prompt]Your prompt[/prompt]")
    
    if user_input.lower() == 'exit':
        console.print("\n[yellow]Goodbye! Have a great day![/yellow]")
        return None
        
    return user_input

def display_processing_start() -> None:
    """
    Display a message indicating that processing has started
    """
    console.print(Panel(
        "[green]Processing your request...[/green]\n"
        "[blue]I will guide you through the solution step by step.[/blue]",
        title="Starting",
        border_style="green",
        box=ROUNDED
    ))

def display_processing_stop(success: bool = True, message: str = None) -> None:
    """
    Display a message indicating that processing has completed
    
    Args:
        success: Whether the processing completed successfully
        message: Optional message to display with the completion status
    """
    if success:
        status = "[green]Successfully completed processing![/green]"
        border_style = "green"
        title = "Completed"
    else:
        status = "[red]Processing stopped[/red]"
        border_style = "red"
        title = "Stopped"

    content = [status]
    if message:
        content.append(f"\n[blue]{message}[/blue]")

    console.print(Panel(
        "\n".join(content),
        title=title,
        border_style=border_style,
        box=ROUNDED
    ))