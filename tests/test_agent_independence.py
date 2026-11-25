import pytest

import main as entrypoint
from agents import GreedyAgent, MinimaxAgent, RandomAgent
from controllers import AgentController, HumanController


@pytest.mark.parametrize("players", [2, 3, 4])
@pytest.mark.parametrize("all_ai", [False, True])
@pytest.mark.parametrize("agent_class", [RandomAgent, GreedyAgent, MinimaxAgent])
def test_main_creates_one_agent_per_bot(monkeypatch, players, all_ai, agent_class):
    captured = []

    class FakeCLI:
        def ask_configuration(self):
            return players, 5, True, False

        def ask_agent_type(self, count):
            assert count == players
            return agent_class()

        def ask_agent_vs_agent(self):
            return all_ai

        def play_round(self, game, controllers):
            assert len(game.players) == players
            captured.extend(controllers)

        def ask_yes_no(self, prompt):
            return False

    monkeypatch.setattr(entrypoint, "CLI", FakeCLI)
    entrypoint.main()

    assert len(captured) == players
    if not all_ai:
        assert isinstance(captured[0], HumanController)
    bots = [controller.agent for controller in captured if isinstance(controller, AgentController)]
    assert len(bots) == (players if all_ai else players - 1)
    assert all(type(bot) is agent_class for bot in bots)
    assert len({id(bot) for bot in bots}) == len(bots)


def test_main_bot_decision_does_not_change_other_bots_state(monkeypatch):
    class FakeCLI:
        def ask_configuration(self):
            return 4, 5, True, False

        def ask_agent_type(self, count):
            return MinimaxAgent()

        def ask_agent_vs_agent(self):
            return True

        def play_round(self, game, controllers):
            agents = [controller.agent for controller in controllers]
            assert len({id(agent.rng) for agent in agents}) == 4
            assert len({id(agent.last_stats) for agent in agents}) == 4
            others_rng = [agent.rng.getstate() for agent in agents[1:]]
            others_stats = [dict(agent.last_stats) for agent in agents[1:]]
            game.current_player_index = 0
            action = agents[0].choose_action(game)
            assert agents[0].last_stats["samples"] > 0
            assert [agent.rng.getstate() for agent in agents[1:]] == others_rng
            assert [agent.last_stats for agent in agents[1:]] == others_stats
            game.apply_action(action)

        def ask_yes_no(self, prompt):
            return False

    monkeypatch.setattr(entrypoint, "CLI", FakeCLI)
    entrypoint.main()
