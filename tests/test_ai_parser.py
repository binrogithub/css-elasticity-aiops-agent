from app.models.decisions import parse_ai_decision


def test_parse_valid_decision():
    parsed = parse_ai_decision(
        '{"decision":"scale_out","node_type":"ess-client","delta":1,"reason":"high pressure","cooldown_minutes":30,"expected_duration_minutes":30}'
    )
    assert parsed.valid
    assert parsed.decision == "scale_out"
    assert parsed.node_type == "ess-client"
    assert parsed.delta == 1


def test_invalid_json_falls_back_to_hold():
    parsed = parse_ai_decision("not json")
    assert parsed.decision == "hold"
    assert parsed.delta == 0
    assert not parsed.valid


def test_invalid_decision_falls_back_to_hold():
    parsed = parse_ai_decision(
        '{"decision":"delete_cluster","delta":1,"reason":"bad","cooldown_minutes":30}'
    )
    assert parsed.decision == "hold"
    assert not parsed.valid


def test_parse_fenced_json_decision():
    parsed = parse_ai_decision(
        '```json\n{"decision":"hold","delta":0,"reason":"stable","cooldown_minutes":30}\n```'
    )
    assert parsed.valid
    assert parsed.decision == "hold"
    assert parsed.delta == 0


def test_parse_json_embedded_in_prose():
    parsed = parse_ai_decision(
        'Decision:\n{"decision":"scale_in","node_type":"ess","delta":1,"reason":"low load","cooldown_minutes":30,"expected_duration_minutes":30}\n'
    )
    assert parsed.valid
    assert parsed.decision == "scale_in"
    assert parsed.delta == 1


def test_scaling_decision_requires_node_type():
    parsed = parse_ai_decision(
        '{"decision":"scale_out","delta":1,"reason":"high pressure","cooldown_minutes":30}'
    )
    assert parsed.decision == "hold"
    assert not parsed.valid


def test_change_flavor_requires_target_flavor():
    parsed = parse_ai_decision(
        '{"decision":"change_flavor","node_type":"ess","delta":0,"reason":"bigger nodes","cooldown_minutes":30}'
    )
    assert parsed.decision == "hold"
    assert not parsed.valid
