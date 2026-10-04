"""Native fnE.EQUIP conditions, with explicit current sheet/unit ownership.

HasAnotherSameEquipment is eQb204/eLZ: same reference, DIFFERENT UID in
fpj/fpd or actual equipped fnZ. Inventory-bag duplicates are irrelevant.
"""
import ast
import json
from functools import lru_cache
from .paths import DATA_ROOT
from .combat_local_criteria import parse_local_criterion


@lru_cache(maxsize=1)
def catalog():
    return json.loads((DATA_ROOT / 'item-equipment-conditions.json').read_text())['items']


def evaluate(criteria, *, item, selected, owned, current_equipped=()):
    root = parse_local_criterion(criteria)
    def check(node):
        if isinstance(node, ast.Constant) and type(node.value) is bool:
            return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            check(node.operand); return
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            for value in node.values: check(value)
            return
        if isinstance(node, ast.IfExp):
            check(node.test);check(node.body);check(node.orelse);return
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'HasAnotherSameEquipment' and not node.args and not node.keywords:
            return
        raise ValueError('Native equipment criteria evaluation is not implemented: ' + criteria)
    def run(node):
        if isinstance(node, ast.Constant):return node.value
        if isinstance(node, ast.UnaryOp):return not run(node.operand)
        if isinstance(node, ast.BoolOp):
            return all(run(n) for n in node.values) if isinstance(node.op,ast.And) else any(run(n) for n in node.values)
        if isinstance(node, ast.IfExp):return run(node.body if run(node.test) else node.orelse)
        for row in (*selected, *current_equipped):
            uid = row['uid']; other = owned.get(uid)
            if other is None:raise ValueError('Equipment criterion references unavailable owned unit')
            if uid != item['uid'] and other['reference'] == item['reference']:
                return True
        return False
    check(root)
    return run(root)
