"""Read selected XLSX worksheet using Python stdlib only (no Excel dependency).

Handles Excel shared strings, inline strings, cached string/numeric values,
column references, and regular sheet paths from workbook relationships.
Only the requested restaurant tab is imported; no outside enrichment.
"""
from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
P = '{http://schemas.openxmlformats.org/package/2006/relationships}'
CELL_RE = re.compile(r'^([A-Z]+)([0-9]+)$')


def col_number(address: str) -> int:
    m = CELL_RE.match(address)
    if not m:
        raise ValueError(f'Bad Excel cell address: {address!r}')
    col = 0
    for letter in m.group(1):
        col = col * 26 + ord(letter) - 64
    return col - 1


def read_sheet(path: Path, sheet_name: str) -> list[dict[str, str]]:
    with ZipFile(path) as z:
        workbook = ET.fromstring(z.read('xl/workbook.xml'))
        ref = None
        for sheet in workbook.findall(f'.//{M}sheet'):
            if sheet.attrib.get('name') == sheet_name:
                ref = sheet.attrib.get(f'{R}id')
                break
        if ref is None:
            raise ValueError(f'Workbook has no {sheet_name!r} sheet')
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target = next((el.attrib['Target'] for el in rels.findall(f'{P}Relationship')
                       if el.attrib.get('Id') == ref), None)
        if target is None:
            raise ValueError('Broken worksheet relationship')
        target = target.lstrip('/')
        if not target.startswith('xl/'):
            target = 'xl/' + target
        # Block unsafe zip path traversal.
        if '..' in Path(target).parts:
            raise ValueError('Unsupported worksheet target path')
        shared: list[str] = []
        if 'xl/sharedStrings.xml' in z.namelist():
            table = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in table.findall(f'{M}si'):
                shared.append(''.join(t.text or '' for t in si.iter(f'{M}t')))
        root = ET.fromstring(z.read(target))
        matrix: list[list[str]] = []
        for row in root.findall(f'.//{M}sheetData/{M}row'):
            fields: dict[int, str] = {}
            for cell in row.findall(f'{M}c'):
                idx = col_number(cell.attrib['r'])
                t = cell.attrib.get('t')
                value = cell.find(f'{M}v')
                inline = cell.find(f'{M}is')
                raw = (value.text if value is not None else None)
                if t == 's' and raw is not None:
                    result = shared[int(raw)]
                elif t == 'inlineStr' and inline is not None:
                    result = ''.join(n.text or '' for n in inline.iter(f'{M}t'))
                else:
                    result = raw or ''
                # Excel may encode numeric identifiers as e.g. 12345.0.
                fields[idx] = result
            if fields:
                width = max(fields) + 1
                matrix.append([fields.get(i, '') for i in range(width)])
        if not matrix:
            raise ValueError(f'{sheet_name!r} is empty')
        header = [x.strip() for x in matrix[0]]
        records = []
        for values in matrix[1:]:
            result = {h: (values[i] if i < len(values) else '') for i, h in enumerate(header) if h}
            if any(str(x).strip() for x in result.values()):
                records.append(result)
        return records
