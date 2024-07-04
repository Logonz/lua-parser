import re
import sys
import json


def comment_replacer(match):
    s = match.group(0)
    newline_count = s.count("\n")
    return "\n" * newline_count


def extract_blocks(lua_code):
    lua_code = re.sub(r"--.*", "", lua_code)
    pattern = re.compile(r"--\[\[.*?\]\]", re.DOTALL)
    lua_code = pattern.sub(comment_replacer, lua_code)

    blocks = []
    stack = []

    start_tokens = ["function", "if", "for", "while", "repeat", "do"]
    end_tokens = {
        "function": "end",
        "if": "end",
        "for": "end",
        "while": "end",
        "repeat": "until",
        "do": "end",
    }

    string_pattern = re.compile(r'"(?:\\.|[^"])*"|\'(?:\\.|[^\'])*\'')

    last_keyword = None

    for idx, line in enumerate(lua_code.splitlines(), start=1):
        line = string_pattern.sub("", line)

        # Match function assignments to variables and capture the variable name
        func_assign_match = re.match(
            r"\s*(local\s+)?([a-zA-Z_]\w*[.:]?[a-zA-Z_]\w*)\s*=\s*function", line
        )
        if func_assign_match:
            variable_name = func_assign_match.group(2)
            stack.append(("function", idx, "anonymous", variable_name))

        # Match function definitions like object:method and capture the function name
        method_assign_match = re.match(
            r"\s*function\s+([a-zA-Z_]\w*[:.][a-zA-Z_]\w*)", line
        )
        if method_assign_match:
            function_name = method_assign_match.group(1)
            stack.append(("function", idx, function_name, function_name))

        words = re.findall(r"\b\w+\b", line)

        for word in words:
            if word == "do" and last_keyword in ["for", "while"]:
                continue
            elif word in start_tokens and not (
                func_assign_match or method_assign_match
            ):
                stack.append((word, idx, None, None))
            elif word in end_tokens.values():
                if not stack:
                    print(f"Unmatched {word} at line {idx}")
                    sys.exit(1)

                start_word, start_idx, func_name, suggested_name = stack.pop()
                if word != end_tokens.get(start_word, None):
                    print(f"Unmatched {start_word} starting at line {start_idx}")
                    sys.exit(1)

                if start_word == "function":
                    blocks.append(
                        (start_word, start_idx, idx, func_name, suggested_name)
                    )

            if word in start_tokens + list(end_tokens.values()):
                last_keyword = word

    if stack:
        unmatched_block, start_line, _, _ = stack[-1]
        print(f"Unmatched {unmatched_block} starting at line {start_line}")
        print("Debug info: ")
        lines = lua_code.splitlines()
        for i in range(max(0, start_line - 1), min(len(lines), start_line + 3)):
            print(f"{i + 1}: {lines[i]}")
        sys.exit(1)

    return blocks


def capture_comments_above_blocks(lua_code, blocks):
    lines = lua_code.splitlines()
    modified_blocks = []

    comment_pattern = re.compile(r"\s*--+\s*@*(.*)")

    for block in blocks:
        block_name, start_line, end_line, func_name, suggested_name = block

        # Scan above the function block for comments
        for i in range(start_line - 2, -1, -1):
            line = lines[i]
            match = comment_pattern.match(line)
            if match or line.strip() == "":
                start_line = i + 1
            else:
                break

        modified_blocks.append(
            (block_name, start_line, end_line, func_name, suggested_name)
        )

    return modified_blocks


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python script.py <input_lua_file> <output_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    with open(input_file, "r") as file:
        lua_code = file.read()
    lines = lua_code.splitlines()

    blocks = extract_blocks(lua_code)

    with open(output_file, "w") as file:
        for block_name, start_line, end_line, func_name, suggested_name in blocks:
            name = func_name or "anonymous"
            # Write block_name, function_name, start_line, end_line, and suggested_name
            file.write(
                f"{block_name} {name}, {start_line}, {end_line}, {suggested_name}\n"
            )

    # Widen the lines captured to include surrounding comments for better context
    modified_blocks = capture_comments_above_blocks(lua_code, blocks)

    # Remove the lines that are in comments and replace each line with a newline character
    for block in modified_blocks:
        print(block)
        block_name, start_line, end_line, func_name, suggested_name = block
        for i in range(start_line - 1, end_line):
            lines[i] = "\n"

    with open("test.out", "w") as file:
        file.write("\n".join(lines).strip())

    # Read the file and extract the block information from the Lua code
    # Put it in a json structure and write it to the output file .json
    # The json structure should look like this:
    # [
    #     {
    #         "block_name": "function",
    #         "function_name": "foo",
    #         "start_line": 1,
    #         "end_line": 3,
    #         "function_type": "r"
    #         "function_code": "function foo()\n    print('Hello, world!')\nend"
    #     },
    # ]
    raw_blocks = []
    for block in modified_blocks:
        block_name, start_line, end_line, func_name, suggested_name = block
        name = func_name or "anonymous"

        function_code = "\n".join(lines[start_line - 1 : end_line])
        raw_blocks.append(
            {
                "block_name": block_name,
                "function_name": name,
                "start_line": start_line,
                "end_line": end_line,
                "function_code": function_code,
            }
        )

    with open(output_file + ".json", "w") as file:
        json.dump(raw_blocks, file, indent=4)

    print(f"Block information has been written to {output_file}")
