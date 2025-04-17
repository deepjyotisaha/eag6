# eag6/math_agent/memory/working_memory.py
from typing import Optional, Dict, List, Any
from datetime import datetime
import json
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from rich.text import Text
from userinteraction.console_ui import UserInteraction
from llm.llm import LLMManager

console = Console()

class UserMemory:
    """
    Manages user-specific memory including facts, preferences, and historical interactions.
    Provides functionality to store and recall information using LLM-powered retrieval.
    """
    
    def __init__(self, llm_manager: LLMManager):
        """
        Initialize user memory system
        
        Args:
            llm_manager: LLM manager instance for fact retrieval
        """
        self.facts = []
        self.llm_manager = llm_manager
        
    def add_fact(self, fact: Dict[str, Any]) -> None:
        """
        Add a new fact to memory
        
        Args:
            fact: Dictionary containing fact information
        """
        fact["timestamp"] = datetime.now()
        fact["fact_id"] = len(self.facts) + 1
        self.facts.append(fact)

    async def gather_initial_facts_hardcoded(self) -> None:
        """Gather initial set of facts from user through a questionnaire"""
        questions = [
            {
                "id": "name",
                "question": "What is your name?",
                "type": "personal",
                "required": True
            },
            {
                "id": "visual_preferences",
                "question": "Do you have any specific visual preferences (e.g., high contrast, large text)?",
                "type": "accessibility",
                "required": True
            },
            {
                "id": "math_experience",
                "question": "How would you rate your mathematics experience (beginner/intermediate/advanced)?",
                "type": "expertise",
                "required": True
            },
            {
                "id": "preferred_explanation_style",
                "question": "How detailed would you like explanations to be (brief/moderate/detailed)?",
                "type": "preference",
                "required": True
            },
            {
                "id": "special_requirements",
                "question": "Do you have any special requirements or preferences we should know about?",
                "type": "accessibility",
                "required": False
            }
        ]
        
        console.print(Panel(
            "Let's gather some information to personalize your experience",
            title="User Profile Setup",
            border_style="blue"
        ))
        
        for question in questions:
            response = UserInteraction.escalate(
                question["question"],
                f"This helps us {self._get_context_for_question(question['type'])}"
            )
            
            self.add_fact({
                "type": question["type"],
                "question_id": question["id"],
                "question": question["question"],
                "response": response
            })
            
    async def add_contextual_fact(self, context: str, question: str) -> None:
        """
        Add a fact based on current context
        
        Args:
            context: Current context or situation
            question: Question to ask user
        """
        response = UserInteraction.escalate(question, context)
        self.add_fact({
            "type": "contextual",
            "context": context,
            "question": question,
            "response": response
        })

    async def recall(self, query: str) -> Optional[Dict]:
        """
        Recall relevant information based on query using LLM
        
        Args:
            query: Question or context to search for
            
        Returns:
            Optional[Dict]: Retrieved information or None
        """
        if not self.facts:
            return None
            
        # Create prompt for LLM
        prompt = self._create_recall_prompt(query)
        
        try:
            # Get LLM's interpretation
            response = await self.llm_manager.generate_with_timeout(prompt)
            
            # Parse and validate response
            if not self.llm_manager.validate_response(response.text):
                return None
                
            result = json.loads(self.llm_manager.clean_response(response.text))
            
            # Add this recall attempt to facts
            self.add_fact({
                "type": "recall_attempt",
                "query": query,
                "result": result
            })
            
            return result
            
        except Exception as e:
            console.print(f"Error during recall: {str(e)}", style="red")
            return None

    def _create_recall_prompt(self, query: str) -> str:
        """Create prompt for LLM recall"""
        facts_json = json.dumps(self.facts, default=str, indent=2)
        
        return f"""Given the following facts about the user and the query, 
        provide relevant information and reasoning for the response.

        Make sure to use the facts to answer the query.
        
        Facts:
        {facts_json}
        
        Query: {query}
        
        Please respond in the following JSON format:
        {{
            "relevant_facts": [
                {{
                    "fact_id": <id>,
                    "relevance": "explanation of why this fact is relevant"
                }}
            ],
            "interpretation": "interpretation of facts in context of query",
            "confidence": "high/medium/low",
            "response": "final response to the query",
            "reasoning": "explanation of how the response was derived"
        }}
        """

    def _get_context_for_question(self, question_type: str) -> str:
        """Get explanatory context for question type"""
        contexts = {
            "personal": "personalize your experience",
            "accessibility": "ensure the interface meets your needs",
            "expertise": "adjust explanations to your knowledge level",
            "preference": "customize our interaction style",
        }
        return contexts.get(question_type, "improve your experience")

    def print_facts(self, detailed: bool = False) -> None:
        """
        Print stored facts in a pretty format
        
        Args:
            detailed: If True, prints full fact details
        """
        main_tree = Tree("📚 User Memory")
        
        # Group facts by type
        facts_by_type = {}
        for fact in self.facts:
            fact_type = fact.get("type", "unknown")
            if fact_type not in facts_by_type:
                facts_by_type[fact_type] = []
            facts_by_type[fact_type].append(fact)
        
        # Add facts to tree
        for fact_type, facts in facts_by_type.items():
            type_tree = main_tree.add(f"[blue]{fact_type.title()}[/blue]")
            for fact in facts:
                if detailed:
                    fact_tree = type_tree.add(f"Fact #{fact['fact_id']}")
                    for key, value in fact.items():
                        if key != "fact_id":
                            if key == "timestamp":
                                fact_tree.add(f"{key}: {value.strftime('%Y-%m-%d %H:%M:%S')}")
                            else:
                                fact_tree.add(f"{key}: {value}")
                else:
                    # Show simplified version
                    question = fact.get("question", "")
                    response = fact.get("response", "")
                    timestamp = fact["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                    type_tree.add(f"#{fact['fact_id']} - {question}: {response} ({timestamp})")
        
        console.print(Panel(
            main_tree,
            title="User Memory Contents",
            subtitle=f"Total Facts: {len(self.facts)}",
            border_style="blue"
        ))

    def save_to_file(self, filepath: str) -> None:
        """
        Save memory contents to file
        
        Args:
            filepath: Path to save file
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(self.facts, f, default=str, indent=2)
            console.print(f"Memory saved to {filepath}", style="green")
        except Exception as e:
            console.print(f"Error saving memory: {str(e)}", style="red")

    def load_from_file(self, filepath: str) -> None:
        """
        Load memory contents from file
        
        Args:
            filepath: Path to load file
        """
        try:
            with open(filepath, 'r') as f:
                self.facts = json.load(f)
            console.print(f"Memory loaded from {filepath}", style="green")
        except Exception as e:
            console.print(f"Error loading memory: {str(e)}", style="red")


    async def test_user_memory(self) -> None:
        """
        Test function to demonstrate and verify user memory functionality.
        
        Args:
            llm_manager: Initialized LLM manager instance
        """
        try:
            UserInteraction.show_information(
                "Starting User Memory Test",
                "Test Suite"
            )

            # Step 1: Test Loading/Initial Setup
            UserInteraction.show_information(
                "Step 1: Testing Memory Loading/Initial Setup",
                "Test Phase"
            )
            
            try:
                #self.load_from_file("user_memory.json")
                UserInteraction.show_information(
                    "Successfully loaded existing memory",
                    "Load Result"
                )
            except:
                UserInteraction.show_information(
                    "No existing memory found - gathering initial facts",
                    "Load Result"
                )
                await self.gather_initial_facts()

            # Step 2: Display Current Memory State
            UserInteraction.show_information(
                "Step 2: Current Memory State",
                "Test Phase"
            )
            self.print_facts(detailed=True)

            # Step 3: Test Adding Contextual Facts
            UserInteraction.show_information(
                "Step 3: Testing Contextual Fact Addition",
                "Test Phase"
            )
            
            test_contexts = [
                {
                    "context": "Working with mathematical equations",
                    "question": "Do you prefer to see intermediate steps in calculations?"
                },
                {
                    "context": "Displaying results",
                    "question": "What font size is most comfortable for you?"
                }
            ]

            for context_info in test_contexts:
                await self.add_contextual_fact(
                    context_info["context"],
                    context_info["question"]
                )

            # Step 4: Test Memory Recall
            UserInteraction.show_information(
                "Step 4: Testing Memory Recall",
                "Test Phase"
            )

            test_queries = [
                "What are the user's visual preferences?",
                "What is the user's preferred level of mathematical explanation detail?",
                "What are the user's preferences for displaying calculations?",
                "Summarize all known user accessibility requirements"
            ]

            for query in test_queries:
                UserInteraction.show_information(
                    f"Testing recall for: {query}",
                    "Recall Test"
                )
                
                recall_result = await self.recall(query)
                if recall_result:
                    UserInteraction.show_information(
                        json.dumps(recall_result, indent=2),
                        "Recall Result"
                    )
                else:
                    UserInteraction.report_error(
                        "No relevant information found",
                        "Recall Error"
                    )

            # Step 5: Save Updated Memory
            UserInteraction.show_information(
                "Step 5: Saving Memory State",
                "Test Phase"
            )
            
            #self.save_to_file("user_memory.json")
            
            # Step 6: Test Summary
            UserInteraction.show_information(
                f"Test Complete\n"
                f"Total Facts: {len(self.facts)}\n"
                f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "Test Summary"
            )

        except Exception as e:
            UserInteraction.report_error(
                "Error during user memory test",
                "Test Error",
                str(e)
            )

    async def gather_initial_facts_for_query(self, query: str, system_prompt: str) -> None:
        """
        Use LLM to generate relevant questions based on the query and system prompt,
        then gather and store answers.
        
        Args:
            query: The user's query or task
            system_prompt: The system prompt providing context
        """
        UserInteraction.show_information(
            f"Analyzing query: {query}\nGenerating relevant questions...",
            "Query Analysis"
        )

        # Create prompt for question generation
        question_prompt = f"""
        Given the following query and system context, generate 5 relevant questions
        that would help better understand the user's needs and preferences for this specific task.

        Your intent is to gather information that will help you better understand the user's needs and preferences for this specific task and help you plan the needed steps to execute the task. Pay attention to the ambiguity of the query and the potential multiple interpretations of the query, and gaps information available in the system context.
        
        Query: {query}
        
        System Context: {system_prompt}
        
        Generate questions that focus on:
        1. User's specific preferences for this type of task
        2. Previous experience with similar problems
        3. Desired level of detail in the solution
        4. Any constraints or special requirements
        5. Preferred format of results
        
        Respond in the following JSON format:
        {{
            "questions": [
                {{
                    "id": "unique_id",
                    "question": "the question text",
                    "purpose": "why this question is relevant",
                    "type": "preference/experience/requirement/format/detail"
                }}
            ]
        }}
        """

        try:
            # Get questions from LLM
            response = await self.llm_manager.generate_with_timeout(question_prompt)
            if not self.llm_manager.validate_response(response.text):
                raise ValueError("Invalid response format from LLM")

            questions_data = json.loads(self.llm_manager.clean_response(response.text))
            
            # Store the query context
            self.add_fact({
                "type": "query_context",
                "query": query,
                "timestamp": datetime.now()
            })

            UserInteraction.show_information(
                "Generated questions for your query. Let's gather some information.",
                "Query-Specific Questions"
            )

            # Ask each question and store responses
            for q_data in questions_data["questions"]:
                # Format the context explanation
                context = (
                    f"Purpose: {q_data['purpose']}\n"
                    f"This helps customize the {q_data['type']} for your query: {query}"
                )
                
                # Get user's response
                response = UserInteraction.escalate(
                    q_data["question"],
                    context
                )
                
                # Store as a fact
                self.add_fact({
                    "type": "query_specific",
                    "query_id": q_data["id"],
                    "question": q_data["question"],
                    "response": response,
                    "purpose": q_data["purpose"],
                    "category": q_data["type"],
                    "related_query": query
                })

            # Add a summary fact
            self.add_fact({
                "type": "query_analysis_summary",
                "query": query,
                "questions_asked": len(questions_data["questions"]),
                "categories_covered": list(set(q["type"] for q in questions_data["questions"]))
            })

            # Show completion message with summary
            UserInteraction.show_information(
                "Successfully gathered query-specific information.\n"
                f"Questions asked: {len(questions_data['questions'])}\n"
                "You can now proceed with the query execution.",
                "Information Gathering Complete"
            )

        except Exception as e:
            UserInteraction.report_error(
                "Error gathering query-specific information",
                "Gathering Error",
                str(e)
            )

    async def recall_query_specific_facts(self, query: str) -> Optional[Dict]:
        """
        Recall facts specifically related to a query
        
        Args:
            query: The query to recall facts for
            
        Returns:
            Optional[Dict]: Retrieved information or None
        """
        recall_prompt = f"""
        Given the following facts and the query, provide relevant information
        focusing specifically on query-related preferences and requirements.
        
        Facts:
        {json.dumps(self.facts, default=str, indent=2)}
        
        Query: {query}
        
        Provide response in the following JSON format:
        {{
            "query_specific_facts": [
                {{
                    "fact_id": "id",
                    "relevance": "explanation of relevance to query",
                    "category": "preference/experience/requirement/format/detail"
                }}
            ],
            "preferences": {{
                "detail_level": "identified preference for detail",
                "format": "identified format preferences",
                "special_requirements": ["any special requirements identified"]
            }},
            "confidence": "high/medium/low",
            "recall_answer": [
                "specific answer based on your analysis of the facts and the query"
            ]
        }}
        """

        try:
            response = await self.llm_manager.generate_with_timeout(recall_prompt)
            if not self.llm_manager.validate_response(response.text):
                return None

            recall_result = json.loads(self.llm_manager.clean_response(response.text))
            
            # Add this recall attempt to facts
            self.add_fact({
                "type": "query_specific_recall",
                "query": query,
                "recall_result": recall_result,
                "timestamp": datetime.now()
            })

            return recall_result

        except Exception as e:
            UserInteraction.report_error(
                "Error recalling query-specific facts",
                "Recall Error",
                str(e)
            )
            return None
        
    def print_status(self) -> None:
        """
        Print a formatted status of the user memory, similar to working memory's style.
        """
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        from datetime import datetime

        console = Console()

        # Create header
        header = Panel(
            "[bold blue]User Memory Status Overview[/bold blue]",
            style="bold white on blue"
        )
        console.print(header)

        # Create facts summary table
        facts_table = Table(show_header=True, title="Facts Summary")
        facts_table.add_column("Category", style="cyan")
        facts_table.add_column("Count", justify="right", style="green")
        facts_table.add_column("Latest Update", style="yellow")

        # Group facts by type
        fact_types = {}
        for fact in self.facts:
            fact_type = fact.get('type', 'unknown')
            if fact_type not in fact_types:
                fact_types[fact_type] = {
                    'count': 0,
                    'latest': None
                }
            fact_types[fact_type]['count'] += 1
            
            timestamp = fact.get('timestamp')
            if timestamp:
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp)
                    except ValueError:
                        timestamp = None
                if timestamp and (not fact_types[fact_type]['latest'] or 
                                timestamp > fact_types[fact_type]['latest']):
                    fact_types[fact_type]['latest'] = timestamp

        # Add rows to facts table
        for fact_type, data in fact_types.items():
            latest_str = data['latest'].strftime("%Y-%m-%d %H:%M:%S") if data['latest'] else "N/A"
            facts_table.add_row(fact_type, str(data['count']), latest_str)

        console.print(facts_table)

        # Print recent facts
        recent_facts_table = Table(
            show_header=True,
            title="Recent Facts (Last 5)",
            title_style="bold magenta"
        )
        recent_facts_table.add_column("Type", style="cyan")
        recent_facts_table.add_column("Content", style="green")
        recent_facts_table.add_column("Timestamp", style="yellow")

        # Sort facts by timestamp and get last 5
        sorted_facts = sorted(
            [f for f in self.facts if 'timestamp' in f],
            key=lambda x: (
                datetime.fromisoformat(x['timestamp'])
                if isinstance(x['timestamp'], str)
                else x['timestamp']
            ),
            reverse=True
        )[:5]

        for fact in sorted_facts:
            content = self._format_fact_content(fact)
            timestamp = (
                datetime.fromisoformat(fact['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(fact['timestamp'], str)
                else fact['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
            )
            recent_facts_table.add_row(fact.get('type', 'unknown'), content, timestamp)

        console.print("\n")
        console.print(recent_facts_table)

        # Print memory statistics
        stats_panel = Panel(
            self._get_memory_stats(),
            title="Memory Statistics",
            style="bold white"
        )
        console.print("\n")
        console.print(stats_panel)

    def _format_fact_content(self, fact: dict) -> str:
        """Format fact content for display."""
        if fact.get('type') == 'preference':
            return f"{fact.get('category', 'N/A')}: {fact.get('value', 'N/A')}"
        elif fact.get('type') == 'query_specific':
            return f"Q: {fact.get('question', 'N/A')[:30]}... -> A: {fact.get('response', 'N/A')[:30]}..."
        elif fact.get('type') == 'intent_analysis':
            intent = fact.get('analysis', {}).get('primary_intent', {})
            return f"Intent: {intent.get('action', 'N/A')} -> {intent.get('objective', 'N/A')}"
        return str(fact.get('response', str(fact)))[:60] + "..."

    def _get_memory_stats(self) -> str:
        """Generate memory statistics string."""
        total_facts = len(self.facts)
        memory_size = len(str(self.facts))
        fact_types = len(set(f.get('type', 'unknown') for f in self.facts))
        
        stats = [
            f"Total Facts: {total_facts}",
            f"Unique Fact Types: {fact_types}",
            f"Memory Size: {memory_size/1024:.2f}KB"
        ]
        return "\n".join(stats)
