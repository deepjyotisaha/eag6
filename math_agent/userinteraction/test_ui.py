from console_ui import UserInteraction

def test_user_interactions():
    # Test information display
    UserInteraction.show_information(
        "Processing your mathematical query...",
        "Status Update"
    )

    # Test confirmation
    result = UserInteraction.get_confirmation(
        "Ready to calculate the exponential sum.",
        "This operation will use the ASCII values of characters."
    )
    print(f"User chose: {result}")

    # Test error reporting
    UserInteraction.report_error(
        "Failed to convert string to ASCII values",
        "Conversion Error",
        "Input string contains unsupported characters"
    )

    # Test escalation
    response = UserInteraction.escalate(
        "Should the calculation include spaces?",
        "The input string contains multiple spaces which could affect the result."
    )
    print(f"User clarification: {response}")

if __name__ == "__main__":
    test_user_interactions()