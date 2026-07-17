from cognitive_runtime.mutation.mutators import generate_mutants


def test_generate_mutants():
    content = "def check(x):\n    return x == 5 and x > 2"
    mutants = generate_mutants(content)

    assert len(mutants) >= 3

    descriptions = [m[1] for m in mutants]
    assert any("Replaced '==' with '!='" in d for d in descriptions)
    assert any("Replaced ' and ' with ' or '" in d for d in descriptions)
