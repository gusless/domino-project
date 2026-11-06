import time
from domino.game import Game
from agents.random_agent import RandomAgent
from agents.greedy_agent import GreedyAgent

def executar_torneio_silencioso(rodadas=1000):
    print(f"Iniciando simulação de {rodadas} rodadas...")
    print("Aleatório (Jogador 1) vs Guloso (Jogador 2) vs Aleatório (Jogador 3) vs Guloso (Jogador 4)\n")
    
    vitorias = {"P1 (Aleatório)": 0, "P2 (Guloso)": 0, "P3 (Aleatório)": 0, "P4 (Guloso)": 0, "Empate": 0}
    tempos_por_rodada = []
    
    agentes_config = [
        RandomAgent(), # P1
        GreedyAgent(), # P2
        RandomAgent(), # P3
        GreedyAgent()  # P4
    ]

    for _ in range(rodadas):
        jogo = Game()

        jogo.start_round(n_players=4, tile_count=7, has_stock=True, pull_one=True)
        
        inicio_rodada = time.time()

        while not jogo.round_over:
            jogador_atual_idx = jogo.current_player_index
            agente = agentes_config[jogador_atual_idx]

            acao = agente.choose_action(jogo)

            jogo.apply_action(acao)
            
        fim_rodada = time.time()
        tempos_por_rodada.append(fim_rodada - inicio_rodada)

        if jogo.winner:
            nome = f"P{jogo.players.index(jogo.winner) + 1}"
            if nome in ["P1", "P3"]:
                vitorias[f"{nome} (Aleatório)"] += 1
            else:
                vitorias[f"{nome} (Guloso)"] += 1
        else:
            vitorias["Empate"] += 1

    total_aleatorio = vitorias["P1 (Aleatório)"] + vitorias["P3 (Aleatório)"]
    total_guloso = vitorias["P2 (Guloso)"] + vitorias["P4 (Guloso)"]
    tempo_medio = sum(tempos_por_rodada) / len(tempos_por_rodada)
    
    print("-" * 40)
    print("MÉTRICAS DE PERFORMANCE DO PROJETO")
    print("-" * 40)
    print(f"Taxa de Vitória - Equipe Aleatória (P1, P3): {(total_aleatorio/rodadas)*100:.2f}%")
    print(f"Taxa de Vitória - Equipe Gulosa    (P2, P4): {(total_guloso/rodadas)*100:.2f}%")
    print(f"Partidas Trancadas s/ Vencedor Único:        {(vitorias['Empate']/rodadas)*100:.2f}%")
    print(f"Tempo médio por partida completa:            {tempo_medio:.6f} segundos")

if __name__ == "__main__":
    executar_torneio_silencioso(1000)