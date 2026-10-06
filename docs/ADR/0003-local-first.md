# ADR-0003: processamento local-first

- Status: aceito
- Data: 2026-10-06

## Contexto

Vídeos podem conter dados pessoais ou institucionais sensíveis. Serviços
externos também criam dependência de rede e custo variável.

## Decisão

O caminho padrão processa arquivos na máquina local. Nenhum upload ou chamada
externa será ativado implicitamente. Um backend remoto futuro exigirá seleção e
informação explícitas ao usuário.

## Alternativas consideradas

- serviço de nuvem obrigatório: simplifica alguns backends, mas viola
  privacidade e uso offline;
- fallback remoto automático: comportamento surpreendente e não auditável.

## Consequências

Modelos locais podem exigir mais armazenamento e processamento. Privacidade,
reprodutibilidade e funcionamento offline melhoram.

