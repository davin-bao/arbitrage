# debug_profiler.py
import sys
import inspect
import threading

def profiler(frame, event, arg):
    if event not in ("call", "return"):
        return profiler

    code = frame.f_code
    func_name = code.co_name
    module = frame.f_globals.get("__name__", "")

    # 过滤系统库
    if not module.startswith("arbitrage"):
        return profiler

    if event == "call":
        args = inspect.getargvalues(frame)
        print(f"[CALL] {module}.{func_name} args={args.locals}")

    elif event == "return":
        print(f"[RET ] {module}.{func_name} -> {arg}")

    return profiler


def enable():
    sys.setprofile(profiler)
    threading.setprofile(profiler)
