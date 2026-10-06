# ADR-0001: LIBRAS-IR como fronteira obrigatória

- Status: aceito
- Data: 2026-10-06

## Contexto

Texto português, estrutura de Libras, movimento corporal e avatar são domínios
distintos. Um backend inicial não pode definir toda a arquitetura.

## Decisão

Todo renderer receberá um LIBRAS-IR versionado e validado. Tradutores não
chamarão diretamente APIs de avatar, e renderers não receberão português cru.

## Alternativas consideradas

- texto/glosas enviados diretamente ao VLibras: menor custo inicial, mas cria
  acoplamento e perde informação linguística;
- formato interno de um avatar: impede substituição do motor;
- vídeo intermediário como contrato: não é auditável nem editável no nível
  linguístico.

## Consequências

Há custo inicial de esquema, validação e adapters. Em troca, tradução,
movimento e renderização evoluem e são testados independentemente.

