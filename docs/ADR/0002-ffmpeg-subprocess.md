# ADR-0002: FFmpeg e FFprobe por subprocesso

- Status: aceito
- Data: 2026-10-06

## Contexto

O SINAL precisa inspecionar streams e operar codecs sem reimplementar um stack
multimídia. Bindings Python adicionariam compatibilidade e empacotamento
específicos sem benefício claro nesta fase.

## Decisão

Invocar FFmpeg e FFprobe como processos locais, por listas de argumentos e sem
shell. Centralizar execução e erros em `media/ffmpeg.py`; interpretar a saída
JSON do FFprobe nas camadas acima.

## Alternativas consideradas

- PyAV/libav direto: API rica, porém nova dependência binária;
- analisar contêineres em Python: escopo e risco desnecessários;
- comandos shell dispersos: inseguros, difíceis de testar e observar.

## Consequências

FFmpeg passa a ser requisito do sistema. A fronteira central pode ser simulada
nos testes e substituída futuramente sem alterar modelos do domínio.

