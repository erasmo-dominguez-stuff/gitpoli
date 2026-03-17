import pytest

# Example TDD test for a new handler
# Replace with your handler input/output

def test_handler_normalization():
    # Arrange: define input event
    event = {"ref": "main", "environment": "production"}
    # Act: normalize event (to be implemented)
    normalized = {"ref": f"refs/heads/{event['ref']}", "environment": event["environment"]}
    # Assert
    assert normalized["ref"].startswith("refs/heads/")

# Add more handler tests here
