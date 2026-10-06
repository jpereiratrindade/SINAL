# ADR-0004: VLibras isolado por adapter

- Status: aceito para investigação
- Data: 2026-10-06

## Contexto

VLibras é o candidato inicial para aproveitar tecnologia aberta existente, mas
sua API, formato interno, cobertura, execução local e licença ainda precisam
ser verificados.

## Decisão

Toda integração ficará em um adapter atrás dos contratos de tradução e/ou
`LibrasRenderer`. Tipos e chamadas do VLibras não atravessarão essa fronteira.
Nenhuma dependência será adicionada antes da prova de conceito e análise de
licença da Fase 4.

## Alternativas consideradas

- usar VLibras como modelo central: acelera o protótipo, mas impede substituição;
- desenvolver tradutor e avatar próprios agora: escopo incompatível com o MVP;
- integrar apenas por automação visual: frágil e difícil de observar.

## Consequências

Será necessário mapear perdas entre LIBRAS-IR e VLibras. O restante do sistema
continua utilizável com mock, motor próprio ou outro renderer.

