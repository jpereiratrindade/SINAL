# Backend VLibras Web

O backend de vídeo usa o player WebGL do repositório oficial
`spbgovbr-vlibras/vlibras-web-browsers`. Isso evita dois erros do protótipo
anterior: movimentos inventados pelo SINAL e seleção de avatar ignorada por um
worker de vídeo legado.

O fluxo é:

1. traduzir o texto pt-BR no endpoint oficial `/translate`;
2. validar o LIBRAS-IR e rejeitar pré-glosas experimentais;
3. abrir localmente o player oficial em Chromium isolado;
4. selecionar explicitamente Hosana, Ícaro ou Guga;
5. reproduzir a glosa e aguardar o contador confirmar todos os sinais;
6. capturar a animação em velocidade natural e validar o MP4 com FFprobe;
7. gravar um sidecar de proveniência.

## Instalação reproduzível

Use uma revisão auditada do projeto oficial. A revisão usada na prova de
integração do SINAL foi `d292d369419196b6e8ba826d674f5d3b4bcefa9a`.

```bash
git clone https://github.com/spbgovbr-vlibras/vlibras-web-browsers.git
cd vlibras-web-browsers
git checkout d292d369419196b6e8ba826d674f5d3b4bcefa9a
corepack enable
pnpm install --frozen-lockfile
pnpm build
pnpm exec playwright install chromium
export SINAL_VLIBRAS_WEB_ROOT="$PWD"
```

Se instalado em `~/.local/share/sinal/vlibras-web-browsers`, o runtime é
descoberto automaticamente e a variável não é necessária.

O checkout oficial e seus arquivos WebGL não são copiados para este
repositório. Isso mantém autoria, licença e atualização separadas.

## Renderização

```bash
sinal render video.libras-ir.json \
  --backend vlibras \
  --avatar hosana \
  --allow-network \
  --output avatar.mp4
```

`--allow-network` é obrigatório porque os movimentos são obtidos do dicionário
oficial do VLibras. O arquivo `avatar.mp4.provenance.json` registra versão do
runtime, avatar, tradutor, revisão, número de sinais concluídos e diferença de
duração.

## Política de sincronismo

A duração natural de uma interpretação em Libras frequentemente é maior que a
janela de uma legenda em português. Acelerar arbitrariamente o avatar pode
tornar os sinais ilegíveis. Por isso:

- `sinal render` sem `--media`/`--duration` gera um vídeo autônomo em velocidade
  natural;
- quando uma duração é solicitada, uma diferença maior que 1 segundo bloqueia
  a composição, mas preserva o vídeo autônomo e seu diagnóstico;
- `sinal compose` também recusa um sidecar marcado como não sincronizado.

Resolver esse conflito exige edição da timeline, pausas no conteúdo original
ou revisão humana — não compressão ilimitada dos sinais.

## Garantias e limites

- A animação vem do player e do dicionário oficiais, não de keyframes
  procedurais do SINAL.
- O capturador confirma que o contador do player concluiu todos os sinais.
- A tradução automática ainda pode conter erros linguísticos e deve ser
  revisada por pessoa surda/especialista antes da publicação.
- A Hosana oficial atual é uma personagem 3D estilizada. A imagem-conceito
  fotorrealista da SINA não é um modelo 3D rigado e não pode substituir o avatar
  sem produção de malha, rig facial/manual e biblioteca de movimentos.
