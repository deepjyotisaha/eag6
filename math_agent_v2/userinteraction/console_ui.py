from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.style import Style
from rich.theme import Theme
from rich.text import Text
from rich.table import Table
from rich.box import ROUNDED
from rich.console import Group
from typing import Tuple

# Custom theme for different message types
custom_theme = Theme({
    "info": "bold blue",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "prompt": "bold cyan",
    "abort": "bold red",
    "redo": "bold yellow",
    "confirm": "bold green"
})

console = Console(theme=custom_theme)

class UserInteraction:
    @staticmethod
    def show_information(message: str, title: str = "Information"):
        """
        Display information to the user with no input expected
        
        Args:
            message: The information message to display
            title: Optional title for the panel
        """
        panel = Panel(
            Text(message, style="info"),
            title=title,
            border_style="blue",
            box=ROUNDED
        )
        console.print(panel)
        console.print()  # Add blank line for spacing

    @staticmethod
    def get_confirmation(message: str, instructions: str = None) -> Tuple[str, str]:
        """
        Ask user for confirmation with three options: Confirm, Redo with feedback, or Abort
        
        Args:
            message: The message describing what needs confirmation
            instructions: Optional additional instructions
            
        Returns:
            Tuple[str, str]: A tuple containing (choice, feedback)
                            choice is one of: 'confirm', 'redo', 'abort'
                            feedback is the user's input if redo was chosen, empty string otherwise
        """
        # Create options table
        table = Table(box=ROUNDED, border_style="cyan", show_header=False)
        table.add_column("Option", style="prompt")
        table.add_column("Description", style="info")
        
        table.add_row("1. Confirm", "[green]Proceed with the current action[/green]")
        table.add_row("2. Redo", "[yellow]Repeat the previous step with your feedback[/yellow]")
        table.add_row("3. Abort", "[red]Stop the current process[/red]")

        # Create content elements
        content_elements = []
        content_elements.append(Text(message, style="prompt"))
        
        if instructions:
            content_elements.append(Text("\nInstructions: ", style="info"))
            content_elements.append(Text(instructions))
        
        content_elements.append(Text("\n"))  # Add spacing
        content_elements.append(table)

        # Group all elements together
        group = Group(*content_elements)
        
        # Create and display panel with grouped content
        panel = Panel(
            group,
            title="Confirmation Required",
            border_style="cyan",
            box=ROUNDED
        )
        
        console.print(panel)
        
        # Get user input
        choice = Prompt.ask(
            "Please enter your choice",
            choices=["1", "2", "3"],
            default="1"
        )
        
        feedback = ""
        if choice == "2":  # Redo option
            feedback_panel = Panel(
                "Please provide your feedback for redoing the step:",
                title="Feedback Required",
                border_style="yellow",
                box=ROUNDED
            )
            console.print(feedback_panel)
            feedback = Prompt.ask("Your feedback")

        return {"1": ("confirm", ""), 
                "2": ("redo", feedback), 
                "3": ("abort", "")}[choice]

    @staticmethod
    def report_error(error_message: str, error_type: str = "Error", details: str = None):
        """
        Report an error to the user
        
        Args:
            error_message: The main error message
            error_type: Type of error (default: "Error")
            details: Optional detailed error information
        """
        error_content = [Text(error_message, style="error")]
        
        if details:
            error_content.extend([
                Text("\nDetails:", style="warning"),
                Text(details, style="info")
            ])

        panel = Panel(
            "\n".join(str(content) for content in error_content),
            title=f"⚠️ {error_type}",
            border_style="red",
            box=ROUNDED
        )
        console.print(panel)

    @staticmethod
    def escalate(question: str, context: str = None) -> str:
        """
        Ask user for clarification when faced with ambiguity
        
        Args:
            question: The clarification question
            context: Optional context about why clarification is needed
            
        Returns:
            str: User's response
        """
        content = [Text(question, style="prompt")]
        
        if context:
            content.extend([
                Text("\nContext:", style="info"),
                Text(context, style="info")
            ])

        panel = Panel(
            "\n".join(str(content) for content in content),
            title="Clarification Needed",
            border_style="yellow",
            box=ROUNDED
        )
        console.print(panel)
        
        return Prompt.ask("Please provide clarification")