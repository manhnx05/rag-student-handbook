class StateManager:
    def __init__(self):
        self.state = {}

    def get_state(self, key: str):
        return self.state.get(key)

    def set_state(self, key: str, value: any):
        self.state[key] = value

    def clear_state(self, key: str):
        if key in self.state:
            del self.state[key]
