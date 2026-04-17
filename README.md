# Docling Stack em Docker

## O que este pacote faz
- Sobe um container com Python 3.10.11
- Monitora continuamente a pasta `E:\docling-stack\documentos`
- Processa automaticamente arquivos novos ou alterados
- Salva resultados em `E:\docling-stack\outputs` nos formatos:
  - JSON
  - Markdown
  - TXT
  - doctags
  - CSV das tabelas

## Tipos de arquivo suportados
- PDF: `.pdf`
- Word: `.docx`
- PowerPoint: `.pptx`
- Excel: `.xlsx`
- Imagens: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`

## Estrutura esperada no Windows
Crie estas pastas:
- `E:\docling-stack\documentos`
- `E:\docling-stack\outputs`
- `E:\docling-stack\models`
- `E:\docling-stack\app` // para os arquivos de configuração docker.compose, dockfile e algoritmo python

## Arquivos deste pacote
- `Dockerfile`
- `docker-compose.yml`
- `requirements-docker.txt`
- `docling_worker.py`

## Observação importante
O `requirements.txt` original tinha `pywin32==311`, que não instala em Linux.
Por isso ele foi removido da versão para Docker.

## Reprocessamento automático
O worker mantém um arquivo de controle em:
- `E:\docling-stack\outputs\.processed_files.json`

Ele reprocessa apenas quando:
- o arquivo é novo; ou
- o conteúdo/tamanho/data de modificação do arquivo mudou.

## Como subir
No PowerShell, dentro da pasta onde estiverem esses arquivos:

```powershell
docker compose up -d --build
```

## Como ver logs
```powershell
docker logs -f docling-stack
```

## Como usar
1. Copie arquivos suportados para `E:\docling-stack\documentos`
2. Aguarde o processamento
3. Pegue os arquivos gerados em `E:\docling-stack\outputs`

## Como parar
```powershell
docker compose down
```

## Como forçar reprocessamento de tudo
Apague o arquivo:
- `E:\docling-stack\outputs\.processed_files.json`

Depois reinicie:
```powershell
docker compose restart
```
