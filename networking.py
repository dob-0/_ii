#!/usr/bin/env python3
"""Network status and station/hotspot helpers for the ii web panel."""

import os
import socket
import subprocess
import time


NETWORKMANAGER_CONF = '/etc/NetworkManager/NetworkManager.conf'
DEFAULT_HOTSPOT_SSID = 'ii-hotspot'
DEFAULT_HOTSPOT_PASSWORD = 'iiiiiiii'


def _run(cmd, timeout=12):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return False, '', f'command not found: {cmd[0]}'
    except subprocess.TimeoutExpired:
        return False, '', f'timeout: {" ".join(cmd)}'
    return proc.returncode == 0, (proc.stdout or '').strip(), (proc.stderr or '').strip()


def _nmcli_rows(fields, args, timeout=12):
    ok, out, err = _run(
        ['nmcli', '--terse', '--escape', 'no', '--fields', ','.join(fields)] + list(args),
        timeout=timeout,
    )
    rows = []
    if ok and out:
        for line in out.splitlines():
            parts = line.split(':', len(fields) - 1)
            if len(parts) < len(fields):
                parts.extend([''] * (len(fields) - len(parts)))
            row = {}
            for idx, field in enumerate(fields):
                row[field.lower().replace('-', '_')] = parts[idx]
            rows.append(row)
    return ok, rows, err


def _ip_summary():
    ok, out, _err = _run(['ip', '-brief', 'addr'])
    rows = []
    if not ok:
        return rows
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        iface = parts[0]
        state = parts[1]
        addrs = [part for part in parts[2:] if part != 'UNKNOWN']
        rows.append({'iface': iface, 'state': state, 'addrs': addrs})
    return rows


def _managed_config_state():
    try:
        with open(NETWORKMANAGER_CONF, encoding='utf-8') as f:
            text = f.read()
    except OSError:
        return None
    for raw in text.splitlines():
        line = raw.strip().lower()
        if not line or line.startswith('#'):
            continue
        if line.startswith('managed='):
            value = line.split('=', 1)[1].strip()
            return value not in ('false', '0', 'no')
    return None


def _permissions():
    ok, rows, err = _nmcli_rows(['PERMISSION', 'VALUE'], ['general', 'permissions'])
    perms = {}
    if ok:
        for row in rows:
            key = row['permission'].split('.')[-1]
            perms[key] = row['value']
    return perms, err


def _active_mode_for_connection(name):
    if not name:
        return ''
    ok, out, _err = _run(['nmcli', '--get-values', '802-11-wireless.mode', 'connection', 'show', name])
    return out.strip() if ok else ''


def _wifi_iface(devices):
    for dev in devices:
        if dev.get('type') == 'wifi':
            return dev
    return None


def _setup_commands():
    return [
        "sudo sed -i 's/^managed=false/managed=true/' /etc/NetworkManager/NetworkManager.conf",
        'sudo systemctl restart NetworkManager',
        'nmcli device status',
    ]


def _base_status():
    state = {
        'ok': True,
        'msg': '',
        'hostname': socket.gethostname(),
        'updated_at': time.time(),
        'hotspot_defaults': {
            'ssid': DEFAULT_HOTSPOT_SSID,
            'password': DEFAULT_HOTSPOT_PASSWORD,
        },
        'setup_commands': _setup_commands(),
    }

    ok, general_rows, general_err = _nmcli_rows(
        ['STATE', 'CONNECTIVITY', 'WIFI-HW', 'WIFI'], ['general', 'status']
    )
    if ok and general_rows:
        state.update({
            'nm_state': general_rows[0].get('state', ''),
            'connectivity': general_rows[0].get('connectivity', ''),
            'wifi_hw': general_rows[0].get('wifi_hw', ''),
            'wifi_radio': general_rows[0].get('wifi', ''),
        })
    else:
        state['ok'] = False
        state['msg'] = general_err or 'nmcli unavailable'

    perms, perm_err = _permissions()
    state['permissions'] = perms
    if perm_err and not state.get('msg'):
        state['msg'] = perm_err

    ok, devices, dev_err = _nmcli_rows(['DEVICE', 'TYPE', 'STATE', 'CONNECTION'], ['device', 'status'])
    state['devices'] = devices if ok else []
    if dev_err and not state.get('msg'):
        state['msg'] = dev_err

    ok, active_cons, cons_err = _nmcli_rows(
        ['NAME', 'UUID', 'TYPE', 'DEVICE'], ['connection', 'show', '--active']
    )
    state['active_connections'] = active_cons if ok else []
    if cons_err and not state.get('msg'):
        state['msg'] = cons_err

    state['ip_addrs'] = _ip_summary()
    state['managed_config'] = _managed_config_state()

    wifi = _wifi_iface(state['devices'])
    state['wifi_iface'] = wifi.get('device', '') if wifi else ''
    state['wifi_state'] = wifi.get('state', '') if wifi else 'missing'
    state['wifi_connection'] = wifi.get('connection', '') if wifi else ''
    state['wifi_managed'] = bool(wifi and wifi.get('state') != 'unmanaged')

    wifi_active = {}
    for conn in state['active_connections']:
        if conn.get('device') == state['wifi_iface'] and conn.get('type') == '802-11-wireless':
            wifi_active = conn
            break
    state['wifi_active'] = wifi_active
    wifi_mode = _active_mode_for_connection(wifi_active.get('name', ''))
    state['wifi_mode'] = wifi_mode or ('ap' if 'hotspot' in wifi_active.get('name', '').lower() else '')
    state['hotspot_active'] = state['wifi_mode'] == 'ap'

    network_control = perms.get('network_control', 'no')
    scan_perm = perms.get('scan', 'no')
    share_open = perms.get('open', 'no')
    share_protected = perms.get('protected', 'no')
    state['control_ready'] = bool(state['wifi_iface']) and state['wifi_managed'] and network_control in ('yes', 'auth')
    state['scan_ready'] = state['control_ready'] and scan_perm in ('yes', 'auth')
    state['hotspot_ready'] = state['control_ready'] and (share_open in ('yes', 'auth') or share_protected in ('yes', 'auth'))
    state['requires_setup'] = not state['wifi_managed'] or state.get('managed_config') is False

    if not state['wifi_iface']:
        state['msg'] = state['msg'] or 'No Wi-Fi adapter detected.'
    elif state['requires_setup']:
        state['msg'] = state['msg'] or (
            'Wi-Fi is not managed by NetworkManager yet, so web station/hotspot control is read-only.'
        )
    elif not state['control_ready']:
        state['msg'] = state['msg'] or 'Wi-Fi interface is present, but NetworkManager control is not available.'

    return state


def _scan_networks(iface):
    ok, _out, err = _run(['nmcli', 'device', 'wifi', 'rescan', 'ifname', iface], timeout=20)
    if not ok and err and 'Scanning not allowed' not in err:
        return False, [], err
    ok, rows, list_err = _nmcli_rows(
        ['IN-USE', 'SIGNAL', 'SECURITY', 'CHAN', 'RATE', 'SSID'],
        ['device', 'wifi', 'list', 'ifname', iface],
        timeout=20,
    )
    if not ok:
        return False, [], list_err or err

    deduped = {}
    for row in rows:
        ssid = row.get('ssid', '').strip()
        key = ssid or f'__hidden__:{row.get("chan","")}:{row.get("security","")}'
        signal = int(row.get('signal') or 0)
        current = deduped.get(key)
        if current is None or signal > current.get('signal', 0):
            deduped[key] = {
                'in_use': row.get('in_use', '').strip() == '*',
                'ssid': ssid,
                'signal': signal,
                'security': row.get('security', '').strip(),
                'chan': row.get('chan', '').strip(),
                'rate': row.get('rate', '').strip(),
                'hidden': not bool(ssid),
            }
    networks = sorted(deduped.values(), key=lambda item: (not item['in_use'], -item['signal'], item['ssid']))
    return True, networks, ''


def network_status(include_scan=False):
    state = _base_status()
    if include_scan and state.get('wifi_iface') and state.get('scan_ready'):
        ok, networks, err = _scan_networks(state['wifi_iface'])
        state['networks'] = networks
        if not ok:
            state['msg'] = err or state['msg']
    else:
        state['networks'] = []
    return state


def _require_iface(state):
    iface = state.get('wifi_iface')
    if not iface:
        return False, 'No Wi-Fi interface found.'
    if state.get('requires_setup'):
        return False, 'Wi-Fi is unmanaged. Run the setup commands shown in the web panel once on the Debian box.'
    if not state.get('control_ready'):
        return False, 'NetworkManager cannot control Wi-Fi from the current session.'
    return True, iface


def network_action(body):
    action = str(body.get('action', '') or '').strip()
    state = _base_status()
    ok, iface_or_msg = _require_iface(state)
    if action in ('connect', 'hotspot_start', 'hotspot_stop') and not ok:
        state['ok'] = False
        state['msg'] = iface_or_msg
        return state
    iface = iface_or_msg if ok else state.get('wifi_iface', '')

    if action == 'scan':
        if not state.get('scan_ready'):
            state['ok'] = False
            state['msg'] = 'Wi-Fi scan is unavailable until NetworkManager manages the adapter.'
            state['networks'] = []
            return state
        ok, networks, err = _scan_networks(iface)
        state['ok'] = ok
        state['networks'] = networks
        state['msg'] = '' if ok else (err or 'Scan failed.')
        return state

    if action == 'connect':
        ssid = str(body.get('ssid', '') or '').strip()
        password = str(body.get('password', '') or '')
        if not ssid:
            state['ok'] = False
            state['msg'] = 'SSID is required.'
            return state
        cmd = ['nmcli', 'device', 'wifi', 'connect', ssid, 'ifname', iface]
        if password:
            cmd += ['password', password]
        ok, out, err = _run(cmd, timeout=45)
        latest = network_status(include_scan=True)
        latest['ok'] = ok
        latest['msg'] = out or err or ('Connected.' if ok else 'Connect failed.')
        return latest

    if action == 'hotspot_start':
        ssid = str(body.get('ssid', '') or '').strip() or DEFAULT_HOTSPOT_SSID
        password = str(body.get('password', '') or '').strip() or DEFAULT_HOTSPOT_PASSWORD
        if len(password) < 8:
            state['ok'] = False
            state['msg'] = 'Hotspot password must be at least 8 characters.'
            return state
        cmd = ['nmcli', 'device', 'wifi', 'hotspot', 'ifname', iface, 'ssid', ssid, 'password', password]
        ok, out, err = _run(cmd, timeout=45)
        latest = network_status(include_scan=False)
        latest['ok'] = ok
        latest['msg'] = out or err or ('Hotspot started.' if ok else 'Hotspot start failed.')
        return latest

    if action == 'hotspot_stop':
        active = state.get('wifi_active') or {}
        if active.get('uuid'):
            cmd = ['nmcli', 'connection', 'down', 'uuid', active['uuid']]
        else:
            cmd = ['nmcli', 'device', 'disconnect', iface]
        ok, out, err = _run(cmd, timeout=30)
        latest = network_status(include_scan=False)
        latest['ok'] = ok
        latest['msg'] = out or err or ('Hotspot stopped.' if ok else 'Hotspot stop failed.')
        return latest

    state['ok'] = False
    state['msg'] = 'Unknown network action.'
    return state
