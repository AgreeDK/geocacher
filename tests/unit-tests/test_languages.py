from collections import Counter
import importlib.util
import pathlib
import pytest
import ast

LANG_DIR = pathlib.Path("src/opensak/lang")
REFERENCE_LANG = "en"  # reference language file

def load_strings(file_path: pathlib.Path):
    spec = importlib.util.spec_from_file_location("lang_module", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    strings = getattr(module, "STRINGS", None)
    if not isinstance(strings, dict):
        raise TypeError(f"{file_path} does not define STRINGS as a dict")
    return strings

# Load reference keys
ref_file = LANG_DIR / f"{REFERENCE_LANG}.py"
ref_strings = load_strings(ref_file)
ref_keys = set(ref_strings.keys())

# Scan all language files except the reference and __init__.py
lang_files = [
    f for f in LANG_DIR.glob("*.py")
    if f.stem not in {REFERENCE_LANG, "__init__"}
]

# Generate human-readable IDs for pytest
lang_ids = [f.stem for f in lang_files]

@pytest.mark.parametrize("lang_file", lang_files, ids=lang_ids)
def test_no_missing_keys(lang_file):
    strings = load_strings(lang_file)
    missing_keys = ref_keys - set(strings.keys())
    assert not missing_keys, f"{lang_file.stem} is missing keys: {sorted(missing_keys)}"


@pytest.mark.parametrize("lang_file", lang_files, ids=lang_ids)
def test_no_empty_values(lang_file):
    strings = load_strings(lang_file)
    empty_values = [k for k, v in strings.items() if not v or str(v).strip() == ""]
    assert not empty_values, f"{lang_file.stem} has empty values: {sorted(empty_values)}"


@pytest.mark.parametrize("lang_file", lang_files, ids=lang_ids)
def test_no_extra_keys(lang_file):
    strings = load_strings(lang_file)
    extra_keys = set(strings.keys()) - ref_keys
    assert not extra_keys, f"{lang_file.stem} has extra keys: {sorted(extra_keys)}"

@pytest.mark.parametrize("lang_file", [ref_file] + lang_files, ids=[REFERENCE_LANG] + lang_ids)
def test_no_duplicate_keys(lang_file):
    """Verifies that there are no duplicate keys defined in the STRINGS dictionary."""
    content = lang_file.read_text(encoding="utf-8")
    tree = ast.parse(content)
    
    found_strings_dict = False
    for node in ast.walk(tree):
        target_name = None
        value_node = None

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "STRINGS":
                    target_name = "STRINGS"
                    value_node = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "STRINGS":
                target_name = "STRINGS"
                value_node = node.value

        if target_name == "STRINGS" and isinstance(value_node, ast.Dict):
            found_strings_dict = True
            
            # Extract keys from the AST nodes
            keys = []
            for key_node in value_node.keys:
                if isinstance(key_node, ast.Constant):
                    keys.append(key_node.value)
                elif isinstance(key_node, (ast.Str, ast.Bytes)):
                    keys.append(getattr(key_node, 's', getattr(key_node, 'n', None)))

            counts = Counter(keys)
            duplicates = {k: v for k, v in counts.items() if v > 1}
            
            # Formatted error message: "key_name (3x), another_key (2x)"
            err_msg = ", ".join([f"'{k}' ({v}x)" for k, v in duplicates.items()])
            
            assert not duplicates, f"{lang_file.name} has duplicate keys defined: {err_msg}"
            break 

    assert found_strings_dict, f"Could not find STRINGS dictionary in {lang_file.name}"