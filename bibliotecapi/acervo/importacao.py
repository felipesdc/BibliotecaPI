"""Importação de acervo: leitura limitada, prévia e confirmação atômica."""
import csv
import hashlib
import io
import json
import re
import unicodedata
import zipfile
from collections import Counter


from .models import Autor, Genero, Lingua, Livro, LivroCopia

CAMPOS = {
    'titulo': 'Título (obrigatório)', 'codigo': 'Código / tombamento',
    'autor': 'Autor', 'isbn': 'ISBN', 'editora': 'Editora',
    'genero': 'Gênero', 'lingua': 'Idioma', 'descricao': 'Descrição',
    'estado': 'Situação do exemplar',
}
ALIASES = {
    'titulo': ['titulo', 'livro', 'nome do livro', 'obra'],
    'codigo': ['codigo', 'tombo', 'tombamento', 'registro', 'codigo do exemplar', 'id'],
    'autor': ['autor', 'autores'], 'isbn': ['isbn'], 'editora': ['editora'],
    'genero': ['genero', 'categoria', 'assunto'], 'lingua': ['lingua', 'idioma'],
    'descricao': ['descricao', 'sinopse', 'resumo'],
    'estado': ['estado', 'situacao', 'status', 'disponibilidade'],
}
MAX_LINHAS = 5000


def normalizar(valor):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(valor)) if not unicodedata.combining(c)).strip().lower()


def texto(valor):
    if valor is None:
        return ''
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def ler_planilha(arquivo):
    conteudo = arquivo.read()
    tabelas = {}
    if arquivo.name.lower().endswith('.csv'):
        try:
            dados = conteudo.decode('utf-8-sig')
        except UnicodeDecodeError:
            dados = conteudo.decode('cp1252')
        try:
            dialect = csv.Sniffer().sniff(dados[:8192], delimiters=';,\t,')
        except csv.Error:
            dialect = csv.excel
        tabelas['Acervo'] = csv.reader(io.StringIO(dados), dialect)
    else:
        from openpyxl import load_workbook
        try:
            with zipfile.ZipFile(io.BytesIO(conteudo)) as pacote:
                if sum(i.file_size for i in pacote.infolist()) > 50 * 1024 * 1024 or len(pacote.infolist()) > 1000:
                    raise ValueError('Planilha muito grande após descompactação. Divida o arquivo.')
            livro = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=False)
            if len(livro.worksheets) > 20:
                raise ValueError('Use um arquivo com até 20 abas.')
            if any(aba.max_column and aba.max_column > 100 for aba in livro.worksheets):
                livro.close()
                raise ValueError('Use no máximo 100 colunas por aba.')
            if any(aba.max_row and aba.max_row > MAX_LINHAS + 20 for aba in livro.worksheets):
                livro.close()
                raise ValueError('Use até 5.000 linhas por arquivo.')
            tabelas = {aba.title: aba.iter_rows(values_only=True) for aba in livro.worksheets}
        except (zipfile.BadZipFile, KeyError) as exc:
            raise ValueError('Arquivo Excel inválido. Salve novamente como .xlsx.') from exc
    resultado = {}
    total = 0
    try:
        for nome, linhas in tabelas.items():
            preparadas = []
            for numero, linha in enumerate(linhas, 1):
                if len(linha) > 100:
                    raise ValueError('Use no máximo 100 colunas por aba.')
                valores = [texto(v) for v in linha]
                if not any(valores):
                    continue
                total += 1
                if total > MAX_LINHAS + 20:
                    raise ValueError('Use até 5.000 linhas no arquivo. Divida planilhas maiores.')
                if any(len(v) > 2000 for v in valores):
                    raise ValueError(f'Aba {nome}, linha {numero}: célula maior que 2.000 caracteres.')
                preparadas.append({'numero': numero, 'valores': valores})
            if preparadas:
                cabecalho = preparadas.pop(0)['valores']
                resultado[nome] = {'cabecalho': cabecalho, 'linhas': preparadas}
    finally:
        if not arquivo.name.lower().endswith('.csv'):
            livro.close()
    if sum(len(t['linhas']) for t in resultado.values()) > MAX_LINHAS:
        raise ValueError('Use até 5.000 linhas de dados no arquivo.')
    if not resultado:
        raise ValueError('A planilha está vazia.')
    return resultado


def sugestoes(cabecalho):
    return {campo: next((str(i) for i, v in enumerate(cabecalho) if normalizar(v) in ALIASES[campo]), '') for campo in CAMPOS}


def preparar(tabela, mapa):
    erros, linhas = [], []
    usados = [v for v in mapa.values() if v != '']
    if len(usados) != len(set(usados)):
        return [], ['Cada coluna pode ser associada a apenas um campo.']
    if mapa.get('titulo', '') == '':
        return [], ['Associe a coluna de título.']
    for campo, indice in mapa.items():
        if indice and (not indice.isdigit() or int(indice) >= len(tabela['cabecalho'])):
            return [], [f'Coluna inválida para {CAMPOS[campo]}.']
    contagem = Counter()
    codigos = set()
    for original in tabela['linhas']:
        numero, valores = original['numero'], original['valores']
        item = {campo: (valores[int(mapa[campo])] if mapa.get(campo, '') != '' and int(mapa[campo]) < len(valores) else '') for campo in CAMPOS}
        item['isbn'] = re.sub(r'[-\s]', '', item['isbn'])
        if not item['titulo']:
            erros.append(f'Linha {numero}: título ausente.')
        for campo, limite in [('titulo', 200), ('codigo', 100), ('autor', 200), ('isbn', 13), ('editora', 200), ('genero', 200), ('lingua', 200), ('descricao', 1000)]:
            if len(item[campo]) > limite:
                erros.append(f'Linha {numero}: {CAMPOS[campo]} excede {limite} caracteres.')
        if any(v.startswith('=') for v in item.values()):
            erros.append(f'Linha {numero}: substitua fórmulas pelos valores antes de importar.')
        if item['isbn']:
            item['isbn'] = re.sub(r'[-\s]', '', item['isbn'])
            isbn = item['isbn']
            valido = len(isbn) == 13 and isbn.isdigit() and sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(isbn)) % 10 == 0
            if not valido:
                erros.append(f'Linha {numero}: informe um ISBN-13 válido ou deixe vazio.')
        partes_autor = item['autor'].split(',', 1) if ',' in item['autor'] else item['autor'].rsplit(' ', 1)
        if any(len(p.strip()) > 100 for p in partes_autor):
            erros.append(f'Linha {numero}: nome ou sobrenome do autor excede 100 caracteres.')
        estado = normalizar(item['estado'])
        estados = {'': 'd', 'd': 'd', 'disponivel': 'd', 'disponivel para emprestimo': 'd', 'm': 'm', 'manutencao': 'm'}
        if estado not in estados:
            erros.append(f'Linha {numero}: situação “{item["estado"]}” não suportada. Esta etapa importa apenas exemplares disponíveis ou em manutenção; reconcilie os empréstimos atuais antes da migração.')
        item['estado'] = estados.get(estado, 'd')
        if not item['codigo']:
            chave = json.dumps({k: normalizar(v) for k, v in item.items() if k != 'codigo'}, sort_keys=True)
            contagem[chave] += 1
            item['codigo'] = 'IMP-' + hashlib.sha256(chave.encode()).hexdigest()[:20] + f'-{contagem[chave]}'
        if item['codigo'] in codigos:
            erros.append(f'Linha {numero}: código repetido no arquivo: {item["codigo"]}.')
        codigos.add(item['codigo'])
        item['linha'] = numero
        linhas.append(item)
    existentes = {c.codigo: c for c in LivroCopia.objects.filter(codigo__in=list(codigos)).select_related('livro')}
    for item in linhas:
        copia = existentes.get(item['codigo'])
        item['existente'] = bool(copia)
        if copia and normalizar(copia.livro.titulo if copia.livro else '') != normalizar(item['titulo']):
            erros.append(f'Linha {item["linha"]}: código {item["codigo"]} já pertence a outro título. Nenhum dado existente será sobrescrito.')
    # O mesmo ISBN não pode representar títulos diferentes dentro do arquivo.
    titulos_isbn = {}
    for item in linhas:
        isbn = item['isbn']
        if isbn:
            titulo = normalizar(item['titulo'])
            anterior = titulos_isbn.setdefault(isbn, titulo)
            livro = Livro.objects.filter(isbn=isbn).first()
            if anterior != titulo or (livro and normalizar(livro.titulo) != titulo):
                erros.append(f'Linha {item["linha"]}: ISBN associado a outro título.')
    return linhas, erros


def importar(linhas):
    criadas, ignoradas = 0, 0
    for item in linhas:
        if LivroCopia.objects.filter(codigo=item['codigo']).exists():
            ignoradas += 1
            continue
        autor = None
        if item['autor']:
            if ',' in item['autor']:
                sobrenome, primeiro_nome = (parte.strip() for parte in item['autor'].split(',', 1))
            else:
                partes = item['autor'].rsplit(' ', 1)
                primeiro_nome, sobrenome = partes[0], partes[1] if len(partes) > 1 else ''
            autor, _ = Autor.objects.get_or_create(primeiro_nome=primeiro_nome, sobrenome=sobrenome)
        lingua = None
        if item['lingua']:
            lingua, _ = Lingua.objects.get_or_create(nome=item['lingua'])
        if item['isbn']:
            livro, _ = Livro.objects.get_or_create(isbn=item['isbn'], defaults={'titulo': item['titulo'], 'autor': autor, 'lingua': lingua, 'descricao': item['descricao']})
        else:
            livro = Livro.objects.filter(titulo__iexact=item['titulo'], autor=autor, isbn__isnull=True).first()
            if livro is None:
                livro = Livro.objects.create(titulo=item['titulo'], autor=autor, lingua=lingua, descricao=item['descricao'])
        if item['genero']:
            genero, _ = Genero.objects.get_or_create(nome=item['genero'])
            livro.genero.add(genero)
        LivroCopia.objects.create(livro=livro, codigo=item['codigo'], editora=item['editora'], estado=item['estado'])
        criadas += 1
    return {'criadas': criadas, 'ignoradas': ignoradas}
