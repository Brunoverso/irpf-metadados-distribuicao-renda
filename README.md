# Metadados das series historicas do IRPF

Este repositorio organiza as tabelas de metadados usadas no levantamento das fontes historicas de distribuicao de renda a partir do Imposto de Renda da Pessoa Fisica no Brasil.

O objetivo imediato e manter, em um lugar reprodutivel, os dados-base e o codigo usado para gerar a tabela-resumo em PDF no formato de tabela academica.

## Conteudo

- `data/tabela_metadados_distribuicoes_irpf.csv`: tabela principal de metadados, com um registro por ano-calendario.
- `data/tabela_metadados_irpf_estilo_referencia.csv`: versao compacta da tabela usada no PDF.
- `scripts/build_tabela_metadados_irpf_estilo_referencia_pdf.py`: script Python que gera o PDF a partir do CSV principal.
- `output/pdf/tabela_metadados_irpf_estilo_referencia.pdf`: PDF gerado com a tabela compacta e as referencias.

## Como reproduzir o PDF

1. Instalar as dependencias:

```powershell
python -m pip install -r requirements.txt
```

2. Rodar o script:

```powershell
python scripts/build_tabela_metadados_irpf_estilo_referencia_pdf.py
```

O script atualiza:

- `data/tabela_metadados_irpf_estilo_referencia.csv`
- `output/pdf/tabela_metadados_irpf_estilo_referencia.pdf`

## Observacao

Este repositorio guarda apenas as tabelas de metadados e o codigo de geracao do PDF. Os PDFs brutos, imagens de OCR, arquivos temporarios e demais materiais grandes ficam fora deste repositorio.
