"""Project finite positive breed alternatives into authentic scene candidates."""
import ast


def positive_target_breed_choices(criterion, *, limit=16):
    if type(limit) is not int or not 1 <= limit <= 16:
        raise ValueError("Invalid native target breed alternative bound")
    if not isinstance(criterion, str) or not criterion.strip() or len(criterion) > 2048:
        return []
    try:
        root = ast.parse("(" + criterion.strip() + ")", mode="eval").body
    except (SyntaxError, ValueError):
        return []
    if not isinstance(root, ast.BoolOp) or not isinstance(root.op, ast.Or):
        return []
    if len(list(ast.walk(root))) > 256:
        return []
    choices = []

    def visit(node):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            return all(visit(value) for value in node.values)
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "IsBreedId"
            and not node.keywords
            and len(node.args) == 2
            and all(isinstance(arg, ast.Constant) for arg in node.args)
            and node.args[0].value == "target"
            and type(node.args[1].value) is int
            and node.args[1].value > 0
        ):
            return False
        breed = node.args[1].value
        if breed not in choices:
            choices.append(breed)
        return len(choices) <= limit

    return choices if visit(root) else []
