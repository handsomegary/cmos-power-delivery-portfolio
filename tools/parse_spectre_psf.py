#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Strict scalar PSF ASCII export; Python 2.7 and Python 3 compatible.

Parsing a complete data file is not evidence that a simulator run or circuit
passed. Missing END, missing signals, nonfinite values and malformed sweep
records fail explicitly. Formats are based on actual Spectre 18.1 ASCII files.

API:
  parse_scalar(path) -> header / values / records / source metadata dictionary
  parse_sweep(path, required_signals=None) -> scalar/complex/structured sweep
  export_sweep(kind, input_path, csv_path, metadata_path=None, signal_map=None)
  parse_native_margins(log_path) -> native margins in deg/dB/Hz or explicit nulls
  extract_dc(parsed, load_a=None, load_current_key='ILOAD:sink',
             nodes=None, devices=None) -> (CSV row dictionary, detailed OP)
  export_dc(input_path, csv_path, op_json_path, **extract_options) -> detailed OP
"""
from __future__ import print_function

import argparse
import bisect
import csv
import hashlib
import io
import json
import math
import os
import re
import sys

DEFAULT_NODES = {
    'vin': 'VIN', 'vout': 'VOUT', 'gate': 'GATE', 'fb': 'FB',
    'tail': 'TAIL', 'bias': 'BIAS', 'mirror': 'MIRROR',
    'supply_current': 'VVIN:p',
}
DEFAULT_DEVICES = ['PPASS', 'PL', 'PR', 'PTAIL', 'NL', 'NR', 'PBIAS']
OP_UNITS = {'vgs': 'V', 'vds': 'V', 'vth': 'V', 'vdsat': 'V',
            'gm': 'S', 'gds': 'S', 'ids': 'A'}
DC_FIELDS = ['vin_v', 'load_a', 'vout_v', 'iq_a']
QUOTED = r'"(?:[^"\\]|\\.)*"'
TOKEN = re.compile(QUOTED + r'|[()]|[^\s()]+')
HEADER_LINE = re.compile(r'^(' + QUOTED + r')\s+(.+)$')


class PSFError(ValueError):
    pass


def number(token, location):
    try:
        # Fortran D exponents are accepted; no suffix scaling is inferred.
        value = float(token.replace('D', 'e').replace('d', 'e'))
    except (ValueError, TypeError, AttributeError):
        raise PSFError('%s: expected scalar number, got %r' % (location, token))
    if math.isnan(value) or math.isinf(value):
        raise PSFError('%s: nonfinite scalar value %r' % (location, token))
    return value


def quoted(token, location):
    if not token.startswith('"'):
        raise PSFError('%s: expected quoted string, got %r' % (location, token))
    try:
        return json.loads(token)
    except ValueError as error:
        raise PSFError('%s: unsupported string escape: %s' % (location, error))


def atom(token):
    if token.startswith('"'):
        return quoted(token, 'property/header')
    try:
        return number(token, 'property/header')
    except PSFError:
        return token


def parse_scalar_text(text, source_name='<memory>', allow_undefined=False):
    lines = text.splitlines()
    section_positions = {}
    for index, line in enumerate(lines):
        item = line.strip()
        if item in ('HEADER', 'TYPE', 'SWEEP', 'TRACE', 'VALUE', 'END'):
            section_positions.setdefault(item, []).append(index)
    for section in ('HEADER', 'TYPE', 'VALUE', 'END'):
        count = len(section_positions.get(section, []))
        if count != 1:
            raise PSFError('%s: require exactly one %s section; found %d (possibly incomplete)' %
                           (source_name, section, count))
    if section_positions.get('SWEEP') or section_positions.get('TRACE'):
        raise PSFError('%s: sweep/trace format unsupported by scalar parser' % source_name)
    header_at, type_at, value_at, end_at = [section_positions[key][0] for key in ('HEADER', 'TYPE', 'VALUE', 'END')]
    if not header_at < type_at < value_at < end_at:
        raise PSFError('%s: invalid HEADER / TYPE / VALUE / END order' % source_name)
    string_types = set()
    for line in lines[type_at + 1:value_at]:
        match = re.match(r'^\s*(' + QUOTED + r')\s+STRING\b', line)
        if match:
            string_types.add(quoted(match.group(1), source_name + ':TYPE'))
    if any(line.strip() for line in lines[:header_at] + lines[end_at + 1:]):
        raise PSFError('%s: unexpected nonblank content outside HEADER ... END' % source_name)
    header = {}
    for index in range(header_at + 1, type_at):
        line = lines[index].strip()
        if not line:
            continue
        match = HEADER_LINE.match(line)
        if not match:
            raise PSFError('%s:%d: unsupported header entry %r' % (source_name, index + 1, line))
        key = quoted(match.group(1), '%s:%d' % (source_name, index + 1))
        if key in header:
            raise PSFError('%s:%d: duplicate header key %s' % (source_name, index + 1, key))
        header[key] = atom(match.group(2))
    body = '\n'.join(lines[value_at + 1:end_at])
    newline_positions = [match.start() for match in re.finditer('\n', body)]
    tokens = [(match.group(), value_at + 2 + bisect.bisect_left(newline_positions, match.start()))
              for match in TOKEN.finditer(body)]
    index = 0
    records = {}

    def location(token_index):
        return '%s:%d' % (source_name, tokens[token_index][1] if token_index < len(tokens) else end_at + 1)

    while index < len(tokens):
        start = index
        if index + 2 >= len(tokens):
            raise PSFError('%s: incomplete scalar record' % location(index))
        name = quoted(tokens[index][0], location(index))
        type_name = quoted(tokens[index + 1][0], location(index + 1))
        value_token = tokens[index + 2][0]
        if value_token.startswith('"'):
            if type_name not in string_types:
                raise PSFError('%s: quoted VALUE requires declared STRING type' % location(index + 2))
            value = quoted(value_token, location(index + 2))
        elif allow_undefined and value_token.lower() in ('nan', '+nan', '-nan'):
            value = None
        else:
            value = number(value_token, location(index + 2))
        index += 3
        properties = {}
        if index < len(tokens) and tokens[index][0] == 'PROP':
            index += 1
            if index >= len(tokens) or tokens[index][0] != '(':
                raise PSFError('%s: PROP requires opening parenthesis' % location(index))
            index += 1
            while index < len(tokens) and tokens[index][0] != ')':
                key = quoted(tokens[index][0], location(index))
                index += 1
                if index >= len(tokens) or tokens[index][0] in ('(', ')', 'PROP'):
                    raise PSFError('%s: property %s has missing/unsupported value' % (location(index), key))
                prop_value = atom(tokens[index][0])
                index += 1
                if key in properties:
                    raise PSFError('%s: duplicate property %s' % (location(index - 1), key))
                properties[key] = prop_value
            if index >= len(tokens) or tokens[index][0] != ')':
                raise PSFError('%s: incomplete PROP block' % location(start))
            index += 1
        if name in records:
            raise PSFError('%s: duplicate signal %s; refusing overwrite' % (location(start), name))
        records[name] = {'type': type_name, 'value': value, 'properties': properties,
                         'source_line': tokens[start][1]}
    if not records:
        raise PSFError('%s: VALUE section contains no scalar data' % source_name)
    return {'format': 'psfascii_scalar', 'complete_file': True,
            'simulation_status': 'not_verified_by_parser', 'source': source_name,
            'header': header, 'record_count': len(records),
            'values': dict((name, record['value']) for name, record in records.items()),
            'records': records}


def parse_scalar(path, allow_undefined=False):
    with open(path, 'rb') as handle:
        raw = handle.read()
    try:
        text = raw.decode('utf-8-sig')
        encoding = 'utf-8-sig'
    except UnicodeDecodeError:
        text = raw.decode('latin-1')
        encoding = 'latin-1'
    parsed = parse_scalar_text(text, os.path.abspath(path), allow_undefined)
    parsed.update(source_sha256=hashlib.sha256(raw).hexdigest(), source_encoding=encoding,
                  source_bytes=len(raw))
    return parsed


def require_signal(parsed, name, expected_unit=None):
    if name not in parsed['records']:
        raise PSFError('Missing required signal: %s' % name)
    record = parsed['records'][name]
    if record['value'] is None:
        raise PSFError('Required signal %s is undefined/nonfinite' % name)
    unit = record['properties'].get('units')
    conventional_units = {'V': 'V', 'I': 'A', 'A': 'A', 'S': 'S'}
    inferred_unit = unit if unit is not None else conventional_units.get(record['type'])
    if expected_unit is not None and inferred_unit != expected_unit:
        raise PSFError('Signal %s unit/type %r/%r does not establish %s' %
                       (name, unit, record['type'], expected_unit))
    return number(str(record['value']), 'required signal ' + name)


def extract_dc(parsed, load_a=None, load_current_key='ILOAD:sink', nodes=None, devices=None):
    selected_nodes = dict(DEFAULT_NODES)
    if nodes is not None:
        unknown = set(nodes) - set(DEFAULT_NODES)
        if unknown:
            raise PSFError('Unknown node roles: %s' % ','.join(sorted(unknown)))
        selected_nodes.update(nodes)
    if devices is None:
        devices = DEFAULT_DEVICES
    elif devices == 'auto':
        candidates = set(name.rsplit(':', 1)[0] for name in parsed['records'] if ':' in name)
        devices = sorted(name for name in candidates
                         if all(name + ':' + parameter in parsed['records'] for parameter in OP_UNITS))
    if not devices:
        raise PSFError('At least one explicit transistor instance is required for DC OP export')
    analysis = parsed['header'].get('analysis type')
    if analysis not in ('dc', 'info'):
        raise PSFError('DC export requires dc/info scalar data, got analysis type %r' % analysis)
    voltages = dict((role, require_signal(parsed, name, 'V')) for role, name in selected_nodes.items()
                    if role != 'supply_current')
    source_current = require_signal(parsed, selected_nodes['supply_current'], 'A')
    if load_a is not None:
        load_a = number(str(load_a), 'explicit load_a')
    measured_load = None
    if load_current_key and load_current_key in parsed['records']:
        measured_load = require_signal(parsed, load_current_key, 'A')
    if measured_load is None and load_a is None:
        raise PSFError('Load current missing: provide actual --load-a or a saved load-current signal')
    if measured_load is not None and load_a is not None:
        tolerance = max(1e-12, abs(load_a) * 1e-5)
        if abs(measured_load - load_a) > tolerance:
            raise PSFError('Saved load current %.16g and explicit load %.16g disagree' % (measured_load, load_a))
    actual_load = measured_load if measured_load is not None else load_a
    if actual_load < 0:
        raise PSFError('Expected positive sink load current, got %.16g; review polarity' % actual_load)
    transistors = {}
    for device in devices:
        if device in transistors:
            raise PSFError('Duplicate transistor instance requested: %s' % device)
        op = dict((parameter, require_signal(parsed, device + ':' + parameter, unit))
                  for parameter, unit in OP_UNITS.items())
        for parameter in ('region', 'vbs', 'vgb', 'vgd', 'vsb', 'ig', 'ib', 'is'):
            signal = device + ':' + parameter
            if signal in parsed['records']:
                op[parameter] = parsed['values'][signal]
        transistors[device] = op
    input_current = -source_current
    iq = number(str(input_current - actual_load), 'derived core IQ')
    row = {'vin_v': voltages['vin'], 'load_a': actual_load, 'vout_v': voltages['vout'], 'iq_a': iq}
    warnings = []
    if input_current < 0:
        warnings.append('negative_current_into_core_review_source_sign_or_power_flow')
    if iq < 0:
        warnings.append('negative_iq_review_supply_and_load_polarity_or_measurement_boundary')
    detail = {'schema_version': 1, 'simulation_status': 'not_verified_by_parser',
              'source': parsed['source'], 'source_sha256': parsed.get('source_sha256'),
              'header': parsed['header'], 'complete_file': parsed['complete_file'], 'dc_csv_row': row,
              'node_map': selected_nodes, 'node_voltages_v': voltages,
              'supply_source_current_a': source_current, 'current_into_core_a': input_current,
              'load_current_source': load_current_key if measured_load is not None else 'explicit_load_a',
              'load_current_a': actual_load, 'iq_a': iq,
              'iq_definition': '-I(VVIN:p)-I_external_load; includes core bias/tail/divider sharing VIN',
              'iq_scope': 'ideal_external_reference_power_not_included_unless_supplied_from_VIN',
              'transistor_op': transistors, 'transistor_op_units': OP_UNITS, 'warnings': warnings,
              'device_voltage_limit_check': 'not_performed_requires_PDK_limits_and_terminal_voltages',
              'raw_scalar_records': parsed['records']}
    return row, detail


def prepare_parent(path):
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        os.makedirs(directory)


def replace_output(temporary, target):
    if hasattr(os, 'replace'):
        os.replace(temporary, target)
    else:
        # Python 2.7 target is Linux, where rename atomically replaces target.
        os.rename(temporary, target)


def write_json(path, value):
    prepare_parent(path)
    temporary = path + '.tmp.' + str(os.getpid())
    try:
        encoded = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n'
        with open(temporary, 'wb') as handle:
            handle.write(encoded.encode('ascii'))
        replace_output(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def write_dc_csv(path, row):
    prepare_parent(path)
    temporary = path + '.tmp.' + str(os.getpid())
    try:
        if sys.version_info[0] < 3:
            handle = open(temporary, 'wb')
        else:
            handle = io.open(temporary, 'w', encoding='ascii', newline='')
        try:
            writer = csv.writer(handle)
            writer.writerow(DC_FIELDS)
            writer.writerow([format(row[key], '.16g') for key in DC_FIELDS])
        finally:
            handle.close()
        replace_output(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def export_dc(input_path, csv_path, op_json_path, op_info_path=None, **extract_options):
    targets = [input_path, csv_path, op_json_path] + ([op_info_path] if op_info_path else [])
    paths = [os.path.normcase(os.path.realpath(path)) for path in targets]
    if len(set(paths)) != len(paths):
        raise PSFError('Input PSF, CSV output and OP JSON output must be distinct files')
    parsed = parse_scalar(input_path)
    if op_info_path:
        info = parse_info(op_info_path)
        for name, record in info['records'].items():
            if name in parsed['records']:
                left, right = parsed['values'][name], record['value']
                if left is None or right is None or abs(left - right) > max(1e-12, abs(left) * 1e-5):
                    raise PSFError('DC and INFO disagree on %s' % name)
            else:
                parsed['records'][name], parsed['values'][name] = record, record['value']
    row, detail = extract_dc(parsed, **extract_options)
    if op_info_path:
        detail.update(op_info_source=info['source'], op_info_source_sha256=info['source_sha256'],
                      undefined_optional_info_signals=info['undefined_signals'])
    # Validate completely before creating either output.
    write_json(op_json_path, detail)
    write_dc_csv(csv_path, row)
    return detail


def small_tokens(text):
    return [match.group() for match in TOKEN.finditer(text)]


def properties_at(tokens, index):
    properties = {}
    if index >= len(tokens) or tokens[index] != 'PROP':
        return properties, index
    index += 1
    if index >= len(tokens) or tokens[index] != '(':
        raise PSFError('PROP requires opening parenthesis')
    index += 1
    while index < len(tokens) and tokens[index] != ')':
        key = quoted(tokens[index], 'declaration property')
        index += 1
        if index >= len(tokens) or tokens[index] in ('(', ')', 'PROP'):
            raise PSFError('Missing/unsupported declaration property value: %s' % key)
        if key in properties:
            raise PSFError('Duplicate declaration property: %s' % key)
        properties[key] = atom(tokens[index])
        index += 1
    if index >= len(tokens):
        raise PSFError('Incomplete declaration PROP block')
    return properties, index + 1


def declarations(text):
    tokens = small_tokens(text)
    index, result = 0, {}
    while index < len(tokens):
        if index + 1 >= len(tokens):
            raise PSFError('Incomplete SWEEP/TRACE declaration')
        name = quoted(tokens[index], 'SWEEP/TRACE')
        type_name = quoted(tokens[index + 1], 'SWEEP/TRACE')
        index += 2
        properties, index = properties_at(tokens, index)
        if name in result:
            raise PSFError('Duplicate SWEEP/TRACE declaration: %s' % name)
        result[name] = {'type': type_name, 'properties': properties}
    return result


def type_shapes(text):
    tokens = small_tokens(text)

    def shape_at(index):
        if index >= len(tokens):
            raise PSFError('Incomplete TYPE declaration')
        kind = tokens[index]
        index += 1
        result = {'kind': kind}
        if kind in ('FLOAT', 'COMPLEX'):
            if index >= len(tokens) or tokens[index] != 'DOUBLE':
                raise PSFError('Unsupported %s numeric TYPE declaration' % kind)
            index += 1
        elif kind == 'INT':
            if index >= len(tokens) or tokens[index] not in ('BYTE', 'SHORT', 'LONG'):
                raise PSFError('Unsupported INT storage TYPE')
            result['storage'] = tokens[index]
            index += 1
        elif kind == 'STRUCT':
            if index >= len(tokens) or tokens[index] != '(':
                raise PSFError('STRUCT requires opening parenthesis')
            index += 1
            fields = []
            while index < len(tokens) and tokens[index] != ')':
                name = quoted(tokens[index], 'STRUCT field')
                field, index = shape_at(index + 1)
                fields.append({'name': name, 'shape': field})
            if index >= len(tokens):
                raise PSFError('Incomplete STRUCT declaration')
            index += 1
            result['fields'] = fields
        else:
            raise PSFError('Unsupported PSF TYPE kind: %s' % kind)
        result['properties'], index = properties_at(tokens, index)
        return result, index

    index, result = 0, {}
    while index < len(tokens):
        name = quoted(tokens[index], 'TYPE')
        shape, index = shape_at(index + 1)
        if name in result:
            raise PSFError('Duplicate TYPE declaration: %s' % name)
        result[name] = shape
    return result


def numeric_payload(text, location, allow_undefined=False):
    tokens = small_tokens(text)

    def value_at(index):
        if index >= len(tokens):
            raise PSFError('%s: missing numeric payload' % location)
        if tokens[index] == '(':
            result = []
            index += 1
            while index < len(tokens) and tokens[index] != ')':
                value, index = value_at(index)
                result.append(value)
            if index >= len(tokens):
                raise PSFError('%s: incomplete vector/STRUCT payload' % location)
            return result, index + 1
        if tokens[index] == ')':
            raise PSFError('%s: unexpected closing parenthesis' % location)
        if allow_undefined and tokens[index].lower().lstrip('+-') in ('nan', 'inf', 'infinity'):
            return None, index + 1
        return number(tokens[index], location), index + 1

    value, index = value_at(0)
    unused_properties, index = properties_at(tokens, index)
    if index != len(tokens):
        raise PSFError('%s: unexpected tokens after numeric payload' % location)
    return value


def parse_info(path):
    """Flatten complete STRUCT INFO OP into instance:parameter scalar records.

    Undefined optional simulator fields are retained as None. require_signal()
    still rejects them when a mandatory exported measurement depends on them.
    """
    with open(path, 'rb') as handle:
        raw = handle.read()
    text = raw.decode('utf-8-sig')
    lines = text.splitlines()
    positions = {}
    for index, line in enumerate(lines):
        item = line.strip()
        if item in ('HEADER', 'TYPE', 'SWEEP', 'TRACE', 'VALUE', 'END'):
            if item in positions:
                raise PSFError('Duplicate INFO section: %s' % item)
            positions[item] = index
    names = ('HEADER', 'TYPE', 'VALUE', 'END')
    if any(name not in positions for name in names) or 'SWEEP' in positions or 'TRACE' in positions:
        raise PSFError('Incomplete or nonscalar INFO file')
    ordered = [positions[name] for name in names]
    if ordered != sorted(ordered):
        raise PSFError('Invalid INFO section order')
    if any(line.strip() for line in lines[:ordered[0]] + lines[ordered[-1] + 1:]):
        raise PSFError('Unexpected content outside INFO HEADER ... END')
    header = {}
    for line in lines[positions['HEADER'] + 1:positions['TYPE']]:
        if not line.strip():
            continue
        match = HEADER_LINE.match(line.strip())
        if not match:
            raise PSFError('Malformed INFO header')
        key = quoted(match.group(1), 'INFO header')
        if key in header:
            raise PSFError('Duplicate INFO header key: %s' % key)
        header[key] = atom(match.group(2))
    if header.get('analysis type') != 'info':
        raise PSFError('Expected INFO analysis')
    shapes = type_shapes('\n'.join(lines[positions['TYPE'] + 1:positions['VALUE']]))
    records, undefined, instances = {}, [], {}

    def flatten(prefix, shape, value, instance_type):
        if shape['kind'] == 'STRUCT':
            for field, item in zip(shape['fields'], value):
                flatten(prefix + ':' + field['name'], field['shape'], item, instance_type)
        elif shape['kind'] == 'COMPLEX':
            raise PSFError('Complex OP INFO fields are not supported')
        else:
            if prefix in records:
                raise PSFError('Duplicate flattened INFO signal: %s' % prefix)
            properties = shape.get('properties', {})
            records[prefix] = {'type': properties.get('units', '-real'), 'value': value,
                               'properties': properties, 'instance_type': instance_type}
            if value is None:
                records[prefix]['status'] = 'undefined_simulator_field'
                undefined.append(prefix)

    index = positions['VALUE'] + 1
    record_start = re.compile(r'^(' + QUOTED + r')\s+(' + QUOTED + r')\s+(.+)$')
    while index < positions['END']:
        line = lines[index].strip()
        location = '%s:%d' % (path, index + 1)
        index += 1
        if not line:
            continue
        match = record_start.match(line)
        if not match:
            raise PSFError('%s: malformed INFO record' % location)
        name, type_name = quoted(match.group(1), location), quoted(match.group(2), location)
        if name in instances or type_name not in shapes:
            raise PSFError('%s: duplicate instance or unknown TYPE' % location)
        payload = match.group(3)
        part = small_tokens(payload)
        depth = part.count('(') - part.count(')')
        while depth > 0 and index < positions['END']:
            line = lines[index].strip()
            index += 1
            payload += '\n' + line
            part = small_tokens(line)
            depth += part.count('(') - part.count(')')
        if depth != 0:
            raise PSFError('%s: unbalanced INFO payload' % location)
        value = numeric_payload(payload, location, allow_undefined=True)
        check_shape(value, shapes[type_name], location)
        instances[name] = type_name
        flatten(name, shapes[type_name], value, type_name)
    if not records:
        raise PSFError('INFO contains no data')
    return {'format': 'psfascii_struct_info', 'complete_file': True,
            'simulation_status': 'not_verified_by_parser', 'source': os.path.abspath(path),
            'source_sha256': hashlib.sha256(raw).hexdigest(), 'source_bytes': len(raw),
            'header': header, 'record_count': len(records), 'records': records,
            'values': dict((name, record['value']) for name, record in records.items()),
            'undefined_signals': undefined, 'instance_types': instances}


def check_shape(value, shape, location):
    if shape['kind'] in ('FLOAT', 'INT'):
        if isinstance(value, list):
            raise PSFError('%s: expected numeric scalar, got vector' % location)
        if shape['kind'] == 'INT' and value is not None and int(value) != value:
            raise PSFError('%s: INT field contains fractional value' % location)
    elif shape['kind'] == 'COMPLEX':
        if not isinstance(value, list) or len(value) != 2 or any(isinstance(item, list) for item in value):
            raise PSFError('%s: expected real/imag pair' % location)
    else:
        fields = shape['fields']
        if not isinstance(value, list) or len(value) != len(fields):
            raise PSFError('%s: STRUCT field count mismatch' % location)
        for item, field in zip(value, fields):
            check_shape(item, field['shape'], location + ':' + field['name'])


def parse_sweep_text(text, source_name='<memory>', required_signals=None):
    lines = text.splitlines()
    positions = {}
    for index, line in enumerate(lines):
        name = line.strip()
        if name in ('HEADER', 'TYPE', 'SWEEP', 'TRACE', 'VALUE', 'END'):
            if name in positions:
                raise PSFError('%s: duplicate %s section' % (source_name, name))
            positions[name] = index
    names = ('HEADER', 'TYPE', 'SWEEP', 'TRACE', 'VALUE', 'END')
    if any(name not in positions for name in names):
        raise PSFError('%s: missing section/END; possibly incomplete sweep' % source_name)
    ordered = [positions[name] for name in names]
    if ordered != sorted(ordered):
        raise PSFError('%s: invalid sweep section order' % source_name)
    if any(line.strip() for line in lines[:ordered[0]] + lines[ordered[-1] + 1:]):
        raise PSFError('%s: unexpected content outside HEADER ... END' % source_name)
    header = {}
    for index in range(positions['HEADER'] + 1, positions['TYPE']):
        line = lines[index].strip()
        if not line:
            continue
        match = HEADER_LINE.match(line)
        if not match:
            raise PSFError('%s:%d: unsupported header entry' % (source_name, index + 1))
        key = quoted(match.group(1), 'header')
        if key in header:
            raise PSFError('Duplicate header key: %s' % key)
        header[key] = atom(match.group(2))
    shapes = type_shapes('\n'.join(lines[positions['TYPE'] + 1:positions['SWEEP']]))
    sweeps = declarations('\n'.join(lines[positions['SWEEP'] + 1:positions['TRACE']]))
    traces = declarations('\n'.join(lines[positions['TRACE'] + 1:positions['VALUE']]))
    if len(sweeps) != 1:
        raise PSFError('Only one-dimensional sweep files are supported')
    axis = next(iter(sweeps))
    if axis in traces or not traces:
        raise PSFError('Sweep axis overlaps traces or TRACE section is empty')
    for signal, declaration in list(sweeps.items()) + list(traces.items()):
        if declaration['type'] not in shapes:
            raise PSFError('Unknown TYPE for signal %s' % signal)
    if shapes[sweeps[axis]['type']]['kind'] != 'FLOAT':
        raise PSFError('Sweep axis must be FLOAT')
    selected = set(traces) if required_signals is None else set(required_signals)
    missing = selected - set(traces)
    if missing:
        raise PSFError('Missing required sweep traces: %s' % ','.join(sorted(missing)))
    rows, current, seen = [], None, set()
    index = positions['VALUE'] + 1

    def finish_row():
        if current is None:
            return
        missing_traces = set(traces) - seen
        if missing_traces:
            raise PSFError('Incomplete sweep sample %.16g, missing %s' %
                           (current['axis_value'], ','.join(sorted(missing_traces))))
        rows.append(current)

    while index < positions['END']:
        line = lines[index].strip()
        location = '%s:%d' % (source_name, index + 1)
        index += 1
        if not line:
            continue
        match = HEADER_LINE.match(line)
        if not match:
            raise PSFError('%s: malformed sweep record' % location)
        signal = quoted(match.group(1), location)
        payload = match.group(2)
        depth = small_tokens(payload).count('(') - small_tokens(payload).count(')')
        while depth > 0 and index < positions['END']:
            continuation = lines[index].strip()
            index += 1
            payload += '\n' + continuation
            part = small_tokens(continuation)
            depth += part.count('(') - part.count(')')
        if depth != 0:
            raise PSFError('%s: incomplete/unbalanced numeric payload' % location)
        value = numeric_payload(payload, location)
        if signal == axis:
            finish_row()
            check_shape(value, shapes[sweeps[axis]['type']], location)
            if rows and value <= rows[-1]['axis_value']:
                raise PSFError('%s: sweep axis not strictly increasing' % location)
            if axis == 'freq' and value <= 0:
                raise PSFError('%s: frequency must be positive' % location)
            current, seen = {'axis_value': value, 'values': {}}, set()
        else:
            if current is None:
                raise PSFError('%s: trace before first sweep axis' % location)
            if signal not in traces:
                raise PSFError('%s: undeclared trace %s' % (location, signal))
            if signal in seen:
                raise PSFError('%s: duplicate trace in sample: %s' % (location, signal))
            check_shape(value, shapes[traces[signal]['type']], location)
            seen.add(signal)
            if signal in selected:
                current['values'][signal] = value
    finish_row()
    if not rows:
        raise PSFError('Sweep has no complete data samples')
    return {'format': 'psfascii_sweep', 'complete_file': True,
            'simulation_status': 'not_verified_by_parser', 'source': source_name, 'header': header,
            'axis_name': axis, 'axis_declaration': sweeps[axis], 'traces': traces, 'type_shapes': shapes,
            'selected_signals': sorted(selected), 'sample_count': len(rows), 'rows': rows}


def parse_sweep(path, required_signals=None):
    """Stream VALUE records; retain only selected traces to bound PSF RAM use."""
    source_size = os.path.getsize(path)
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    with io.open(path, encoding='utf-8-sig') as handle:
        stream = iter(enumerate(handle, 1))
        preamble, positions = [], {}
        for line_number, line in stream:
            stripped = line.strip()
            if stripped in ('HEADER', 'TYPE', 'SWEEP', 'TRACE', 'VALUE', 'END'):
                if stripped in positions or stripped == 'END':
                    raise PSFError('Duplicate section or premature END in sweep preamble')
                positions[stripped] = len(preamble)
            preamble.append(line.rstrip('\r\n'))
            if stripped == 'VALUE':
                break
        names = ('HEADER', 'TYPE', 'SWEEP', 'TRACE', 'VALUE')
        if any(name not in positions for name in names):
            raise PSFError('Incomplete sweep preamble')
        ordered = [positions[name] for name in names]
        if ordered != sorted(ordered) or any(line.strip() for line in preamble[:ordered[0]]):
            raise PSFError('Invalid sweep section order')
        header = {}
        for line in preamble[positions['HEADER'] + 1:positions['TYPE']]:
            if not line.strip():
                continue
            match = HEADER_LINE.match(line.strip())
            if not match:
                raise PSFError('Malformed sweep header')
            key = quoted(match.group(1), 'header')
            if key in header:
                raise PSFError('Duplicate sweep header key')
            header[key] = atom(match.group(2))
        shapes = type_shapes('\n'.join(preamble[positions['TYPE'] + 1:positions['SWEEP']]))
        sweeps = declarations('\n'.join(preamble[positions['SWEEP'] + 1:positions['TRACE']]))
        traces = declarations('\n'.join(preamble[positions['TRACE'] + 1:positions['VALUE']]))
        if len(sweeps) != 1 or not traces:
            raise PSFError('Require one-dimensional sweep and nonempty TRACE')
        axis = next(iter(sweeps))
        for signal, declaration in list(sweeps.items()) + list(traces.items()):
            if declaration['type'] not in shapes:
                raise PSFError('Unknown TYPE for signal ' + signal)
        if axis in traces or shapes[sweeps[axis]['type']]['kind'] != 'FLOAT':
            raise PSFError('Invalid sweep axis declaration')
        selected = set(traces) if required_signals is None else set(required_signals)
        if selected - set(traces):
            raise PSFError('Missing required sweep traces: ' + ','.join(sorted(selected - set(traces))))
        rows, current, seen, ended = [], None, set(), False
        expected_traces = set(traces)

        def finish_row():
            if current is None:
                return
            if expected_traces != seen:
                raise PSFError('Incomplete sweep sample %.16g; missing %s' %
                               (current['axis_value'], ','.join(sorted(expected_traces - seen))))
            rows.append(current)

        for line_number, line in stream:
            line = line.strip()
            if not line:
                continue
            if line == 'END':
                finish_row()
                ended = True
                break
            location = '%s:%d' % (path, line_number)
            match = HEADER_LINE.match(line)
            if not match:
                raise PSFError('%s: malformed sweep record' % location)
            signal = quoted(match.group(1), location)
            payload = match.group(2)
            part = small_tokens(payload)
            depth = part.count('(') - part.count(')')
            while depth > 0:
                try:
                    next_number, continuation = next(stream)
                except StopIteration:
                    raise PSFError('%s: incomplete vector/STRUCT payload' % location)
                continuation = continuation.strip()
                if continuation == 'END':
                    raise PSFError('%s: END inside incomplete payload' % location)
                payload += '\n' + continuation
                part = small_tokens(continuation)
                depth += part.count('(') - part.count(')')
            if depth != 0:
                raise PSFError('%s: unbalanced payload' % location)
            value = numeric_payload(payload, location)
            if signal == axis:
                finish_row()
                check_shape(value, shapes[sweeps[axis]['type']], location)
                if rows and value <= rows[-1]['axis_value']:
                    raise PSFError('%s: axis not strictly increasing' % location)
                if axis == 'freq' and value <= 0:
                    raise PSFError('Frequency must be positive')
                current, seen = {'axis_value': value, 'values': {}}, set()
            else:
                if current is None or signal not in traces or signal in seen:
                    raise PSFError('%s: trace before axis, undeclared, or duplicate' % location)
                check_shape(value, shapes[traces[signal]['type']], location)
                seen.add(signal)
                if signal in selected:
                    current['values'][signal] = value
        if not ended or not rows:
            raise PSFError('Sweep missing END or complete samples')
        if any(line.strip() for line_number, line in stream):
            raise PSFError('Unexpected nonblank content after END')
    if os.path.getsize(path) != source_size:
        raise PSFError('Source changed size during parsing; rerun after transfer completion')
    return {'format': 'psfascii_sweep', 'complete_file': True, 'simulation_status': 'not_verified_by_parser',
            'source': os.path.abspath(path), 'source_sha256': digest.hexdigest(), 'source_encoding': 'utf-8-sig',
            'source_bytes': source_size, 'header': header, 'axis_name': axis, 'axis_declaration': sweeps[axis],
            'traces': traces, 'type_shapes': shapes, 'selected_signals': sorted(selected),
            'sample_count': len(rows), 'rows': rows, 'read_method': 'streamed_preamble_and_VALUE_records'}


def write_table(path, fields, rows):
    prepare_parent(path)
    temporary = path + '.tmp.' + str(os.getpid())
    try:
        handle = open(temporary, 'wb') if sys.version_info[0] < 3 else io.open(temporary, 'w', encoding='ascii', newline='')
        try:
            writer = csv.writer(handle)
            writer.writerow(fields)
            for row in rows:
                writer.writerow([format(number(str(row[field]), field), '.16g') for field in fields])
        finally:
            handle.close()
        replace_output(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def export_sweep(kind, input_path, csv_path, metadata_path=None, signal_map=None):
    specifications = {
        'stb': ('stb', 'freq', ['frequency_hz', 'loop_real', 'loop_imag'], {'loop': 'loopGain'}),
        'ac': ('ac', 'freq', ['frequency_hz', 'vout_real', 'vout_imag', 'vin_real', 'vin_imag'], {'vout': 'VOUT', 'vin': 'VIN'}),
        'noise': ('noise', 'freq', ['frequency_hz', 'vout_noise_v_sqrthz'], {'noise': 'out'}),
        'tran': ('tran', 'time', ['time_s', 'vout_v', 'gate_v', 'fb_v', 'vin_v', 'load_a'],
                 {'vout': 'VOUT', 'gate': 'GATE', 'fb': 'FB', 'vin': 'VIN', 'load': 'ILOAD:sink'}),
    }
    if kind not in specifications:
        raise PSFError('Unknown export kind: %s' % kind)
    analysis, axis, fields, signals = specifications[kind]
    signals = dict(signals)
    if signal_map is not None:
        if set(signal_map) - set(signals):
            raise PSFError('Unknown sweep signal roles')
        signals.update(signal_map)
    targets = [input_path, csv_path] + ([metadata_path] if metadata_path else [])
    if len(set(os.path.normcase(os.path.realpath(path)) for path in targets)) != len(targets):
        raise PSFError('Input and output paths must be distinct')
    parsed = parse_sweep(input_path, list(signals.values()))
    if parsed['header'].get('analysis type') != analysis or parsed['axis_name'] != axis:
        raise PSFError('Expected %s analysis on %s axis' % (analysis, axis))
    expected_kind = 'COMPLEX' if kind in ('stb', 'ac') else 'FLOAT'
    for role, signal in signals.items():
        declaration = parsed['traces'][signal]
        shape = parsed['type_shapes'][declaration['type']]
        if shape['kind'] != expected_kind:
            raise PSFError('Trace %s must use %s values' % (signal, expected_kind))
        if kind != 'stb':
            expected_unit = 'V/sqrt(Hz)' if kind == 'noise' else 'A' if role == 'load' else 'V'
            unit = declaration['properties'].get('units', shape['properties'].get('units'))
            if unit != expected_unit:
                raise PSFError('Trace %s unit %r does not establish %s' % (signal, unit, expected_unit))
    rows = []
    for sample in parsed['rows']:
        values = dict((role, sample['values'][signal]) for role, signal in signals.items())
        if kind == 'stb':
            row = dict(zip(fields, [sample['axis_value']] + values['loop']))
        elif kind == 'ac':
            row = dict(zip(fields, [sample['axis_value']] + values['vout'] + values['vin']))
        elif kind == 'noise':
            if isinstance(values['noise'], list) or values['noise'] < 0:
                raise PSFError('Output noise ASD must be a nonnegative scalar')
            row = dict(zip(fields, [sample['axis_value'], values['noise']]))
        else:
            if any(isinstance(value, list) for value in values.values()):
                raise PSFError('Transient exported channels must be scalar')
            row = dict(zip(fields, [sample['axis_value'], values['vout'], values['gate'], values['fb'], values['vin'], values['load']]))
        if set(row) != set(fields):
            raise PSFError('Trace shape does not match required CSV schema')
        rows.append(row)
    metadata = dict((key, value) for key, value in parsed.items() if key != 'rows')
    metadata.update(csv_schema=fields, signal_map=signals, csv_path=os.path.abspath(csv_path),
                    axis_range=[parsed['rows'][0]['axis_value'], parsed['rows'][-1]['axis_value']])
    if kind == 'noise':
        integral = sum((right['frequency_hz'] - left['frequency_hz']) *
                       (left['vout_noise_v_sqrthz'] ** 2 + right['vout_noise_v_sqrthz'] ** 2) / 2
                       for left, right in zip(rows, rows[1:]))
        metadata['band_limited_output_noise'] = {'status': 'computed_estimate', 'rms_v': math.sqrt(integral),
                                                'band_hz': metadata['axis_range'], 'integration': 'trapezoidal_ASD_squared_over_frequency',
                                                'scope': 'sampled_band_only_no_out_of_band_extrapolation'}
    if metadata_path:
        write_json(metadata_path, metadata)
    write_table(csv_path, fields, rows)
    return metadata


def parse_native_margins(log_path, margin_path=None):
    with open(log_path, 'rb') as handle:
        raw = handle.read()
    text = raw.decode('latin-1')
    numeric = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
    pattern = re.compile(r'(Gain|Phase)\s+margin\s*=\s*(' + numeric +
                         r')\s+(dB|Deg|deg)\s+at\s+frequency\s*=\s*(' + numeric + r')\s*([GMkmunp]?Hz)\b')
    scale = {'Hz': 1.0, 'kHz': 1e3, 'MHz': 1e6, 'GHz': 1e9,
             'mHz': 1e-3, 'uHz': 1e-6, 'nHz': 1e-9, 'pHz': 1e-12}
    result = dict((key, None) for key in ('phase_margin_deg', 'gain_margin_db', 'pm_frequency_hz', 'gm_frequency_hz'))
    matches, counts = [], {}
    for match in pattern.finditer(text):
        kind, value, unit, frequency, frequency_unit = match.groups()
        if (kind == 'Gain' and unit != 'dB') or (kind == 'Phase' and unit not in ('Deg', 'deg')):
            raise PSFError('Native margin units do not match quantity')
        counts[kind] = counts.get(kind, 0) + 1
        if counts[kind] > 1:
            raise PSFError('Multiple %s margin results in log; specify one analysis/run' % kind)
        value, frequency = number(value, 'native margin'), number(frequency, 'native frequency') * scale[frequency_unit]
        value_key, frequency_key = ('gain_margin_db', 'gm_frequency_hz') if kind == 'Gain' else ('phase_margin_deg', 'pm_frequency_hz')
        result[value_key], result[frequency_key] = value, frequency
        matches.append({'text': match.group(), 'quantity': kind, 'value': value, 'unit': unit, 'frequency_hz': frequency})
    metric_keys = tuple(result)
    result.update(status='native_log_export' if matches else 'unavailable',
                  source=os.path.abspath(log_path), source_sha256=hashlib.sha256(raw).hexdigest(),
                  raw_matches=matches, simulation_status='not_verified_by_parser')
    if margin_path is None:
        candidate = os.path.join(os.path.dirname(log_path), 'psf', 'stb.margin.stb')
        margin_path = candidate if os.path.isfile(candidate) else None
    result.update(native_state_text=None, native_stability_state='unavailable')
    if margin_path is not None:
        parsed = parse_scalar(margin_path, allow_undefined=True)
        if parsed['header'].get('analysis type') != 'margin.stb':
            raise PSFError('Expected complete native margin.stb file')
        mapping = {'gainMargin': ('gain_margin_db', 'dB'),
                   'gainMarginFreq': ('gm_frequency_hz', 'Hz'),
                   'phaseMargin': ('phase_margin_deg', 'Deg'),
                   'phaseMarginFreq': ('pm_frequency_hz', 'Hz')}
        for signal, (key, expected_unit) in mapping.items():
            if signal not in parsed['records']:
                raise PSFError('Native margin file missing ' + signal)
            record = parsed['records'][signal]
            if record['type'] != expected_unit:
                raise PSFError('Native margin type does not establish ' + expected_unit)
            result[key] = None if record['value'] is None else number(str(record['value']), signal)
        state = parsed['values'].get('stb_state')
        if not isinstance(state, type(u'')) and not isinstance(state, str):
            raise PSFError('Native margin file missing string stb_state')
        result['native_state_text'] = state
        state_lower = state.lower()
        if 'not stable' in state_lower or 'unstable' in state_lower:
            result['native_stability_state'] = 'unstable'
        elif 'is stable' in state_lower:
            result['native_stability_state'] = 'stable'
        else:
            result['native_stability_state'] = 'unknown'
        result.update(status='native_margin_file_export', margin_source=os.path.abspath(margin_path),
                      margin_source_sha256=parsed['source_sha256'], margin_complete_file=True,
                      native_margin_records=parsed['records'], native_margin_header=parsed['header'],
                      metric_source='full_precision_native_margin_VALUE')
    result['unavailable_metrics'] = [key for key in metric_keys if result[key] is None]
    return result


def command_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command')
    scalar = commands.add_parser('scalar', help='Strictly parse arbitrary scalar dc/info file')
    scalar.add_argument('input')
    scalar.add_argument('--out-json', required=True)
    dc = commands.add_parser('dc', help='Export complete LDO operating point')
    dc.add_argument('input')
    dc.add_argument('--out-csv', required=True)
    dc.add_argument('--out-op-json', required=True)
    dc.add_argument('--op-info', help='Optional structured dcOpInfo.info supplying saved MOS OP')
    dc.add_argument('--load-a', type=float)
    dc.add_argument('--load-current-key', default='ILOAD:sink')
    dc.add_argument('--nodes-json', help='Optional role-to-signal JSON map; defaults listed in source')
    dc.add_argument('--device', action='append', help='Explicit MOS instance; repeat; default seven core instances')
    dc.add_argument('--auto-devices', action='store_true', help='Require/save every instance having all seven MOS OP fields')
    for kind in ('stb', 'ac', 'noise', 'tran'):
        sweep = commands.add_parser(kind, help='Export validated %s sweep CSV' % kind)
        sweep.add_argument('input')
        sweep.add_argument('--out-csv', required=True)
        sweep.add_argument('--out-metadata-json')
        sweep.add_argument('--signals-json', help='Optional role-to-trace mapping JSON')
    margins = commands.add_parser('margins', help='Export native margin lines from one Spectre log')
    margins.add_argument('input')
    margins.add_argument('--out-json', required=True)
    return parser


def main(argv=None):
    parser = command_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    try:
        if args.command == 'scalar':
            if os.path.normcase(os.path.realpath(args.input)) == os.path.normcase(os.path.realpath(args.out_json)):
                raise PSFError('Output cannot overwrite input PSF evidence')
            parsed = parse_scalar(args.input)
            write_json(args.out_json, parsed)
            result = {'status': 'scalar_file_parsed', 'record_count': parsed['record_count'],
                      'output': os.path.abspath(args.out_json),
                      'simulation_status': 'not_verified_by_parser'}
        elif args.command == 'dc':
            nodes = None
            if args.nodes_json:
                with io.open(args.nodes_json, encoding='utf-8-sig') as handle:
                    nodes = json.load(handle)
                if not isinstance(nodes, dict):
                    raise PSFError('nodes-json must contain an object')
            detail = export_dc(args.input, args.out_csv, args.out_op_json, load_a=args.load_a,
                               load_current_key=args.load_current_key, nodes=nodes, devices='auto' if args.auto_devices else args.device,
                               op_info_path=args.op_info)
            result = {'status': 'dc_data_exported', 'csv': os.path.abspath(args.out_csv),
                      'op_json': os.path.abspath(args.out_op_json), 'warnings': detail['warnings'],
                      'simulation_status': 'not_verified_by_parser'}
        elif args.command == 'margins':
            if os.path.realpath(args.input) == os.path.realpath(args.out_json):
                raise PSFError('Output cannot overwrite source log')
            result = parse_native_margins(args.input)
            write_json(args.out_json, result)
            result = {'status': result['status'], 'json': os.path.abspath(args.out_json),
                      'simulation_status': 'not_verified_by_parser'}
        else:
            signals = None
            if args.signals_json:
                with io.open(args.signals_json, encoding='utf-8-sig') as handle:
                    signals = json.load(handle)
                if not isinstance(signals, dict):
                    raise PSFError('signals-json must contain an object')
            metadata = export_sweep(args.command, args.input, args.out_csv, args.out_metadata_json, signals)
            result = {'status': 'sweep_data_exported', 'csv': os.path.abspath(args.out_csv),
                      'sample_count': metadata['sample_count'], 'simulation_status': 'not_verified_by_parser'}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PSFError, IOError, OSError, ValueError) as error:
        print('PSF_PARSE_FAILED: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
