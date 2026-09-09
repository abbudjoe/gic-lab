"""Bound upstream test input for the retained runtime wrapper; never a SiRA run.

The wrapper installs its actual locked LLM factory and instruments this agent and
browser. Session content comes from the returned fake effect, not from a supplied
completion receipt. The bootstrap supplies only explicit local fixture inputs.
"""

import json
import os
from types import SimpleNamespace

from giclab_offline_condition_inputs import inputs


def make_llm(*args, **kwargs):
    raise AssertionError("the retained locked LLM factory did not execute")


class Agent:
    def __init__(self, models):
        self.models = models

    def step(self, observation):
        roles = ("world_model", "critic") if inputs.mode == "simulative" else ("default", "actor")
        response = None
        for role in roles:
            response = self.models[role]._completion(
                messages=[{"role": "user", "content": "offline fixture observation"}],
                max_completion_tokens=64,
            )
        return response["choices"][0]["message"]["content"], {"fixture": "offline-condition-1"}


def make_agent(models):
    return Agent(models)


class Browser:
    def step(self, action):
        if not isinstance(action, str):
            raise AssertionError("fixture browser requires the actual effect response")
        return {"url": "about:blank"}, 0.0, action.startswith("send_msg_to_user("), False, {}

    def close(self):
        pass


gym = SimpleNamespace(make=lambda: Browser())


def get_serializable_obs(environment, observation):
    return observation


def get_agent_logger(*args, **kwargs):
    raise AssertionError("fixture logger must be bound through the retained wrapper")


def main():
    models = make_llm("gpt-4o-2024-11-20", os.environ["SIRA_API_KEY"])
    agent = make_agent(models)
    browser = gym.make()
    action, thought = agent.step({"url": "about:blank"})
    observation, _reward, complete, _truncated, _info = browser.step(action)
    document = {
        "goal": inputs.goal,
        "instance_id": None,
        "history": [[observation, action, thought]],
        "is_complete": complete,
        "error": "" if complete else "fixture task ended without an answer",
    }
    inputs.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (inputs.output / "offline-session.json").open("x") as stream:
        json.dump(document, stream, sort_keys=True)
        stream.write("\n")
    # Separately bound negative input: actual attach bytes after actual partial
    # session production. The host writer, not this fixture, must prevent growth.
    for _ in range(inputs.attach_output_blocks):
        os.write(1, b"x" * 65536)
    if inputs.process_failure:
        raise RuntimeError("fixture upstream process failed after partial session output")
