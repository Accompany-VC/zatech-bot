from plugins.modlog.utils import (
    format_channel_archive_event,
    format_message_changed_event,
    format_message_deleted_event,
    format_team_join_event,
    normalize_channel_identifier,
)


def test_normalize_channel_identifier_handles_common_inputs():
    assert normalize_channel_identifier("<#C12345678|mod-log>") == "C12345678"
    assert normalize_channel_identifier("C87654321") == "C87654321"
    assert normalize_channel_identifier("#general") == "#general"
    assert normalize_channel_identifier("general") == "#general"


def test_format_team_join_event_produces_expected_summary():
    event = {
        "user": {
            "id": "U123",
            "profile": {"display_name": "newbie"},
        }
    }
    result = format_team_join_event(event)
    assert result == ":tada: <@U123> (newbie) joined the workspace."


def test_format_message_deleted_event_includes_snippet():
    event = {
        "channel": "C123",
        "user": "U999",
        "previous_message": {
            "user": "U123",
            "text": "This is a secret message that should not stay around.",
        },
    }
    result = format_message_deleted_event(event)
    assert ":wastebasket: Message deleted in <#C123>" in result
    assert "from <@U123>" in result
    assert "by <@U999>" in result
    assert "> This is a secret message" in result


def test_format_message_changed_event_includes_before_and_after():
    event = {
        "channel": "C456",
        "message": {
            "user": "U555",
            "text": "Updated text",
            "edited": {"user": "U777"},
        },
        "previous_message": {
            "user": "U555",
            "text": "Old text",
        },
    }
    result = format_message_changed_event(event)
    assert ":pencil2: Message edited in <#C456>" in result
    assert "by <@U555>" in result
    assert "(edited by <@U777>)" in result
    assert "> *Before:* Old text" in result
    assert "> *After:* Updated text" in result


def test_format_channel_archive_event_handles_unarchive():
    event = {"channel": "C111", "user": "U333"}
    result = format_channel_archive_event(event, archived=False)
    assert result == ":file_folder: Channel unarchived: <#C111> by <@U333>"
