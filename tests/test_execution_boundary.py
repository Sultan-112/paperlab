import ast
from pathlib import Path


def test_market_providers_have_no_order_submission_calls():
    for path in Path("providers").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "create_order",
                    "submit_order",
                }, path


def test_broker_has_no_network_imports():
    tree = ast.parse(Path("services/broker.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name in {"httpx", "requests", "socket", "websockets"} for a in node.names)
