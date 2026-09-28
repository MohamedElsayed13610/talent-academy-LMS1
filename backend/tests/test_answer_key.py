from app.services.answer_key import parse_answer_key


def test_compact_format():
    result = parse_answer_key("BCAD")
    assert result.ok
    assert result.letters == ["B", "C", "A", "D"]


def test_space_separated():
    result = parse_answer_key("B C A D")
    assert result.ok
    assert result.letters == ["B", "C", "A", "D"]


def test_lowercase_is_normalized():
    result = parse_answer_key("bcad")
    assert result.ok
    assert result.letters == ["B", "C", "A", "D"]


def test_comma_separated():
    result = parse_answer_key("B,C,A,D")
    assert result.ok
    assert result.letters == ["B", "C", "A", "D"]


def test_newline_separated():
    result = parse_answer_key("B\nC\nA\nD")
    assert result.ok
    assert result.letters == ["B", "C", "A", "D"]


def test_numbered_dash_format():
    result = parse_answer_key("1-B 2-C 3-A 4-D")
    assert result.ok
    assert result.letters == ["B", "C", "A", "D"]


def test_numbered_paren_format():
    result = parse_answer_key("1)B 2)C 3)A 4)D")
    assert result.ok
    assert result.letters == ["B", "C", "A", "D"]


def test_numbered_dot_format():
    result = parse_answer_key("1.B 2.C 3.A 4.D")
    assert result.ok
    assert result.letters == ["B", "C", "A", "D"]


def test_numbered_colon_format():
    result = parse_answer_key("1:B 2:C 3:A 4:D")
    assert result.ok
    assert result.letters == ["B", "C", "A", "D"]


def test_numbered_multiline():
    result = parse_answer_key("1-B\n2-C\n3-A\n4-D")
    assert result.ok
    assert result.letters == ["B", "C", "A", "D"]


def test_numbered_out_of_order_is_sorted_by_number():
    result = parse_answer_key("3-A 1-B 4-D 2-C")
    assert result.ok
    assert result.letters == ["B", "C", "A", "D"]


def test_numbered_not_starting_at_1_is_rejected():
    result = parse_answer_key("2-B 3-C 4-A 5-D")
    assert not result.ok
    assert result.errors


def test_numbered_with_gap_is_rejected():
    result = parse_answer_key("1-B 2-C 4-D")
    assert not result.ok
    assert result.errors


def test_numbered_with_duplicate_is_rejected():
    result = parse_answer_key("1-B 1-C 2-A")
    assert not result.ok
    assert result.errors


def test_empty_input_is_rejected():
    result = parse_answer_key("")
    assert not result.ok
    assert result.errors


def test_whitespace_only_is_rejected():
    result = parse_answer_key("   \n  ")
    assert not result.ok


def test_invalid_letters_rejected():
    result = parse_answer_key("BXAD")
    assert not result.ok


def test_mixed_numbered_and_bare_letters_rejected():
    result = parse_answer_key("1-B C 3-A")
    assert not result.ok


def test_single_letter():
    result = parse_answer_key("B")
    assert result.ok
    assert result.letters == ["B"]


def test_single_numbered():
    result = parse_answer_key("1-B")
    assert result.ok
    assert result.letters == ["B"]
