# Agente Minimax / Max-n com informação oculta

Execute `.venv\Scripts\python.exe main.py` na raiz do projeto, escolha de dois
a quatro jogadores e a opção **3** do menu de agentes. O modo é individual:
cada jogador busca a própria vitória. Não inclui duplas. Os agentes aleatório e
guloso continuam disponíveis. No modo IA vs IA, todos usam o tipo escolhido,
como no fluxo original. No modo humano vs IA, P1 é humano e os demais são IAs.

Cada bot recebe uma instância própria do agente escolhido. No Minimax/Max-n,
o gerador de hipóteses e as estatísticas da decisão pertencem ao respectivo bot.
Decidir com P2 não altera os sorteios ou estatísticas de P3/P4. O código e a
estratégia são os mesmos; não há compartilhamento de mãos ocultas. O histórico
do motor é público e usado por cada IA a partir de sua própria perspectiva.

Com compra habilitada, o jogador compra até encontrar encaixe ou esgotar o monte.
Cada compra continua sendo uma ação do motor no mesmo turno. O humano confirma
cada compra com Enter; a IA compra automaticamente. Ao obter encaixe deve jogar.
A CLI não oferece mais a limitação de uma compra por turno. A API antiga do motor
continua aceitando `pull_one=True` para compatibilidade.

## Como decide

`Observation` contém apenas mão própria, mesa orientada, quantidade de peças
adversárias, tamanho do monte, histórico público e regras públicas. A conversão não percorre nem
indexa as peças reais adversárias ou do monte. O agente não copia a partida real.

As peças do conjunto duplo-seis que não aparecem na mão própria ou mesa formam
um conjunto desconhecido. Cada amostra redistribui esse conjunto
entre todas as mãos adversárias hipotéticas e um monte hipotético, respeitando os limites
deduzidos das compras e passes. Sem compras, as peças
restantes ficam fora da simulação, como peças não distribuídas.

Em cada hipótese, a busca usa o motor existente para validar ações e detectar
o resultado. Com dois jogadores usa **Minimax com Alfa-Beta**. Com três/quatro,
o padrão é **Max-n**: cada participante maximiza a própria componente de um
vetor de avaliações. Não usa a poda Alfa-Beta convencional nesse modo. Paranoid
permanece somente como referência interna para comparações. Comprar pode manter
o mesmo jogador; a busca respeita esse turno. A profundidade conta ações,
incluindo compras e passes. Vitórias/derrotas valem +10000/-10000; posições
intermediárias consideram quantidade de peças, pontos e mobilidade em relação
ao adversário mais ameaçador (menor avaliação relativa). Empates valem 0.
Para cada ação da raiz, a janela Alfa-Beta começa completa, evitando somar limites
de poda como se fossem avaliações exatas. Escolhe-se a melhor média das amostras
completas; uma amostra interrompida é descartada para todas as ações.

Padrões: profundidade 3, até 6 amostras, 2500 nós e orçamento de 0,2 segundo por
decisão. São limites configuráveis no construtor `MinimaxAgent`. O tempo é um
limite cooperativo verificado em cada nó, não uma garantia de tempo real nem
execução em segundo plano. Se não concluir uma amostra, retorna uma jogada legal
priorizando a soma de pontos da peça. `last_stats` informa nós, podas, amostras
completas e duração. O gerador aleatório é próprio e aceita `seed` para testes.

## Limitações

É Minimax sobre determinações hipotéticas, não uma solução ótima de dominó com
informação oculta. As restrições do histórico são necessárias, mas não reconstroem
exatamente todas as mãos e trajetórias possíveis. Dentro de cada hipótese a busca pressupõe
informação completa, o que pode introduzir viés. Não há garantia de superar o
agente guloso. Não inclui interface gráfica, treinamento ou novas dependências.

A profundidade padrão 3 conta ações, não voltas completas. Com três/quatro
jogadores pode não alcançar outra decisão da IA. Max-n melhora a representação
dos interesses individuais, mas não elimina essa limitação da busca.

## Verificação

Execute `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests`.
Os testes cobrem privacidade das peças, ausência de mutações, Minimax comparado
à busca exaustiva, limites, compra repetida, seleção no menu e partidas completas
contra os agentes existentes, com e sem monte.

## Dedução pelo histórico público

`Game.public_history` registra jogador, tipo de ação, pontas anteriores à ação
e somente a identidade das peças **jogadas**. Nunca registra peças compradas.
O histórico é limpo ao iniciar uma rodada e não inclui ações inválidas. A interface
gráfica pode continuar chamando `game.apply_action`: o registro ocorre no motor.

Se o adversário compra com pontas 2 e 5, sua mão imediatamente anterior não
continha nenhum desses números. Após uma compra pode haver até uma peça com
2 ou 5; após jogar essa peça, volta a não haver nenhuma, até uma nova compra.
Uma passagem sem compras posteriores implica limite zero para aqueles números.
Para cada evento, calcula-se o máximo atual como compras desde aquele evento
menos peças correspondentes jogadas depois. Compras próprias não são confundidas
com aquisições adversárias. Cada adversário tem suas próprias restrições:
compras de P2 não relaxam as pistas de P3. O histórico permanece público.

As mãos são amostradas por rejeição, até 64 tentativas por hipótese. Para
restrições fortes, uma busca conjunta de subconjuntos com até 4096 visitas
procura mãos válidas sem repetir peças nem esgotar indevidamente as opções dos
outros jogadores. Essa recuperação não tem distribuição uniforme. Se
o orçamento acabar sem uma hipótese válida completa, o agente usa a jogada legal
de reserva ou a melhor avaliação das hipóteses já completas, sem aceitar mãos
que violem as restrições. A ordem real do monte nunca é consultada.

## Comparação

`tools/compare_minimax.py` compara o agente com e sem uso do histórico, mantendo
os demais parâmetros, com seeds pareadas, lugares alternados e com/sem monte.
Use `.venv\Scripts\python.exe tools/compare_minimax.py --seeds 30`.
O relatório JSON é escrito em `reports/minimax_comparison.json`. A referência
sem histórico é apenas do experimento; o menu oferece um único MinimaxAgent.
O parâmetro opcional `--baseline-path` permite comparar com uma cópia externa
da implementação anterior. Vitórias de uma amostra não provam superioridade.

### Resultado histórico em 17/11/2026 (versão para dois jogadores)

Comparação com cópia da implementação anterior: 480 rodadas contra os agentes
aleatório/guloso e 120 confrontos diretos, totalizando 600 rodadas. Cada versão
enfrentou os agentes existentes em 240 rodadas. Usaram-se 30 seeds, ambos os
lugares e cenários com/sem monte, sem ajustar parâmetros aos resultados.

| Adversário / monte | Vitórias anterior (60 jogos) | Vitórias com histórico (60 jogos) |
| --- | ---: | ---: |
| Aleatório / sem monte | 34 | 38 |
| Aleatório / com monte | 37 | 41 |
| Guloso / sem monte | 24 | 29 |
| Guloso / com monte | 37 | 40 |
| Total | 132/240 | 148/240 |

No confronto direto, a versão com histórico teve **52 vitórias, 67 derrotas e
1 empate**. Portanto, o resultado é misto; não se afirma superioridade geral.
Nos jogos contra os agentes existentes, o tempo médio por decisão foi 11,16 ms
na anterior e 10,89 ms com histórico; máximos de 108,96 e 99,60 ms, respectivamente.
São medições locais, não garantias de latência nem resultado estatístico definitivo.
O histórico foi mantido como parte da única versão do agente, por incorporar
as pistas públicas solicitadas, sem alegar aumento garantido de força de jogo.

### Benchmark histórico paranoid em 19/11/2026 (anterior ao padrão Max-n)

Execute `.venv\Scripts\python.exe tools/benchmark_multiplayer.py --seeds 4`.
Relatório: `reports/minimax_multiplayer.json`. Foram 144 partidas individuais,
com 5 peças iniciais, com/sem monte, lugares alternados e adversários homogêneos
aleatórios ou gulosos. Todos os jogos terminaram; nenhuma busca iniciada ficou
sem amostra completa nessa medição. A tabela agrega ambos os adversários/regras.

| Jogadores | Partidas | Vitórias da IA | Média por decisão | Máximo |
| --- | ---: | ---: | ---: | ---: |
| 2 | 32 | 20 | 6,52 ms | 34,38 ms |
| 3 | 48 | 18 | 8,29 ms | 50,35 ms |
| 4 | 64 | 17 | 8,72 ms | 64,67 ms |

São poucos seeds: os resultados verificam funcionamento e custo, não provam
superioridade sobre os oponentes ou sobre Max-n, ainda não implementado naquela data.
Vitórias entre quantidades diferentes de jogadores não são diretamente comparáveis.
Também foram concluídas partidas pelo `main.py` com todos os participantes
controlados pelo agente, para 2, 3 e 4 jogadores. A integração gráfica segue pendente.

### Escolha atual em 25/11/2026

Após comparação controlada de **1920 partidas**, o padrão passou a Max-n para
três/quatro jogadores, mantendo Minimax com Alfa-Beta para dois. Max-n teve mais
vitórias nas comparações agregadas, mas os intervalos exploratórios incluem
empate de desempenho: não se demonstrou superioridade estatística. O tempo
médio ficou semelhante. Métodos, resultados e ressalvas estão em
`SEARCH_COMPARISON.md`; os dados completos estão em `reports/maxn_vs_paranoid.json`.

`MinimaxAgent()` seleciona automaticamente. Para reproduzir os experimentos,
`MinimaxAgent(strategy="paranoid")` força a referência antiga, e
`MinimaxAgent(strategy="maxn")` força a busca Max-n para três/quatro jogadores.
O parâmetro não cria novos agentes ou opções no menu. Os testes também verificam
que Max-n maximiza o interesse do participante do turno e coincide com a busca
vetorial exaustiva em cenários controlados, sem ler mãos ocultas reais.

### Conferência da entrega em 25/11/2026

Foi executado `git fetch origin`. A `origin/main` permanece em `7d26a95`, mesma
base desta implementação: não foram encontrados novos commits remotos para
conciliar. As alterações locais foram preservadas. A suíte passou com **114
testes**, incluindo construção independente dos bots nos modos humano/IA e
IA/IA, para 2/3/4 jogadores e os três tipos de agentes. A independência dos
geradores e estatísticas do Minimax/Max-n também foi verificada após uma decisão.
A interface gráfica continua pendente do trabalho do colega e de validação conjunta.
