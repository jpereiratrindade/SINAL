# ADR-0004: VLibras isolado por adapter

- Status: aceito; tradução textual em prova de conceito
- Data: 2026-10-06

## Contexto

VLibras é o candidato inicial para aproveitar tecnologia aberta existente. A
auditoria dos repositórios oficiais encontrou uma API com operações separadas
para [tradução textual e solicitação de vídeo][api]. A geração de vídeo depende
de um serviço chamado Video Core; ele não aparece entre os repositórios públicos
da [organização oficial][org]. O endpoint remoto de vídeo também não constitui
um contrato anônimo adequado ao CLI. Essa ausência é uma inferência a partir do
material público disponível em 2026-10-06, não a afirmação de que o componente
não exista internamente.

## Decisão

Toda integração fica em um adapter atrás dos contratos de tradução e/ou
`LibrasRenderer`. O primeiro adapter usa apenas `POST /translate` de uma
instância configurada pelo operador. Não há endpoint remoto padrão: o valor
inicial é local (`127.0.0.1`) e a CLI exige `--allow-network`, mesmo nesse caso,
para tornar o envio do texto observável. O SINAL não imita cabeçalhos do widget
oficial nem tenta contornar controles do serviço público.

O retorno textual é preservado como glosa automática na LIBRAS-IR. Como esse
contrato não informa a duração de cada sinal, a distribuição dentro do segmento
é marcada como `estimated-uniform`. Renderização continuará atrás de
`LibrasRenderer` e não será alegada até existir um backend verificável.

## Alternativas consideradas

- usar VLibras como modelo central: acelera o protótipo, mas impede substituição;
- desenvolver tradutor e avatar próprios agora: escopo incompatível com o MVP;
- integrar apenas por automação visual: frágil e difícil de observar.

## Consequências

Será necessário mapear perdas entre LIBRAS-IR e VLibras. O restante do sistema
continua utilizável com mock, motor próprio ou outro renderer. Uma instalação
local completa da API oficial ainda exige serviços externos descritos no
próprio repositório, inclusive seu Video Core.

[api]: https://github.com/spbgovbr-vlibras/vlibras-translator-api
[org]: https://github.com/spbgovbr-vlibras
