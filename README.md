# SINAL

**Sistema Inteligente de Acessibilidade Narrativa em Libras**

O SINAL é uma arquitetura local-first para transformar conteúdo audiovisual em
uma representação linguística e corporal de Libras. O projeto separa extração
de conteúdo, transcrição, tradução, LIBRAS-IR, movimento, renderização e
composição. Ele não trata Libras como substituição palavra por palavra do
português.

> Estado atual: o pipeline de mídia e o contrato LIBRAS-IR estão implementados.
> A renderização procedural é somente uma pré-visualização técnica. Para vídeo
> real, o SINAL captura o player web oficial do VLibras e preserva a velocidade
> natural dos sinais. Traduções automáticas continuam exigindo revisão humana.

## O que já funciona

- inspeção de vídeo, áudio e legendas com FFprobe;
- seleção do stream padrão de áudio ou legenda;
- extração de legendas textuais incorporadas para SRT;
- transcrição de áudio para SRT (`sinal transcribe`, com suporte a Whisper e mock);
- validação de SRT externo e incorporação como faixa selecionável em MP4;
- parser e escritor SRT com timestamps e texto multilinha;
- geração e validação estrita do LIBRAS-IR 0.1.0;
- mock honesto, que registra tradução pendente sem inventar sinais;
- adaptadores para tradução textual e captura do player WebGL oficial atual;
- auditoria fail-closed de tradução, lacunas, proveniência e cobertura de movimentos;
- pré-visualizador procedural sincronizado, sempre marcado visualmente como não validado;
- compositor FFmpeg (`sinal compose`), sobrepondo o avatar nos quatro cantos (`bottom-right`, `bottom-left`, `top-right`, `top-left`) com preservação de faixas;
- orquestrador fail-closed, que bloqueia composição quando a Libras natural não cabe na timeline;
- detecção dinâmica de encoders H.264/compatíveis no FFmpeg (suporte multiplataforma para Fedora, Ubuntu, Arch, etc.);
- saída humana ou JSON no comando de inspeção;
- erros explícitos e sem dependências ocultas.

## Requisitos

- Linux;
- Python 3.12 ou posterior;
- FFmpeg e FFprobe acessíveis no `PATH`.
- para o backend oficial: Node.js, Chromium/Playwright e um checkout compilado
  de `vlibras-web-browsers` (veja [VLibras Web](docs/VLIBRAS_VIDEO.md)).

No Fedora:

```bash
sudo dnf install ffmpeg
```

No Debian/Ubuntu:

```bash
sudo apt install ffmpeg
```

## Instalação para desenvolvimento

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Sem instalar, também é possível executar a partir da raiz do repositório:

```bash
python -m sinal --version
```

## Uso

### 1. Inspecionar mídia
```bash
sinal inspect video.mp4
sinal inspect video.mp4 --json
```

### 2. Extrair ou transcrever legendas
```bash
# Extrair de faixa embutida no arquivo
sinal extract-subtitles video.mp4 -o video.srt

# Ou transcrever o áudio
sinal transcribe video.mp4 -o video.srt --engine mock
```

### 3. Gerar e validar o LIBRAS-IR
```bash
# Modo padrão e seguro: registra lacunas sem inventar glosas
sinal build-ir video.srt --engine mock --output video.libras-ir.json

# Ou usando a tradução oficial do VLibras
sinal build-ir video.srt --engine vlibras \
  --endpoint https://traducao2.vlibras.gov.br --allow-network

# Validar contra o esquema 0.1.0
sinal validate-ir video.libras-ir.json
```

### 4. Auditar e renderizar

Um documento só fica linguisticamente pronto quando `review.status` indica
revisão humana e todos os IDs possuem movimento revisado no catálogo. Veja
[Catálogo de movimentos](docs/MOTION_CATALOG.md).

```bash
sinal audit-render video.libras-ir.json --motion-catalog motions.reviewed.json
```

Para produzir um MP4 autônomo, em velocidade natural, com a Hosana oficial:

```bash
export SINAL_VLIBRAS_WEB_ROOT='/caminho/para/vlibras-web-browsers'
sinal render video.libras-ir.json --backend vlibras --avatar hosana \
  --allow-network -o avatar.mp4
```

O backend aguarda o contador do player concluir todos os sinais, valida o MP4 e
grava `avatar.mp4.provenance.json`. Veja [VLibras Web](docs/VLIBRAS_VIDEO.md).

O renderer procedural não possui a malha SINA rigada nem articulação
suficiente para produção. Para depurar timeline e enquadramento com aviso visível:

```bash
sinal render video.libras-ir.json --backend preview -o preview.mp4
```

### 5. Compor o vídeo final

A composição só é aceita quando o sidecar confirma compatibilidade temporal.
O SINAL não acelera sinais arbitrariamente para fazê-los caber.

```bash
sinal compose video.mp4 --avatar avatar.mp4 --position bottom-right -o video-final.mp4
```

### 6. Executar o pipeline validado em um único comando

Para tradução e avatar oficiais, selecione VLibras explicitamente:

```bash
sinal process video.mp4 --srt video.srt --render --engine vlibras \
  --endpoint https://traducao2.vlibras.gov.br \
  --vlibras-root "$SINAL_VLIBRAS_WEB_ROOT" --avatar hosana \
  --allow-network --position bottom-right -o video-final.mp4
```

Se a interpretação natural for maior que a mídia, o vídeo de avatar e o
diagnóstico são preservados, mas a composição final é interrompida.

## Testes

Os testes usam `unittest` da biblioteca padrão e também são descobertos pelo
Pytest:

```bash
python -m unittest discover -s tests -v
# ou, após instalar o extra dev:
pytest
```

## Arquitetura e princípios

```text
fonte audiovisual
       │
       ▼
texto pt-BR ──► análise/tradução ──► LIBRAS-IR
                                      │
                         ┌────────────┼────────────┐
                         ▼            ▼            ▼
                       sinais       corpo         face
                         └────────────┼────────────┘
                                      ▼
                             renderer substituível
                                      ▼
                              composição de vídeo
```

O LIBRAS-IR é o contrato obrigatório entre a camada linguística e os
renderizadores. VLibras será um backend por adaptador, nunca uma dependência
espalhada pelo sistema. Veja [Arquitetura](docs/ARCHITECTURE.md),
[LIBRAS-IR](docs/LIBRAS_IR.md), [Pipeline](docs/PIPELINE.md) e
[Roadmap](docs/ROADMAP.md).

## Limitações atuais

- legendas bitmap (PGS, VobSub etc.) não podem ser convertidas para texto sem OCR;
- o parser SRT não tenta corrigir arquivos estruturalmente inválidos;
- arquivos com múltiplas legendas exigem `--stream` quando a seleção padrão não
  for a desejada;
- a configuração TOML é um contrato inicial e ainda não é carregada pelo CLI;
- a geração oficial requer o runtime web do VLibras compilado localmente e rede
  para obter os movimentos do dicionário oficial;
- a imagem-conceito da SINA não é uma malha 3D rigada. O renderizador procedural
  atual não reproduz aquela identidade visual e, por isso, é apenas preview;
- os movimentos internos são protótipos não revisados e nunca passam na auditoria
  de produção;
- a duração da sinalização pode exceder a mídia original e exigir edição humana
  da timeline ou pausas adicionais;
- tradução automática não garante equivalência com interpretação humana.

## Ética e revisão

Conteúdo automático deverá ser identificado, registrar confiança e proveniência
e permanecer revisável por pessoas. O projeto não inventará sinais ausentes e
deverá ser validado com participação de pessoas surdas e especialistas em
Libras.

## Licença

A licença aberta ainda será escolhida após análise das dependências e da
integração com VLibras. Até essa decisão, consulte o arquivo `LICENSE`: não há
permissão de uso ou redistribuição implícita.
