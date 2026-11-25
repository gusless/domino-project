# Max-n versus paranoid

## O que muda

O mesmo `MinimaxAgent` oferece duas buscas internas para os testes:
`strategy="paranoid"` e `strategy="maxn"`. Não são novos jogadores ou opções
de menu; a seleção normal continua automática. Para dois jogadores mantém-se
Minimax com Alfa-Beta, independentemente da opção multijogador solicitada.

Paranoid maximiza uma avaliação da IA e a minimiza nos turnos de todos os
adversários. Max-n propaga um vetor com uma avaliação por jogador. No turno de
P2, escolhe o ramo que melhora a componente de P2, não o que piora a da IA.
Empates mantêm a primeira ação na mesma ordenação usada pelo paranoid.
Não se aplica a poda Alfa-Beta convencional aos vetores Max-n.

Em ambas as buscas, as decisões reais recebem somente a mão própria e os dados
públicos. As mãos dos outros são hipotéticas, respeitando contagens, ausência
de duplicação e restrições deduzidas das compras/passes de cada jogador.
O Max-n consulta todas as mãos somente nos estados **hipotéticos**, nunca na
partida real. Compras podem manter o mesmo jogador e isso é respeitado na busca.

## Comparação controlada

Execute `.venv\Scripts\python.exe tools/compare_searches.py --seeds 12`.
O resultado completo fica em `reports/maxn_vs_paranoid.json`.

Ambas as estratégias usam profundidade 3, até 6 hipóteses, 2500 nós e orçamento
cooperativo de 0,2 segundo por decisão. A avaliação de uma posição para a IA é
a mesma; Max-n calcula a fórmula equivalente para cada participante. Não se
ajustaram parâmetros para favorecer uma estratégia após observar os resultados.

O benchmark cobre 3/4 jogadores, 5/7 peças iniciais, com/sem monte e todos os
lugares da mesa. As seeds das distribuições e das amostras são pareadas. São
1344 partidas contra aleatórios/gulosos e 576 confrontos mistos entre as duas
buscas (1920 partidas no total, com 12 seeds). Nos confrontos com 3 jogadores,
há tanto um Max-n contra dois paranoid quanto a composição inversa, em todos
os lugares. Com 4 jogadores são dois de cada busca, nas seis distribuições de
lugares possíveis. Não há duplas: cada jogador busca a própria vitória.

Com quatro jogadores e sete peças, as 28 peças são distribuídas: os cenários
com/sem monte são equivalentes nesse caso, o que é considerado uma limitação
do desenho e não duas evidências independentes de superioridade.

Os intervalos exploratórios reamostram blocos de seeds, preservando os lugares
e cenários de cada seed. O saldo de pontuação considera vitória=1, empate=0,5
e derrota=0. Seeds e lugares não são tratados como jogos independentes para
estimar o intervalo. Não é um torneio exaustivo nem prova de superioridade geral.

## Limitações comuns

A busca continua curta: três ações podem não alcançar todos os adversários,
principalmente com quatro jogadores e compras repetidas. Max-n não elimina
essa limitação por si só. Ambos usam determinações hipotéticas, sem resolver
completamente a informação oculta. O orçamento de tempo pode interromper uma
hipótese; somente hipóteses completas participam da média. Melhor desempenho
medido em um conjunto de partidas não garante melhor desempenho contra humanos.

## Resultado em 25/11/2026

| Cenário | Jogos por busca | Vitórias paranoid | Vitórias Max-n |
| --- | ---: | ---: | ---: |
| 3 jogadores contra aleatório/guloso | 288 | 104 | 107 |
| 4 jogadores contra aleatório/guloso | 384 | 107 | 122 |

| Confronto misto direto | Jogos totais | Vitórias paranoid | Vitórias Max-n | Empates |
| --- | ---: | ---: | ---: | ---: |
| 3 jogadores | 288 | 134 | 149 | 5 |
| 4 jogadores | 288 | 142 | 145 | 1 |

Tempo médio contra os agentes existentes: com três jogadores, 21,44 ms para
paranoid e 21,36 ms para Max-n; com quatro, 22,52 e 22,45 ms. Não há evidência
de aceleração relevante. Algumas decisões atingiram aproximadamente 200 ms;
o limite cooperativo pode ser ultrapassado ligeiramente pelo nó em execução.
Nenhuma busca iniciada nesses jogos ficou sem hipótese completa.

**Escolha de entrega:** modo automático usa Minimax/Alfa-Beta para dois e Max-n
para três/quatro jogadores. A classe, as observações, as regras e as hipóteses
continuam compartilhadas. Paranoid fica acessível só como referência interna de
experimento, sem outro agente ou opção de seleção de estratégia para o jogador.

Max-n ganhou mais jogos nas quatro comparações agregadas e representa interesses
individuais, com tempo médio semelhante. Porém, os intervalos bootstrap de 95%
em blocos de seeds incluem zero em todos os casos. Logo, o resultado **sugere**
uma melhora nesta amostra, sem demonstrar superioridade estatística nem universal.
Não se aumentou a profundidade ou mudou a avaliação para obter esse resultado.
