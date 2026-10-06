# SINAL

**Sistema Inteligente de Acessibilidade Narrativa em Libras**

O SINAL é uma arquitetura local-first para transformar conteúdo audiovisual em
uma representação linguística e corporal de Libras. O projeto separa extração
de conteúdo, transcrição, tradução, LIBRAS-IR, movimento, renderização e
composição. Ele não trata Libras como substituição palavra por palavra do
português.

> Estado atual: pipeline de acessibilidade de ponta a ponta implementado.
> Suporta inspeção, extração e transcrição de legendas (Whisper/mock), geração e
> validação de LIBRAS-IR (mock/VLibras), renderização de avatar/janela de Libras e
> composição audiovisual com preservação de áudio e legendas.

## O que já funciona

- inspeção de vídeo, áudio e legendas com FFprobe;
- seleção do stream padrão de áudio ou legenda;
- extração de legendas textuais incorporadas para SRT;
- transcrição de áudio para SRT (`sinal transcribe`, com suporte a Whisper e mock);
- validação de SRT externo e incorporação como faixa selecionável em MP4;
- parser e escritor SRT com timestamps e texto multilinha;
- geração e validação estrita do LIBRAS-IR 0.1.0;
- mock honesto, que registra tradução pendente sem inventar sinais;
- adapter opcional para o endpoint de tradução de uma instância VLibras API;
- renderizador sintético de janela de Libras (`sinal render`), gerando `avatar.mp4` animado e sincronizado com a linha do tempo;
- compositor FFmpeg (`sinal compose`), sobrepondo o avatar nos quatro cantos (`bottom-right`, `bottom-left`, `top-right`, `top-left`) com preservação de faixas;
- orquestrador completo de ponta a ponta (`sinal process --render`);
- detecção dinâmica de encoders H.264/compatíveis no FFmpeg (suporte multiplataforma para Fedora, Ubuntu, Arch, etc.);
- saída humana ou JSON no comando de inspeção;
- erros explícitos e sem dependências ocultas.

## Requisitos

- Linux;
- Python 3.12 ou posterior;
- FFmpeg e FFprobe acessíveis no `PATH`.

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
# Modo mock honesto (registra lacunas e estrutura temporal sem falsas glosas)
sinal build-ir video.srt --engine mock --output video.libras-ir.json

# Ou usando uma instância VLibras local configurada
sinal build-ir video.srt --engine vlibras --endpoint http://127.0.0.1:3000 --allow-network

# Validar contra o esquema 0.1.0
sinal validate-ir video.libras-ir.json
```

### 4. Renderizar o avatar de Libras
```bash
sinal render video.libras-ir.json --media video.mp4 -o avatar.mp4
```

### 5. Compor o vídeo final
```bash
sinal compose video.mp4 --avatar avatar.mp4 --position bottom-right -o video-final.mp4
```

### 6. Executar o pipeline completo em um único comando
```bash
sinal process video.mp4 --srt video.srt --render --position bottom-right -o video-final.mp4
```

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
- o adapter VLibras traduz texto em glosa, mas a geração/renderização pública de
  vídeo do avatar ainda não está integrada;
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
