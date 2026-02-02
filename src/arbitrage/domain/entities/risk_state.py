class RiskState:
    def __init__(self):
        self.halted = False
        self.reason = None

    def enter_fatal(self, reason: str):
        self.halted = True
        self.reason = reason

    def is_halted(self) -> bool:
        return self.halted
