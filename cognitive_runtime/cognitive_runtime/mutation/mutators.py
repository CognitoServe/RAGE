import re

MUTATORS = [
    ("==", "!="),
    ("!=", "=="),
    (" > ", " <= "),
    (" < ", " >= "),
    (" >= ", " < "),
    (" <= ", " > "),
    (" and ", " or "),
    (" or ", " and "),
    ("True", "False"),
    ("False", "True"),
]


def generate_mutants(file_content: str) -> list[tuple[str, str, int]]:
    """
    Scans the file content and generates mutants.
    Returns a list of tuples: (mutated_content, description, line_number)
    """
    lines = file_content.splitlines()
    mutants = []

    in_docstring = False

    for line_idx, line in enumerate(lines):
        # Handle simple docstring detection (triple quotes)
        if '"""' in line or "'''" in line:
            # If it starts and ends on the same line, it's a single line docstring
            if line.count('"""') % 2 != 0 or line.count("'''") % 2 != 0:
                in_docstring = not in_docstring
            continue

        if in_docstring:
            continue

        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        for orig, repl in MUTATORS:
            # Find all occurrences of the pattern in the line
            occurrences = [m.start() for m in re.finditer(re.escape(orig), line)]
            for occ in occurrences:
                # Create mutant by replacing only this occurrence
                mutated_line = line[:occ] + repl + line[occ + len(orig) :]
                mutated_lines = list(lines)
                mutated_lines[line_idx] = mutated_line

                desc = f"Line {line_idx + 1}: Replaced '{orig}' with '{repl}'"
                mutated_content = "\n".join(mutated_lines) + (
                    "\n" if file_content.endswith("\n") else ""
                )
                mutants.append((mutated_content, desc, line_idx + 1))

    return mutants
