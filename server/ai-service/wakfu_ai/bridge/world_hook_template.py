"""The single final world function, kept here for review and regression tests."""

HOOK = """def pass_test_monster_turn():
    import hashlib
    import pathlib
    import sys
    import types

    directory = pathlib.Path(os.environ.get("WAKFU_AI_SDK_DIR",
        str(pathlib.Path(__file__).resolve().parent / "ai-service")))
    path = directory / "world_loader.py"
    source = path.read_bytes()
    name = "_wakfu_world_ai_loader_" + hashlib.sha256(source).hexdigest()
    loader = sys.modules.get(name)
    if loader is None:
        candidate = types.ModuleType(name)
        candidate.__file__ = str(path)
        exec(compile(source, str(path), "exec"), candidate.__dict__)
        loader = sys.modules.setdefault(name, candidate)
    entry = loader.load_entry(directory)
    scopes = []
    frame = sys._getframe(1)
    try:
        while frame is not None:
            if frame.f_globals is globals():
                scopes.append(dict(frame.f_locals))
            frame = frame.f_back
    finally:
        del frame
    for _ in entry(fight_messages, world_context=dict(globals=globals(), scopes=scopes)):
        pass
"""
