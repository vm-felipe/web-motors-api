from fastapi import FastAPI, Query, Response
from curl_cffi import requests
from typing import Literal
import urllib.parse
import logging
import uvicorn
import json
import os
import re

logging.basicConfig(level=logging.ERROR, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
_logger = logging.getLogger(__name__)

app = FastAPI(
    title="Webmotors API",
    description="Wrapper não oficial para busca de carros, motos, tabela FIPE e telefones de vendedores.",
)

_BASE_URL = "https://www.webmotors.com.br"

MAPA_ESTADOS = {
    "ac": "Acre", "al": "Alagoas", "ap": "Amapá", "am": "Amazonas", "ba": "Bahia", "ce": "Ceará",
    "df": "Distrito Federal", "es": "Espírito Santo", "go": "Goiás", "ma": "Maranhão", "mt": "Mato Grosso",
    "ms": "Mato Grosso do Sul", "mg": "Minas Gerais", "pa": "Pará", "pb": "Paraíba", "pr": "Paraná",
    "pe": "Pernambuco", "pi": "Piauí", "rj": "Rio de Janeiro", "rn": "Rio Grande do Norte",
    "rs": "Rio Grande do Sul", "ro": "Rondônia", "rr": "Roraima", "sc": "Santa Catarina",
    "sp": "São Paulo", "se": "Sergipe", "to": "Tocantins",
}


def slugify(text: str, default: str = "veiculo") -> str:
    """Converte texto em slug válido para URLs do Webmotors."""
    if not text:
        return default
    text = str(text).lower().replace(" ", "-").replace("/", "-")
    text = re.sub(r'[^a-z0-9-]', '', text)
    return re.sub(r'-+', '-', text).strip("-")


def _formatar_imagem(caminho: str):
    """Monta a URL de imagem em alta resolução a partir do caminho retornado pela API."""
    if not caminho:
        return None
    if caminho.startswith("http"):
        return caminho
    caminho_limpo = caminho.replace("\\", "/").lstrip("/")
    return f"https://image.webmotors.com.br/_fotos/anunciousados/gigante/{caminho_limpo}?s=fill&w=1920&h=1440&q=75"


def _formatar_telefone(ddd: str, numero: str) -> str:
    """Formata DDD + número em (XX) XXXXX-XXXX ou (XX) XXXX-XXXX."""
    if len(numero) == 9:
        return f"({ddd}) {numero[:5]}-{numero[5:]}"
    return f"({ddd}) {numero[:4]}-{numero[4:]}"


def _carregar_cookies():
    caminho = "cookies.json"
    if not os.path.exists(caminho):
        return None
    try:
        with open(caminho, encoding="utf-8") as f:
            lista = json.load(f)
            return "; ".join(f"{c['name']}={c['value']}" for c in lista)
    except Exception:
        return None


def _get_headers():
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "pt-BR,pt;q=0.9",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "referer": f"{_BASE_URL}/",
        "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "cookie": _carregar_cookies(),
    }


def _parse_link(url: str, is_car: bool):
    """Extrai os componentes do link de anúncio para alimentar os endpoints de detalhes."""
    url = url.split('?')[0]
    parts = url.rstrip('/').split('/')
    try:
        idx = parts.index('comprar')
        marca = parts[idx + 1]
        modelo = parts[idx + 2]
        versao = parts[idx + 3]
        if is_car:
            anos_str = parts[idx + 5]  # carros têm "X-portas" antes dos anos
            veiculo_id = parts[idx + 6]
        else:
            anos_str = parts[idx + 4]  # motos não têm o segmento de portas
            veiculo_id = parts[idx + 5]
        ano_f, ano_m = anos_str.split('-', 1)
        return veiculo_id, marca, modelo, versao, ano_m, ano_f
    except Exception:
        return None, None, None, None, None, None


def _buscar_veiculos(
    tipo: str, marca: str, modelo: str, estado: str, cidade: str,
    ano_min: int, ano_max: int, preco_min: int, preco_max: int,
    pagina: int, response_api: Response,
):
    if tipo == "car":
        url_api = f"{_BASE_URL}/api/search/car"
        base_path = "carros"
        lkid = "1000"
        tipoveiculo = "carros-usados"
    else:
        # A API de motos usa /api/search/bike, com comportamento distinto de /api/search/car
        url_api = f"{_BASE_URL}/api/search/bike"
        base_path = "motos-usadas"
        lkid = "1002"
        tipoveiculo = "motos-usadas"

    rota = f"{_BASE_URL}/{base_path}"
    if estado:
        rota += f"/{estado.lower()}"
        if cidade:
            rota += f"/{slugify(cidade)}"
    else:
        rota += "/estoque"

    # A API de carros aceita filtro de marca/modelo no path; a de motos usa apenas query string.
    if tipo == "car" and marca:
        rota += f"/{slugify(marca)}"
        if modelo:
            rota += f"/{slugify(modelo)}"

    q_params = [f"lkid={lkid}", f"tipoveiculo={tipoveiculo}"]

    if cidade:
        q_params.append(f"estadocidade={urllib.parse.quote(cidade)}")
    elif estado:
        if tipo == "car":
            q_params.append(f"estadocidade={estado.upper()}")
        else:
            nome_estado = MAPA_ESTADOS.get(estado.lower(), estado.upper())
            q_params.append(f"estadocidade={urllib.parse.quote(nome_estado)}")

    if marca:
        q_params.append(f"marca1={urllib.parse.quote(marca.upper())}")
    if modelo:
        q_params.append(f"modelo1={urllib.parse.quote(modelo.upper().replace('-', ' '))}")

    q_params.append(f"page={pagina}")
    if ano_min: q_params.append(f"anode={ano_min}")
    if ano_max: q_params.append(f"anoate={ano_max}")
    if preco_min: q_params.append(f"precode={preco_min}")
    if preco_max: q_params.append(f"precoate={preco_max}")

    url_completa = rota + "?" + "&".join(q_params)

    params = {
        "url": url_completa,
        "displayPerPage": "24",
        "actualPage": str(pagina),
        "order": "1",
        "showCount": "true",  # necessário para o campo Count aparecer na resposta de bikes
    }

    headers = _get_headers()
    if not headers["cookie"]:
        response_api.status_code = 500
        return {"erro": "Arquivo cookies.json vazio."}

    try:
        response = requests.get(url_api, params=params, headers=headers, impersonate="chrome120", timeout=15.0)

        if response.status_code == 403:
            response_api.status_code = 403
            return {"erro": "Bloqueio PerimeterX (403). Renove o cookies.json."}

        dados = response.json()
        veiculos = []

        # A API de motos só filtra por modelo com nomes exatos do catálogo.
        # Para buscas parciais, aplicamos filtro client-side nas SearchResults.
        palavras_modelo = (
            [p for p in modelo.upper().replace('-', ' ').split() if p]
            if tipo == "moto" and modelo
            else []
        )

        for item in dados.get("SearchResults", []):
            spec = item.get("Specification", {})
            seller = item.get("Seller", {})
            uid = item.get("UniqueId")

            mk = spec.get("Make", {}).get("Value", "")
            md = spec.get("Model", {}).get("Value", "")
            vs = spec.get("Version", {}).get("Value", "")
            ano_f = spec.get("YearFabrication", "")
            ano_m = str(spec.get("YearModel", "")).split('.')[0]

            if palavras_modelo and not all(p in md.upper() for p in palavras_modelo):
                continue

            lista_fotos = [
                _formatar_imagem(f.get("PhotoPath"))
                for f in item.get("Media", {}).get("Photos", [])
                if f.get("PhotoPath")
            ]

            link = item.get("AdvertisementLink")
            if not link and uid:
                s_mk, s_md, s_vs = slugify(mk), slugify(md), slugify(vs)
                if tipo == "car":
                    portas = spec.get("NumberPorts", "4")
                    link = f"{_BASE_URL}/comprar/{s_mk}/{s_md}/{s_vs}/{portas}-portas/{ano_f}-{ano_m}/{uid}"
                else:
                    link = f"{_BASE_URL}/comprar/{s_mk}/{s_md}/{s_vs}/{ano_f}-{ano_m}/{uid}"

            veiculos.append({
                "id": uid,
                "titulo": f"{mk} {md} {vs}".strip(),
                "preco": item.get("Prices", {}).get("Price"),
                "ano": f"{ano_f}/{ano_m}",
                "km": spec.get("Odometer"),
                "local": f"{seller.get('City')} - {seller.get('State')}",
                "vendedor_tipo": seller.get("SellerType", "PJ"),
                "foto_principal": lista_fotos[0] if lista_fotos else None,
                "todas_fotos": lista_fotos,
                "link": link,
                "dados_originais": item,
            })

        chave = "carros" if tipo == "car" else "motos"
        paginacao = dados.get("Pagination", {})
        resultado = {
            "total_encontrados": dados.get("Count"),
            "pagina_atual": paginacao.get("PageCurrent"),
            "total_paginas": paginacao.get("PageTotal"),
            "url_backend": url_completa,
            chave: veiculos,
        }

        if palavras_modelo:
            search_results = dados.get("SearchResults", [])
            modelos_encontrados = sorted({
                item.get("Specification", {}).get("Model", {}).get("Value", "")
                for item in search_results
                if all(
                    p in item.get("Specification", {}).get("Model", {}).get("Value", "").upper()
                    for p in palavras_modelo
                )
            })
            # Se nenhum modelo bateu na página atual, exibe todos os disponíveis
            # para que o usuário possa identificar o nome correto e navegar
            if not modelos_encontrados:
                modelos_encontrados = sorted({
                    item.get("Specification", {}).get("Model", {}).get("Value", "")
                    for item in search_results
                    if item.get("Specification", {}).get("Model", {}).get("Value", "")
                })
            resultado["aviso_modelo"] = (
                "A API de motos exige nome exato do catálogo. "
                "Use 'modelos_nesta_pagina' para descobrir os nomes corretos."
            )
            resultado["modelos_nesta_pagina"] = modelos_encontrados

        return resultado

    except Exception:
        _logger.exception("Erro em _buscar_veiculos")
        response_api.status_code = 500
        return {"erro": "Erro interno. Tente novamente."}


def _buscar_detalhes(tipo: str, link: str, seller_type: str, response_api: Response):
    headers = _get_headers()

    veiculo_id, marca, modelo, versao, ano_modelo, ano_fab = _parse_link(link, is_car=(tipo == "car"))
    if not veiculo_id:
        response_api.status_code = 400
        return {"erro": "O link do anúncio fornecido é inválido ou mal formatado."}

    tipo_vendedor = "dealer" if seller_type.upper() == "PJ" else "owner"
    tipo_veiculo_api = "car" if tipo == "car" else "bike"

    url_fipe = f"{_BASE_URL}/api/detail/averageprice/{tipo_veiculo_api}/{veiculo_id}?pandora=false"
    resultados = {"fipe": None, "telefones": []}

    try:
        with requests.Session(impersonate="chrome120", headers=headers, timeout=10.0) as session:
            res_fipe = session.get(url_fipe)
            if res_fipe.status_code == 200:
                resultados["fipe"] = res_fipe.json()

            if tipo == "car":
                url_phone = (
                    f"{_BASE_URL}/api/detail/phone/{tipo_vendedor}/{tipo_veiculo_api}"
                    f"/{marca}/{modelo}/{versao}/{ano_modelo}/{veiculo_id}?pandora=false"
                )
                res_phone = session.get(url_phone)
                if res_phone.status_code == 200:
                    dados_tel = res_phone.json()
                    if isinstance(dados_tel, list):
                        resultados["telefones"] = [t.get("Phone") for t in dados_tel if t.get("Phone")]

                # Fallback: extrai telefone do HTML caso a API não retorne dados
                if not resultados["telefones"] and link.startswith(f"{_BASE_URL}/comprar/"):
                    res_html = session.get(link)
                    if res_html.status_code == 200:
                        html = res_html.text
                        match_dom = re.search(r'<small[^>]*>\(?(\d{2})\)?</small>[\s\r\n]*(\d{8,9})', html)
                        if match_dom:
                            ddd, num = match_dom.groups()
                            resultados["telefones"] = [_formatar_telefone(ddd, num)]
                        else:
                            match_next = re.search(r'<script id="__NEXT_DATA__".*?>(.*?)</script>', html)
                            if match_next:
                                json_str = match_next.group(1)
                                numeros = re.findall(
                                    r'["\'](?:[Nn]umber|phone(?:Number)?)["\']?\s*:\s*["\'](\d{10,11})["\']',
                                    json_str,
                                )
                                if numeros:
                                    ddd, num = numeros[0][:2], numeros[0][2:]
                                    resultados["telefones"] = [_formatar_telefone(ddd, num)]
            else:
                # Para motos, /api/detail/bike retorna telefones em Seller.Phones
                # e FIPE em Specification.Evaluation como alternativa ao averageprice
                url_detail = (
                    f"{_BASE_URL}/api/detail/bike/{marca}/{modelo}/{versao}"
                    f"/{ano_fab}-{ano_modelo}/{veiculo_id}?pandora=false"
                )
                res_detail = session.get(url_detail)
                if res_detail.status_code == 200:
                    dados_detail = res_detail.json()
                    phones = dados_detail.get("Seller", {}).get("Phones", [])
                    resultados["telefones"] = [p.get("Value") for p in phones if p.get("Value")]
                    if not resultados["fipe"]:
                        avaliacao = dados_detail.get("Specification", {}).get("Evaluation", {})
                        if avaliacao.get("FIPE"):
                            resultados["fipe"] = {
                                "FipePrice": avaliacao.get("FIPE"),
                                "FipeCode": avaliacao.get("FIPEId"),
                            }

        return resultados

    except Exception:
        _logger.exception("Erro em _buscar_detalhes")
        response_api.status_code = 500
        return {"erro": "Erro interno. Tente novamente."}


def _listar_modelos(tipo: str, marca: str, response_api: Response):
    if tipo == "car":
        url_api = f"{_BASE_URL}/api/search/car"
        inner_url = f"{_BASE_URL}/carros/estoque/{slugify(marca)}?lkid=1000&tipoveiculo=carros-usados&marca1={marca.upper()}&page=1"
    else:
        url_api = f"{_BASE_URL}/api/search/bike"
        inner_url = f"{_BASE_URL}/motos-usadas/estoque?lkid=1002&tipoveiculo=motos-usadas&marca1={marca.upper()}&page=1"

    params = {"url": inner_url, "displayPerPage": "1", "actualPage": "1", "order": "1", "showMenu": "true"}
    headers = _get_headers()

    if not headers["cookie"]:
        response_api.status_code = 500
        return {"erro": "Arquivo cookies.json vazio."}

    try:
        r = requests.get(url_api, params=params, headers=headers, impersonate="chrome120", timeout=15.0)

        if r.status_code == 403:
            response_api.status_code = 403
            return {"erro": "Bloqueio PerimeterX (403). Renove o cookies.json."}

        data = r.json()
        modelos = []
        for f in data.get("Filters", []):
            if f.get("name") == "Make":
                for brand in f.get("items", []):
                    if brand.get("name", "").upper() == marca.upper():
                        modelos = [
                            {"modelo": m["name"], "anuncios": m["count"]}
                            for m in brand.get("items", [])
                        ]
                        break
                break

        if not modelos:
            response_api.status_code = 404
            return {"erro": f"Marca '{marca}' não encontrada ou sem anúncios."}

        return {"marca": marca.upper(), "total_modelos": len(modelos), "modelos": modelos}

    except Exception:
        _logger.exception("Erro em _listar_modelos")
        response_api.status_code = 500
        return {"erro": "Erro interno. Tente novamente."}


@app.get("/modelos-carro", tags=["Carros"])
def listar_modelos_carro(
    marca: str = Query(..., description="Ex: honda, volkswagen, fiat"),
    response_api: Response = None,
):
    return _listar_modelos("car", marca, response_api)


@app.get("/buscar-carros", tags=["Carros"])
def endpoint_carros(
    marca: str = Query(None),
    modelo: str = Query(None),
    estado: str = Query(None, min_length=2, max_length=2, description="Sigla do estado. Ex: sp, rj, mg"),
    cidade: str = Query(None),
    ano_min: int = Query(None, ge=1900, le=2030),
    ano_max: int = Query(None, ge=1900, le=2030),
    preco_min: int = Query(None, ge=0),
    preco_max: int = Query(None, ge=0),
    pagina: int = Query(1, ge=1),
    response_api: Response = None,
):
    return _buscar_veiculos("car", marca, modelo, estado, cidade, ano_min, ano_max, preco_min, preco_max, pagina, response_api)


@app.get("/carro/detalhes", tags=["Carros"])
def detalhes_carro(
    link_anuncio: str = Query(..., description="Link do anúncio retornado na busca"),
    vendedor_tipo: Literal["PJ", "PF"] = Query("PJ", description="PJ (Loja) ou PF (Pessoa Física)"),
    response_api: Response = None,
):
    return _buscar_detalhes("car", link_anuncio, vendedor_tipo, response_api)


@app.get("/modelos-moto", tags=["Motos"])
def listar_modelos_moto(
    marca: str = Query(..., description="Ex: honda, yamaha, suzuki"),
    response_api: Response = None,
):
    return _listar_modelos("moto", marca, response_api)


@app.get("/buscar-motos", tags=["Motos"])
def endpoint_motos(
    marca: str = Query(None),
    modelo: str = Query(None, description="Ex: pcx, nmax-160, biz-110i"),
    estado: str = Query(None, min_length=2, max_length=2, description="Sigla do estado. Ex: sp, rj, mg"),
    cidade: str = Query(None),
    ano_min: int = Query(None, ge=1900, le=2030),
    ano_max: int = Query(None, ge=1900, le=2030),
    preco_min: int = Query(None, ge=0),
    preco_max: int = Query(None, ge=0),
    pagina: int = Query(1, ge=1),
    response_api: Response = None,
):
    return _buscar_veiculos("moto", marca, modelo, estado, cidade, ano_min, ano_max, preco_min, preco_max, pagina, response_api)


@app.get("/moto/detalhes", tags=["Motos"])
def detalhes_moto(
    link_anuncio: str = Query(..., description="Link do anúncio retornado na busca"),
    vendedor_tipo: Literal["PJ", "PF"] = Query("PJ", description="PJ (Loja) ou PF (Pessoa Física)"),
    response_api: Response = None,
):
    return _buscar_detalhes("moto", link_anuncio, vendedor_tipo, response_api)


if __name__ == "__main__":
    print("Iniciando API Webmotors... Acesse: http://localhost:8000/docs")
    uvicorn.run(app, host="127.0.0.1", port=8000)
