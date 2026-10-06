# Catálogo de movimentos

O catálogo liga cada ID do LIBRAS-IR a keyframes aplicados ao mesmo rig. Isso
mantém a identidade do avatar estável; trocar imagens a cada frame ou gerar
gestos por IA não faz parte do pipeline.

## Regra de publicação

O pipeline opera em modo *fail closed*. Para produzir um vídeo rotulado como
Libras, as três condições abaixo precisam ser verdadeiras:

1. `review.status` do LIBRAS-IR é `human-reviewed`, `human-corrected` ou
   `approved`;
2. todo sinal possui movimento em um catálogo `libras-BR` com revisor, data e
   estado de revisão equivalente;
3. o renderer usa um avatar rigado e validado. O renderer procedural incluído
   no repositório não atende a este requisito e funciona somente como preview.

Glosa não implica movimento. Uma palavra desconhecida nunca é substituída por
pose neutra, hash, gesto genérico ou movimento visualmente plausível.

## Formato 1.0.0

```json
{
  "schema": "sinal.motion-catalog",
  "version": "1.0.0",
  "language": "libras-BR",
  "source": {
    "name": "Nome do corpus ou laboratório",
    "version": "2026.1",
    "url": "https://origem.example/catalogo"
  },
  "review": {
    "status": "approved",
    "reviewer": "Nome ou identificador do especialista",
    "reviewed_at": "2026-10-06"
  },
  "motions": [
    {
      "id": "EXEMPLO",
      "description": "Descrição articulatória revisada",
      "dominant_hand": "right",
      "is_two_handed": false,
      "keyframes": [
        {
          "time": 0.0,
          "pose": {
            "left_elbow": [-0.24, -0.02, 0.12],
            "left_wrist": [-0.12, 0.08, 0.24],
            "right_elbow": [0.24, -0.02, 0.12],
            "right_wrist": [0.12, 0.08, 0.24],
            "left_hand": {"thumb": 0.2, "index": 0.2, "middle": 0.2, "ring": 0.2, "pinky": 0.2},
            "right_hand": {"thumb": 0.2, "index": 0.2, "middle": 0.2, "ring": 0.2, "pinky": 0.2},
            "head_rotation": [0.0, 0.0, 0.0],
            "eyebrow_raise": 0.0,
            "mouth_open": 0.0
          }
        },
        {
          "time": 1.0,
          "pose": {
            "left_elbow": [-0.24, -0.02, 0.12],
            "left_wrist": [-0.12, 0.08, 0.24],
            "right_elbow": [0.24, -0.02, 0.12],
            "right_wrist": [0.12, 0.08, 0.24]
          }
        }
      ]
    }
  ]
}
```

Os tempos de cada movimento devem começar em `0.0`, terminar em `1.0` e ser
estritamente crescentes. Flexões dos dedos e marcadores faciais usam o intervalo
de `0.0` a `1.0`.

## Auditoria

```bash
sinal audit-render video.libras-ir.json --motion-catalog motions.reviewed.json
sinal audit-render video.libras-ir.json --motion-catalog motions.reviewed.json --json
```

O comando retorna `0` somente quando a cobertura e a revisão linguísticas estão completas.
Retorna `1` para documentos automáticos, lacunas, movimentos ausentes ou
movimentos sem proveniência revisada.
