# Webmotors API

Wrapper não oficial da API interna do Webmotors, exposto localmente via FastAPI. Permite buscar carros e motos com filtros completos, consultar a tabela FIPE e obter o telefone do vendedor — tudo programaticamente.

## O que este projeto faz

- Lista todos os modelos disponíveis de uma marca para busca precisa.
- Busca anúncios de carros e motos usados com filtros por marca, modelo, estado, cidade, faixa de ano e faixa de preço.
- Retorna tabela FIPE e telefone do vendedor (loja ou pessoa física) por anúncio.
- Retorna links de imagens em alta resolução (1920×1440).
- Pagina os resultados.
- Expõe interface interativa via Swagger UI em `/docs`.

## Stack

- Python 3.10+
- [fastapi>=0.110.0](https://pypi.org/project/fastapi/)
- [uvicorn>=0.27.0](https://pypi.org/project/uvicorn/)
- [curl-cffi>=0.7.0](https://pypi.org/project/curl-cffi/)

## Estrutura esperada

- `api_webmotors.py`
- `requirements.txt`
- `cookies.json`

## 1) Criar e ativar ambiente virtual

PowerShell (Windows):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2) Configurar os cookies

A API do Webmotors é protegida por PerimeterX. Para autenticar as requisições, é necessário fornecer cookies de uma sessão ativa do seu navegador.

1. Instale a extensão [Cookie-Editor](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) no Chrome.
2. Acesse [webmotors.com.br](https://www.webmotors.com.br) e faça login na sua conta.
3. Com a aba do Webmotors aberta, clique no ícone da extensão **Cookie-Editor** na barra do Chrome.
4. Clique em **Export** → **Export as JSON**.
   - O JSON é copiado automaticamente para a área de transferência.
5. Abra o Bloco de Notas (ou VS Code), cole o conteúdo (`Ctrl+V`) e salve como `cookies.json` na raiz do projeto.

## 3) Executar

```powershell
python .\api_webmotors.py
```

A API estará disponível em `http://localhost:8000`.
Acesse `http://localhost:8000/docs` para a interface interativa (Swagger UI).

## Endpoints

### Carros

| Endpoint | Descrição |
|---|---|
| `GET /modelos-carro` | Lista todos os modelos de uma marca |
| `GET /buscar-carros` | Busca anúncios de carros usados |
| `GET /carro/detalhes` | Retorna FIPE e telefone do vendedor |

### Motos

| Endpoint | Descrição |
|---|---|
| `GET /modelos-moto` | Lista todos os modelos de uma marca |
| `GET /buscar-motos` | Busca anúncios de motos usadas |
| `GET /moto/detalhes` | Retorna FIPE e telefone do vendedor |

### Parâmetros de busca

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `marca` | string | Ex: `honda`, `yamaha`, `volkswagen` |
| `modelo` | string | Ex: `civic`, `nmax-160`, `biz-110i` |
| `estado` | string (2 letras) | Sigla do estado. Ex: `sp`, `rj`, `mg` |
| `cidade` | string | Ex: `campinas`, `belo-horizonte` |
| `ano_min` | int (1900–2030) | Ano mínimo de fabricação |
| `ano_max` | int (1900–2030) | Ano máximo de fabricação |
| `preco_min` | int (≥ 0) | Preço mínimo em reais |
| `preco_max` | int (≥ 0) | Preço máximo em reais |
| `pagina` | int (≥ 1) | Número da página (padrão: `1`) |

Para `/modelos-carro` e `/modelos-moto`, o único parâmetro é `marca`.
Para `/carro/detalhes` e `/moto/detalhes`, os parâmetros são `link_anuncio` (obrigatório) e `vendedor_tipo` (aceita apenas `PJ` ou `PF`, padrão `PJ`).

### Fluxo recomendado

A API de motos (e eventualmente carros) só filtra por modelo com nomes exatos do catálogo. O fluxo ideal é:

1. `GET /modelos-moto?marca=honda` — descobre os nomes exatos (ex: `BIZ 110I`).
2. `GET /buscar-motos?marca=honda&modelo=BIZ+110I` — busca com filtro preciso e paginação correta.

## Solução de problemas

- **Erro 403:**
  - Os cookies expiraram. Repita o processo da seção 2 e substitua o `cookies.json`.
- **`cookies.json` não encontrado:**
  - Confirme que o arquivo está na raiz do projeto, no mesmo diretório de `api_webmotors.py`.
- **Resultado vazio em motos:**
  - Use `/modelos-moto?marca=<marca>` para descobrir o nome exato do modelo no catálogo.
- **Telefone não retornado:**
  - Confirme o parâmetro `vendedor_tipo`: `PJ` para lojas, `PF` para pessoa física.

## Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para os detalhes completos.

Este projeto não tem afiliação com o Webmotors ou o Grupo Santander. É um projeto independente desenvolvido para fins educacionais e de automação pessoal.
