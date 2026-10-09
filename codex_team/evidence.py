"""Conservative correlation of native command events with test-runner evidence."""
import re
import ast


def _runner_code(source):
    """A literal/comment about a runner is not a Python runner invocation."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return False
    for statement in tree.body:
        value = getattr(statement, "value", None)
        if value is None:
            continue
        for node in ast.walk(value):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            owner, method = node.func.value, node.func.attr
            if isinstance(owner, ast.Name) and (owner.id, method) in {("pytest", "main"), ("unittest", "main")}:
                return True
            if method == "run" and isinstance(owner, ast.Call) and isinstance(owner.func, ast.Attribute):
                if isinstance(owner.func.value, ast.Name) and owner.func.value.id == "unittest" and owner.func.attr == "TextTestRunner":
                    return True
    return False


def _inline_source(arguments):
    inline = re.search(r"(?:^|\s)['\"]?-c['\"]?\s+(.+)$", arguments, re.S)
    if not inline:
        return None
    code = inline.group(1).strip()
    if len(code) >= 2 and code[0] == code[-1] and code[0] in "'\"":
        code = code[1:-1]
        # PowerShell literal apostrophes are doubled, Windows argv quotes escaped.
        code = code.replace("''", "'").replace('\\"', '"')
    return code


def _test_arguments(arguments):
    if re.search(r"(?:^|\s)-m\s+(?:pytest|unittest)(?:\s|$)", arguments):
        return True
    code = _inline_source(arguments)
    return code is not None and _runner_code(code)


def _base64_exec(arguments):
    source = _inline_source(arguments)
    try:
        tree = ast.parse(source or "")
    except (SyntaxError, ValueError):
        return False
    for statement in tree.body:
        node = statement.value if isinstance(statement, ast.Expr) else None
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "exec" or not node.args:
            continue
        decoder = node.args[0]
        if isinstance(decoder, ast.Call) and isinstance(decoder.func, ast.Attribute):
            if isinstance(decoder.func.value, ast.Name) and decoder.func.value.id == "base64" and decoder.func.attr == "b64decode":
                return True
    return False


def _ps_code(script):
    """Mask PS strings/comments, preserving offsets for explicit assignments."""
    output = list(script)
    cursor = 0
    while cursor < len(script):
        start = cursor
        if script.startswith("<#", cursor):
            end = script.find("#>", cursor + 2)
            cursor = len(script) if end < 0 else end + 2
        elif script[cursor] == "#":
            end = script.find("\n", cursor)
            cursor = len(script) if end < 0 else end
        elif script[cursor:cursor + 2] in {"@'", '@"'} and script[cursor + 2:cursor + 3] in {"\r", "\n"}:
            quote = script[cursor + 1]
            end = re.search(r"(?m)^" + re.escape(quote + "@"), script[cursor + 2:])
            cursor = len(script) if not end else cursor + 2 + end.end()
        elif script[cursor] in "'\"":
            quote = script[cursor]
            cursor += 1
            while cursor < len(script):
                if quote == '"' and script[cursor] == "`":
                    cursor += 2
                elif script[cursor] == quote:
                    if quote == "'" and script[cursor + 1:cursor + 2] == "'":
                        cursor += 2
                    else:
                        cursor += 1
                        break
                else:
                    cursor += 1
        else:
            cursor += 1
            continue
        for index in range(start, min(cursor, len(script))):
            if output[index] not in "\r\n":
                output[index] = " "
    return "".join(output)


def _ps_literal(value):
    value = value.strip()
    if re.fullmatch(r"'(?:[^']|'')*'", value, re.S):
        return value[1:-1].replace("''", "'")
    if re.fullmatch(r'"[^"$`]*"', value, re.S):
        return value[1:-1]
    return None


def _process_test(script):
    code = _ps_code(script)
    created = list(re.finditer(r"(?im)^\s*(\$[A-Za-z_]\w*)\s*=\s*(?:New-Object\s+(?:-TypeName\s+)?System\.Diagnostics\.Process|\[System\.Diagnostics\.Process\]::new\(\))\s*;?\s*$", code))
    for create in created:
        variable = re.escape(create.group(1))
        def field(name):
            matches = list(re.finditer(r"(?im)^\s*" + variable + r"\.StartInfo\." + name + r"[ \t]*=", code))
            if len(matches) != 1:
                return None
            start = matches[0].end()
            end = re.search(r"[;\r\n]", code[start:])
            return script[start:start + end.start() if end else len(script)].strip()
        filename = _ps_literal(field("FileName") or "")
        if not filename or not re.search(r"(?:^|[/\\])python(?:3(?:\.\d+)?)?(?:\.exe)?$", filename, re.I):
            continue
        if field("UseShellExecute") != "$false":
            continue
        started = re.search(variable + r"\.Start\(\)", code[create.end():], re.I)
        waited = re.search(variable + r"\.WaitForExit\(\)", code[create.end():], re.I)
        exited = re.search(r"(?im)^\s*exit\s+" + variable + r"\.ExitCode\s*;?\s*$", code)
        if not started or not waited or not exited or started.start() >= waited.start():
            continue
        if exited.start() <= create.end() + waited.end():
            continue
        arguments = field("Arguments") or ""
        literal = _ps_literal(arguments)
        if literal is not None and _test_arguments(literal):
            return True
        # Official observed QA wrapper: literal here-string -> UTF8 Base64 ->
        # python exec(base64.b64decode(...)). Track the exact variable chain.
        encoded = re.search(r"\+\s*(\$\w+)\s*\+", arguments)
        if encoded and "base64.b64decode" in arguments:
            left, right = _ps_literal(arguments[:encoded.start()]), _ps_literal(arguments[encoded.end():])
            if left is None or right is None or not _base64_exec(left + "QQ==" + right):
                continue
            assignment = re.search(r"(?im)^\s*" + re.escape(encoded.group(1)) + r"\s*=\s*\[Convert\]::ToBase64String\(\[Text\.Encoding\]::UTF8\.GetBytes\((\$\w+)\)\)", code)
            if assignment:
                source = re.search(r"(?ms)^\s*" + re.escape(assignment.group(1)) + r"\s*=\s*@'\r?\n(.*?)\r?\n'@", script)
                source_bindings = re.findall(r"(?im)^\s*" + re.escape(assignment.group(1)) + r"\s*=", code)
                encoded_bindings = re.findall(r"(?im)^\s*" + re.escape(encoded.group(1)) + r"\s*=", code)
                if source and source.start() < assignment.start() and len(source_bindings) == len(encoded_bindings) == 1 and _runner_code(source.group(1)):
                    return True
    return False

def is_test_execution(command: dict) -> bool:
    actions = command.get("actions") or []
    scripts = [a.get("command", "") for a in actions if a.get("type") == "unknown"]
    if actions and not scripts:
        return False  # A read/search of test files isn't running tests.
    scripts = scripts or [command.get("command", "")]
    for script in scripts:
        script = script.strip()
        if _process_test(script):
            return True
        if re.match(r"^(?:&\s*)?['\"]?(?:[^\s'\"]*[/\\])?pytest(?:\.exe)?['\"]?(?:\s|$)", script, re.I):
            return True
        if re.match(r"^(?:&\s*)?['\"]?(?:[^\s'\"]*[/\\])?(?:dotnet\s+test|cargo\s+test|npm\s+(?:test|run\s+test)|ctest|node\b.*--test)", script, re.I):
            return True
        python = re.match(r"^(?:&\s*)?(?:'[^']*python(?:\.exe)?'|\"[^\"]*python(?:\.exe)?\"|[^\s'\"]*python(?:\.exe)?)\s+(.+)$", script, re.I | re.S)
        if python:
            args = python.group(1)
            if _test_arguments(args):
                return True
    return False

def successful_test_execution(command: dict) -> bool:
    if command.get("status") != "completed" or command.get("exit_code") != 0 or not is_test_execution(command):
        return False
    output = command.get("output") or ""
    if re.search(r"(?:^\s*FAILED\b|\b[1-9]\d*\s+(?:failed|errors?)\b|\b(?:Failures|Errors|Failed)\s*:\s*[1-9]\d*|^\s*#\s*fail\s+[1-9]\d*)", output, re.I | re.M):
        return False
    if re.search(r"\bRan\s+[1-9]\d*\s+tests?\b", output) and not re.search(r"^OK(?:\s|$)", output, re.M):
        return False
    return bool(re.search(r"(?:\b[1-9]\d*\s+passed\b|Ran\s+[1-9]\d*\s+tests?\b|(?:Passed|Total tests)\s*:\s*[1-9]\d*|100% tests passed[^\n]*out of [1-9]\d*|^\s*#\s*pass\s+[1-9]\d*)", output, re.I | re.M))
